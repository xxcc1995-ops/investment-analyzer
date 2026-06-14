"""
网格交易 API 端点

提供以下接口：
- GET /philosophy   → 获取网格交易教学内容
- GET /analysis     → 完整网格分析（含回测、风险指标、图表数据）
- GET /levels       → 生成网格价格层级
- GET /status       → 当前网格状态
- GET /optimize     → 参数优化（自动找最优参数组合）
"""

from fastapi import APIRouter, Query, Body
from app.services.grid_service import (
    analyze_grid_trading, get_philosophy, generate_grid_levels,
    get_grid_status, optimize_parameters,
    add_to_grid_portfolio, get_grid_portfolio, remove_from_grid_portfolio,
    detect_grid_decay, stress_test_grid,
    grid_vs_buy_and_hold, suggest_adaptive_grid,
    grid_health_monitor, save_grid_health_snapshot, get_grid_health_history,
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


@router.post("/portfolio/add")
def portfolio_add(
    code: str = Body(..., embed=True),
    name: str = Body(..., embed=True),
    market: str = Body(..., embed=True),
    grid_type: str = Body(..., embed=True),
    grid_width_pct: float = Body(..., embed=True),
    num_grids: int = Body(..., embed=True),
    capital: float = Body(..., embed=True),
    sizing: str = Body(..., embed=True),
    current_price: float = Body(..., embed=True),
):
    """添加网格到组合"""
    return add_to_grid_portfolio(
        code=code, name=name, market=market,
        grid_type=grid_type, grid_width_pct=grid_width_pct,
        num_grids=num_grids, capital=capital, sizing=sizing,
        current_price=current_price,
    )


@router.get("/portfolio")
def portfolio():
    """获取网格组合"""
    return get_grid_portfolio()


@router.delete("/portfolio/{code}")
def portfolio_remove(
    code: str,
    market: str = Query(..., description="市场"),
):
    """从组合中移除网格"""
    return remove_from_grid_portfolio(code, market)


@router.get("/decay")
def decay(
    stock_code: str = Query(..., description="股票代码"),
    lookback: int = Query(20, description="回看天数"),
):
    """检测网格衰减"""
    from app.services.grid_service import _fetch_historical, generate_grid_levels, calculate_atr

    hist_data = _fetch_historical(stock_code, 60)
    if not hist_data:
        return {"error": "无法获取历史数据"}

    closes = [d["close"] for d in hist_data]
    highs = [d["high"] for d in hist_data]
    lows = [d["low"] for d in hist_data]
    atr = calculate_atr(highs, lows, closes, 14)
    current_price = closes[-1]

    levels = generate_grid_levels(current_price, "equal_distance", 10, 10, atr)
    levels_with_price = [{"price": lv["price"]} for lv in levels] if isinstance(levels, list) and levels and "price" in levels[0] else levels

    return detect_grid_decay(closes, levels_with_price, lookback)


@router.get("/stress-test")
def stress(
    stock_code: str = Query(..., description="股票代码"),
    capital: float = Query(1000000, description="总资金"),
    grid_width_pct: float = Query(2.0, description="网格宽度%"),
    num_simulations: int = Query(500, description="模拟次数"),
):
    """蒙特卡洛压力测试"""
    from app.services.grid_service import _fetch_historical

    hist_data = _fetch_historical(stock_code, 252)
    if not hist_data:
        return {"error": "无法获取历史数据"}

    return stress_test_grid(
        klines=hist_data,
        grid_type="equal_distance",
        num_grids_up=10,
        num_grids_down=10,
        grid_width_pct=grid_width_pct,
        capital=capital,
        sizing="equal",
        num_simulations=min(num_simulations, 1000),
    )


@router.get("/compare")
def compare(
    stock_code: str = Query(..., description="股票代码"),
    capital: float = Query(1000000, description="总资金"),
    hist_days: int = Query(252, description="回测天数"),
):
    """网格策略 vs 买入持有对比"""
    return grid_vs_buy_and_hold(stock_code=stock_code, total_capital=capital, hist_days=hist_days)


@router.get("/suggest")
def suggest(
    stock_code: str = Query(..., description="股票代码"),
    capital: float = Query(1000000, description="总资金"),
):
    """自适应网格参数建议"""
    return suggest_adaptive_grid(stock_code=stock_code, capital=capital)


@router.get("/health")
def health(
    stock_code: str = Query(..., description="股票代码"),
    capital: float = Query(1000000, description="总资金"),
):
    """网格健康监控"""
    return grid_health_monitor(stock_code=stock_code, capital=capital)


@router.post("/health/snapshot")
def health_snapshot(
    stock_code: str = Query(..., description="股票代码"),
):
    """保存网格健康快照"""
    return save_grid_health_snapshot(stock_code=stock_code)


@router.get("/health/history")
def health_history(
    stock_code: str = Query(..., description="股票代码"),
):
    """获取网格健康历史趋势"""
    return get_grid_health_history(stock_code=stock_code)
