/**
 * 微信读书 API 客户端
 * 封装登录、拉取公众号列表、文章列表、正文提取等逻辑
 */

import fetch from 'node-fetch';
import { load } from 'cheerio';
import { readAuth, saveAuth, readConfig } from './store.js';

const API_BASE = readConfig().wereadApiBase || 'https://weread.111965.xyz';

/**
 * 礼貌延迟
 * @param {number} ms - 毫秒数
 */
export function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * 带重试的 fetch 请求
 * @param {string} url - 请求地址
 * @param {object} options - fetch 选项
 * @param {boolean} allowEmpty - 是否允许空响应（空数组 []）
 * @returns {Promise<any>} 响应数据
 */
export async function fetchWithRetry(url, options = {}, allowEmpty = false) {
  const config = readConfig();
  const maxAttempts = config.retryMaxAttempts || 5;
  const retryDelay = config.retryDelayMs || 400;

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      const res = await fetch(url, options);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }
      const data = await res.json();

      // 空数组也视为需要重试的情况（除非明确允许）
      if (!allowEmpty && Array.isArray(data) && data.length === 0 && attempt < maxAttempts) {
        console.log(`  ⚠️ 响应为空，第 ${attempt}/${maxAttempts} 次重试...`);
        await delay(retryDelay);
        continue;
      }

      return data;
    } catch (err) {
      if (attempt === maxAttempts) {
        throw new Error(`请求失败（已重试 ${maxAttempts} 次）: ${err.message}`);
      }
      console.log(`  ⚠️ 请求出错，第 ${attempt}/${maxAttempts} 次重试: ${err.message}`);
      await delay(retryDelay);
    }
  }
}

/**
 * 发起登录流程
 * 生成二维码图片并轮询登录结果
 */
export async function login() {
  console.log('🔐 开始微信读书登录流程...\n');

  // 1. 获取 uuid
  const uuidData = await fetchWithRetry(`${API_BASE}/api/v2/login/platform`, {}, true);
  const uuid = uuidData.uuid;
  if (!uuid) {
    throw new Error('获取 uuid 失败');
  }
  console.log(`✅ 获取 uuid: ${uuid}`);

  // 2. 生成二维码图片
  const qrUrl = `https://login.weixin.qq.com/l/${uuid}`;
  const qrImagePath = 'data/login-qrcode.png';

  const QRCode = await import('qrcode');
  await QRCode.toFile(qrImagePath, qrUrl, {
    width: 400,
    margin: 2,
    color: { dark: '#000000', light: '#ffffff' }
  });
  console.log(`✅ 二维码已保存到: ${qrImagePath}`);

  // 3. 自动打开图片
  const { exec } = await import('child_process');
  const process = await import('process');
  const path = await import('path');

  const absolutePath = path.resolve(qrImagePath);
  if (process.platform === 'win32') {
    exec(`start "" "${absolutePath}"`);
  } else if (process.platform === 'darwin') {
    exec(`open "${absolutePath}"`);
  } else {
    exec(`xdg-open "${absolutePath}"`);
  }
  console.log('📱 已打开二维码图片，请用微信扫码登录...\n');

  // 4. 轮询登录结果
  const maxPolls = 60; // 最多 2 分钟
  for (let i = 0; i < maxPolls; i++) {
    await delay(2000);

    try {
      const result = await fetchWithRetry(
        `${API_BASE}/api/v2/login/platform/${uuid}`,
        {},
        true
      );

      if (result.vid && result.token) {
        saveAuth({ vid: result.vid, token: result.token });
        console.log('✅ 登录成功！');
        console.log(`   VID: ${result.vid}`);
        console.log('   认证信息已保存到 data/auth.json');
        return result;
      }

      // 还没扫码，继续等待
      if (i % 5 === 0 && i > 0) {
        console.log(`⏳ 等待扫码中... (${i * 2}秒)`);
      }
    } catch (err) {
      // 轮询中间的错误忽略
    }
  }

  throw new Error('登录超时（2分钟），请重试');
}

/**
 * 获取请求头
 * @returns {object} 包含认证信息的请求头
 */
export function getHeaders() {
  const auth = readAuth();
  if (!auth || !auth.vid || !auth.token) {
    throw new Error('未登录，请先运行 login 命令');
  }
  return {
    'xid': auth.vid,
    'Authorization': `Bearer ${auth.token}`,
    'Content-Type': 'application/json'
  };
}

/**
 * 获取已关注的公众号列表
 * @returns {Promise<Array>} 公众号列表
 */
export async function getFollowedMPs() {
  console.log('📋 获取已关注公众号列表...');
  const data = await fetchWithRetry(
    `${API_BASE}/api/v2/platform/mps`,
    { headers: getHeaders() }
  );

  // 处理不同的响应格式
  const mps = Array.isArray(data) ? data : (data.mps || data.data || []);
  console.log(`✅ 找到 ${mps.length} 个公众号`);
  return mps;
}

/**
 * 获取指定公众号的文章列表
 * @param {string} mpId - 公众号 ID
 * @param {number} page - 页码（从 0 开始）
 * @returns {Promise<Array>} 文章列表
 */
export async function getMPArticles(mpId, page = 0) {
  const data = await fetchWithRetry(
    `${API_BASE}/api/v2/platform/mps/${mpId}/articles?page=${page}`,
    { headers: getHeaders() }
  );

  // 处理不同的响应格式
  const articles = Array.isArray(data) ? data : (data.articles || data.data || []);
  return articles;
}

/**
 * 提取微信文章正文
 * @param {string} url - 文章链接
 * @returns {Promise<string>} 提取的正文内容
 */
export async function extractArticleContent(url) {
  try {
    const res = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
      }
    });
    const html = await res.text();

    // 方案1：正则提取 content_noencode
    const match = html.match(/var\s+content_noencode\s*=\s*"([\s\S]*?)";/);
    if (match) {
      let content = match[1]
        .replace(/\\n/g, '\n')
        .replace(/\\t/g, '\t')
        .replace(/\\"/g, '"')
        .replace(/\\\\/g, '\\')
        .replace(/<[^>]+>/g, '')  // 去除 HTML 标签
        .trim();
      return content;
    }

    // 方案2：cheerio 解析 #js_content
    const $ = load(html);
    const text = $('#js_content').text().trim();
    if (text) {
      return text;
    }

    // 方案3：尝试从其他常见位置提取
    const articleText = $('article').text().trim() ||
                       $('.rich_media_content').text().trim() ||
                       $('#page-content').text().trim();

    return articleText || '（无法提取正文）';
  } catch (err) {
    console.log(`  ⚠️ 提取正文失败: ${err.message}`);
    return '（提取失败）';
  }
}

/**
 * 通过文章链接查询公众号信息
 * @param {string} url - 文章链接
 * @returns {Promise<object>} 公众号信息
 */
export async function getMPByArticleUrl(url) {
  const data = await fetchWithRetry(
    `${API_BASE}/api/v2/platform/wxs2mp`,
    {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ url })
    },
    true
  );
  return data;
}
