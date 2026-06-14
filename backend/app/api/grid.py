"""
网格交易 API 端点

提供以下接口：
- GET /philosophy   → 获取网格交易教学内容
- GET /analysis     → 完整网格分析（含回测、风险指标、图表数据）
- GET /levels       → 生成网格价格层级
- GET /status       → 当前网格状态
- GET /optimize     → 参数优化（自动找最优参数组合）
"""

from fastapi import APIRouter, Query
from app.services.grid_service import (
    analyze_grid_trading, get_philosophy, generate_grid_levels,
    get_grid_status, optimize_parameters
)

router = APIRouter()


@router.get("/philosophy")
def philosophy():
    """获取网格交易的教学理念和策略说明"""
    return get_philosophy()


@router.get("/analysis")
def analysis(
    stock_code: str = Query('00700', description="股票代码，如00700(港股)或600519(A股)"),
    grid_type: str = Query('equal_distance', description="网格类型: equal_distance(等距)/equal_ratio(等比)/dynamic(动态布林带)"),
    num_grids_up: int = Query(10, ge=3, le=30, description="上行网格数(3-30)"),
    num_grids_down: int = Query(10, ge=3, le=30, description="下行网格数(3-30)"),
    grid_width_pct: float = Query(None, description="网格宽度百分比(如2表示2%)，不填则用ATR自动计算"),
    capital: float = Query(1000000, description="总资金(HKD或CNY)"),
    hist_days: int = Query(252, ge=60, le=1000, description="回测天数(60-1000)"),
    sizing: str = Query('equal', description="仓位方法: equal(等额)/pyramid(金字塔)"),
    stop_loss_pct: float = Query(0.10, ge=0.05, le=0.30, description="止损比例(0.05-0.30，默认10%)"),
    enable_stop_loss: bool = Query(True, description="是否启用止损"),
    atr_multiplier: float = Query(1.0, ge=0.3, le=3.0, description="ATR倍数(0.3-3.0，默认1.0)，控制网格宽度"),
):
    """
    网格交易完整分析

    返回内容包括：
    - 基础信息：股票名称、当前价格、52周高低、ATR
    - 网格配置：网格宽度、层级列表、每格股数/资金
    - 回测结果：总收益、胜率、最大回撤、夏普比率等风险指标
    - 盈亏平衡：最小网格宽度、每格利润
    - 图表数据：K线数据（dates/opens/highs/lows/closes/volumes）
    - 当前状态：最近网格、下一买入/卖出触发价
    """
    return analyze_grid_trading(
        stock_code=stock_code,
        grid_type=grid_type,
        num_grids_up=num_grids_up,
        num_grids_down=num_grids_down,
        grid_width_pct=grid_width_pct,
        total_capital=capital,
        hist_days=hist_days,
        sizing_method=sizing,
        stop_loss_pct=stop_loss_pct,
        enable_stop_loss=enable_stop_loss,
        atr_multiplier=atr_multiplier,
    )


@router.get("/levels")
def levels(
    current_price: float = Query(..., description="当前价格"),
    grid_type: str = Query('equal_distance', description="网格类型"),
    num_grids: int = Query(10, description="单侧网格数"),
    grid_width_pct: float = Query(None, description="网格宽度百分比"),
):
    """生成网格价格层级（不需要历史数据，只根据当前价格计算）"""
    grid_width = current_price * grid_width_pct / 100 if grid_width_pct is not None else None
    return generate_grid_levels(current_price, grid_type, num_grids, num_grids, grid_width)


@router.get("/status")
def status(
    current_price: float = Query(..., description="当前价格"),
    grid_type: str = Query('equal_distance', description="网格类型"),
    num_grids: int = Query(10, description="单侧网格数"),
    grid_width_pct: float = Query(2.0, description="网格宽度百分比"),
):
    """获取当前价格在网格中的位置状态"""
    grid_width = current_price * grid_width_pct / 100
    levels = generate_grid_levels(current_price, grid_type, num_grids, num_grids, grid_width)
    return get_grid_status(current_price, levels)


@router.get("/optimize")
def optimize(
    stock_code: str = Query(..., description="股票代码"),
    capital: float = Query(1000000, description="总资金"),
    hist_days: int = Query(252, description="回测天数"),
):
    """
    网格参数优化

    自动扫描不同网格宽度×数量×仓位方法的组合，
    返回评分最高的前5个参数配置。

    评分公式：年化收益×0.4 + 夏普比率×0.3 - 最大回撤×0.3
    """
    return optimize_parameters(
        stock_code=stock_code,
        total_capital=capital,
        hist_days=hist_days,
    )
