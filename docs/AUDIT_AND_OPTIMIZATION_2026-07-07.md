# 投资分析器 — 安全与功能审计 + 优化报告

日期：2026-07-07
范围：`backend/app` + `frontend/src` + `backend/tractor`（拖拉机套利）
方式：静态审计 + 关键计算逐行复核 + 修复

---

## 一、前后端安全审计结论

整体评估：**无高危远程可利用漏洞**（无 SQL 注入、无命令注入、无 `eval/exec/subprocess`、无 TLS 校验关闭、前端无 `innerHTML`/`eval`、无硬编码密钥）。
但存在多处「私有工具也该修」的中高风险点，已全部修复。

### 已修复（安全）

| # | 问题 | 文件 | 风险 | 修复 |
|---|------|------|------|------|
| S1 | API Key 用 `==` 比较，可被计时攻击 | `core/security_middleware.py` | 中 | 改用 `hmac.compare_digest`（常数时间） |
| S2 | 爬虫 SSRF 防护可被绕过（十进制/十六进制 IP、DNS 技巧、`user@host`） | `api/scraper.py` | 高 | 解析域名为 IP 二次校验私有/回环/链路本地/保留段；禁止 URL 携带 userinfo |
| S3 | 爬虫端点未纳入认证，且 `dynamic` 模式超 60s 被全局超时掐断 | `main.py` | 中 | 爬虫前缀加入 `SENSITIVE_PREFIXES`（设了 API_KEY 才生效）；全局超时对 `/api/scraper` 豁免 |
| S4 | `SENSITIVE_PREFIXES` 漏掉写操作/交易类路由 | `core/security_middleware.py` + 前端 `client.ts` | 中 | 补齐 `/scraper /t-trading /decision /drawdown /backtest /cb-backtest /quant /airdrop-scanner /crypto-master /national-team /right-side /fund-holdings`；前端拦截器前缀同步 |
| S5 | 券商**交易密码明文**存 `accounts.json`，并原样拼进 AutoIt 脚本（`'","'.join`）——含 `"` 会截断/注入脚本 | `tractor/tractor_models.py` + `tractor/tractor_config.py` | 高 | 模型层校验账户名/密码仅含可见字符且无双引号/控制字符；生成脚本时对 `"` 做 `""` 转义（防御纵深） |
| S6 | `accounts.json`、自动生成的 `*.au3`（含明文密码）被 **git 跟踪** | `.gitignore` + `git rm --cached` | 高 | 加入 `.gitignore` 并从索引移除（本地文件保留，仅停止纳入版本库）。**建议：若仓库曾 push，立即修改券商密码** |

### 备注（未改，建议）

- 输入校验：仅 `stocks.py` 用了 `validate_stock_code`，其余 ~30 个路由直接收参。因无注入点且为单机私有工具，未全量改造；如需可统一加依赖校验。
- `cached` 装饰器：并发缓存未命中会「惊群」重复打外部源（限流已缓解），属性能优化非安全。
- 爬虫仍有 DNS 重绑定残留风险（校验与抓取分两次解析）：私有本机可接受，生产多租户需固定解析 IP。

---

## 二、投资功能逻辑审计结论

对核心功能做了逐行复核。**DCF、LOF 折溢价率、收益率曲线 2Y-10Y 利差方向**均正确，无需改。
发现并已修复 6 处会**直接误导真实决策**的计算/口径问题：

| # | 功能 | 文件 | 严重度 | 问题 | 修复 |
|---|------|------|--------|------|------|
| I1 | 全球指数股权风险溢价 | `services/index_valuation_service.py` | 高 | `_BOND_YIELDS` 写死且已过时（如中国 10Y 仍用 2.3%，实际约 1.7%），直接污染所有非美指数的「低估/高估」评分 | 改为实时拉取 10Y（美/中走既有 `akshare` 收益率曲线封装），取不到则风险溢价置空、**不**用陈旧值（符合项目「宁可空着」原则） |
| I2 | 可转债纯债价值/税后 YTM | `services/cb_service.py` | 中 | 票息反推符号错：`(100-price)` 应为减号。溢价债票息被低估→债底虚低；折价债票息被高估→债底虚高，污染「双低/债底保护」评分 | 改为 `coupon = (price*ytm - (100-price)/year_left)/100` |
| I3 | 标普500 股息率历史百分位 | `services/index_valuation_service.py` | 中 | 直接复用「历史中≤当前的比例」，对股息率（越高越便宜）语义正好相反，与 PE/PB 百分位及综合信号自相矛盾 | 取反：`percentile = 100 - raw`，使「高股息率→低分位(便宜)」与 PE/PB 口径一致 |
| I4 | 个股 EV/EBITDA | `api/valuation.py` | 中 | 总债务只含短/长借款，遗漏应付债券/应付票据/租赁负债，系统性低估 EV→标的显得「更便宜」 | 债务纳入三项，并在 `data_service.py` 资产负债表拉取与映射对应字段（东方财富 `BOND_PAYABLE/NOTE_PAYABLE/LEASE_LIABILITY`） |
| I5 | 估值告警综合判读 | `api/valuation.py` | 中 | 同一综合评分两套分档互相矛盾（DCF：≥80 严重低估/≥65 低估/≥45 合理/≥30 偏高；摘要：≥70 低估/≥45 合理/else 高估） | 告警摘要直接复用 DCF `calculate_composite_score` 返回的 `level`，消除分歧 |
| I6 | 美国衰退概率 | `api/macro.py` | 低 | `100 - score*0.8` 使「全面健康」仍显示 20% 衰退概率 | 改为 `100 - score`，景气评分与概率自洽 |

### 复核确认「无 bug」的项（避免误报）
- DCF 终值：`discount_rate > terminal_growth_rate` 已强制，且 `terminal_pct` 有除零保护。
- LOF 折溢价率：`(price - est_nav)/est_nav` 符号正确。
- 2Y-10Y 利差：`spread<0 → 倒挂` 方向正确。
- 「10年分红回本」：后端无此计算；派息率 `dividend_ratio` 已有 `eps>0 & ttm_dividend>0` 守卫，无除零。前端若有「回本年数=100/股息率」需注意股息率为 0 时的除零。

---

## 三、改动文件清单
- `backend/app/core/security_middleware.py`
- `backend/app/api/scraper.py`
- `backend/app/main.py`
- `backend/app/api/valuation.py`
- `backend/app/api/macro.py`
- `backend/app/services/cb_service.py`
- `backend/app/services/index_valuation_service.py`
- `backend/app/services/data_service.py`
- `backend/app/tractor/tractor_models.py`
- `backend/app/tractor/tractor_config.py`
- `frontend/src/services/api/client.ts`
- `.gitignore`

所有改动均通过 `python -m py_compile` 语法校验。

## 四、仍需你留意的运营项
1. 若 `accounts.json` 曾提交/推送过，请**立即修改券商交易密码**。
2. 生产/多设备暴露时务必设置 `API_KEY` 环境变量，前端同步配置 `VITE_API_KEY`。
3. 指数风险溢价现在依赖实时 10Y 收益率；网络不可达时该分项会从综合信号中剔除（属预期行为）。
