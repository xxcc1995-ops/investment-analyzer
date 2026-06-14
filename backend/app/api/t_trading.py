"""金渐成做T交易系统 API（机构级增强版）

端点：
- GET  /signals          全市场做T信号扫描
- GET  /signals/{code}   单只股票详细分析（含回测验证）
- GET  /position         全部仓位状态
- GET  /position/{code}  单只股票仓位
- POST /position/init    初始化持仓
- POST /execute          执行做T操作（含滑点和风险控制）
- GET  /trades           交易历史
- GET  /pyramid          金字塔加仓方案
- GET  /negative-cost    负成本持股进度
- GET  /philosophy       做T方法论
- GET  /backtest/{code}  历史回测验证
- GET  /risk-summary     风险汇总报告
- DELETE /position       删除仓位
- POST /reset            重置全部
"""

from fastapi import APIRouter, Query, Body
from app.services.t_trading_service import (
    scan_all_signals, get_detailed_analysis, calc_pyramid_orders,
    get_t_philosophy, fetch_historical_klines, backtest_t_strategy,
    calc_trend_filter, calc_round_trip_cost, compare_t_strategies,
    calculate_position_size,
)
from app.services.t_position_service import (
    init_position, get_all_positions, get_position,
    execute_t_trade, get_trade_history, calc_cost_analysis,
    delete_position, reset_all, get_risk_summary,
    get_trade_analytics, get_trade_journal, check_trading_alerts,
)
from app.services.grid_service import calculate_atr

router = APIRouter()


@router.get("/signals")
def signals(
    market: str = Query("all", description="市场: A/HK/US/all"),
    t_capital: float = Query(300000, description="做T资金（默认30万）"),
):
    """全市场做T信号扫描"""
    return scan_all_signals(market=market, t_capital=t_capital)


@router.get("/signals/{code}")
def signal_detail(
    code: str,
    market: str = Query(..., description="市场: A/HK/US"),
    t_capital: float = Query(300000, description="做T资金"),
):
    """单只股票详细T点分析"""
    return get_detailed_analysis(code=code, market=market, t_capital=t_capital)


@router.get("/position")
def all_positions():
    """全部仓位状态与成本分析"""
    return get_all_positions()


@router.get("/position/{code}")
def single_position(
    code: str,
    market: str = Query(..., description="市场: A/HK/US"),
):
    """单只股票仓位详情"""
    pos = get_position(code, market)
    if not pos:
        return {"error": f"未找到 {code} 的持仓记录"}
    return pos


@router.post("/position/init")
def init_pos(
    code: str = Body(..., embed=True),
    name: str = Body(..., embed=True),
    market: str = Body(..., embed=True),
    shares: int = Body(..., embed=True),
    cost_price: float = Body(..., embed=True),
):
    """初始化持仓（自动分层：7成底仓 + 3成做T仓）"""
    return init_position(code=code, name=name, market=market,
                         shares=shares, cost_price=cost_price)


@router.post("/execute")
def execute(
    code: str = Body(..., embed=True),
    market: str = Body(..., embed=True),
    action: str = Body(..., embed=True, description="buy_t / sell_t"),
    shares: int = Body(..., embed=True),
    price: float = Body(..., embed=True),
    note: str = Body("", embed=True),
):
    """执行做T操作"""
    return execute_t_trade(code=code, market=market, action=action,
                           shares=shares, price=price, note=note)


@router.get("/trades")
def trades(
    code: str = Query(None, description="股票代码（可选）"),
    market: str = Query(None, description="市场（可选）"),
    limit: int = Query(100, description="返回条数"),
):
    """做T交易历史"""
    return get_trade_history(code=code, market=market, limit=limit)


@router.get("/pyramid")
def pyramid(
    code: str = Query(..., description="股票代码"),
    market: str = Query(..., description="市场: A/HK/US"),
    t_capital: float = Query(300000, description="做T资金"),
):
    """金字塔加仓方案"""
    from app.services.t_trading_service import _get_current_price_and_info
    from app.services.t_trading_service import fetch_historical_klines

    stock_info = _get_current_price_and_info(code, market)
    if not stock_info or "error" in stock_info:
        return {"error": f"无法获取 {code} 行情"}

    current_price = stock_info.get("price", 0)
    if current_price <= 0:
        return {"error": f"获取价格失败"}

    klines = fetch_historical_klines(code, market, 60)
    if not klines:
        return {"error": "无法获取历史数据"}

    highs = [k["high"] for k in klines]
    lows = [k["low"] for k in klines]
    closes = [k["close"] for k in klines]
    atr = calculate_atr(highs, lows, closes, 14)

    return calc_pyramid_orders(current_price, atr, t_capital, market)


@router.get("/negative-cost")
def negative_cost():
    """负成本持股进度汇总"""
    all_pos = get_all_positions()
    positions = all_pos.get("positions", [])

    # 按负成本进度排序
    positions.sort(key=lambda p: p["cost_analysis"]["recovery_pct"], reverse=True)

    return {
        "positions": [
            {
                "code": p["code"],
                "name": p["name"],
                "market": p["market"],
                "total_shares": p["total_shares"],
                "avg_cost": p["avg_cost"],
                "cost_analysis": p["cost_analysis"],
            }
            for p in positions
        ],
        "summary": all_pos["summary"],
        "update_time": all_pos["update_time"],
    }


@router.get("/philosophy")
def philosophy():
    """做T方法论说明"""
    return get_t_philosophy()


@router.get("/backtest/{code}")
def backtest(
    code: str,
    market: str = Query(..., description="市场: A/HK/US"),
    t_capital: float = Query(300000, description="做T资金"),
):
    """
    历史回测验证

    使用最近60个交易日数据模拟做T策略：
    - 胜率、盈亏比、最大回撤
    - 交易日志
    - 策略有效性评估
    """
    klines = fetch_historical_klines(code, market, 252)
    if not klines or len(klines) < 60:
        return {"error": f"无法获取 {code} 的历史数据（需要至少60个交易日）"}

    result = backtest_t_strategy(code, market, klines, t_capital)

    # 附加趋势分析
    closes = [k["close"] for k in klines]
    trend = calc_trend_filter(closes)
    result["current_trend"] = trend

    # 附加交易成本信息
    result["cost_info"] = {
        "round_trip_cost_pct": round(calc_round_trip_cost(market) * 100, 4),
        "market": market,
    }

    return result


@router.get("/risk-summary")
def risk_summary():
    """
    风险汇总报告

    分析所有持仓的风险状况：
    - 做T仓占比是否超标
    - 今日交易频率
    - 累计手续费占比
    - 整体风险等级
    """
    return get_risk_summary()


@router.get("/compare-strategies/{code}")
def compare_strategies(
    code: str,
    market: str = Query(..., description="市场: A/HK/US"),
    t_capital: float = Query(300000, description="做T资金"),
):
    """
    策略对比分析 — 三种做T风格对比

    对比保守/标准/激进三种策略：
    - 胜率、盈亏比、最大回撤
    - 交易频率
    - 推荐最适合的策略
    """
    return compare_t_strategies(code=code, market=market, t_capital=t_capital)


@router.get("/risk-calculator/{code}")
def risk_calculator(
    code: str,
    market: str = Query(..., description="市场: A/HK/US"),
    account_balance: float = Query(1000000, description="账户总资金"),
    risk_per_trade_pct: float = Query(2.0, description="单笔风险比例(%)"),
    stop_loss_price: float = Query(None, description="自定义止损价(可选)"),
):
    """
    风险计算器 — 基于凯利公式和ATR的仓位计算

    返回：
    - 建议仓位（股数、金额、占比）
    - 止损价位和止损距离
    - 止盈目标（1R/2R/3R）
    - 凯利公式最优仓位
    - 风险等级
    """
    return calculate_position_size(
        code=code, market=market,
        account_balance=account_balance,
        risk_per_trade_pct=risk_per_trade_pct,
        stop_loss_price=stop_loss_price,
    )


@router.get("/analytics")
def analytics():
    """
    盈亏分析仪表盘 — 专家级交易复盘

    返回：
    - 综合评分（胜率、盈亏比、质量评分）
    - 按星期几统计（哪天做T最赚钱）
    - 按时间段统计（上午 vs 下午）
    - 按股票统计（哪些股票做T效果好）
    - 连续盈亏统计
    - 交易频率 vs 收益率分析
    - 最佳/最差交易排名
    - 累计P&L曲线数据
    """
    return get_trade_analytics()


@router.get("/journal")
def journal(
    code: str = Query(None, description="股票代码筛选"),
    market: str = Query(None, description="市场筛选"),
    start_date: str = Query(None, description="起始日期 (YYYY-MM-DD)"),
    end_date: str = Query(None, description="结束日期 (YYYY-MM-DD)"),
    pnl_filter: str = Query(None, description="盈亏筛选: win/lose/all"),
    limit: int = Query(50, description="返回条数"),
):
    """
    交易日志 — 带筛选的详细交易记录

    每笔交易附加：
    - 交易质量标签（优秀/盈利/小幅亏损/重大亏损）
    - 持有时间
    - 盈亏百分比
    """
    return get_trade_journal(
        code=code, market=market,
        start_date=start_date, end_date=end_date,
        pnl_filter=pnl_filter, limit=limit,
    )


@router.get("/alerts")
def alerts():
    """
    自动告警系统 — 检查所有持仓的告警条件

    告警类型：
    - 止损预警 — 价格接近止损位
    - 做T仓超限 — 做T仓占比过高
    - 连续亏损 — 连续亏损达到阈值
    - 手续费过高 — 累计手续费占比过大
    - 今日交易频次 — 接近或达到每日上限
    - 负成本达成 — 做T回收超过投入
    """
    return check_trading_alerts()


@router.delete("/position/{code}")
def del_position(
    code: str,
    market: str = Query(..., description="市场: A/HK/US"),
):
    """删除仓位记录"""
    return delete_position(code, market)


@router.post("/reset")
def reset():
    """重置全部仓位和交易记录"""
    return reset_all()
