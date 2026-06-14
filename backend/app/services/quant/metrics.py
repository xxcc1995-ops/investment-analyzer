"""
机构级绩效指标计算

覆盖指标：
- 收益类：总收益、年化收益、超额收益
- 风险类：最大回撤、波动率、下行波动率
- 风险调整：Sharpe、Sortino、Calmar、Omega、信息比率
- 因子类：Alpha、Beta、因子暴露
- 交易类：换手率、胜率、盈亏比
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple


def calc_total_return(equity_curve: np.ndarray) -> float:
    """总收益率"""
    if len(equity_curve) < 2:
        return 0.0
    return equity_curve[-1] / equity_curve[0] - 1.0


def calc_annual_return(equity_curve: np.ndarray, trading_days_per_year: int = 252) -> float:
    """年化收益率（几何）"""
    total = calc_total_return(equity_curve)
    n_days = len(equity_curve) - 1
    if n_days <= 0 or total <= -1:
        return 0.0
    years = n_days / trading_days_per_year
    if years <= 0:
        return 0.0
    return (1 + total) ** (1 / years) - 1


def calc_daily_returns(equity_curve: np.ndarray) -> np.ndarray:
    """日收益率序列"""
    if len(equity_curve) < 2:
        return np.array([])
    return np.diff(equity_curve) / equity_curve[:-1]


def calc_volatility(daily_returns: np.ndarray, trading_days_per_year: int = 252) -> float:
    """年化波动率"""
    if len(daily_returns) < 2:
        return 0.0
    return np.std(daily_returns, ddof=1) * np.sqrt(trading_days_per_year)


def calc_max_drawdown(equity_curve: np.ndarray) -> Tuple[float, int, int]:
    """
    最大回撤

    Returns:
        (最大回撤比例, 回撤起始index, 回撤结束index)
    """
    if len(equity_curve) < 2:
        return 0.0, 0, 0

    peak = np.maximum.accumulate(equity_curve)
    drawdown = (equity_curve - peak) / peak
    end_idx = np.argmin(drawdown)
    start_idx = np.argmax(equity_curve[:end_idx + 1]) if end_idx > 0 else 0

    return float(drawdown[end_idx]), int(start_idx), int(end_idx)


def calc_max_drawdown_duration(equity_curve: np.ndarray) -> int:
    """最大回撤持续天数（从峰值到恢复）"""
    if len(equity_curve) < 2:
        return 0

    peak = np.maximum.accumulate(equity_curve)
    in_drawdown = equity_curve < peak

    max_duration = 0
    current_duration = 0
    for dd in in_drawdown:
        if dd:
            current_duration += 1
            max_duration = max(max_duration, current_duration)
        else:
            current_duration = 0

    return max_duration


def calc_sharpe_ratio(daily_returns: np.ndarray, risk_free_rate: float = 0.02,
                      trading_days_per_year: int = 252) -> float:
    """夏普比率"""
    if len(daily_returns) < 20:
        return 0.0
    excess = daily_returns - risk_free_rate / trading_days_per_year
    std = np.std(excess, ddof=1)
    if std < 1e-10:
        return 0.0
    return np.mean(excess) / std * np.sqrt(trading_days_per_year)


def calc_sortino_ratio(daily_returns: np.ndarray, risk_free_rate: float = 0.02,
                       trading_days_per_year: int = 252) -> float:
    """Sortino比率（仅下行风险）"""
    if len(daily_returns) < 20:
        return 0.0
    excess = daily_returns - risk_free_rate / trading_days_per_year
    downside = excess[excess < 0]
    if len(downside) < 5:
        return 0.0
    downside_std = np.std(downside, ddof=1)
    if downside_std < 1e-10:
        return 0.0
    return np.mean(excess) / downside_std * np.sqrt(trading_days_per_year)


def calc_calmar_ratio(equity_curve: np.ndarray, trading_days_per_year: int = 252) -> float:
    """Calmar比率 = 年化收益 / 最大回撤"""
    annual = calc_annual_return(equity_curve, trading_days_per_year)
    max_dd, _, _ = calc_max_drawdown(equity_curve)
    if abs(max_dd) < 1e-10:
        return 0.0
    return annual / abs(max_dd)


def calc_omega_ratio(daily_returns: np.ndarray, threshold: float = 0.0) -> float:
    """Omega比率 = P(returns > threshold) / P(returns < threshold)"""
    if len(daily_returns) < 10:
        return 1.0
    gains = daily_returns[daily_returns > threshold] - threshold
    losses = threshold - daily_returns[daily_returns <= threshold]
    sum_losses = np.sum(losses)
    if sum_losses < 1e-10:
        return 10.0  # cap
    return float(np.sum(gains) / sum_losses)


def calc_tail_ratio(daily_returns: np.ndarray) -> float:
    """尾部比率 = 95th percentile / |5th percentile|"""
    if len(daily_returns) < 20:
        return 1.0
    p95 = np.percentile(daily_returns, 95)
    p5 = np.percentile(daily_returns, 5)
    if abs(p5) < 1e-10:
        return 10.0
    return float(abs(p95 / p5))


def calc_alpha_beta(portfolio_returns: np.ndarray, benchmark_returns: np.ndarray) -> Tuple[float, float]:
    """
    CAPM Alpha 和 Beta

    Alpha = R_p - R_f - Beta * (R_b - R_f)
    """
    if len(portfolio_returns) < 20 or len(benchmark_returns) < 20:
        return 0.0, 1.0

    n = min(len(portfolio_returns), len(benchmark_returns))
    p_ret = portfolio_returns[:n]
    b_ret = benchmark_returns[:n]

    cov = np.cov(p_ret, b_ret)
    if cov[1, 1] < 1e-10:
        return 0.0, 1.0

    beta = cov[0, 1] / cov[1, 1]
    alpha = np.mean(p_ret) - beta * np.mean(b_ret)

    return float(alpha * 252), float(beta)


def calc_information_ratio(portfolio_returns: np.ndarray, benchmark_returns: np.ndarray) -> Tuple[float, float]:
    """
    信息比率 = 超额收益均值 / 跟踪误差

    Returns:
        (信息比率, 跟踪误差)
    """
    if len(portfolio_returns) < 20 or len(benchmark_returns) < 20:
        return 0.0, 0.0

    n = min(len(portfolio_returns), len(benchmark_returns))
    excess = portfolio_returns[:n] - benchmark_returns[:n]
    te = np.std(excess, ddof=1) * np.sqrt(252)
    if te < 1e-10:
        return 0.0, 0.0
    ir = np.mean(excess) * 252 / te
    return float(ir), float(te)


def calc_monthly_win_rate(daily_returns: np.ndarray, trading_days_per_month: int = 21) -> float:
    """月度胜率"""
    if len(daily_returns) < trading_days_per_month:
        return 0.0
    n_months = len(daily_returns) // trading_days_per_month
    monthly_returns = []
    for i in range(n_months):
        start = i * trading_days_per_month
        end = start + trading_days_per_month
        month_ret = np.prod(1 + daily_returns[start:end]) - 1
        monthly_returns.append(month_ret)
    if not monthly_returns:
        return 0.0
    return float(np.sum(np.array(monthly_returns) > 0) / len(monthly_returns))


def calc_profit_loss_ratio(daily_returns: np.ndarray) -> float:
    """盈亏比 = 平均盈利 / 平均亏损"""
    wins = daily_returns[daily_returns > 0]
    losses = daily_returns[daily_returns < 0]
    if len(losses) < 1 or len(wins) < 1:
        return 0.0
    return float(np.mean(wins) / abs(np.mean(losses)))


def calc_turnover(weights_history: List[Dict[str, float]]) -> float:
    """
    平均换手率

    Args:
        weights_history: 每期持仓权重字典列表
    """
    if len(weights_history) < 2:
        return 0.0
    turnovers = []
    for i in range(1, len(weights_history)):
        prev = weights_history[i - 1]
        curr = weights_history[i]
        all_keys = set(prev.keys()) | set(curr.keys())
        turnover = sum(abs(curr.get(k, 0) - prev.get(k, 0)) for k in all_keys) / 2
        turnovers.append(turnover)
    return float(np.mean(turnovers))


def calc_yearly_returns(daily_returns: np.ndarray, dates: Optional[np.ndarray] = None,
                        trading_days_per_year: int = 252) -> Dict[int, float]:
    """分年度收益率"""
    if dates is not None and len(dates) == len(daily_returns) + 1:
        # 使用日期分组
        years = {}
        for i, ret in enumerate(daily_returns):
            year = pd.Timestamp(dates[i + 1]).year
            if year not in years:
                years[year] = []
            years[year].append(ret)
        return {y: float(np.prod(1 + np.array(rets)) - 1) for y, rets in years.items()}
    else:
        # 按交易日分组
        n_years = len(daily_returns) // trading_days_per_year
        result = {}
        for i in range(n_years):
            start = i * trading_days_per_year
            end = start + trading_days_per_year
            year_ret = np.prod(1 + daily_returns[start:end]) - 1
            result[2020 + i] = float(year_ret)
        return result


def calculate_full_metrics(equity_curve: np.ndarray,
                           benchmark_curve: Optional[np.ndarray] = None,
                           dates: Optional[np.ndarray] = None,
                           weights_history: Optional[List[Dict[str, float]]] = None,
                           risk_free_rate: float = 0.02) -> Dict:
    """
    计算完整的绩效指标

    Args:
        equity_curve: 净值曲线（初始值=1.0或初始资金）
        benchmark_curve: 基准净值曲线
        dates: 日期序列
        weights_history: 持仓权重历史
        risk_free_rate: 无风险利率

    Returns:
        完整指标字典
    """
    daily_returns = calc_daily_returns(equity_curve)
    metrics = {}

    # 收益指标
    metrics['total_return'] = calc_total_return(equity_curve)
    metrics['annual_return'] = calc_annual_return(equity_curve)

    # 风险指标
    metrics['volatility'] = calc_volatility(daily_returns)
    max_dd, dd_start, dd_end = calc_max_drawdown(equity_curve)
    metrics['max_drawdown'] = max_dd
    metrics['max_drawdown_start'] = int(dd_start)
    metrics['max_drawdown_end'] = int(dd_end)
    metrics['max_drawdown_duration'] = calc_max_drawdown_duration(equity_curve)

    # 风险调整收益
    metrics['sharpe_ratio'] = calc_sharpe_ratio(daily_returns, risk_free_rate)
    metrics['sortino_ratio'] = calc_sortino_ratio(daily_returns, risk_free_rate)
    metrics['calmar_ratio'] = calc_calmar_ratio(equity_curve)
    metrics['omega_ratio'] = calc_omega_ratio(daily_returns)
    metrics['tail_ratio'] = calc_tail_ratio(daily_returns)

    # 交易指标
    metrics['monthly_win_rate'] = calc_monthly_win_rate(daily_returns)
    metrics['profit_loss_ratio'] = calc_profit_loss_ratio(daily_returns)

    # 分年度收益
    metrics['yearly_returns'] = calc_yearly_returns(daily_returns, dates)

    # 换手率
    if weights_history:
        metrics['avg_turnover'] = calc_turnover(weights_history)

    # 基准对比
    if benchmark_curve is not None and len(benchmark_curve) > 1:
        bench_returns = calc_daily_returns(benchmark_curve)
        metrics['benchmark_total_return'] = calc_total_return(benchmark_curve)
        metrics['benchmark_annual_return'] = calc_annual_return(benchmark_curve)
        metrics['excess_return'] = metrics['annual_return'] - metrics['benchmark_annual_return']

        alpha, beta = calc_alpha_beta(daily_returns, bench_returns)
        metrics['alpha'] = alpha
        metrics['beta'] = beta

        ir, te = calc_information_ratio(daily_returns, bench_returns)
        metrics['information_ratio'] = ir
        metrics['tracking_error'] = te

    return metrics
