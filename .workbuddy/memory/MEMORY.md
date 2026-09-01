# 投资分析器项目记忆

## ⚠️ 硬性流程要求（用户明确指令）
- **每次操作前必须先读 `D:/investment-analyzer/CLAUDE.md`**，核对数据时效性与数据源，再动手。核心原则：**宁可空着，不要不可靠数据**（真金白银项目）。

## 项目概况与环境
- FastAPI(8022) + React/Vite(5180)，启动 `start.bat`（自提权→start.ps1 强制重启8022）；后端 venv `backend/venv/`。旧 8002/5173 已废止勿用。
- **沙箱↔宿主共享网络命名空间**（2026-08-06 实测）：沙箱可直连宿主 8022/5180/11111(富途)，**有外网出口**；可在备用端口(如8023)起 uvicorn 验证新端点；**无权杀宿主提权进程**→新后端路由需用户管理员重启 start.bat。
- 安全：CORS 白名单(5180等)、API_KEY 中间件、输入校验、日志脱敏；前后端 `SENSITIVE_PREFIXES` 须保持一致。

## 可转债数据源（三级容错，与 CLAUDE.md 对齐）
- 集思录API(登录态,64字段) → 集思录网页版 Scrapling(懒导入,无playwright时回落) → AKShare `bond_zh_cov`(缺 year_left/ytm_rt/turnover，仅基础字段)。
- 依赖 year_left/turnover/ytm 的策略在 AKShare 源下返回空+提示，不展示伪候选。

## 全球指数估值模块
- `backend/app/services/index_valuation_service.py`，19个指数。可靠性原则：SPX 全字段(multpl.com)；NDX 仅 PE(stockanalysis.com)，其余 null；SPXDIV 全 null。yfinance ETF priceToBook 不可靠不用。缓存：估值1h/历史1天。

## 相对估值法模块（2026-07-08）
- `relative_valuation_service.py` 内联 A_PEER_GROUPS(8行业)/HK_PEER_GROUPS(7行业)；API `/api/relative-valuation/{sectors,stocks,compare,stock}`，sector 可空自动定位。前端默认「选标的对比」Tab（用户明确不要默认整组自动跑），二级Tab按行业浏览。缺字段留 None。

## 实时做T模块（腾讯00700.HK，2026-08-06）
- 三层：tencent_source(分时/盘口) → intraday_t_signal_service(三重确认+2倍成本门槛,空数据返回hold) → realtime_t_monitor(asyncio广播,熔断/冷却)。API `/api/t-realtime` + WS；前端 `TTradingRealtime.tsx` 常驻操作参考横幅(含收盘时段)。
- **数据源：富途OpenAPI主源**(11111,真实五档量+5分钟K；`_ensure_futu_ctx` 先socket预检防卡112秒) → 腾讯兜底(分时可用;盘口港股量恒0;mkline港股已失效)。
- main.py lifespan 启动即 `watch('00700')`；start.ps1 FORCE-RESTART 故 start.bat 启动即激活。
- 无逐笔成交（免费源均无），UI 须标注。

## 基金套利模块（2026-08-15 改造）
- 申购状态双源：集思录(主,含 min_amt 限额原文) → 天天基金 `ak.fund_purchase_em()`(兜底,`FundService.get_em_purchase_status_map`,1h缓存,日限≥1亿=无限额)。**集思录匿名访问各列表仅前20条**(rp无效)，QDII LOF 多需登录，故兜底必需。
- 字段口径陷阱：`amount`=份额(万份)**不是成交额**；`turnover`=成交额(万元)=volume(万份)×price。scan/est-list 必须经 `_normalize_fund` 标准化（裸代码索引，LOF_FUND_CONFIG 键带 SH/SZ 前缀）。
- 前端 `FundArbitragePage.tsx`：`getSubscribeInfo`(可申/限购/暂停/未知/ETF不适用 徽章+提示) + `formatTurnover`(万亿格式化,<1000万警告)。

## 已删除功能（勿再引用）
- 拖拉机套利执行层(2026-07-08删,保留基金套利分析层)；策略回测/量化回测/回撤控制三页面(`/api/backtest` 后端保留,StrategyValidation 与 TTrading 共用)。SENSITIVE_PREFIXES 已对齐不含 tractor/drawdown/quant。

## 记忆管理纪律（与 L2 对齐）
- L3 日志追加式(完成/决策/待续三必答)；「已废止」标注不物理删除；检索优先级 L2→L3→conversation_search→提问。
- 绝不写入：持仓成本/盈亏、隐私、一次性路径、工具瞬时输出、未验证假设。

## 认知纠偏规则（用户论述触发时主动指出）
过度泛化(样本能代表总体?) / 精确-准确滑坡(口径假设?) / 类比替代论证(差异点?) / 高手可复制性幻觉(成本约束一致?) / 放弃安全边际(最坏亏损?) / 忽视机会成本(备选收益?)。
