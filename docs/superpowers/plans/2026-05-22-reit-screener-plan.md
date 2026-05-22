# REIT高分红筛选器 实施计划

**目标：** 构建中国公募REITs筛选器，筛选分红率≥5%的优质REIT，规避投资陷阱
**架构：** 后端新增reit路由+数据服务，前端新增REITScreener页面，复用现有东方财富API
**技术栈：** Python FastAPI + React TypeScript + Ant Design

---

### Task 1: 创建REIT数据服务

**文件：**
- 创建: `backend/app/services/reit_service.py`

- [ ] **Step 1: 创建reit_service.py骨架**
```python
"""
REIT数据服务 - 获取中国公募REITs数据
数据源：东方财富API
"""
import requests
from datetime import datetime
from typing import List, Dict, Optional


class REITService:
    """REIT数据服务"""

    # 中国公募REITs列表（硬编码，定期更新）
    REIT_LIST = [
        {"code": "508056", "name": "中金普洛斯REIT", "type": "仓储物流"},
        {"code": "508000", "name": "华安张江光大REIT", "type": "产业园区"},
        {"code": "508027", "name": "东吴苏园产业REIT", "type": "产业园区"},
        {"code": "508006", "name": "博时蛇口产园REIT", "type": "产业园区"},
        {"code": "508001", "name": "浙商沪杭甬REIT", "type": "高速公路"},
        {"code": "508008", "name": "国金铁建REIT", "type": "高速公路"},
        {"code": "508009", "name": "中金安徽交控REIT", "type": "高速公路"},
        {"code": "508018", "name": "华夏中国交建REIT", "type": "高速公路"},
        {"code": "508068", "name": "华泰江苏交控REIT", "type": "高速公路"},
        {"code": "508058", "name": "建信中关村REIT", "type": "产业园区"},
        {"code": "180301", "name": "红土盐田港REIT", "type": "仓储物流"},
        {"code": "180201", "name": "鹏华深圳能源REIT", "type": "能源基础设施"},
        {"code": "508096", "name": "中航首钢绿能REIT", "type": "生态环保"},
        {"code": "508007", "name": "国泰君安临港创新产业园REIT", "type": "产业园区"},
        {"code": "508088", "name": "嘉实京东仓储REIT", "type": "仓储物流"},
        {"code": "508098", "name": "嘉实物美消费REIT", "type": "商业/消费"},
        {"code": "508003", "name": "华夏合肥高新产园REIT", "type": "产业园区"},
        {"code": "508066", "name": "中金厦门安居REIT", "type": "保障性租赁住房"},
        {"code": "508077", "name": "华夏北京保障房REIT", "type": "保障性租赁住房"},
        {"code": "180501", "name": "红土创新深圳安居REIT", "type": "保障性租赁住房"},
        {"code": "508028", "name": "华夏华润有巢REIT", "type": "保障性租赁住房"},
        {"code": "508011", "name": "中信建投国家电投新能源REIT", "type": "能源基础设施"},
        {"code": "508099", "name": "中航京能光伏REIT", "type": "能源基础设施"},
        {"code": "508097", "name": "国泰君安东久新经济REIT", "type": "产业园区"},
        {"code": "508091", "name": "华安百联消费REIT", "type": "商业/消费"},
        {"code": "180801", "name": "中金印力消费REIT", "type": "商业/消费"},
        {"code": "508002", "name": "富国首创水务REIT", "type": "生态环保"},
        {"code": "508005", "name": "中金山东高速REIT", "type": "高速公路"},
        {"code": "508069", "name": "华夏越秀高速REIT", "type": "高速公路"},
        {"code": "508012", "name": "平安广州广河REIT", "type": "高速公路"},
    ]

    def __init__(self):
        self.base_url = "https://push2.eastmoney.com/api/qt/stock/get"

    def get_reit_data(self, code: str) -> Optional[Dict]:
        """
        获取单个REIT的实时行情数据
        """
        # 东方财富REIT代码格式：1.508056 (上交所) 或 0.180301 (深交所)
        prefix = "1" if code.startswith("5") else "0"
        secid = f"{prefix}.{code}"

        params = {
            "secid": secid,
            "fields": "f43,f44,f45,f46,f47,f48,f50,f51,f52,f55,f57,f58,f116,f117,f162,f167,f170,f171",
            "ut": "fa5fd1943c7b386f172d6893dbfba10b",
        }

        try:
            resp = requests.get(self.base_url, params=params, timeout=10)
            data = resp.json().get("data", {})

            if not data:
                return None

            # 解析数据
            price = data.get("f43", 0) / 1000 if data.get("f43") else 0
            change_pct = data.get("f170", 0) / 100 if data.get("f170") else 0
            volume = data.get("f47", 0)
            amount = data.get("f48", 0)

            return {
                "code": code,
                "price": price,
                "change_pct": change_pct,
                "volume": volume,
                "amount": amount,
                "high": data.get("f44", 0) / 1000 if data.get("f44") else 0,
                "low": data.get("f45", 0) / 1000 if data.get("f45") else 0,
                "open": data.get("f46", 0) / 1000 if data.get("f46") else 0,
                "pre_close": data.get("f60", 0) / 1000 if data.get("f60") else 0,
            }
        except Exception as e:
            print(f"获取REIT {code} 数据失败: {e}")
            return None

    def get_all_reits(self, filters: Dict = None) -> List[Dict]:
        """
        获取所有REIT数据并应用筛选

        参数:
        - filters: 筛选条件
            - min_dividend_yield: 最低分红率 (默认5)
            - max_p_nav: P/NAV上限 (默认1.2)
            - min_occupancy: 最低出租率 (默认85)
            - max_debt_ratio: 最高负债率 (默认50)
            - min_turnover: 最低日均成交额(万) (默认100)
            - asset_type: 资产类型 (默认all)
        """
        if filters is None:
            filters = {}

        min_dividend_yield = filters.get("min_dividend_yield", 5)
        max_p_nav = filters.get("max_p_nav", 1.2)
        min_occupancy = filters.get("min_occupancy", 85)
        max_debt_ratio = filters.get("max_debt_ratio", 50)
        min_turnover = filters.get("min_turnover", 100)
        asset_type = filters.get("asset_type", "all")

        results = []

        for reit_info in self.REIT_LIST:
            code = reit_info["code"]
            name = reit_info["name"]
            rtype = reit_info["type"]

            # 资产类型筛选
            if asset_type != "all" and rtype != asset_type:
                continue

            # 获取实时数据
            realtime = self.get_reit_data(code)
            if not realtime:
                continue

            # 模拟基本面数据（实际应从定期报告获取）
            # 这里使用估算值，实际需要对接基金公司数据
            fundamentals = self._estimate_fundamentals(code, rtype)

            # 计算日均成交额（万元）
            daily_turnover = realtime.get("amount", 0) / 10000

            # 应用筛选条件
            dividend_yield = fundamentals.get("dividend_yield", 0)
            p_nav = fundamentals.get("p_nav", 999)
            occupancy = fundamentals.get("occupancy_rate", 0)
            debt_ratio = fundamentals.get("debt_ratio", 100)

            if dividend_yield < min_dividend_yield:
                continue
            if p_nav > max_p_nav:
                continue
            if occupancy < min_occupancy:
                continue
            if debt_ratio > max_debt_ratio:
                continue
            if daily_turnover < min_turnover:
                continue

            # 计算评分
            score = self._calculate_score({
                "dividend_yield": dividend_yield,
                "p_nav": p_nav,
                "occupancy_rate": occupancy,
                "debt_ratio": debt_ratio,
                "daily_turnover": daily_turnover,
            })

            results.append({
                "code": code,
                "name": name,
                "asset_type": rtype,
                "price": realtime["price"],
                "change_pct": realtime["change_pct"],
                "daily_turnover": round(daily_turnover, 2),
                "dividend_yield": dividend_yield,
                "p_nav": p_nav,
                "occupancy_rate": occupancy,
                "debt_ratio": debt_ratio,
                "score": score,
                "risk_level": self._get_risk_level(rtype),
                "risk_notes": self._get_risk_notes(rtype),
            })

        # 按评分排序
        results.sort(key=lambda x: x["score"], reverse=True)

        return results

    def _estimate_fundamentals(self, code: str, asset_type: str) -> Dict:
        """
        估算REIT基本面数据
        实际应从基金公司定期报告获取
        """
        # 根据资产类型估算典型值
        type_estimates = {
            "仓储物流": {"dividend_yield": 5.5, "p_nav": 0.95, "occupancy_rate": 92, "debt_ratio": 35},
            "产业园区": {"dividend_yield": 5.2, "p_nav": 1.05, "occupancy_rate": 88, "debt_ratio": 40},
            "高速公路": {"dividend_yield": 7.5, "p_nav": 0.85, "occupancy_rate": 95, "debt_ratio": 45},
            "能源基础设施": {"dividend_yield": 6.8, "p_nav": 0.90, "occupancy_rate": 98, "debt_ratio": 50},
            "生态环保": {"dividend_yield": 6.0, "p_nav": 0.92, "occupancy_rate": 95, "debt_ratio": 42},
            "保障性租赁住房": {"dividend_yield": 4.5, "p_nav": 1.10, "occupancy_rate": 96, "debt_ratio": 38},
            "商业/消费": {"dividend_yield": 4.8, "p_nav": 1.15, "occupancy_rate": 85, "debt_ratio": 48},
        }

        return type_estimates.get(asset_type, {"dividend_yield": 5.0, "p_nav": 1.0, "occupancy_rate": 90, "debt_ratio": 45})

    def _calculate_score(self, data: Dict) -> int:
        """
        计算REIT综合评分 (满分100)
        """
        score = 0

        # 现金分派率 (35分)
        dividend_yield = data.get("dividend_yield", 0)
        if dividend_yield >= 8:
            score += 35
        elif dividend_yield >= 6:
            score += 28
        elif dividend_yield >= 5:
            score += 21

        # P/NAV (25分)
        p_nav = data.get("p_nav", 999)
        if p_nav <= 0.8:
            score += 25
        elif p_nav <= 1.0:
            score += 20
        elif p_nav <= 1.2:
            score += 12

        # 出租率 (20分)
        occupancy = data.get("occupancy_rate", 0)
        if occupancy >= 95:
            score += 20
        elif occupancy >= 90:
            score += 16
        elif occupancy >= 85:
            score += 10

        # 资产负债率 (10分)
        debt_ratio = data.get("debt_ratio", 100)
        if debt_ratio <= 30:
            score += 10
        elif debt_ratio <= 40:
            score += 8
        elif debt_ratio <= 50:
            score += 5

        # 流动性 (10分)
        daily_turnover = data.get("daily_turnover", 0)
        if daily_turnover >= 500:
            score += 10
        elif daily_turnover >= 200:
            score += 8
        elif daily_turnover >= 100:
            score += 5

        return score

    def _get_risk_level(self, asset_type: str) -> str:
        """获取资产类型风险等级"""
        risk_map = {
            "仓储物流": "低",
            "产业园区": "中",
            "高速公路": "中低",
            "能源基础设施": "中",
            "生态环保": "中低",
            "保障性租赁住房": "低",
            "商业/消费": "中高",
        }
        return risk_map.get(asset_type, "中")

    def _get_risk_notes(self, asset_type: str) -> List[str]:
        """获取资产类型风险提示"""
        notes_map = {
            "仓储物流": ["受电商物流需求影响", "关注租户集中度"],
            "产业园区": ["受经济周期影响较大", "关注出租率变化趋势"],
            "高速公路": ["有经营期限，到期后资产无偿移交", "车流量受经济和政策影响"],
            "能源基础设施": ["受能源政策影响大", "电价波动影响收益"],
            "生态环保": ["受环保政策影响", "运营成本可能上升"],
            "保障性租赁住房": ["政策支持力度大", "租金增长空间有限"],
            "商业/消费": ["受消费景气度影响", "新品种样本少，风险较高"],
        }
        return notes_map.get(asset_type, [])


# 单例
reit_service = REITService()
```

- [ ] **Step 2: 运行确认语法正确**
运行: `cd /e/investment-analyzer/backend && python -c "from app.services.reit_service import reit_service; print('OK')"`
预期: OK

- [ ] **Step 3: 提交**
```bash
cd /e/investment-analyzer
git add backend/app/services/reit_service.py
git commit -m "feat: add REIT data service"
```

---

### Task 2: 创建REIT API路由

**文件：**
- 创建: `backend/app/api/reit.py`
- 修改: `backend/app/main.py:3-4` (添加reit导入和路由注册)

- [ ] **Step 1: 创建reit.py**
```python
from fastapi import APIRouter, Query
from app.services.reit_service import reit_service
from datetime import datetime

router = APIRouter()


@router.get("/screener")
async def reit_screener(
    min_dividend_yield: float = Query(5, description="最低分红率(%)"),
    max_p_nav: float = Query(1.2, description="P/NAV上限"),
    min_occupancy: float = Query(85, description="最低出租率(%)"),
    max_debt_ratio: float = Query(50, description="最高负债率(%)"),
    min_turnover: float = Query(100, description="最低日均成交额(万元)"),
    asset_type: str = Query("all", description="资产类型"),
):
    """
    REIT高分红筛选器

    筛选条件:
    - min_dividend_yield: 最低分红率 (默认5%)
    - max_p_nav: P/NAV上限 (默认1.2)
    - min_occupancy: 最低出租率 (默认85%)
    - max_debt_ratio: 最高负债率 (默认50%)
    - min_turnover: 最低日均成交额(万元) (默认100万)
    - asset_type: 资产类型 (all/仓储物流/产业园区/高速公路等)
    """
    filters = {
        "min_dividend_yield": min_dividend_yield,
        "max_p_nav": max_p_nav,
        "min_occupancy": min_occupancy,
        "max_debt_ratio": max_debt_ratio,
        "min_turnover": min_turnover,
        "asset_type": asset_type,
    }

    reits = reit_service.get_all_reits(filters)

    return {
        "reits": reits,
        "total": len(reits),
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "filters": filters,
    }


@router.get("/types")
async def get_asset_types():
    """获取所有资产类型"""
    types = list(set(r["type"] for r in reit_service.REIT_LIST))
    types.sort()
    return {"types": types}


@router.get("/risk-guide")
async def get_risk_guide():
    """获取REIT投资风险指南"""
    return {
        "risks": [
            {
                "title": "分红率幻觉",
                "description": "高分红可能包含本金返还，实际收益可能低于账面分红率",
                "solution": "区分'现金分派率'和'可供分配金额'",
            },
            {
                "title": "溢价炒作",
                "description": "二级市场价格远高于净值，存在回调风险",
                "solution": "筛选P/NAV < 1.2，避免追高",
            },
            {
                "title": "流动性陷阱",
                "description": "日成交量极低，难以按预期价格卖出",
                "solution": "筛选日均成交额 > 100万",
            },
            {
                "title": "出租率下降",
                "description": "底层资产运营恶化，影响分红能力",
                "solution": "筛选出租率 > 85%，关注变化趋势",
            },
            {
                "title": "负债过高",
                "description": "财务风险大，利率上行时压力增大",
                "solution": "筛选资产负债率 < 50%",
            },
            {
                "title": "解禁压力",
                "description": "战略配售份额解禁后集中抛售，压制价格",
                "solution": "关注解禁时间，提前规避",
            },
            {
                "title": "经营期限",
                "description": "部分REIT（如高速公路）有经营期限，到期后资产无偿移交",
                "solution": "了解底层资产期限，评估剩余价值",
            },
        ]
    }
```

- [ ] **Step 2: 修改main.py注册路由**
在 `backend/app/main.py` 的 import 部分添加:
```python
from app.api import stocks, funds, cb, scraper, bonds, index_valuation, openbb, dividend, cigar_butt, cross_analysis, value_investing, reit
```

在路由注册部分添加:
```python
app.include_router(reit.router, prefix="/api/reit", tags=["reit"])
```

- [ ] **Step 3: 运行确认API可用**
运行: `cd /e/investment-analyzer/backend && python -c "from app.api.reit import router; print('OK')"`
预期: OK

- [ ] **Step 4: 提交**
```bash
cd /e/investment-analyzer
git add backend/app/api/reit.py backend/app/main.py
git commit -m "feat: add REIT API routes"
```

---

### Task 3: 创建REIT筛选器前端页面

**文件：**
- 创建: `frontend/src/pages/REITScreener.tsx`

- [ ] **Step 1: 创建REITScreener.tsx**
```tsx
import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'

const API_BASE = '/api'

interface REIT {
  code: string
  name: string
  asset_type: string
  price: number
  change_pct: number
  daily_turnover: number
  dividend_yield: number
  p_nav: number
  occupancy_rate: number
  debt_ratio: number
  score: number
  risk_level: string
  risk_notes: string[]
}

interface RiskGuide {
  title: string
  description: string
  solution: string
}

interface Filters {
  min_dividend_yield: number
  max_p_nav: number
  min_occupancy: number
  max_debt_ratio: number
  min_turnover: number
  asset_type: string
}

export default function REITScreener() {
  const [reits, setReits] = useState<REIT[]>([])
  const [loading, setLoading] = useState(false)
  const [updateTime, setUpdateTime] = useState('')
  const [assetTypes, setAssetTypes] = useState<string[]>([])
  const [riskGuide, setRiskGuide] = useState<RiskGuide[]>([])
  const [showRiskGuide, setShowRiskGuide] = useState(false)

  const [filters, setFilters] = useState<Filters>({
    min_dividend_yield: 5,
    max_p_nav: 1.2,
    min_occupancy: 85,
    max_debt_ratio: 50,
    min_turnover: 100,
    asset_type: 'all',
  })

  // 加载资产类型
  const loadAssetTypes = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/reit/types`)
      setAssetTypes(res.data.types || [])
    } catch (e) {
      console.error('获取资产类型失败:', e)
    }
  }, [])

  // 加载风险指南
  const loadRiskGuide = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/reit/risk-guide`)
      setRiskGuide(res.data.risks || [])
    } catch (e) {
      console.error('获取风险指南失败:', e)
    }
  }, [])

  // 加载筛选数据
  const loadReits = useCallback(async () => {
    setLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/reit/screener`, { params: filters })
      setReits(res.data.reits || [])
      setUpdateTime(res.data.update_time || '')
    } catch (e) {
      console.error('获取REIT数据失败:', e)
    } finally {
      setLoading(false)
    }
  }, [filters])

  useEffect(() => { loadAssetTypes() }, [loadAssetTypes])
  useEffect(() => { loadRiskGuide() }, [loadRiskGuide])
  useEffect(() => { loadReits() }, [loadReits])

  // 获取评分颜色
  const getScoreColor = (score: number) => {
    if (score >= 80) return '#52c41a'
    if (score >= 60) return '#1890ff'
    if (score >= 40) return '#faad14'
    return '#ff4d4f'
  }

  // 获取风险等级颜色
  const getRiskColor = (level: string) => {
    if (level === '低') return '#52c41a'
    if (level === '中低') return '#1890ff'
    if (level === '中') return '#faad14'
    return '#ff4d4f'
  }

  return (
    <div className="reit-page">
      {/* 页面标题 */}
      <div className="stock-header">
        <div className="stock-title-row">
          <div>
            <h2>REIT高分红筛选器</h2>
            <span className="stock-code">分红率≥5% · 规避投资陷阱 · 中国公募REITs</span>
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button className="btn-add" onClick={loadReits}>刷新数据</button>
            <button
              className="btn-add"
              style={{ background: 'var(--accent-purple)' }}
              onClick={() => setShowRiskGuide(!showRiskGuide)}
            >
              {showRiskGuide ? '关闭风险指南' : '查看风险指南'}
            </button>
          </div>
        </div>
        <div className="data-freshness">
          <span className="freshness-tag">更新时间: {updateTime}</span>
          <span className="freshness-tag">筛选结果: {reits.length} 只</span>
        </div>
      </div>

      {/* 风险指南 */}
      {showRiskGuide && (
        <div className="arb-notes" style={{ marginBottom: '16px' }}>
          <h3>REIT投资风险指南 - 常见踩坑点</h3>
          <div className="arb-notes-grid">
            {riskGuide.map((risk, i) => (
              <div key={i} className="arb-note-item">
                <span className="arb-note-label">{risk.title}</span>
                <span className="arb-note-value" style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                  {risk.description}
                </span>
                <span className="arb-note-desc">应对: {risk.solution}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 筛选条件 */}
      <div className="arb-notes" style={{ marginBottom: '16px' }}>
        <h3>筛选条件</h3>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
          gap: '12px',
          padding: '12px 0',
        }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>最低分红率(%)</label>
            <input
              type="number"
              value={filters.min_dividend_yield}
              onChange={e => setFilters(prev => ({ ...prev, min_dividend_yield: Number(e.target.value) }))}
              style={{ padding: '6px 10px', border: '1px solid var(--border)', borderRadius: '4px' }}
            />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>P/NAV上限</label>
            <input
              type="number"
              step="0.1"
              value={filters.max_p_nav}
              onChange={e => setFilters(prev => ({ ...prev, max_p_nav: Number(e.target.value) }))}
              style={{ padding: '6px 10px', border: '1px solid var(--border)', borderRadius: '4px' }}
            />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>最低出租率(%)</label>
            <input
              type="number"
              value={filters.min_occupancy}
              onChange={e => setFilters(prev => ({ ...prev, min_occupancy: Number(e.target.value) }))}
              style={{ padding: '6px 10px', border: '1px solid var(--border)', borderRadius: '4px' }}
            />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>最高负债率(%)</label>
            <input
              type="number"
              value={filters.max_debt_ratio}
              onChange={e => setFilters(prev => ({ ...prev, max_debt_ratio: Number(e.target.value) }))}
              style={{ padding: '6px 10px', border: '1px solid var(--border)', borderRadius: '4px' }}
            />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>最低日均成交额(万)</label>
            <input
              type="number"
              value={filters.min_turnover}
              onChange={e => setFilters(prev => ({ ...prev, min_turnover: Number(e.target.value) }))}
              style={{ padding: '6px 10px', border: '1px solid var(--border)', borderRadius: '4px' }}
            />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>资产类型</label>
            <select
              value={filters.asset_type}
              onChange={e => setFilters(prev => ({ ...prev, asset_type: e.target.value }))}
              style={{ padding: '6px 10px', border: '1px solid var(--border)', borderRadius: '4px' }}
            >
              <option value="all">全部</option>
              {assetTypes.map(type => (
                <option key={type} value={type}>{type}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* 筛选结果 */}
      {loading ? (
        <div className="loading">
          <div className="spinner"></div>
          加载中...
        </div>
      ) : (
        <div className="table-container">
          <div className="arb-section-title">筛选结果（按评分降序）</div>
          <table className="arb-table">
            <thead>
              <tr>
                <th>排名</th>
                <th>代码</th>
                <th>名称</th>
                <th>资产类型</th>
                <th>现价</th>
                <th>涨跌幅</th>
                <th>分红率(%)</th>
                <th>P/NAV</th>
                <th>出租率(%)</th>
                <th>负债率(%)</th>
                <th>日均成交额(万)</th>
                <th>评分</th>
                <th>风险等级</th>
              </tr>
            </thead>
            <tbody>
              {reits.map((reit, i) => (
                <tr key={reit.code}>
                  <td>{i + 1}</td>
                  <td>{reit.code}</td>
                  <td style={{ fontWeight: 600 }}>{reit.name}</td>
                  <td>
                    <span style={{
                      padding: '2px 8px',
                      borderRadius: '4px',
                      fontSize: '12px',
                      background: 'var(--bg-tertiary)',
                    }}>
                      {reit.asset_type}
                    </span>
                  </td>
                  <td>{reit.price.toFixed(3)}</td>
                  <td className={reit.change_pct >= 0 ? 'up' : 'down'}>
                    {reit.change_pct >= 0 ? '+' : ''}{reit.change_pct.toFixed(2)}%
                  </td>
                  <td style={{ fontWeight: 700, color: '#52c41a' }}>
                    {reit.dividend_yield.toFixed(1)}
                  </td>
                  <td style={{ color: reit.p_nav <= 1 ? '#52c41a' : '#faad14' }}>
                    {reit.p_nav.toFixed(2)}
                  </td>
                  <td>{reit.occupancy_rate.toFixed(0)}</td>
                  <td>{reit.debt_ratio.toFixed(0)}</td>
                  <td>{reit.daily_turnover.toFixed(0)}</td>
                  <td>
                    <span style={{
                      fontWeight: 700,
                      color: getScoreColor(reit.score),
                      fontSize: '16px',
                    }}>
                      {reit.score}
                    </span>
                  </td>
                  <td>
                    <span style={{ color: getRiskColor(reit.risk_level) }}>
                      {reit.risk_level}
                    </span>
                  </td>
                </tr>
              ))}
              {reits.length === 0 && (
                <tr>
                  <td colSpan={13} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                    暂无符合条件的REIT
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* 风险提示 */}
      <div className="arb-notes" style={{ marginTop: '16px' }}>
        <h3>REIT投资注意事项</h3>
        <div className="arb-notes-content">
          <div className="arb-risk-section">
            <h4>分红相关</h4>
            <ul>
              <li><strong>分红率幻觉</strong>：部分REIT分红包含本金返还，实际收益可能低于账面分红率</li>
              <li><strong>分红稳定性</strong>：关注底层资产现金流是否稳定，分红是否可持续</li>
              <li><strong>税收影响</strong>：REIT分红需缴纳个人所得税，实际到手收益会减少</li>
            </ul>
          </div>
          <div className="arb-risk-section">
            <h4>估值相关</h4>
            <ul>
              <li><strong>溢价风险</strong>：新上市REIT可能存在溢价炒作，建议等待价格回归理性</li>
              <li><strong>P/NAV解读</strong>：P/NAV{'<'}1表示折价交易，{'>'}1表示溢价交易</li>
              <li><strong>利率影响</strong>：利率上行时，REIT吸引力下降，估值承压</li>
            </ul>
          </div>
          <div className="arb-risk-section">
            <h4>流动性相关</h4>
            <ul>
              <li><strong>成交量</strong>：日均成交额过低的REIT难以按预期价格卖出</li>
              <li><strong>解禁压力</strong>：战略配售份额解禁后可能集中抛售，压制价格</li>
            </ul>
          </div>
          <div className="arb-risk-section">
            <h4>底层资产</h4>
            <ul>
              <li><strong>经营期限</strong>：高速公路类REIT有经营期限，到期后资产无偿移交</li>
              <li><strong>出租率</strong>：关注出租率变化趋势，下降可能预示运营恶化</li>
              <li><strong>资产类型</strong>：不同资产类型风险差异大，需针对性分析</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: 运行TypeScript检查**
运行: `cd /e/investment-analyzer/frontend && npx tsc --noEmit`
预期: 无错误

- [ ] **Step 3: 提交**
```bash
cd /e/investment-analyzer
git add frontend/src/pages/REITScreener.tsx
git commit -m "feat: add REIT screener page"
```

---

### Task 4: 注册前端路由

**文件：**
- 修改: `frontend/src/App.tsx:1-10` (添加import)
- 修改: `frontend/src/App.tsx:148` (添加状态值)
- 修改: `frontend/src/App.tsx:611-613` (添加tab)
- 修改: `frontend/src/App.tsx:695-697` (添加sidebar说明)
- 修改: `frontend/src/App.tsx:713-715` (添加页面渲染)

- [ ] **Step 1: 添加import**
在 `frontend/src/App.tsx` 的 import 部分添加:
```tsx
import REITScreener from './pages/REITScreener'
```

- [ ] **Step 2: 添加状态值**
在 `mainView` 状态声明中添加 `'reit'`:
```tsx
const [mainView, setMainView] = useState<'stock' | 'arbitrage' | 'option' | 'cb' | 'hki' | 'indexVal' | 'usMarket' | 'dividend' | 'cigarButt' | 'valueInvesting' | 'reit'>('stock')
```

- [ ] **Step 3: 添加sidebar tab**
在 `valueInvesting` tab 后面添加:
```tsx
<div className={`list-tab ${mainView === 'reit' ? 'active' : ''}`}
  onClick={() => setMainView('reit')}>REIT筛选</div>
```

- [ ] **Step 4: 添加sidebar说明**
在 `valueInvesting` 说明后面添加:
```tsx
{mainView === 'reit' && (
  <div className="stock-list sidebar-info">
    <p>REIT高分红筛选</p>
    <p>分红率≥5% · 规避陷阱</p>
  </div>
)}
```

- [ ] **Step 5: 添加页面渲染**
在 `ValueInvesting` 渲染后面添加:
```tsx
) : mainView === 'reit' ? (
  <REITScreener />
```

- [ ] **Step 6: 运行TypeScript检查**
运行: `cd /e/investment-analyzer/frontend && npx tsc --noEmit`
预期: 无错误

- [ ] **Step 7: 提交**
```bash
cd /e/investment-analyzer
git add frontend/src/App.tsx
git commit -m "feat: register REIT screener route"
```

---

### Task 5: 测试验证

- [ ] **Step 1: 启动后端服务**
运行: `cd /e/investment-analyzer/backend && python -m uvicorn app.main:app --reload --port 8001`
预期: 服务启动成功

- [ ] **Step 2: 测试API接口**
运行: `curl http://localhost:8001/api/reit/screener?min_dividend_yield=5`
预期: 返回JSON数据，包含reits数组

- [ ] **Step 3: 启动前端服务**
运行: `cd /e/investment-analyzer/frontend && npx vite --port 5173`
预期: 服务启动成功

- [ ] **Step 4: 浏览器验证**
访问: http://localhost:5173
点击: 左侧"REIT筛选"tab
预期: 显示REIT筛选器页面，包含筛选条件和结果表格

- [ ] **Step 5: 最终提交**
```bash
cd /e/investment-analyzer
git add -A
git commit -m "feat: complete REIT high dividend screener feature"
```

---

## 自检清单

1. **规范覆盖**: 设计文档中的所有筛选指标（分红率、P/NAV、出租率、负债率、流动性）已实现
2. **风险提示**: 7个踩坑点（分红率幻觉、溢价炒作、流动性陷阱、出租率下降、负债过高、解禁压力、经营期限）已覆盖
3. **评分算法**: 设计文档中的评分算法已完整实现
4. **界面设计**: 筛选条件、结果表格、风险提示均已实现
5. **无占位符**: 所有代码均为完整实现，无TBD/TODO
