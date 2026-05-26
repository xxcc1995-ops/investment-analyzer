"""网格交易 API"""

from fastapi import APIRouter, Query
from app.services.grid_service import (
    analyze_grid_trading, get_philosophy, generate_grid_levels, get_grid_status
)

router = APIRouter()


@router.get("/philosophy")
def philosophy():
    return get_philosophy()


@router.get("/analysis")
def analysis(
    stock_code: str = Query('00700', description="港股代码, 如00700"),
    grid_type: str = Query('equal_distance', description="网格类型: equal_distance/equal_ratio"),
    num_grids_up: int = Query(10, description="上行网格数"),
    num_grids_down: int = Query(10, description="下行网格数"),
    grid_width_pct: float = Query(None, description="网格宽度百分比(如2表示2%)"),
    capital: float = Query(1000000, description="总资金(HKD)"),
    hist_days: int = Query(252, description="回测天数"),
    sizing: str = Query('equal', description="仓位方法: equal/pyramid"),
):
    return analyze_grid_trading(
        stock_code=stock_code,
        grid_type=grid_type,
        num_grids_up=num_grids_up,
        num_grids_down=num_grids_down,
        grid_width_pct=grid_width_pct,
        total_capital=capital,
        hist_days=hist_days,
        sizing_method=sizing,
    )


@router.get("/levels")
def levels(
    current_price: float = Query(..., description="当前价格"),
    grid_type: str = Query('equal_distance', description="网格类型"),
    num_grids: int = Query(10, description="单侧网格数"),
    grid_width_pct: float = Query(None, description="网格宽度百分比"),
):
    grid_width = current_price * grid_width_pct / 100 if grid_width_pct is not None else None
    return generate_grid_levels(current_price, grid_type, num_grids, num_grids, grid_width)


@router.get("/status")
def status(
    current_price: float = Query(..., description="当前价格"),
    grid_type: str = Query('equal_distance', description="网格类型"),
    num_grids: int = Query(10, description="单侧网格数"),
    grid_width_pct: float = Query(2.0, description="网格宽度百分比"),
):
    grid_width = current_price * grid_width_pct / 100
    levels = generate_grid_levels(current_price, grid_type, num_grids, num_grids, grid_width)
    return get_grid_status(current_price, levels)
