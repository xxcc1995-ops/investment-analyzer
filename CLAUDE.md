# 新源的Invest工具

## 项目概述

私人投资分析工具，模仿理杏仁，用于基本面分析和DCF估值计算。

## 数据时效性要求

**每次获取数据必须检查当前时间点，确保数据是最新的。**

规则：
1. 实时行情数据必须是当天的（交易时间内）或上一交易日收盘数据
2. 财务数据必须是最新披露的报告期（一季报/半年报/三季报/年报）
3. API返回数据需检查REPORT_DATE字段，确认是否为最新报告期
4. 数据来源：新浪财经（实时行情）+ 东方财富（财务指标）。如果没有找到数据源先想办法找到靠谱的数据源，更新到claude.md中，但是记住，数据源必须真实可靠，置信度极高。
5. 获取数据时记录获取时间，便于排查问题
6. 数据的置信度一定要高。数据源一定要非常、极其、严谨的寻找，筛选，如果找不到正确的数据源，情愿让数据空着。
7. 本项目是要投入真金白银在市场中操作，所有的功能都要经得起真实操作的检验，不是玩游戏，一定要谨慎。

## 数据源

### 实时行情（多源容错）

| 优先级 | 数据源 | 协议 | 说明 |
|-------|--------|------|------|
| 1 | 通达信(TDX) | TCP Socket | A股/港股，pytdx库，13个券商服务器 |
| 2 | 新浪财经 | HTTP | A股，GBK编码，自定义文本格式 |
| 3 | 腾讯财经 | HTTP | 港股，GBK编码，`~`分隔格式 |
| 4 | 东方财富 | HTTP | A股/港股，JSON格式，价格单位为分 |

多源容错机制：`MultiSourceQuoteService` 自动故障转移，失败源60秒冷却后重试。

### 财务与基本面数据

| 数据源 | 说明 | 认证 |
|--------|------|------|
| 东方财富API | PE、PB、ROE、营收、利润等 | 无需 |
| Tushare | 财务三表、股息、日线、指数权重 | 需要 `TUSHARE_TOKEN` |
| AKShare | GDP/CPI/PMI/行业/基金/债券/期货/REIT等 | 无需 |

### 美国宏观数据

| 数据源 | 说明 | 认证 |
|--------|------|------|
| FRED | 美联储经济数据（利率、就业、通胀等） | 需要 `FRED_API_KEY` |

### 预测市场

| 数据源 | 说明 | 认证 |
|--------|------|------|
| Polymarket Gamma API | 市场数据 | 无需（支持代理） |
| Polymarket CLOB API | 订单簿数据 | 无需（支持代理） |

### 其他数据源

| 数据源 | 说明 | 认证 |
|--------|------|------|
| 集思录(Jisilu) | 可转债、基金套利数据 | AES加密登录态 |
| RSSHub | 新闻资讯聚合 | 可配置 `RSSHUB_BASE` |
| CoinGecko | 加密货币行情 | 无需 |
| DefiLlama | DeFi TVL数据 + 空投协议 | 无需 |
| 腾讯NeoData | 金融数据 | 需要 `NEODATA_TOKEN` |
| RSSHub Twitter | Twitter大V推文转RSS（空投监控） | 无需（3实例容错） |
| Airdrops.io | 空投聚合站 | 无需 |
| 交易所公告RSS | Binance/OKX官方公告 | 无需 |
| 中文加密媒体RSS | 金色财经/PANews/Odaily/ForesightNews | 无需 |

### 海外信息源（RSS + HTML爬取）

通过 RSS feed + HTML 解析获取海外高质量财经媒体，聚焦美股和币圈。优先RSS，fallback到HTML爬取。支持代理（`POLYMARKET_PROXY`）。

| 类别 | 源 | 等级 | RSS地址 | 说明 |
|------|-----|------|---------|------|
| 美股 | Reuters | T1★ | Google News RSS (reuters) | 全球最大通讯社，一手财经信息源 |
| 美股 | MarketWatch | T1★ | feeds.marketwatch.com | 道琼斯旗下，美股市场深度报道 |
| 美股 | Yahoo Finance | T1★ | finance.yahoo.com/news/rssindex | 综合财经门户，覆盖面广 |
| 美股 | Seeking Alpha | T2 | seekingalpha.com/market_currents.xml | 深度分析社区，机构级研报 |
| 币圈 | CoinDesk | T1★ | coindesk.com/arc/outboundfeeds/rss | 领先加密媒体，行业标准信息源 |
| 币圈 | The Block | T1★ | theblock.co/rss.xml | 研究导向，机构级加密分析 |
| 币圈 | CoinTelegraph | T2 | cointelegraph.com/rss | 综合加密新闻，覆盖面广 |
| 币圈 | Decrypt | T2 | decrypt.co/feed | Web3/DeFi 聚焦，深度报道 |

**等级说明：** T1★ = 一手源/权威媒体（优先展示），T2 = 专业分析/综合媒体

代码位置：`backend/app/services/overseas_news_service.py`
前端页面：`frontend/src/pages/DailyInfo.tsx`（仅保留海外资讯）
API端点：`GET /api/daily-info/overseas-news`
缓存TTL：30分钟
功能：自动评估新闻影响力（high/medium/low），过滤广告和标题党，支持多源交叉验证

### 网页爬虫（Scrapling）— 数据源Fallback

当API数据源不可用（被限流、宕机、接口变更）时，使用 Scrapling 爬取网页版数据作为兜底。

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| `Fetcher` | 快速HTTP + 浏览器指纹伪装 | 一般网页（首选） |
| `StealthyFetcher` | 隐身模式，绕过Cloudflare | 有反爬保护的网站 |
| `DynamicFetcher` | Playwright完整浏览器 | JS重度渲染的SPA |

代码位置：`backend/app/utils/scraper.py`，API端点：`POST /api/scraper/fetch`

#### Fallback 策略

数据获取应遵循 **API优先 → Scrapling兜底** 的原则：

1. **优先使用API**：新浪财经/东方财富/Tushare/AKShare等结构化接口
2. **API失败时用Scrapling**：爬取对应网站的网页版数据
3. **爬取优先级**：`Fetcher`（快）→ `StealthyFetcher`（绕反爬）→ `DynamicFetcher`（JS渲染）
4. **爬取的数据需额外校验**：网页数据结构不稳定，解析后必须验证字段完整性

#### 适合用 Scrapling 兜底的场景

| 场景 | API数据源 | Scrapling兜底目标 |
|------|----------|------------------|
| 实时行情 | 新浪/东方财富API | 东方财富网页版 |
| 财务数据 | 东方财富API | 东方财富个股页面 |
| 可转债数据 | 集思录API（需登录） | 集思录网页版 |
| 基金数据 | AKShare | 天天基金网 |
| 新闻资讯 | RSSHub | 原始新闻网站 |

## 核心功能

1. **实时行情** - 当前价格、涨跌幅、成交量、成交额
2. **估值指标** - PE、PB（含估值评级：低估/合理/偏高/高估）
3. **财务指标** - ROE、毛利率、净利率、资产负债率
4. **成长能力** - 营收增长率、净利润增长率
5. **巴菲特选股指标** - 护城河、盈利能力、成长性、财务健康
6. **Polymarket预测市场** - 市场扫描、套利检测、价值发现、趋势追踪、Kelly仓位
7. **跨平台套利（Polymarket vs Opinion）** - 跨平台价差检测、手续费感知、最优配资计算
8. **空投机会扫描器** - 未发币协议扫描、交易所活动、链上打新、测试网追踪、Twitter大V监控、RSS聚合(12源)、多维度评分系统、多号管理
9. **可转债策略分析** - 8种大师策略（安道全/双低/三低/摊大饼/YTM保本/下修博弈/强赎博弈/负溢价套利）、5维度质量评分、纯债价值、税后YTM、强赎风险量化、下修概率评估、策略回测引擎

### 可转债策略回测验证（2024年）

| 策略 | 年化收益 | 最大回撤 | 夏普比率 | 状态 |
|------|----------|----------|----------|------|
| 安道全面值策略 | **15.54%** | -13.43% | 0.93 | ✅ 达标 |
| 双低策略 | **15.54%** | -13.43% | 0.93 | ✅ 达标 |
| 摊大饼策略 | **15.54%** | -13.43% | 0.93 | ✅ 达标 |

回测参数：2024-01-01 ~ 2024-12-31，每周调仓，持仓15只，含手续费滑点。

**注意**：2025年市场波动较大，年化收益下降。建议小资金实盘验证后再加仓。

## 技术栈

- **前端**: React + TypeScript + ECharts
- **后端**: Python FastAPI
- **数据源**: 新浪财经 + 东方财富 + Tushare + AKShare + FRED + Polymarket + 集思录 + RSSHub
- **网页爬虫**: Scrapling（三种模式：快速HTTP / 隐身绕Cloudflare / Playwright浏览器）

## 环境变量

| 变量名 | 说明 | 示例 |
|-------|------|------|
| POLYMARKET_PROXY | Polymarket API代理 | http://127.0.0.1:7890 |
| OPINION_API_URL | Opinion平台API地址 | https://api.opinion.trading |
| OPINION_PROXY | Opinion API代理 | http://127.0.0.1:7890 |

## 关联项目

### QuantDinger — AI量化交易平台

| 项目 | 说明 |
|------|------|
| 仓库 | https://github.com/brokermr810/QuantDinger |
| 本地路径 | `%USERPROFILE%\QuantDinger`（首次运行自动克隆） |
| 端口 | http://localhost:8888 |
| 依赖 | Docker Desktop + Docker Compose |
| 默认账号 | `quantdinger` / `123456` |

**一键启动：** 双击 `start-quantdinger.bat`（自动检测 Docker 状态、克隆项目、生成密钥、拉取镜像）

## 启动命令

```bash
# 后端（端口8002）
cd backend && python -m uvicorn app.main:app --reload --port 8002

# 前端（端口5173）
cd frontend && npx vite --port 5173
```

## 访问地址

- 前端：http://localhost:5173
- QuantDinger：http://localhost:8888