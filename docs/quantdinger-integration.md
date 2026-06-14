# QuantDinger AI分析集成说明

## 功能概述

将QuantDinger的AI快速分析能力集成到investment-analyzer中，为A股提供：
- AI驱动的技术分析（技术面、基本面、市场情绪三维度）
- 多时间周期趋势展望（24小时/3天/1周/1月）
- 交易计划（入场价、止损、止盈、仓位建议）
- 分析历史记录和绩效统计

## 工作原理

```
┌─────────────────────────────────────────────────────────────┐
│  investment-analyzer (你的项目)                              │
│  ┌─────────────────┐                                        │
│  │  StockAnalysis   │ ──── 用户点击"AI分析"Tab ────┐        │
│  │  页面            │                              │        │
│  └─────────────────┘                              ▼        │
│                                          ┌──────────────┐   │
│                                          │ AIAnalysisPanel│  │
│                                          │ 组件          │  │
│                                          └──────┬───────┘   │
│                                                 │           │
│                                          POST /api/quantdinger/analyze/{code}
│                                                 │           │
└─────────────────────────────────────────────────┼───────────┘
                                                  │
                                                  ▼
                                  ┌────────────────────────────┐
                                  │  QuantDinger (端口8888)     │
                                  │  ┌──────────────────────┐  │
                                  │  │ Fast Analysis API     │  │
                                  │  └──────────┬───────────┘  │
                                  │             │              │
                                  │  ┌──────────▼───────────┐  │
                                  │  │ MarketDataCollector   │  │
                                  │  │ (采集价格/K线/宏观/新闻)│ │
                                  │  └──────────┬───────────┘  │
                                  │             │              │
                                  │  ┌──────────▼───────────┐  │
                                  │  │ LLM分析 (GPT-4o等)    │  │
                                  │  │ + 客观评分校准         │  │
                                  │  └──────────┬───────────┘  │
                                  │             │              │
                                  │  ┌──────────▼───────────┐  │
                                  │  │ 结构化输出            │  │
                                  │  │ (决策/评分/交易计划)   │  │
                                  │  └──────────────────────┘  │
                                  └────────────────────────────┘
```

## 使用步骤

### 1. 启动QuantDinger服务

```bash
# 方式一：双击启动脚本（推荐）
start-quantdinger.bat

# 方式二：手动启动
cd %USERPROFILE%\QuantDinger
docker-compose up -d
```

服务启动后，默认地址：http://localhost:8888
默认账号：`quantdinger` / `123456`

### 2. 启动investment-analyzer

```bash
# 后端
cd backend && python -m uvicorn app.main:app --reload --port 8002

# 前端
cd frontend && npx vite --port 5173
```

### 3. 使用AI分析

1. 打开 http://localhost:5173
2. 进入任意股票的详情页（如 StockAnalysis 页面）
3. 点击 **🤖 AI分析** Tab
4. 选择时间周期（1H/4H/1D/1W）
5. 点击 **开始分析**
6. 等待10-30秒，查看AI分析结果

## 功能特性

### 1. AI分析结果

| 字段 | 说明 |
|------|------|
| **决策** | BUY（买入）/ SELL（卖出）/ HOLD（持有） |
| **置信度** | 0-100%，表示AI对决策的确定程度 |
| **评分** | 技术面/基本面/情绪面/综合（0-100分） |
| **趋势展望** | 24小时/3天/1周/1月的趋势方向和强度 |
| **交易计划** | 入场价、止损价、止盈价、建议仓位 |
| **买入理由** | 支持买入决策的关键因素 |
| **风险提示** | 需要注意的风险点 |

### 2. 多周期共识

AI会对多个时间周期（1H/4H/1D等）分别计算客观评分，然后加权投票得出共识决策。这比单一周期分析更可靠。

- **共识分数**：加权投票后的综合得分
- **一致性**：各周期分析的一致程度（越高越可靠）
- **市场状态**：trending（趋势）/ ranging（震荡）/ volatile（波动）

### 3. 历史记录

查看同一股票的历史AI分析记录，包括：
- 分析时间
- 当时的决策和置信度
- 事后验证结果（是否正确、实际收益）

### 4. 绩效统计

统计AI分析的整体表现：
- 总分析次数
- 准确率
- 平均收益
- 分决策统计（BUY/SELL/HOLD各自的准确率和收益）

## 与价值投资的结合

QuantDinger的AI分析**不是替代**你的基本面研究，而是**补充**：

| 你的研究（左侧/价值投资） | AI分析（右侧/技术分析） |
|--------------------------|------------------------|
| PE/PB估值评级 | 技术面评分 |
| ROE/毛利率/资产负债率 | 市场情绪评分 |
| DCF现金流折现 | 趋势展望 |
| 护城河/商业模式分析 | 多周期共识 |
| 巴菲特选股指标 | 交易计划（入场/止损/止盈） |

**最佳实践：**

1. **先用你的方法选出好公司**（低估值、高ROE、强护城河）
2. **再用AI分析确定买入时机**（趋势向上、情绪良好、技术面支撑）
3. **用AI的止损建议控制风险**（即使基本面好，也要设止损）
4. **定期复盘AI的绩效统计**（验证AI分析是否对你的选股有帮助）

## 配置说明

### 环境变量（可选）

在 `backend/.env` 中添加：

```bash
# QuantDinger API地址（默认http://localhost:8888）
QUANTDINGER_API_URL=http://localhost:8888

# QuantDinger登录凭据（默认quantdinger/123456）
QUANTDINGER_USERNAME=quantdinger
QUANTDINGER_PASSWORD=123456
```

### 使用不同的LLM模型

QuantDinger支持多个LLM供应商，你可以在分析时指定模型：

```python
# 在AIAnalysisPanel中，可以扩展模型选择功能
{
  "model": "openai/gpt-4o"  # 或 "google/gemini-pro", "deepseek/deepseek-chat" 等
}
```

## 注意事项

1. **积分消耗**：每次AI分析消耗10积分（QuantDinger的计费单位）
2. **分析耗时**：通常需要10-30秒，取决于数据量和LLM响应速度
3. **A股支持**：当前支持A股（沪/深/北交所），代码格式如 `600519`、`000858`
4. **服务依赖**：需要QuantDinger服务在后台运行
5. **网络要求**：需要能访问QuantDinger的LLM供应商（OpenAI/DeepSeek等）

## 故障排查

### 问题1：服务不可用

```
QuantDinger服务未启动
```

**解决方案：**
1. 检查QuantDinger是否已启动：`docker ps | grep quantdinger`
2. 检查端口是否被占用：`netstat -ano | findstr 8888`
3. 重启服务：`docker-compose restart`

### 问题2：分析超时

```
QuantDinger分析超时
```

**解决方案：**
1. 检查网络连接（可能需要代理访问LLM供应商）
2. 尝试使用不同的LLM模型
3. 稍后重试（可能是LLM服务繁忙）

### 问题3：积分不足

```
QuantDinger积分不足
```

**解决方案：**
1. 登录QuantDinger管理界面充值积分
2. 或者使用自部署的LLM（如Ollama）免除积分限制

## 后续优化方向

1. **批量分析**：对筛选出的股票批量进行AI分析
2. **定时扫描**：每天自动分析自选股，发送分析报告
3. **回测验证**：用历史数据验证AI分析的准确性
4. **策略集成**：将AI分析结果接入GridTrading或TTrading系统
5. **MCP集成**：通过MCP Server让Claude Code直接调用QuantDinger

## 相关文件

| 文件 | 说明 |
|------|------|
| `backend/app/services/quantdinger_service.py` | 后端服务，封装QuantDinger API调用 |
| `backend/app/api/quantdinger.py` | FastAPI路由，提供REST接口 |
| `frontend/src/services/api/quantdinger.ts` | 前端API服务 |
| `frontend/src/components/AIAnalysisPanel.tsx` | AI分析面板组件 |
| `frontend/src/pages/StockAnalysis.tsx` | 股票分析页面（已集成AI Tab） |
