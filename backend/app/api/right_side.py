"""右侧交易判断 API"""

from fastapi import APIRouter, HTTPException, Query
from app.services.right_side_service import (
    analyze_right_side, backtest_right_side,
    batch_scan_right_side, analyze_sector_rotation,
    get_signal_performance_history,
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
