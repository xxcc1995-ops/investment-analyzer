"""金渐成（机哥）投资体系筛选 - 第一兼唯一选股法"""

from fastapi import APIRouter, Query
from app.services.jc_service import screen_stocks, get_buy_signals, get_philosophy

router = APIRouter()


@router.get("/philosophy")
def philosophy():
    """获取金渐成完整投资哲学体系"""
    return get_philosophy()


@router.get("/screener")
def screener(
    market: str = Query('all', description="市场: A/HK/US/all"),
    min_score: int = Query(0, description="最低分数"),
    max_pe: float = Query(None, description="最大PE"),
    top_n: int = Query(50, description="返回前N只"),
):
    """金渐成体系股票筛选"""
    return screen_stocks(
        market=market,
        min_score=min_score,
        max_pe=max_pe,
        top_n=top_n,
    )


@router.get("/buy-signals")
def buy_signals(
    market: str = Query('all', description="市场: A/HK/US/all"),
):
    """买入信号 - 基于下跌20%开始捞的逻辑"""
    return get_buy_signals(market=market)
