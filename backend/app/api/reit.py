from fastapi import APIRouter, Query
from app.services.reit_service import reit_service
from datetime import datetime

router = APIRouter()


@router.get("/screener")
def reit_screener(
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
def get_asset_types():
    """获取所有资产类型"""
    types = list(set(r["type"] for r in reit_service.REIT_LIST))
    types.sort()
    return {"types": types}


@router.get("/risk-guide")
def get_risk_guide():
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
