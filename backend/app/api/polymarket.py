"""Polymarket 智能分析 API"""

from fastapi import APIRouter, Query
from pydantic import BaseModel
from app.services.polymarket_service import (
    get_active_markets,
    get_market_detail,
    get_price_history,
    get_order_book,
    find_arbitrage_opportunities,
    find_value_markets,
    find_trending_markets,
    calculate_kelly,
    analyze_market,
)

router = APIRouter()


class KellyRequest(BaseModel):
    price: float
    estimated_prob: float
    bankroll: float = 1000
    fraction: float = 0.25


@router.get("/markets")
def markets(
    limit: int = Query(100, description="返回数量"),
    offset: int = Query(0, description="偏移量"),
    order: str = Query('volume', description="排序: volume/liquidity/startDate"),
    ascending: bool = Query(False, description="升序"),
    tag: str = Query(None, description="标签过滤"),
):
    """获取活跃市场列表"""
    data = get_active_markets(limit=limit, offset=offset, order=order,
                              ascending=ascending, tag=tag)
    return {"markets": data, "total": len(data)}


@router.get("/markets/{market_id}")
def market_detail(market_id: str):
    """获取单个市场详情+综合分析"""
    return analyze_market(market_id)


@router.get("/arbitrage")
def arbitrage(
    min_profit: float = Query(0.5, description="最低套利利润百分比"),
):
    """扫描套利机会 - Yes+No<1.00时买入双方锁定利润"""
    data = find_arbitrage_opportunities(min_profit=min_profit)
    return {"opportunities": data, "total": len(data)}


@router.get("/trending")
def trending():
    """趋势追踪 - 价格快速变动的市场"""
    data = find_trending_markets()
    return {"markets": data, "total": len(data)}


@router.get("/value")
def value():
    """价值发现 - 极端定价市场"""
    return find_value_markets()


@router.get("/price-history/{market_id}")
def price_history(
    market_id: str,
    interval: str = Query('1d', description="时间间隔"),
    fidelity: int = Query(100, description="数据点数量"),
):
    """获取价格历史"""
    data = get_price_history(market_id, interval=interval, fidelity=fidelity)
    return {"history": data, "total": len(data)}


@router.get("/order-book/{token_id}")
def order_book(token_id: str):
    """获取订单簿"""
    data = get_order_book(token_id)
    if not data:
        return {"error": "无法获取订单簿"}
    return data


@router.post("/kelly")
def kelly(req: KellyRequest):
    """Kelly仓位计算器"""
    return calculate_kelly(
        price=req.price,
        estimated_prob=req.estimated_prob,
        bankroll=req.bankroll,
        fraction=req.fraction,
    )
