"""
参数优化引擎

- GridSearchOptimizer：网格搜索 + 并行回测
- 过拟合检测：训练集 vs 测试集表现差异
- 目标指标：sharpe / calmar / total_return

参考：
- Robert Pardo "The Evaluation and Optimization of Trading Strategies"
- Marcos Lopez de Prado "Advances in Financial Machine Learning" (walk-forward)
"""

import logging
import time
from itertools import product
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Any, Type
from dataclasses import dataclass, field

import numpy as np

from .strategy_base import BaseStrategy

logger = logging.getLogger(__name__)

# 最大允许的参数组合数
MAX_COMBINATIONS = 500
# 过拟合阈值：训练集指标 / 测试集指标 > 此值则警告
OVERFIT_THRESHOLD = 2.0
# 训练集 vs 测试集指标差异警告阈值（百分比）
OVERFIT_DIFF_PCT = 0.50


@dataclass
class OptimizationResult:
    """单组参数的优化结果"""
    params: Dict[str, Any]
    train_metric: float
    test_metric: float
    train_metrics: Dict[str, float] = field(default_factory=dict)
    test_metrics: Dict[str, float] = field(default_factory=dict)
    overfit_ratio: float = 0.0  # train_metric / test_metric


@dataclass
class GridSearchOutput:
    """网格搜索输出"""
    best_params: Dict[str, Any]
    best_test_metric: float
    best_train_metric: float
    all_results: List[Dict[str, Any]]  # 排序后的所有结果
    overfit_warning: bool
    overfit_details: str
    total_combinations: int
    elapsed_seconds: float
    metric_name: str
    strategy_name: str


def _extract_metric(metrics: Dict[str, float], metric_name: str) -> float:
    """从回测指标中提取目标值"""
    mapping = {
        'sharpe': 'sharpe_ratio',
        'sharpe_ratio': 'sharpe_ratio',
        'calmar': 'calmar_ratio',
        'calmar_ratio': 'calmar_ratio',
        'return': 'annual_return',
        'annual_return': 'annual_return',
        'total_return': 'total_return',
    }
    key = mapping.get(metric_name, metric_name)
    val = metrics.get(key, 0.0)
    if val is None:
        return 0.0
    return float(val)


def _generate_param_grid(param_space: Dict[str, List]) -> List[Dict[str, Any]]:
    """
    生成参数网格

    Args:
        param_space: {param_name: [value1, value2, ...]}

    Returns:
        所有参数组合的列表
    """
    keys = list(param_space.keys())
    values = list(param_space.values())

    combinations = []
    for combo in product(*values):
        combinations.append(dict(zip(keys, combo)))

    return combinations


def _run_single_backtest(
    strategy_name: str,
    params: Dict[str, Any],
    start_date: str,
    end_date: str,
    initial_capital: float,
    benchmark: str,
    rebalance_freq: str,
    top_n: int,
) -> Optional[Dict[str, float]]:
    """
    运行单次回测，返回指标

    Returns:
        指标字典，失败返回 None
    """
    try:
        from .backtest_engine import run_quant_backtest

        result = run_quant_backtest(
            strategy_name=strategy_name,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            benchmark=benchmark,
            rebalance_freq=rebalance_freq,
            walk_forward=False,  # 优化时关闭 walk-forward，手动分 train/test
            strategy_params=params,
            top_n=top_n,
        )

        if 'error' in result:
            logger.warning(f"Backtest error with params {params}: {result['error']}")
            return None

        return result.get('metrics', {})

    except Exception as e:
        logger.warning(f"Backtest exception with params {params}: {e}")
        return None


class GridSearchOptimizer:
    """
    网格搜索参数优化器

    用法:
        optimizer = GridSearchOptimizer(
            strategy_name='multi_factor',
            param_space={
                'top_n': [10, 20, 30],
                'weight_value': [0.15, 0.25, 0.35],
                'weight_momentum': [0.20, 0.30, 0.40],
            },
            metric='sharpe',
        )
        output = optimizer.optimize(
            train_start='2020-01-01', train_end='2023-12-31',
            test_start='2024-01-01', test_end='2025-12-31',
        )
    """

    def __init__(
        self,
        strategy_name: str,
        param_space: Dict[str, List],
        metric: str = 'sharpe',
        max_workers: int = 4,
        initial_capital: float = 1_000_000,
        benchmark: str = '000300',
        rebalance_freq: str = 'monthly',
        top_n: int = 20,
    ):
        self.strategy_name = strategy_name
        self.param_space = param_space
        self.metric = metric
        self.max_workers = max_workers
        self.initial_capital = initial_capital
        self.benchmark = benchmark
        self.rebalance_freq = rebalance_freq
        self.top_n = top_n

        # 验证参数空间大小
        self.param_combinations = _generate_param_grid(param_space)
        if len(self.param_combinations) > MAX_COMBINATIONS:
            raise ValueError(
                f"Parameter space too large: {len(self.param_combinations)} combinations "
                f"(max {MAX_COMBINATIONS}). Reduce parameter grid."
            )

        logger.info(
            f"GridSearchOptimizer: {strategy_name}, {len(self.param_combinations)} combinations, "
            f"metric={metric}"
        )

    def optimize(
        self,
        train_start: str,
        train_end: str,
        test_start: str,
        test_end: str,
    ) -> GridSearchOutput:
        """
        运行网格搜索优化

        对每组参数分别在训练集和测试集上回测，用测试集指标排序，
        检测过拟合。

        Args:
            train_start: 训练集开始日期
            train_end: 训练集结束日期
            test_start: 测试集开始日期
            test_end: 测试集结束日期

        Returns:
            GridSearchOutput
        """
        t0 = time.time()
        n_combos = len(self.param_combinations)
        logger.info(f"Starting grid search: {n_combos} combinations")

        # 1. 并行运行训练集回测
        train_results = self._parallel_backtest(
            self.param_combinations, train_start, train_end
        )

        # 2. 并行运行测试集回测（只对训练集成功的参数）
        valid_params = [p for p, m in zip(self.param_combinations, train_results) if m is not None]
        valid_train_metrics = [m for m in train_results if m is not None]

        if not valid_params:
            logger.error("All train backtests failed")
            return GridSearchOutput(
                best_params={},
                best_test_metric=0.0,
                best_train_metric=0.0,
                all_results=[],
                overfit_warning=True,
                overfit_details="All train backtests failed",
                total_combinations=n_combos,
                elapsed_seconds=time.time() - t0,
                metric_name=self.metric,
                strategy_name=self.strategy_name,
            )

        test_results = self._parallel_backtest(valid_params, test_start, test_end)

        # 3. 汇总结果
        results: List[OptimizationResult] = []
        for params, train_m, test_m in zip(valid_params, valid_train_metrics, test_results):
            train_val = _extract_metric(train_m, self.metric)
            test_val = _extract_metric(test_m, self.metric) if test_m else 0.0

            overfit_ratio = 0.0
            if test_val > 0.001:
                overfit_ratio = train_val / test_val
            elif train_val > 0:
                overfit_ratio = float('inf')

            results.append(OptimizationResult(
                params=params,
                train_metric=train_val,
                test_metric=test_val,
                train_metrics=train_m or {},
                test_metrics=test_m or {},
                overfit_ratio=overfit_ratio,
            ))

        # 4. 按测试集指标排序（降序）
        results.sort(key=lambda r: r.test_metric, reverse=True)

        # 5. 过拟合检测
        overfit_warning, overfit_details = self._check_overfit(results)

        # 6. 构造输出
        best = results[0] if results else None

        all_results_list = []
        for r in results:
            entry = {
                'params': r.params,
                'train_metric': round(r.train_metric, 6),
                'test_metric': round(r.test_metric, 6),
                'overfit_ratio': round(r.overfit_ratio, 3) if r.overfit_ratio != float('inf') else 'inf',
            }
            # 附带关键指标
            if r.test_metrics:
                for k in ['annual_return', 'sharpe_ratio', 'max_drawdown', 'calmar_ratio', 'total_return']:
                    if k in r.test_metrics:
                        entry[f'test_{k}'] = round(float(r.test_metrics[k] or 0), 6)
            if r.train_metrics:
                for k in ['annual_return', 'sharpe_ratio', 'max_drawdown']:
                    if k in r.train_metrics:
                        entry[f'train_{k}'] = round(float(r.train_metrics[k] or 0), 6)
            all_results_list.append(entry)

        elapsed = time.time() - t0
        logger.info(
            f"Grid search complete: best_test_metric={best.test_metric:.4f}, "
            f"overfit_warning={overfit_warning}, elapsed={elapsed:.1f}s"
        )

        return GridSearchOutput(
            best_params=best.params if best else {},
            best_test_metric=best.test_metric if best else 0.0,
            best_train_metric=best.train_metric if best else 0.0,
            all_results=all_results_list,
            overfit_warning=overfit_warning,
            overfit_details=overfit_details,
            total_combinations=n_combos,
            elapsed_seconds=round(elapsed, 2),
            metric_name=self.metric,
            strategy_name=self.strategy_name,
        )

    def _parallel_backtest(
        self,
        param_list: List[Dict[str, Any]],
        start_date: str,
        end_date: str,
    ) -> List[Optional[Dict[str, float]]]:
        """
        并行运行多组参数的回测

        Args:
            param_list: 参数列表
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            与 param_list 对应的指标列表
        """
        results = [None] * len(param_list)

        # 数据准备只需做一次，但因为 run_quant_backtest 内部会自行准备数据，
        # 使用线程池并行执行（数据获取是 IO 密集型）
        def _task(idx: int, params: Dict[str, Any]):
            return idx, _run_single_backtest(
                strategy_name=self.strategy_name,
                params={**params, 'top_n': self.top_n},
                start_date=start_date,
                end_date=end_date,
                initial_capital=self.initial_capital,
                benchmark=self.benchmark,
                rebalance_freq=self.rebalance_freq,
                top_n=self.top_n,
            )

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(_task, i, p): i
                for i, p in enumerate(param_list)
            }
            for future in as_completed(futures):
                try:
                    idx, metrics = future.result()
                    results[idx] = metrics
                except Exception as e:
                    idx = futures[future]
                    logger.warning(f"Task {idx} failed: {e}")

        return results

    def _check_overfit(self, results: List[OptimizationResult]) -> tuple:
        """
        过拟合检测

        检查：
        1. 最优参数的 train/test Sharpe 比值 > 2.0
        2. 所有参数的平均 train/test 差异 > 50%

        Returns:
            (warning: bool, details: str)
        """
        if not results:
            return True, "No valid results"

        warnings = []

        # 检查最优参数
        best = results[0]
        if best.overfit_ratio > OVERFIT_THRESHOLD and best.test_metric > 0:
            warnings.append(
                f"Best params overfit: train {self.metric}={best.train_metric:.4f}, "
                f"test {self.metric}={best.test_metric:.4f}, "
                f"ratio={best.overfit_ratio:.2f} (threshold={OVERFIT_THRESHOLD})"
            )

        # 检查所有参数的平均差异
        valid = [r for r in results if r.test_metric > 0 and r.train_metric > 0]
        if valid:
            ratios = [r.train_metric / r.test_metric for r in valid if r.test_metric > 0.001]
            if ratios:
                avg_ratio = np.mean(ratios)
                if avg_ratio > OVERFIT_THRESHOLD:
                    warnings.append(
                        f"Average overfit ratio across all params: {avg_ratio:.2f} "
                        f"(threshold={OVERFIT_THRESHOLD})"
                    )

                # 检查训练集最优但在测试集表现差的参数数量
                train_best_idx = max(range(len(results)), key=lambda i: results[i].train_metric)
                if train_best_idx != 0:
                    train_best = results[train_best_idx]
                    test_rank = next(
                        (i + 1 for i, r in enumerate(results) if r.params == train_best.params),
                        len(results)
                    )
                    if test_rank > len(results) * 0.5:
                        warnings.append(
                            f"Train-best params rank #{test_rank}/{len(results)} in test — "
                            f"strong signal of overfitting"
                        )

        if warnings:
            return True, "; ".join(warnings)
        return False, "No overfitting detected"
