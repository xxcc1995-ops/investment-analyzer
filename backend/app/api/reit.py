from fastapi import APIRouter, Query
from app.services.reit_service import reit_service
from datetime import datetime

router = APIRouter()


@router.get("/screener")
def reit_screener(
    min_dividend_yield: float = Query(3, description="最低年化分派率(%)"),
    max_p_nav: float = Query(1.5, description="P/NAV上限"),
    min_occupancy: float = Query(80, description="最低出租率(%)"),
    max_debt_ratio: float = Query(60, description="最高负债率(%)"),
    min_turnover: float = Query(50, description="最低日均成交额(万元)"),
    asset_type: str = Query("all", description="资产类型筛选"),
):
    """
    REIT机构级筛选器

    筛选条件:
    - min_dividend_yield: 最低年化分派率 (默认3%)
    - max_p_nav: P/NAV上限 (默认1.5，>1.5通常为溢价炒作)
    - min_occupancy: 最低出租率 (默认80%)
    - max_debt_ratio: 最高负债率 (默认60%，监管上限约58%)
    - min_turnover: 最低日均成交额(万元) (默认50万)
    - asset_type: 资产类型 (all/仓储物流/产业园区/高速公路等)

    返回数据包含:
    - 基本信息 + 实时行情
    - NAV折溢价分析（P/NAV、溢价率、评估）
    - 分派率分析（年化分派率、累计分红、计算方法）
    - 资产质量（出租率、底层资产描述）
    - 杠杆分析（负债率、杠杆水平、利息负担、杠杆空间）
    - 利率敏感性（敏感度等级、利差分析、利率变动影响）
    - 经营期限（高速公路等有期限资产的剩余年限）
    - 综合评分（100分制，5维度分项评分 + 等级）
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


@router.get("/overview")
def reit_overview(
    asset_type: str = Query("all", description="资产类型筛选"),
):
    """
    REIT市场概览

    返回:
    - 市场整体统计（平均分派率、平均P/NAV、平均出租率）
    - 各资产类型分布和平均分派率
    - 利率环境分析
    """
    filters = {"asset_type": asset_type} if asset_type != "all" else {}
    overview = reit_service.get_market_overview(filters)
    return overview


@router.get("/types")
def get_asset_types():
    """获取所有资产类型及其特性"""
    types = {}
    for reit in reit_service.REIT_LIST:
        t = reit["type"]
        if t not in types:
            profile = reit_service.ASSET_PROFILES.get(t, {})
            types[t] = {
                "name": t,
                "count": 0,
                "risk_level": profile.get("risk_level", "中"),
                "rate_sensitivity": profile.get("rate_sensitivity", "中"),
                "description": profile.get("description", ""),
            }
        types[t]["count"] += 1

    type_list = sorted(types.values(), key=lambda x: x["name"])
    return {"types": type_list}


@router.get("/risk-guide")
def get_risk_guide():
    """获取REIT投资风险指南"""
    return {
        "risks": [
            {
                "title": "分派率幻觉",
                "description": "高分派率可能包含本金返还（return of capital），实际收益低于账面分派率",
                "solution": "区分'现金分派率'和'可供分配金额'，关注累计NAV与单位NAV的差值",
                "severity": "高",
            },
            {
                "title": "NAV溢价炒作",
                "description": "二级市场价格远高于NAV，存在均值回归风险",
                "solution": "筛选P/NAV < 1.2，避免追高；关注NAV更新日期",
                "severity": "高",
            },
            {
                "title": "流动性陷阱",
                "description": "日成交量极低，大额卖出可能严重冲击价格",
                "solution": "筛选日均成交额 > 100万，避免持仓过重",
                "severity": "中高",
            },
            {
                "title": "利率风险",
                "description": "利率上行时，REIT融资成本上升+相对吸引力下降，估值双重承压",
                "solution": "关注利率环境，高杠杆长久期REIT（如高速公路）受冲击最大",
                "severity": "高",
            },
            {
                "title": "经营期限风险",
                "description": "高速公路等REIT有经营期限，到期后资产无偿移交政府",
                "solution": "了解底层资产剩余经营期限，剩余年限<10年的不建议长期持有",
                "severity": "中高",
            },
            {
                "title": "出租率恶化",
                "description": "底层资产运营恶化（租户退租、需求下降），直接影响分红能力",
                "solution": "筛选出租率 > 85%，关注季度变化趋势",
                "severity": "中",
            },
            {
                "title": "杠杆过高",
                "description": "财务风险大，利率上行时利息支出侵蚀利润",
                "solution": "筛选资产负债率 < 50%，关注杠杆空间（距监管上限的距离）",
                "severity": "中",
            },
            {
                "title": "解禁压力",
                "description": "战略配售份额解禁后集中抛售，压制价格",
                "solution": "关注解禁时间表，提前规避或在解禁后寻找低位机会",
                "severity": "中",
            },
        ],
        "scoring_dimensions": [
            {"dimension": "分派率", "weight": "25%", "description": "核心收益指标，年化分派率越高越好"},
            {"dimension": "P/NAV估值", "weight": "20%", "description": "安全边际，折价买入优于溢价买入"},
            {"dimension": "资产质量", "weight": "20%", "description": "出租率 + 资产类型经济周期敏感性"},
            {"dimension": "财务健康", "weight": "20%", "description": "杠杆率 + 利率风险暴露"},
            {"dimension": "流动性", "weight": "15%", "description": "日均成交额，影响退出能力"},
        ],
    }


@router.get("/rate-analysis")
def rate_analysis():
    """
    利率环境分析

    返回当前利率环境下各类REIT的敏感性分析
    """
    overview = reit_service.get_market_overview()
    rate_env = overview.get("rate_environment", {})

    # 各资产类型的利率敏感性
    type_sensitivity = {}
    for asset_type, profile in reit_service.ASSET_PROFILES.items():
        type_sensitivity[asset_type] = {
            "rate_sensitivity": profile.get("rate_sensitivity", "中"),
            "description": profile.get("description", ""),
            "impact_explanation": {
                "低": "短久期或低杠杆，利率变动对分红和估值影响有限",
                "中": "有一定利率暴露，但可通过租金调整或低杠杆部分对冲",
                "中高": "长久期或高杠杆，利率上行时分红和估值承压明显",
                "高": "长久期+高杠杆，利率上行冲击最大，需特别警惕",
            }.get(profile.get("rate_sensitivity", "中"), ""),
        }

    return {
        "current_environment": rate_env,
        "type_sensitivity": type_sensitivity,
        "investment_implications": {
            "rate_cut_scenario": "降息周期：利好所有REIT，尤其高杠杆长久期品种（高速公路、能源）",
            "rate_hike_scenario": "加息周期：利空所有REIT，优先选择低杠杆短久期品种（仓储物流、保租房）",
            "rate_stable_scenario": "利率平稳：关注分派率和资产质量，优选高分派+低溢价品种",
        },
    }
