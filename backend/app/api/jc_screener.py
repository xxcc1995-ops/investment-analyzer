"""金渐成（机哥）投资体系筛选 - 第一兼唯一选股法

新增筛选维度: max_pb, min_roe, min_dividend
新增排序控制: sort_by, sort_order
"""

import logging
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from app.services.jc_service import screen_stocks, get_buy_signals, get_philosophy

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/philosophy")
def philosophy():
    """获取金渐成完整投资哲学体系"""
    try:
        return get_philosophy()
    except Exception as e:
        logger.error(f"获取投资体系失败: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/screener")
def screener(
    market: str = Query('all', description="市场: A/HK/US/all"),
    min_score: int = Query(0, ge=0, le=100, description="最低分数"),
    max_pe: float = Query(None, description="最大PE"),
    max_pb: float = Query(None, description="最大PB"),
    min_roe: float = Query(None, description="最低ROE(%)"),
    min_dividend: float = Query(None, description="最低股息率(%)"),
    top_n: int = Query(50, ge=1, le=200, description="返回前N只"),
    sort_by: str = Query('jc_score', description="排序字段: jc_score/pe/roe/dividend_yield/price/market_cap"),
    sort_order: str = Query('desc', description="排序方向: asc/desc"),
):
    """金渐成体系股票筛选"""
    try:
        return screen_stocks(
            market=market,
            min_score=min_score,
            max_pe=max_pe,
            max_pb=max_pb,
            min_roe=min_roe,
            min_dividend=min_dividend,
            top_n=top_n,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    except Exception as e:
        logger.error(f"筛选失败: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/buy-signals")
def buy_signals(
    market: str = Query('all', description="市场: A/HK/US/all"),
):
    """买入信号 - 基于下跌20%开始捞的逻辑"""
    try:
        return get_buy_signals(market=market)
    except Exception as e:
        logger.error(f"获取买入信号失败: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
