"""国家队监控 API"""

from typing import List, Optional
from fastapi import APIRouter, Query, HTTPException
from app.core.validators import validate_stock_code
from app.services.national_team_service import (
    get_shareholdings, get_etf_fund_flow, get_all_etf_flows, get_volume_alerts,
    get_dragon_tiger_board, get_block_trades, get_etf_share_changes,
    get_shareholder_changes, get_comprehensive_assessment,
    get_northbound_flow, get_margin_trading,
    get_holdings_trend, get_industry_allocation, get_market_context,
)

router = APIRouter()


@router.get("/shareholdings")
def shareholdings(
    end_date: str = Query(None, description="报告期, 如2025-09-30，默认最近季末"),
):
    """获取国家队十大流通股东持仓"""
    return get_shareholdings(end_date)


@router.get("/etf-flows")
def etf_flows():
    """获取所有大盘ETF资金流向（实时）"""
    return get_etf_fund_flow()


@router.get("/etf-flow/{etf_code}")
def etf_flow(etf_code: str):
    """获取单只ETF资金流向"""
    etf_code = validate_stock_code(etf_code)
    result = get_etf_fund_flow()
    etf = result.get('etfs', {}).get(etf_code)
    if not etf:
        raise HTTPException(status_code=404, detail=f'未找到ETF: {etf_code}')
    return {'etf': etf, 'update_time': result.get('update_time')}


@router.get("/volume-alerts")
def volume_alerts(
    threshold: float = Query(2.0, description="量比阈值", ge=1.0, le=5.0),
):
    """蓝筹股量比异动检测"""
    return get_volume_alerts(threshold)


@router.get("/dragon-tiger")
def dragon_tiger(
    days: int = Query(5, description="查询天数", ge=1, le=30),
):
    """龙虎榜机构席位监控 - 追踪机构大额买卖方向"""
    return get_dragon_tiger_board(days)


@router.get("/block-trades")
def block_trades(
    days: int = Query(5, description="查询天数", ge=1, le=30),
):
    """大宗交易机构监控 - 筛选机构专用席位的大宗交易"""
    return get_block_trades(days)


@router.get("/etf-shares")
def etf_shares():
    """ETF份额变动追踪 - 追踪宽基ETF申购/赎回（国家队入场信号）"""
    return get_etf_share_changes()


@router.get("/shareholder-changes")
def shareholder_changes(
    codes: str = Query(None, description="股票代码逗号分隔，如 600519,601318"),
):
    """股东人数变动监控 - 筹码集中度变化"""
    code_list = [c.strip() for c in codes.split(',')] if codes else None
    return get_shareholder_changes(code_list)


@router.get("/assessment")
def assessment():
    """综合研判评分 - 多维信号融合的国家队动向评分"""
    return get_comprehensive_assessment()


@router.get("/northbound")
def northbound():
    """北向资金（沪深港通）监控 - 外资动向是机构最关注的信号"""
    return get_northbound_flow()


@router.get("/margin")
def margin():
    """融资融券监控 - 杠杆资金方向"""
    return get_margin_trading()


@router.get("/holdings-trend")
def holdings_trend():
    """持仓趋势分析 - 多季度持仓变化追踪"""
    return get_holdings_trend()


@router.get("/industry-allocation")
def industry_allocation(
    end_date: str = Query(None, description="报告期, 如2025-09-30，默认最近季末"),
):
    """行业配置分析 - 国家队持仓行业分布"""
    return get_industry_allocation(end_date)


@router.get("/market-context")
def market_context():
    """市场走势背景 - 沪深300趋势与国家队信号结合分析"""
    return get_market_context()
