"""基金套利API路由"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from app.services.fund_service import FundService

router = APIRouter()


class LoginRequest(BaseModel):
    user_name: str
    password: str


@router.post("/login")
async def login(req: LoginRequest):
    """登录集思录"""
    result = FundService.login(req.user_name, req.password)
    if not result['success']:
        raise HTTPException(status_code=400, detail=result['error'])
    return result


@router.get("/login_status")
async def login_status():
    """获取登录状态"""
    return FundService.get_login_status()


@router.get("/arbitrage")
async def get_arbitrage(
    min_threshold: float = Query(0.0, ge=0, description="最低折溢价率阈值(%)"),
    direction: str = Query("all", description="筛选方向: all/溢价/折价"),
    min_turnover: float = Query(300.0, ge=0, description="最低成交额(万元)"),
    open_subscribe_only: bool = Query(True, description="仅显示开放申购"),
):
    """获取当前套利机会"""
    if direction not in ("all", "溢价", "折价"):
        raise HTTPException(status_code=400, detail="direction 必须是 all/溢价/折价")

    result = FundService.get_arbitrage_opportunities(
        min_threshold=min_threshold,
        direction=direction,
        min_turnover=min_turnover,
        open_subscribe_only=open_subscribe_only,
    )

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return result


@router.get("/refresh")
async def refresh_data():
    """强制刷新数据"""
    result = FundService.refresh_data()
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result
