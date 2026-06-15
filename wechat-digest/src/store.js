/**
 * 文章存储模块
 * 负责读写 JSON 文件，管理认证信息和文章数据
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync, readdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT_DIR = join(__dirname, '..');

// 文件路径
const AUTH_FILE = join(ROOT_DIR, 'data', 'auth.json');
const CONFIG_FILE = join(ROOT_DIR, 'config.json');
const ARTICLES_DIR = join(ROOT_DIR, 'data', 'articles');

// 确保目录存在
function ensureDir(dir) {
  if (!existsSync(dir)) {
    mkdirSync(dir, { recursive: true });
  }
}

/**
 * 读取配置文件
 * @returns {object} 配置对象
 */
export function readConfig() {
  try {
    const data = readFileSync(CONFIG_FILE, 'utf-8');
    return JSON.parse(data);
  } catch {
    return {
      wereadApiBase: 'https://weread.111965.xyz',
      accounts: [],
      maxArticlesPerAccount: 20,
      retryMaxAttempts: 5,
      retryDelayMs: 400,
      syncDays: 2
    };
  }
}

/**
 * 保存配置文件
 * @param {object} config - 配置对象
 */
export function saveConfig(config) {
  writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2), 'utf-8');
}

/**
 * 读取认证信息
 * @returns {object|null} 认证对象 { vid, token }
 */
export function readAuth() {
  try {
    const data = readFileSync(AUTH_FILE, 'utf-8');
    return JSON.parse(data);
  } catch {
    return null;
  }
}

/**
 * 保存认证信息
 * @param {object} auth - 认证对象 { vid, token }
 */
export function saveAuth(auth) {
  ensureDir(dirname(AUTH_FILE));
  writeFileSync(AUTH_FILE, JSON.stringify(auth, null, 2), 'utf-8');
}

/**
 * 获取公众号文章文件路径
 * @param {string} mpId - 公众号 ID
 * @returns {string} 文件路径
 */
function getArticleFilePath(mpId) {
  ensureDir(ARTICLES_DIR);
  return join(ARTICLES_DIR, `${mpId}.json`);
}

/**
 * 读取指定公众号的文章列表
 * @param {string} mpId - 公众号 ID
 * @returns {Array} 文章列表
 */
export function readArticles(mpId) {
  const filePath = getArticleFilePath(mpId);
  try {
    const data = readFileSync(filePath, 'utf-8');
    return JSON.parse(data);
  } catch {
    return [];
  }
}

/**
 * 保存指定公众号的文章列表
 * @param {string} mpId - 公众号 ID
 * @param {Array} articles - 文章列表
 */
export function saveArticles(mpId, articles) {
  const filePath = getArticleFilePath(mpId);
  const config = readConfig();
  const maxArticles = config.maxArticlesPerAccount || 20;

  // 只保留最新的 maxArticles 篇
  const sorted = articles.sort((a, b) => (b.publishedAt || 0) - (a.publishedAt || 0));
  const trimmed = sorted.slice(0, maxArticles);

  writeFileSync(filePath, JSON.stringify(trimmed, null, 2), 'utf-8');
}

/**
 * 添加新文章（自动去重）
 * @param {string} mpId - 公众号 ID
 * @param {Array} newArticles - 新文章列表
 * @returns {number} 实际新增的文章数
 */
export function addArticles(mpId, newArticles) {
  const existing = readArticles(mpId);
  const existingUrls = new Set(existing.map(a => a.url));

  const uniqueNew = newArticles.filter(a => !existingUrls.has(a.url));
  if (uniqueNew.length === 0) {
    return 0;
  }

  const merged = [...existing, ...uniqueNew];
  saveArticles(mpId, merged);
  return uniqueNew.length;
}

/**
 * 获取所有公众号的文章文件列表
 * @returns {Array<{mpId: string, name: string, count: number}>} 公众号列表
 */
export function listStoredMPs() {
  ensureDir(ARTICLES_DIR);

  try {
    const files = readdirSync(ARTICLES_DIR).filter(f => f.endsWith('.json'));
    return files.map(f => {
      const mpId = f.replace('.json', '');
      const articles = readArticles(mpId);
      return {
        mpId,
        name: articles[0]?.mpName || mpId,
        count: articles.length
      };
    });
  } catch {
    return [];
  }
}
