#!/usr/bin/env node

/**
 * 微信公众号每日内容自动抓取与总结系统
 * CLI 入口
 */

import { login, getFollowedMPs, getMPArticles, extractArticleContent, delay } from './api.js';
import { readConfig, saveConfig, readAuth, readArticles, addArticles } from './store.js';
import { generateDailyReport, getTodayArticles } from './summarize.js';

// 获取命令行参数
const args = process.argv.slice(2);
const command = args[0] || 'help';

/**
 * 显示帮助信息
 */
function showHelp() {
  console.log(`
📰 微信公众号每日内容自动抓取与总结系统
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

用法: node src/index.js <命令>

命令:
  login      🔐 扫码登录微信读书
  accounts   📋 查看已关注公众号列表
  sync       🔄 同步所有公众号的最新文章
  today      📅 查看今日文章列表
  summarize  📝 生成今日 Markdown 日报
  help       ❓ 显示此帮助信息

示例:
  npm run login
  npm run sync
  npm run summarize
  `);
}

/**
 * 处理 login 命令
 */
async function handleLogin() {
  try {
    await login();
  } catch (err) {
    console.error(`\n❌ 登录失败: ${err.message}`);
    process.exit(1);
  }
}

/**
 * 处理 accounts 命令
 */
async function handleAccounts() {
  try {
    const auth = readAuth();
    if (!auth) {
      console.log('❌ 未登录，请先运行: npm run login');
      process.exit(1);
    }

    const mps = await getFollowedMPs();

    if (mps.length === 0) {
      console.log('📭 没有找到已关注的公众号');
      return;
    }

    console.log(`\n📋 已关注公众号列表（共 ${mps.length} 个）\n`);
    console.log('━'.repeat(50));

    mps.forEach((mp, index) => {
      const name = mp.name || mp.mpName || '未知';
      const mpId = mp.mpId || mp.id || '';
      console.log(`${index + 1}. ${name} (ID: ${mpId})`);
    });

    console.log('━'.repeat(50));

    // 同步到 config.json
    const config = readConfig();
    config.accounts = mps.map(mp => ({
      mpId: mp.mpId || mp.id,
      name: mp.name || mp.mpName || '未知'
    }));
    saveConfig(config);
    console.log('\n✅ 已同步到 config.json');

  } catch (err) {
    console.error(`\n❌ 获取公众号列表失败: ${err.message}`);
    process.exit(1);
  }
}

/**
 * 处理 sync 命令
 */
async function handleSync() {
  try {
    const auth = readAuth();
    if (!auth) {
      console.log('❌ 未登录，请先运行: npm run login');
      process.exit(1);
    }

    console.log('🔄 开始同步公众号文章...\n');

    // 获取公众号列表
    let mps;
    try {
      mps = await getFollowedMPs();
    } catch (err) {
      // 如果 API 获取失败，尝试从配置读取
      console.log('⚠️ 从 API 获取公众号列表失败，尝试从配置读取...');
      const config = readConfig();
      mps = config.accounts || [];
    }

    if (mps.length === 0) {
      console.log('📭 没有找到已关注的公众号');
      return;
    }

    const config = readConfig();
    const syncDays = config.syncDays || 2;
    const cutoffTime = Math.floor(Date.now() / 1000) - (syncDays * 24 * 60 * 60);

    let totalNew = 0;
    let totalSkipped = 0;
    let failedMPs = [];

    // 逐个同步
    for (let i = 0; i < mps.length; i++) {
      const mp = mps[i];
      const mpId = mp.mpId || mp.id;
      const mpName = mp.name || mp.mpName || '未知';

      console.log(`\n[${i + 1}/${mps.length}] 📥 同步: ${mpName}`);

      try {
        // 获取文章列表（最多 2 页，即 40 篇）
        let allArticles = [];
        for (let page = 0; page < 2; page++) {
          const articles = await getMPArticles(mpId, page);
          if (!articles || articles.length === 0) break;
          allArticles = allArticles.concat(articles);
          await delay(300); // 礼貌延迟
        }

        // 过滤近 N 天的文章
        const recentArticles = allArticles.filter(a => {
          const createTime = a.createTime || 0;
          return createTime >= cutoffTime;
        });

        if (recentArticles.length === 0) {
          console.log(`  📭 最近 ${syncDays} 天内没有新文章`);
          continue;
        }

        console.log(`  📄 找到 ${recentArticles.length} 篇近期文章`);

        // 提取正文并保存
        let newCount = 0;
        for (const article of recentArticles) {
          const articleUrl = article.url || `https://mp.weixin.qq.com/s/${article.articleId || ''}`;

          // 检查是否已存在
          const existing = readArticles(mpId);
          if (existing.some(a => a.url === articleUrl)) {
            totalSkipped++;
            continue;
          }

          console.log(`  📖 正在提取: ${article.title || '未知标题'}`);

          // 提取正文
          let content = '';
          try {
            content = await extractArticleContent(articleUrl);
          } catch (err) {
            console.log(`  ⚠️ 提取失败: ${err.message}`);
          }

          await delay(300); // 礼貌延迟

          // 构造文章对象
          const articleObj = {
            title: article.title || '未知标题',
            url: articleUrl,
            publishedAt: article.createTime || Math.floor(Date.now() / 1000),
            fetchedAt: Math.floor(Date.now() / 1000),
            content: content,
            mpId: mpId,
            mpName: mpName
          };

          // 保存
          const added = addArticles(mpId, [articleObj]);
          if (added > 0) {
            newCount++;
            totalNew++;
          } else {
            totalSkipped++;
          }
        }

        console.log(`  ✅ 新增 ${newCount} 篇文章`);

      } catch (err) {
        console.log(`  ❌ 同步失败: ${err.message}`);
        failedMPs.push(mpName);
      }

      // 公众号之间的延迟
      if (i < mps.length - 1) {
        await delay(500);
      }
    }

    // 汇总
    console.log('\n' + '━'.repeat(50));
    console.log('📊 同步完成！');
    console.log(`  ✅ 新增文章: ${totalNew} 篇`);
    console.log(`  ⏭️  已跳过: ${totalSkipped} 篇`);
    if (failedMPs.length > 0) {
      console.log(`  ❌ 失败: ${failedMPs.join(', ')}`);
    }
    console.log('━'.repeat(50));

  } catch (err) {
    console.error(`\n❌ 同步失败: ${err.message}`);
    process.exit(1);
  }
}

/**
 * 处理 today 命令
 */
async function handleToday() {
  try {
    const days = parseInt(args[1]) || undefined;
    const articles = await getTodayArticles(days);

    if (articles.length === 0) {
      console.log('📭 今日暂无新文章，请先运行 sync 同步');
      return;
    }

    console.log(`\n📅 今日文章列表（共 ${articles.length} 篇）\n`);
    console.log('━'.repeat(60));

    articles.forEach((article, index) => {
      const pubDate = article.publishedAt
        ? new Date(article.publishedAt * 1000).toLocaleDateString('zh-CN')
        : '未知';

      console.log(`${index + 1}. [${article.mpName || '未知'}] ${article.title}`);
      console.log(`   📅 ${pubDate}  🔗 ${article.url}`);
      console.log('');
    });

    console.log('━'.repeat(60));

  } catch (err) {
    console.error(`\n❌ 获取今日文章失败: ${err.message}`);
    process.exit(1);
  }
}

/**
 * 处理 summarize 命令
 */
async function handleSummarize() {
  try {
    const days = parseInt(args[1]) || undefined;
    const outputPath = await generateDailyReport({ days });

    if (outputPath) {
      console.log('\n💡 提示: 可以用 Markdown 编辑器打开日报文件查看');
    }

  } catch (err) {
    console.error(`\n❌ 生成日报失败: ${err.message}`);
    process.exit(1);
  }
}

// 命令分发
switch (command) {
  case 'login':
    await handleLogin();
    break;

  case 'accounts':
    await handleAccounts();
    break;

  case 'sync':
    await handleSync();
    break;

  case 'today':
    await handleToday();
    break;

  case 'summarize':
    await handleSummarize();
    break;

  case 'help':
  case '--help':
  case '-h':
    showHelp();
    break;

  default:
    console.log(`❌ 未知命令: ${command}`);
    showHelp();
    process.exit(1);
}
