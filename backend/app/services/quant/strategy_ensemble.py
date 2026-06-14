"""
策略5：多策略集成

灵感来源：Citadel/Millennium 多策略平台

风险平价分配：
- 每个策略贡献相等的风险
- 月度再平衡权重
- 相关性监控（相关性 > 0.7 时减仓）

集成方式：
- 运行多个独立策略
- 风险平价分配资金
- 合并交易信号
"""

import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Optional, Tuple, Any

from .backtest_engine import (
    run_quant_backtest, STRATEGY_REGISTRY,
    _prepare_data, _create_strategy, _run_in_sample_backtest
)
from .cost_model import DEFAULT_COST_MODEL
from .risk_manager import RiskManager, RiskConfig
from .metrics import calc_daily_returns, calc_volatility

logger = logging.getLogger(__name__)


def risk_parity_weights(volatilities: np.ndarray,
                        correlation_matrix: np.ndarray) -> np.ndarray:
    """
    风险平价权重计算

    目标：每个资产对组合风险的贡献相等

    使用迭代法求解：
    1. 初始权重 = 波动率倒数
    2. 迭代调整使得风险贡献趋近相等

    Args:
        volatilities: 各策略波动率
        correlation_matrix: 策略间相关性矩阵

    Returns:
        权重数组（和为1）
    """
    n = len(volatilities)
    if n == 0:
        return np.array([])

    # 协方差矩阵
    cov_matrix = np.outer(volatilities, volatilities) * correlation_matrix

    # 初始权重：波动率倒数
    inv_vol = 1.0 / np.maximum(volatilities, 1e-8)
    weights = inv_vol / inv_vol.sum()

    # 迭代优化
    for _ in range(200):
        portfolio_vol = np.sqrt(weights @ cov_matrix @ weights)
        if portfolio_vol < 1e-10:
            break

        # 边际风险贡献
        marginal_risk = cov_matrix @ weights / portfolio_vol
        risk_contrib = weights * marginal_risk
        target_rc = portfolio_vol / n

        # 调整权重
        adjustment = target_rc / np.maximum(risk_contrib, 1e-8)
        weights = weights * adjustment
        weights = weights / weights.sum()

    return weights


def calc_strategy_correlation(daily_returns_list: List[np.ndarray],
                              lookback: int = 60) -> np.ndarray:
    """
    计算策略间滚动相关性矩阵

    Args:
        daily_returns_list: 各策略的日收益率列表
        lookback: 回望窗口

    Returns:
        相关性矩阵
    """
    n = len(daily_returns_list)
    if n == 0:
        return np.array([])

    # 取最近 lookback 天的数据
    recent = []
    for dr in daily_returns_list:
        if len(dr) >= lookback:
            recent.append(dr[-lookback:])
        else:
            recent.append(dr)

    # 对齐长度
    min_len = min(len(r) for r in recent)
    if min_len < 10:
        return np.eye(n)

    aligned = np.array([r[:min_len] for r in recent])
    return np.corrcoef(aligned)


def run_ensemble_backtest(
    strategy_names: Optional[List[str]] = None,
    start_date: str = '2020-01-01',
    end_date: str = '2025-12-31',
    initial_capital: float = 1_000_000,
    benchmark: str = '000300',
    allocation_method: str = 'risk_parity',
    walk_forward: bool = True,
) -> Dict[str, Any]:
    """
    多策略集成回测

    Args:
        strategy_names: 策略名称列表
        start_date: 开始日期
        end_date: 结束日期
        initial_capital: 初始资金
        benchmark: 基准
        allocation_method: 分配方法 (risk_parity/equal_weight)
        walk_forward: 是否使用Walk-Forward

    Returns:
        集成回测结果
    """
    if strategy_names is None:
        strategy_names = ['multi_factor', 'mean_reversion', 'trend_following']

    logger.info(f"Running ensemble backtest: {strategy_names}")

    # 运行各策略的独立回测
    strategy_results = {}
    strategy_daily_returns = {}

    for name in strategy_names:
        logger.info(f"Running strategy: {name}")
        result = run_quant_backtest(
            strategy_name=name,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital / len(strategy_names),
            benchmark=benchmark,
            walk_forward=walk_forward,
        )

        if 'error' not in result:
            strategy_results[name] = result
            strategy_daily_returns[name] = np.array(result.get('daily_returns', []))

    if not strategy_results:
        return {'error': 'All strategies failed'}

    # 计算策略间相关性
    returns_list = list(strategy_daily_returns.values())
    volatilities = np.array([calc_volatility(dr) for dr in returns_list])
    corr_matrix = calc_strategy_correlation(returns_list)

    # 计算分配权重
    if allocation_method == 'risk_parity':
        weights = risk_parity_weights(volatilities, corr_matrix)
    else:
        # 等权
        weights = np.ones(len(returns_list)) / len(returns_list)

    # 检查相关性警告
    high_corr_warning = False
    if len(corr_matrix) > 1:
        for i in range(len(corr_matrix)):
            for j in range(i + 1, len(corr_matrix)):
                if corr_matrix[i, j] > 0.7:
                    high_corr_warning = True
                    logger.warning(f"High correlation between strategies: {corr_matrix[i, j]:.2f}")

    # 合并净值曲线
    ensemble_equity = _build_ensemble_equity(
        strategy_results, weights, initial_capital
    )

    # 计算集成指标
    from .metrics import calculate_full_metrics
    ensemble_arr = np.array(ensemble_equity)

    # 基准
    benchmark_curve = None
    from .data_provider import get_index_daily
    bench_data = get_index_daily(benchmark, start_date, end_date)
    if bench_data is not None and not bench_data.empty:
        bench_close = bench_data['close'].values
        benchmark_curve = bench_close / bench_close[0] * initial_capital

    metrics = calculate_full_metrics(ensemble_arr, benchmark_curve=benchmark_curve)

    # 各策略贡献
    strategy_contributions = {}
    for i, name in enumerate(strategy_names):
        if name in strategy_results:
            sr = strategy_results[name]
            strategy_contributions[name] = {
                'weight': float(weights[i]) if i < len(weights) else 0,
                'annual_return': sr.get('metrics', {}).get('annual_return', 0),
                'sharpe_ratio': sr.get('metrics', {}).get('sharpe_ratio', 0),
                'max_drawdown': sr.get('metrics', {}).get('max_drawdown', 0),
            }

    return {
        'metrics': metrics,
        'equity_curve': ensemble_equity,
        'strategy_contributions': strategy_contributions,
        'weights': {name: float(weights[i]) for i, name in enumerate(strategy_names) if i < len(weights)},
        'correlation_matrix': corr_matrix.tolist() if len(corr_matrix) > 0 else [],
        'volatilities': {name: float(volatilities[i]) for i, name in enumerate(strategy_names) if i < len(volatilities)},
        'high_correlation_warning': high_corr_warning,
        'final_value': ensemble_equity[-1] if ensemble_equity else initial_capital,
        'strategy': 'ensemble',
        'allocation_method': allocation_method,
    }


def _build_ensemble_equity(strategy_results: Dict, weights: np.ndarray,
                           initial_capital: float) -> List[float]:
    """构建集成净值曲线"""
    # 找到最短的曲线长度
    curves = []
    for name, result in strategy_results.items():
        eq = result.get('equity_curve', [])
        if eq:
            # 归一化到初始值=1
            curves.append(np.array(eq) / eq[0])

    if not curves:
        return [initial_capital]

    min_len = min(len(c) for c in curves)
    curves = [c[:min_len] for c in curves]

    # 加权合并
    ensemble = np.zeros(min_len)
    for i, curve in enumerate(curves):
        w = weights[i] if i < len(weights) else 1.0 / len(curves)
        ensemble += w * curve

    # 缩放到初始资金
    return (ensemble * initial_capital).tolist()
