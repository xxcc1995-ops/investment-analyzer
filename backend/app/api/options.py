"""期权轮动 API"""

from fastapi import APIRouter, Query
from app.services.options_service import (
    analyze_options_rotation, bsm_price, get_philosophy, get_rolling_recommendation
)

router = APIRouter()


@router.get("/philosophy")
def philosophy():
    return get_philosophy()


@router.get("/analysis")
def analysis(
    stock_code: str = Query('00700', description="港股代码, 如00700"),
    option_type: str = Query('put', description="期权类型: put/call"),
    iv_override: float = Query(None, description="自定义IV (小数, 如0.35)"),
    risk_free_rate: float = Query(0.04, description="无风险利率"),
):
    return analyze_options_rotation(
        stock_code=stock_code,
        option_type=option_type,
        risk_free_rate=risk_free_rate,
        iv_override=iv_override,
    )


@router.get("/greeks")
def greeks(
    spot: float = Query(..., description="标的价格"),
    strike: float = Query(..., description="行权价"),
    days: int = Query(30, description="到期天数"),
    sigma: float = Query(0.3, description="波动率"),
    option_type: str = Query('put', description="期权类型"),
    risk_free_rate: float = Query(0.04, description="无风险利率"),
):
    T = days / 365
    result = bsm_price(spot, strike, T, risk_free_rate, sigma, option_type)
    return {
        'spot': spot, 'strike': strike, 'days': days,
        'sigma': sigma, 'option_type': option_type,
        'greeks': result,
    }


@router.get("/rolling")
def rolling(
    spot: float = Query(..., description="当前标的价格"),
    strike: float = Query(..., description="当前持仓行权价"),
    premium: float = Query(..., description="开仓权利金"),
    dte_left: int = Query(..., description="剩余到期天数"),
    entry_dte: int = Query(30, description="开仓时到期天数"),
    option_type: str = Query('put', description="期权类型"),
    hv: float = Query(0.3, description="历史波动率"),
):
    return get_rolling_recommendation(spot, strike, premium, dte_left,
                                      entry_dte, option_type, hv)
