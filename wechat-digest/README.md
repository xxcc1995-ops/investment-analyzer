# 📰 微信公众号每日内容自动抓取与总结系统

自动抓取微信读书中关注的公众号文章，提取正文，并生成 Markdown 格式的每日日报。

## 🚀 快速开始

### 1. 安装依赖

```bash
cd wechat-digest
npm install
```

### 2. 登录微信读书

```bash
npm run login
```

会自动弹出二维码图片，用微信扫码登录。

### 3. 查看已关注公众号

```bash
npm run accounts
```

### 4. 同步文章

```bash
npm run sync
```

增量同步最近 2 天的文章（可在 config.json 中配置）。

### 5. 生成日报

```bash
npm run summarize
```

生成 Markdown 格式的日报到 `output/` 目录。

### 6. 查看今日文章

```bash
npm run today
```

## 📁 目录结构

```
wechat-digest/
├── package.json          # 项目配置
├── config.json           # 用户配置
├── src/
│   ├── index.js          # CLI 入口
│   ├── api.js            # 微信读书 API 客户端
│   ├── store.js          # 文章存储
│   └── summarize.js      # 日报生成
├── data/
│   ├── auth.json         # 登录认证信息（自动生成）
│   └── articles/         # 各公众号文章数据（自动生成）
└── output/               # 每日日报（自动生成）
```

## ⚙️ 配置说明

编辑 `config.json`：

```json
{
  "wereadApiBase": "https://weread.111965.xyz",  // 微信读书 API 代理地址
  "accounts": [],                                  // 公众号列表（自动同步）
  "maxArticlesPerAccount": 20,                     // 每个公众号保留最大文章数
  "retryMaxAttempts": 5,                           // API 请求最大重试次数
  "retryDelayMs": 400,                             // 重试间隔（毫秒）
  "syncDays": 2                                    // 同步最近几天的文章
}
```

## 📝 日报格式

生成的日报格式如下：

```markdown
# 📰 微信公众号日报 - 2026-06-15

## 公众号A（3篇）

### 1. 文章标题
- 🔗 链接：https://mp.weixin.qq.com/s/xxx
- 📅 发布时间：2026-06-15
- 📝 摘要：（从文章正文前200字自动提取）

### 2. 文章标题
...

---
*由 wechat-digest 自动生成*
```

## ⚠️ 注意事项

1. **首次使用必须登录**：`npm run login`
2. **API 稳定性**：代理服务可能不稳定，所有请求都有重试机制
3. **礼貌延迟**：所有 API 请求间隔 300ms，避免被封
4. **数据安全**：认证信息保存在本地 `data/auth.json`，不会上传

## 🔧 故障排除

### 登录失败
- 确保网络能访问 `weread.111965.xyz`
- 检查代理设置（如需要）

### 同步失败
- 检查是否已登录：`data/auth.json` 是否存在
- 尝试重新登录：`npm run login`

### 无法提取正文
- 微信文章可能有反爬机制，系统会尝试多种提取方式
- 部分文章可能无法提取，会显示"（无法提取正文）"

## 📄 许可证

MIT
