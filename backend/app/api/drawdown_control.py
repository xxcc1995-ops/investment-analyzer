"""回撤控制分析 API"""

from fastapi import APIRouter, HTTPException, Query
from app.services.drawdown_control_service import analyze_drawdown

router = APIRouter()


@router.get("/{stock_code}")
async def get_drawdown_analysis(
    stock_code: str,
    days: int = Query(default=500, ge=60, le=2000, description="分析天数"),
):
    """回撤控制分析

    参考顶级机构（桥水、Citadel、文艺复兴科技等）风控方法论，
    提供8维度回撤分析、阶梯预警、仓位管理建议。
    """
    result = analyze_drawdown(stock_code, days)
    if 'error' in result:
        raise HTTPException(status_code=400, detail=result['error'])
    return result
