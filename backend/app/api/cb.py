"""可转债双低轮动策略API路由"""

from fastapi import APIRouter, HTTPException, Query
from app.services.cb_service import CBService

router = APIRouter()


@router.get("/double-low")
def get_double_low(
    max_double_low: float = Query(130.0, ge=0, description="双低值上限"),
    min_rating: str = Query('A', description="最低信用评级: A/A+/AA-/AA/AA+/AAA"),
    min_year_left: float = Query(1.0, ge=0, description="最低剩余年限(年)"),
    min_turnover: float = Query(100.0, ge=0, description="最低成交额(万元)"),
    top_n: int = Query(20, ge=1, le=100, description="返回前N只"),
    exclude_st: bool = Query(True, description="排除ST"),
    exclude_force_redeem: bool = Query(True, description="排除已公告强赎"),
):
    """获取可转债双低排名"""
    result = CBService.get_double_low_list(
        max_double_low=max_double_low,
        min_rating=min_rating,
        min_year_left=min_year_left,
        min_turnover=min_turnover,
        top_n=top_n,
        exclude_st=exclude_st,
        exclude_force_redeem=exclude_force_redeem,
    )

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return result


@router.get("/refresh")
def refresh_data():
    """强制刷新可转债数据"""
    result = CBService.refresh_data()
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result
