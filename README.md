# Investment Analyzer - 投资分析工具

私人投资分析工具，用于基本面分析和DCF估值计算。

## 功能

- 基本面指标查询：PE、PB、ROE、营收增长率、净利润增长率
- DCF估值模型：自由现金流折现计算买点
- 巴菲特选股逻辑分析

## 技术栈

- 前端：React + TypeScript + ECharts + Ant Design
- 后端：Python FastAPI
- 数据源：NeoData金融搜索服务

## 快速开始

### 后端

```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173

## 多设备同步

1. GitHub私有仓库存储代码
2. 家里和公司都clone同一仓库
3. 环境变量放 `.env.local`（不提交）
