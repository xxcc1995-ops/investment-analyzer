/**
 * 日报生成模块
 * 将今日文章汇总为 Markdown 格式的日报
 */

import { writeFileSync, existsSync, mkdirSync, readdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { readArticles, readConfig } from './store.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT_DIR = join(__dirname, '..');
const OUTPUT_DIR = join(ROOT_DIR, 'output');

/**
 * 获取今日日期字符串
 * @returns {string} YYYY-MM-DD 格式的日期
 */
function getTodayStr() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/**
 * 格式化时间戳为日期字符串
 * @param {number} timestamp - Unix 时间戳（秒）
 * @returns {string} YYYY-MM-DD 格式的日期
 */
function formatDate(timestamp) {
  if (!timestamp) return '未知';
  const date = new Date(timestamp * 1000);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/**
 * 生成摘要（从正文前 200 字）
 * @param {string} content - 文章正文
 * @returns {string} 摘要文本
 */
function generateSummary(content) {
  if (!content || content === '（无法提取正文）' || content === '（提取失败）') {
    return '（无摘要）';
  }
  // 去除多余空白，取前 200 字
  const cleaned = content.replace(/\s+/g, ' ').trim();
  if (cleaned.length <= 200) {
    return cleaned;
  }
  return cleaned.substring(0, 200) + '...';
}

/**
 * 获取指定天数内的文章
 * @param {string} mpId - 公众号 ID
 * @param {number} days - 天数
 * @returns {Array} 近期文章列表
 */
function getRecentArticles(mpId, days) {
  const articles = readArticles(mpId);
  const now = Math.floor(Date.now() / 1000);
  const cutoff = now - (days * 24 * 60 * 60);

  return articles.filter(a => {
    // 优先用 publishedAt，没有则用 fetchedAt
    const time = a.publishedAt || a.fetchedAt || 0;
    return time >= cutoff;
  }).sort((a, b) => (b.publishedAt || 0) - (a.publishedAt || 0));
}

/**
 * 生成今日日报
 * @param {object} options - 选项
 * @param {number} options.days - 获取最近几天的文章（默认从配置读取）
 * @returns {string} 日报文件路径
 */
export async function generateDailyReport(options = {}) {
  const config = readConfig();
  const days = options.days || config.syncDays || 2;
  const today = getTodayStr();

  console.log(`📰 开始生成 ${today} 日报...\n`);

  // 获取所有存储的公众号
  const articlesDir = join(ROOT_DIR, 'data', 'articles');

  if (!existsSync(articlesDir)) {
    console.log('⚠️ 没有找到文章数据，请先运行 sync 命令');
    return null;
  }

  const files = readdirSync(articlesDir).filter(f => f.endsWith('.json'));
  if (files.length === 0) {
    console.log('⚠️ 没有找到文章数据，请先运行 sync 命令');
    return null;
  }

  // 收集近期文章
  const reportSections = [];
  let totalArticles = 0;

  for (const file of files) {
    const mpId = file.replace('.json', '');
    const recentArticles = getRecentArticles(mpId, days);

    if (recentArticles.length === 0) continue;

    const mpName = recentArticles[0]?.mpName || mpId;
    totalArticles += recentArticles.length;

    const articlesMd = recentArticles.map((article, index) => {
      const summary = generateSummary(article.content);
      const pubDate = formatDate(article.publishedAt);

      return `### ${index + 1}. ${article.title}
- 🔗 链接：${article.url}
- 📅 发布时间：${pubDate}
- 📝 摘要：${summary}`;
    }).join('\n\n');

    reportSections.push(`## ${mpName}（${recentArticles.length}篇）\n\n${articlesMd}`);
  }

  if (reportSections.length === 0) {
    console.log(`⚠️ 最近 ${days} 天内没有新文章`);
    return null;
  }

  // 组装完整日报
  const report = `# 📰 微信公众号日报 - ${today}

${reportSections.join('\n\n---\n\n')}

---
*由 wechat-digest 自动生成于 ${new Date().toLocaleString('zh-CN')}*
`;

  // 保存到文件
  if (!existsSync(OUTPUT_DIR)) {
    mkdirSync(OUTPUT_DIR, { recursive: true });
  }

  const outputPath = join(OUTPUT_DIR, `${today}.md`);
  writeFileSync(outputPath, report, 'utf-8');

  console.log(`✅ 日报已生成: ${outputPath}`);
  console.log(`📊 共 ${reportSections.length} 个公众号，${totalArticles} 篇文章`);

  return outputPath;
}

/**
 * 获取今日文章列表（仅显示，不生成日报）
 * @param {number} days - 获取最近几天的文章
 * @returns {Array} 今日文章列表
 */
export async function getTodayArticles(days) {
  const config = readConfig();
  const targetDays = days || config.syncDays || 2;

  const articlesDir = join(ROOT_DIR, 'data', 'articles');

  if (!existsSync(articlesDir)) {
    return [];
  }

  const files = readdirSync(articlesDir).filter(f => f.endsWith('.json'));
  const allArticles = [];

  for (const file of files) {
    const mpId = file.replace('.json', '');
    const recentArticles = getRecentArticles(mpId, targetDays);
    allArticles.push(...recentArticles);
  }

  return allArticles.sort((a, b) => (b.publishedAt || 0) - (a.publishedAt || 0));
}
