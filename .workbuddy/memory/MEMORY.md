# 投资分析器项目记忆

## 项目概况
- 投资分析工具，包含前后端（FastAPI + React/Vite）
- 后端端口 8002，前端端口 5173，启动用 `start.bat`
- 后端 venv 在 `backend/venv/`

## 全球指数估值模块
- 核心服务文件：`backend/app/services/index_valuation_service.py` (~1050行)
- 19个全球指数，INDEX_CONFIG 字典定义元数据
- 数据源：中证指数(A股)、multpl.com(SPX)、stockanalysis.com(NDX PE)、富途OpenAPI、yfinance(全球ETF)、乐咕乐股
- 缓存 TTL：估值数据 1 小时，历史数据 1 天
- **数据可靠性原则：只提供高可靠度数据，不可靠数据不显示避免误导**
  - SPX: 全部数据来自 multpl.com（高可靠）— PE/PB/百分位/股息率/ROE
  - NDX: 仅提供 PE（来自 stockanalysis.com 实时抓取）— PB/百分位/股息率/ROE 全为 null
  - SPXDIV: 全部数据为 null（无可靠指数级数据源，ETF数据不可靠）
- yfinance ETF `priceToBook` 不准确（QQQ≈2.02 vs 实际≈7.66），不用于指数级 PB
- NDX 不可靠数据已删除：硬编码PB、估算参考百分位、ETF级股息率
- NDX 历史序列为空（无真实月度历史数据，估算参考值不可靠）

## 安全配置
- CORS 白名单模式（默认 localhost:5173/3000）
- API_KEY 认证中间件保护敏感端点（未设置时自动跳过）
- 输入校验加固（阻止路径遍历、超长输入、特殊字符注入）
- 日志敏感信息过滤（password/token/api_key 脱敏）

## 技术栈
- 后端：Python 3.13 + FastAPI + uvicorn + yfinance + requests
- 前端：React + TypeScript + Vite + Ant Design
- 数据库：SQLite（本地缓存）
