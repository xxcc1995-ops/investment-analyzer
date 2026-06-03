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
    find_cross_platform_arbitrage,
    calculate_optimal_allocation,
    calculate_opinion_fee,
)

router = APIRouter()


class KellyRequest(BaseModel):
    price: float
    estimated_prob: float
    bankroll: float = 1000
    fraction: float = 0.25


class AllocationRequest(BaseModel):
    yes_price: float
    no_price: float
    budget: float = 100
    yes_fee_rate: float = 0
    no_fee_rate: float = 0


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


# ============================================================
# 跨平台套利功能（Polymarket vs Opinion）
# ============================================================

@router.get("/cross-arbitrage")
def cross_arbitrage(
    min_profit: float = Query(0.5, description="最低套利利润率(%)"),
    budget: float = Query(100, description="总预算(U)"),
    pm_limit: int = Query(100, description="Polymarket市场数量"),
    op_limit: int = Query(100, description="Opinion市场数量"),
):
    """
    跨平台套利扫描（Polymarket vs Opinion）

    检测两个平台相同事件的价格差异，找到套利机会。
    考虑手续费后计算真实利润。
    """
    data = find_cross_platform_arbitrage(
        min_profit=min_profit,
        budget=budget,
        pm_limit=pm_limit,
        op_limit=op_limit,
    )
    return {
        "opportunities": data,
        "total": len(data),
        "budget": budget,
        "note": "套利利润已扣除手续费，为保底净利润"
    }


@router.post("/allocation-calculator")
def allocation_calculator(req: AllocationRequest):
    """
    最优配资计算器

    输入两个平台的价格和费率，计算最优资金分配方案。
    让两边"赢的金额"完全相等，实现无风险套利。
    """
    result = calculate_optimal_allocation(
        yes_price=req.yes_price,
        no_price=req.no_price,
        budget=req.budget,
        yes_fee_rate=req.yes_fee_rate,
        no_fee_rate=req.no_fee_rate,
    )
    return result


@router.get("/opinion-fee-calculator")
def opinion_fee_calculator(
    price: float = Query(..., description="价格 (0-1)"),
    amount: float = Query(..., description="交易金额"),
):
    """
    Opinion 手续费计算器

    手续费规则：
    - 吃单（Taker）收费 0%～2%
    - 价格越接近 50%，手续费越高；接近 0 或 1 越低
    - 最低 0.5U
    """
    fee = calculate_opinion_fee(price, amount)
    fee_rate = fee / amount * 100 if amount > 0 else 0
    return {
        "price": price,
        "amount": amount,
        "fee": fee,
        "fee_rate": round(fee_rate, 2),
        "net_amount": round(amount - fee, 2),
    }


@router.get("/opinion-markets")
def opinion_markets(
    limit: int = Query(100, description="返回数量"),
    tag: str = Query(None, description="标签过滤"),
):
    """
    获取Opinion平台市场列表

    注意：需要配置 OPINION_API_URL 环境变量
    """
    try:
        from app.services.prediction_market.opinion import OpinionSource
        source = OpinionSource()
        markets = source.get_markets(limit=limit, tag=tag)
        return {
            "markets": [m.__dict__ for m in markets],
            "total": len(markets),
            "source": "opinion",
        }
    except Exception as e:
        return {
            "error": str(e),
            "markets": [],
            "total": 0,
            "note": "请确保已配置 OPINION_API_URL 环境变量"
        }
