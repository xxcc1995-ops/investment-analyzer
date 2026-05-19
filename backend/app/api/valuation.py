from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.dcf import DCFService
from app.services.neodata import NeoDataService
from app.models.stock import DCFValuation

router = APIRouter()
dcf_service = DCFService()
neodata = NeoDataService()

class DCFRequest(BaseModel):
    stock_code: str
    growth_rate: float | None = None  # 可选，不提供则自动估算
    safety_margin: float = 0.30

@router.post("/dcf", response_model=DCFValuation)
async def calculate_dcf(request: DCFRequest):
    """计算DCF估值"""
    try:
        # 1. 获取当前FCF和股价
        # 这里需要从NeoData获取实际数据
        # 示例数据，实际需要解析NeoData返回
        current_fcf = 100  # 示例：100亿
        current_price = 1500  # 示例：1500元
        shares = 12.56  # 示例：12.56亿股

        # 2. 确定增长率
        growth_rate = request.growth_rate
        if growth_rate is None:
            # 自动估算（需要历史数据）
            growth_rate = 0.08  # 示例：8%

        # 3. 计算DCF
        result = dcf_service.calculate_intrinsic_value(
            current_fcf=current_fcf,
            growth_rate=growth_rate,
            shares=shares
        )

        # 4. 计算上行空间
        upside = (result["buy_price"] - current_price) / current_price * 100

        return DCFValuation(
            code=request.stock_code,
            name="",  # 从NeoData获取
            current_price=current_price,
            intrinsic_value=result["intrinsic_value"],
            buy_price=result["buy_price"],
            safety_margin=request.safety_margin,
            upside=round(upside, 2),
            fcf_projections=result["fcf_projections"],
            terminal_value=result["terminal_value"],
            discount_rate=result["discount_rate"],
            growth_rate=growth_rate,
            terminal_growth_rate=result["terminal_growth_rate"]
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
