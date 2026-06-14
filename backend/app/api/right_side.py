"""右侧交易判断 API"""

from fastapi import APIRouter, HTTPException, Query
from app.services.right_side_service import (
    analyze_right_side, backtest_right_side,
    batch_scan_right_side, analyze_sector_rotation,
    get_signal_performance_history,
    add_to_watchlist, remove_from_watchlist, get_watchlist, scan_watchlist,
)

router = APIRouter()


@router.get("/{stock_code}")
def get_right_side_analysis(stock_code: str):
    """获取右侧交易判断结果（V2: 多时间框架 + ADX + 新指标）"""
    result = analyze_right_side(stock_code)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/{stock_code}/backtest")
def get_right_side_backtest(stock_code: str):
    """获取右侧交易历史回测信号"""
    result = backtest_right_side(stock_code)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/scan/batch")
def scan_batch(
    market: str = Query("all", description="市场: A/HK/all"),
    min_score: float = Query(0, description="最低分数"),
    limit: int = Query(50, description="返回条数"),
):
    """批量扫描全市场右侧信号"""
    return batch_scan_right_side(market=market, min_score=min_score, limit=limit)


@router.get("/sector/rotation")
def sector_rotation():
    """板块轮动分析"""
    return analyze_sector_rotation()


@router.get("/{stock_code}/signal-history")
def signal_history(stock_code: str):
    """获取历史信号及后续表现"""
    return get_signal_performance_history(stock_code)


@router.post("/watchlist/add")
def watchlist_add(
    code: str = Query(..., description="股票代码"),
    name: str = Query("", description="股票名称"),
    market: str = Query("A", description="市场"),
    note: str = Query("", description="备注"),
):
    """添加到自选股"""
    return add_to_watchlist(code=code, name=name, market=market, note=note)


@router.delete("/watchlist/{code}")
def watchlist_remove(code: str):
    """从自选股移除"""
    return remove_from_watchlist(code)


@router.get("/watchlist/list")
def watchlist_list():
    """获取自选股列表"""
    return get_watchlist()


@router.get("/watchlist/scan")
def watchlist_scan():
    """扫描自选股的右侧信号"""
    return scan_watchlist()
