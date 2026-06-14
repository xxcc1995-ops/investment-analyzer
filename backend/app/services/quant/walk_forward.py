"""
Walk-Forward 验证引擎

避免过拟合的核心机制：
- 锚定式扩展窗口：训练集不断增长，测试集向前滚动
- OOS（样本外）收益聚合：几何链接得到真实年化收益
- 参数稳定性检查：各折参数变异系数

参考：
- Robert Pardo "The Evaluation and Optimization of Trading Strategies"
"""

import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class WalkForwardConfig:
    """Walk-Forward 配置"""
    train_days: int = 504        # 训练窗口（2年交易日）
    test_days: int = 63          # 测试窗口（3个月交易日）
    step_days: int = 63          # 步进（与测试窗口相同，无重叠）
    min_train_days: int = 252    # 最小训练窗口（1年）
    anchored: bool = True        # 锚定模式（训练集扩展）


@dataclass
class FoldResult:
    """单折结果"""
    fold_id: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    daily_returns: np.ndarray
    equity_curve: np.ndarray
    total_return: float
    annual_return: float
    sharpe_ratio: float
    max_drawdown: float
    params: Dict[str, Any] = field(default_factory=dict)
    trade_count: int = 0


def walk_forward_split(dates: np.ndarray, config: WalkForwardConfig) -> List[Tuple[int, int, int, int]]:
    """
    生成 Walk-Forward 分割点

    Returns:
        [(train_start_idx, train_end_idx, test_start_idx, test_end_idx), ...]
    """
    n = len(dates)
    splits = []

    if config.anchored:
        # 锚定模式：训练集从0开始，不断扩展
        fold_start = config.train_days
        fold_id = 0

        while fold_start + config.test_days <= n:
            train_start = 0
            train_end = fold_start
            test_start = fold_start
            test_end = min(fold_start + config.test_days, n)

            splits.append((train_start, train_end, test_start, test_end))

            fold_start += config.step_days
            fold_id += 1
    else:
        # 滚动模式：训练窗口固定
        fold_start = config.train_days
        fold_id = 0

        while fold_start + config.test_days <= n:
            train_start = fold_start - config.train_days
            train_end = fold_start
            test_start = fold_start
            test_end = min(fold_start + config.test_days, n)

            splits.append((train_start, train_end, test_start, test_end))

            fold_start += config.step_days
            fold_id += 1

    return splits


def aggregate_oos_returns(fold_results: List[FoldResult]) -> Dict[str, Any]:
    """
    聚合样本外收益

    将各折的OOS收益几何链接，得到真实的年化收益
    """
    if not fold_results:
        return {
            'oos_annual_return': 0.0,
            'oos_total_return': 0.0,
            'oos_sharpe': 0.0,
            'oos_max_drawdown': 0.0,
            'n_folds': 0,
            'fold_returns': [],
        }

    # 几何链接各折收益
    fold_returns = [f.total_return for f in fold_results]
    cumulative = 1.0
    for ret in fold_returns:
        cumulative *= (1 + ret)

    total_return = cumulative - 1.0

    # 计算总交易日数
    total_days = sum(len(f.daily_returns) for f in fold_results)
    years = total_days / 252 if total_days > 0 else 1.0

    annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0.0

    # 聚合日收益率
    all_daily_returns = np.concatenate([f.daily_returns for f in fold_results])

    # 计算聚合指标
    if len(all_daily_returns) > 20:
        sharpe = (np.mean(all_daily_returns) - 0.02 / 252) / np.std(all_daily_returns, ddof=1) * np.sqrt(252)

        # 最大回撤
        equity = np.cumprod(1 + all_daily_returns)
        peak = np.maximum.accumulate(equity)
        drawdown = (equity - peak) / peak
        max_dd = float(np.min(drawdown))
    else:
        sharpe = 0.0
        max_dd = 0.0

    # 参数稳定性
    param_stability = calc_param_stability(fold_results)

    return {
        'oos_annual_return': float(annual_return),
        'oos_total_return': float(total_return),
        'oos_sharpe': float(sharpe),
        'oos_max_drawdown': float(max_dd),
        'n_folds': len(fold_results),
        'fold_returns': fold_returns,
        'total_trading_days': total_days,
        'param_stability': param_stability,
    }


def calc_param_stability(fold_results: List[FoldResult]) -> Dict[str, float]:
    """
    计算参数稳定性

    如果参数在不同折之间变化很大，说明策略可能过拟合。

    Returns:
        {param_name: coefficient_of_variation}
    """
    if len(fold_results) < 2:
        return {}

    # 收集所有折的参数
    all_params = [f.params for f in fold_results if f.params]
    if not all_params:
        return {}

    # 计算每个参数的变异系数
    stability = {}
    all_keys = set()
    for p in all_params:
        all_keys.update(p.keys())

    for key in all_keys:
        values = [p.get(key, 0) for p in all_params if isinstance(p.get(key), (int, float))]
        if len(values) >= 2 and np.mean(values) != 0:
            cv = np.std(values, ddof=1) / abs(np.mean(values))
            stability[key] = float(cv)

    return stability


def generate_wf_report(fold_results: List[FoldResult], oos_metrics: Dict) -> str:
    """
    生成 Walk-Forward 验证报告

    Returns:
        可读的文本报告
    """
    lines = []
    lines.append("=" * 60)
    lines.append("Walk-Forward Validation Report")
    lines.append("=" * 60)
    lines.append(f"Number of folds: {oos_metrics['n_folds']}")
    lines.append(f"Total trading days: {oos_metrics.get('total_trading_days', 0)}")
    lines.append("")
    lines.append("--- Out-of-Sample Performance ---")
    lines.append(f"OOS Annual Return: {oos_metrics['oos_annual_return']:.2%}")
    lines.append(f"OOS Total Return: {oos_metrics['oos_total_return']:.2%}")
    lines.append(f"OOS Sharpe Ratio: {oos_metrics['oos_sharpe']:.2f}")
    lines.append(f"OOS Max Drawdown: {oos_metrics['oos_max_drawdown']:.2%}")
    lines.append("")

    # 分折详情
    lines.append("--- Fold Details ---")
    for fold in fold_results:
        lines.append(
            f"  Fold {fold.fold_id}: "
            f"{fold.test_start} to {fold.test_end} | "
            f"Return={fold.total_return:.2%} | "
            f"Sharpe={fold.sharpe_ratio:.2f} | "
            f"MaxDD={fold.max_drawdown:.2%} | "
            f"Trades={fold.trade_count}"
        )
    lines.append("")

    # 参数稳定性
    stability = oos_metrics.get('param_stability', {})
    if stability:
        lines.append("--- Parameter Stability (CV) ---")
        for param, cv in sorted(stability.items(), key=lambda x: -x[1]):
            status = "UNSTABLE" if cv > 0.5 else "OK"
            lines.append(f"  {param}: {cv:.3f} [{status}]")
        lines.append("")

    # 评估
    lines.append("--- Assessment ---")
    if oos_metrics['oos_annual_return'] > 0.30:
        lines.append("  ✓ Strong OOS performance (annual > 30%)")
    elif oos_metrics['oos_annual_return'] > 0.10:
        lines.append("  ~ Moderate OOS performance (annual > 10%)")
    else:
        lines.append("  ✗ Weak OOS performance (annual < 10%)")

    if oos_metrics['oos_sharpe'] > 1.0:
        lines.append("  ✓ Good risk-adjusted return (Sharpe > 1.0)")
    elif oos_metrics['oos_sharpe'] > 0.5:
        lines.append("  ~ Moderate risk-adjusted return (Sharpe > 0.5)")
    else:
        lines.append("  ✗ Poor risk-adjusted return (Sharpe < 0.5)")

    unstable_params = sum(1 for cv in stability.values() if cv > 0.5)
    if unstable_params == 0:
        lines.append("  ✓ All parameters stable across folds")
    else:
        lines.append(f"  ✗ {unstable_params} unstable parameter(s) — possible overfitting")

    lines.append("=" * 60)

    return "\n".join(lines)
