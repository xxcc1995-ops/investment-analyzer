"""国家队监控 API"""

from fastapi import APIRouter, Query
from app.services.national_team_service import (
    get_shareholdings, get_etf_fund_flow, get_all_etf_flows, get_volume_alerts
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
    result = get_etf_fund_flow()
    etf = result.get('etfs', {}).get(etf_code)
    if not etf:
        return {'error': f'未找到ETF: {etf_code}'}
    return {'etf': etf, 'update_time': result.get('update_time')}


@router.get("/volume-alerts")
def volume_alerts(
    threshold: float = Query(2.0, description="量比阈值", ge=1.0, le=5.0),
):
    """蓝筹股量比异动检测"""
    return get_volume_alerts(threshold)
