from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class DCFRequest(BaseModel):
    stock_code: str
    growth_rate: float | None = None
    safety_margin: float = 0.30


@router.post("/dcf")
async def calculate_dcf(request: DCFRequest):
    """DCF估值 — 暂不可用"""
    raise HTTPException(
        status_code=501,
        detail="DCF估值功能暂不可用：缺少可靠的自由现金流数据源。需要接入专业财务数据API（如Wind、同花顺iFinD）才能获取准确的FCF数据。"
    )
