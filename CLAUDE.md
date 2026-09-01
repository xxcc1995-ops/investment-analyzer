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

#### 日内实时行情（实时做T专用，2026-08-06 新增）

腾讯控股 00700.HK 日内做T所需高频行情，**分层数据源（富途主源 + 腾讯兜底）**：

| 数据类型 | 主源（富途 OpenAPI） | 兜底（腾讯免费源） | 说明 |
|---------|------|------|------|
| 1分钟分时 | — | `web.ifzq.gtimg.cn/appstock/app/minute/query?code=hk00700`（**无 r_ 前缀**） | 当日分时（价/量），腾讯高可靠 |
| 5分钟K线 | `subscribe(K_5M)`→`get_cur_kline(KLType.K_5M)` | `mkline` 接口**对港股已失效**（301→web3 DNS 不可解析），不可用 | 日内支撑压力计算，走富途 |
| 五档盘口 | `subscribe(ORDER_BOOK)`→`get_order_book(num=5)` | `qt.gtimg.cn/q=r_hk00700`（fields[9..28]）**港股量恒为0，仅价可用** | 买卖五档价/量 + 盘口失衡，走富途真实量 |

代码位置：
- 富途：`backend/app/services/realtime_t_monitor.py`（`_get_futu_order_book`/`_get_futu_5min_kline` + 模块级 `get_best_order_book`/`get_best_5min_kline`，富途优先、失败回落腾讯）；需 FutuOpenD 运行于 `127.0.0.1:11111` 且账户有港股 LV2 权限。
- 腾讯：`backend/app/services/quote_sources/tencent_source.py`（`get_minute_kline`/`get_5min_kline`/`get_order_book`）。`QuoteData` 已扩展 bid2-5/ask2-5 字段。

⚠️ **无逐笔成交**：免费源 + 富途免费档均不提供逐笔，最细粒度为1分钟分时 + 实时五档盘口。UI须明确标注，避免误导。

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

### 指数盈利估值自动取数源（2026-08-16 沙箱实测）

为「指数盈利与估值查阅」模块自动化做的数据源实测结论（脚本备查 `backend/scripts/test_index_data_sources*.py`，沙箱需 `env -u HTTPS_PROXY -u HTTP_PROXY` 直连）：

| 数据 | 源 | 状态 | 口径备注 |
|------|-----|------|----------|
| 中国十年期国债 | `ak.bond_zh_us_rate`（英为财情） | ✅ 日频长历史 | 与用户 Excel 2000-2007 段同源 |
| 中国十年期国债（校验） | `ak.bond_china_yield`（中债官方） | ✅ 官方 | 取「中债国债收益率曲线」10年列 |
| 美国十年期国债 | `ak.bond_zh_us_rate`（英为财情） | ✅ 同上 | FRED_API_KEY 未配置，DGS10 可作备选 |
| 沪深300 收盘+PE-TTM | `ak.stock_index_pe_lg("沪深300")`（乐咕乐股） | ✅ 2005-04起日频5189行 | 收盘价与Wind完全一致；滚动PE与Wind差~5%（13.68 vs 14.38 同日实测） |
| 沪深300 PE（校验） | `ak.stock_zh_index_value_csindex`（中证官网） | ✅ 仅最近20条 | 市盈率1=14.73，比乐咕更贴近Wind(差2.4%) |
| 标普500 PE/EPS | multpl.com 月度表 | ⚠️ 半可用 | reported(GAAP)口径，与Wind(operating)系统性差~15%；仅月度+当日值，无周频 |
| 标普500 EPS官方 | spglobal sp-500-eps-est.xlsx | ❌ 403 | 需浏览器头或手工下载 |
| 纳指100 PE | stockanalysis.com/etf/qqq | ⚠️ 仅当前值(33.62) | 无免费长历史；历史需理杏仁或从即日起自攒 |
| 万得全A 881001.WI | 新浪/腾讯/乐咕/韭圈儿 | ❌ 全军覆没 | Wind专有指数；乐咕"全A"是等权中位数口径≠万得全A；韭圈儿API 405 |
| Tushare index_dailybasic | 需2000积分 | ⏸ 未启用 | `.env` 中 TUSHARE_TOKEN 为空；有token后可作沪深300 PE-TTM更优源 |

**结论**：国债与沪深300可全自动（乐咕主源+官方校验）；标普500半自动（口径降级需用户确认）；纳指100可新建但历史自攒；万得全A免费通道不存在，维持Wind手工导出或理杏仁付费API。

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
9. **可转债策略分析** - 八大战法（正收益/YTM保本、双低、轮动、临期债网格、下修博弈、强赎、问题债博弈、负溢价转股；源自《可转债：从入门到精通的八大战法》）、5维度质量评分、纯债价值、税后YTM、强赎风险量化、下修概率评估、策略回测引擎。数据源严格按「集思录API → 集思录网页版(Scrapling) → AKShare(仅基础字段)」三级容错；**AKShare 不提供 剩余年限/成交额/到期收益率(YTM)**，依赖这些字段的策略在无集思录登录态时严格返回空+提示（遵循「宁可空着不要不可靠数据」）。
10. **实时做T（腾讯 00700.HK）** - 日内回转交易机会识别与实时推送。基于1分钟分时 + 五档盘口 + 5分钟K，算日内 VWAP / 支撑压力 / 盘口失衡 / 量能异动，三重确认 + 利润门槛（2倍 round-trip 成本）。WebSocket 实时推送信号到前端（弹窗+声音+桌面通知），风控熔断（单日4次硬限 / T仓30%上限 / 止损线）。做T记录复用 `t_position_service`（FIFO 盈亏 / 成本追踪）。**仅识别提醒，手动下单**（与拖拉机执行层删除后的取向一致）。数据源（分层）：**富途 OpenAPI 主源**（真实五档量+5分钟K，需 FutuOpenD:11111 + 港股 LV2）→ 腾讯兜底（分时 `web.ifzq.gtimg.cn/minute` + 盘口 `qt.gtimg.cn` 价可用量恒0）。代码：`backend/app/services/intraday_t_signal_service.py` + `realtime_t_monitor.py` + `app/api/t_realtime.py`；前端 `TTradingRealtime.tsx`（路由 `/t-trading-realtime`）。
11. **指数盈利与估值查阅（2026-08-15 新增）** - 用户手工维护的三大指数「盈利与估值分析表」Excel（周度数据）在线查阅：标普500(1957~)/万得全A(2000~)/沪深300(2005~)。口径：估值中枢偏移率=PE-TTM×十年期国债收益率（基准线 标普70/全A60/沪深300=折价线）；合理收盘价=(100÷国债)×折扣×隐含EPS；风险溢价=100÷PE−国债收益率；EPS周期=隐含EPS平滑+4%zigzag（红涨绿跌）。**数据源 = 用户 Excel 原文件直读**（`D:/1957~2026年标普500盈利与估值/` 等三个固定路径，按文件 mtime 缓存失效，用户更新 Excel 后自动生效，不做外部抓取校验）。代码：`backend/app/services/index_earnings_service.py` + `app/api/index_earnings.py`（`/api/index-earnings/{list,data/{code}}`）；前端 `IndexEarnings.tsx`（路由 `/index-earnings`，菜单「行情总览→指数盈利估值」）。拆解脚本备查：`backend/scripts/analyze_index_excels.py`。
  - **自动重建版 hs300_auto（2026-08-16）**：`backend/app/services/index_earnings_auto_service.py`，乐咕收盘+PE-TTM（日频→ISO周，周日标签=每周最后交易日）+ 英为财情国债，复刻用户公式（4周平滑+4%zigzag、利差×20、偏移率、合理价、风险溢价）；日频原始数据落盘 `backend/data/manual/hs300_auto_cache.json`（国债增量拉取，TTL 12h）；payload 内嵌 compare 块（Wind vs 乐咕 PE 对比序列+统计+中证官网校验）。实测口径：乐咕PE 比 Wind 系统性低 ~4.2%（1087周重叠），收盘价完全一致。

### 可转债策略回测验证（2024年）

| 策略 | 年化收益 | 最大回撤 | 夏普比率 | 状态 |
|------|----------|----------|----------|------|
| 安道全面值策略 | **15.54%** | -13.43% | 0.93 | ✅ 达标 |
| 双低策略 | **15.54%** | -13.43% | 0.93 | ✅ 达标 |
| 摊大饼策略 | **15.54%** | -13.43% | 0.93 | ✅ 达标 |

回测参数：2024-01-01 ~ 2024-12-31，每周调仓，持仓15只，含手续费滑点。

> ⚠️ **此表数据已失效，待重跑（2026-07-16 修复）**：原回测引擎存在 bug——策略定义里的 `sell_rule`（止盈/止损价）是死配置，从未被执行，卖出只按"轮出 top_n"；加上三策略 filter 截断(115/130/140)在低价券充足时失效，导致三个策略在模拟中计算上等价，故指标完全相同。已修复 `cb_backtest_service.py`：新增 `sell_fn`（lambda），每个交易日按价格阈值触发卖出（先于调仓轮出）。合成数据测试确认三策略卖出时机已真正分化（andaoquan@130 / dual_low@140 / pancake@145）。**上表数字需用修复后的引擎重跑 2024 全年真实数据后更新**，在此之前不得据此表做实盘决策。

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

> **正式模式（日常使用，2026-08-17 起）**：双击 **`启动.vbs`** —— 全程无命令行窗口，托盘气泡提示进度，自动完成：强杀 8022 旧进程（含挂死，杀不掉自动自提权重试）→ 前端源码有更新则自动 `vite build` → 隐藏启动后端 → 健康等待（最长180s）→ 自动打开浏览器 **http://127.0.0.1:8022**。后端直接托管 `frontend/dist`（SPA 回退，单进程单端口）。双击 `停止.vbs` 停止。`start.bat` 为兼容入口（等价于启动.vbs）。日志在 `logs/`（backend.log / backend-error.log / frontend-build.log）。
> 稳定性设计：每次启动必强杀旧进程再起新进程 → 不存在端口占用/挂死残留；前端构建产物由后端托管 → 不需要 vite 常驻、无 5180 冲突。
> 开发模式（需要 HMR 时）手动起两个进程：
> 8002/5173 为旧僵尸端口，**勿再使用**。

```bash
# 开发模式-后端（端口8022）
cd backend && python -m uvicorn app.main:app --port 8022 --no-use-colors

# 开发模式-前端（端口5180，代理 /api → 8022）
cd frontend && npx vite --port 5180

# 前端生产构建（正式模式所需，dist 由后端托管）
cd frontend && npx vite build
```

## 访问地址

- 正式模式（单端口）：http://127.0.0.1:8022
- 开发模式前端：http://localhost:5180
- QuantDinger：http://localhost:8888