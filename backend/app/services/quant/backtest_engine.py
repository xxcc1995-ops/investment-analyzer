"""
量化回测引擎

替代 mock 引擎，集成：
- 真实数据（AKShare + EastMoney）
- 5大策略（多因子/均值回归/趋势跟踪/配对交易/集成）
- Walk-Forward 验证
- 风险管理（三层止损 + Kelly仓位 + 回撤控制）
- A股规则（T+1/100股整手/涨跌停）
- 完整绩效指标
"""

import numpy as np
import pandas as pd
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

from .data_provider import get_stock_ohlcv, get_index_daily, get_batch_ohlcv, build_stock_universe, get_snapshot_for_universe
from .cost_model import AShareCostModel, DEFAULT_COST_MODEL
from .risk_manager import RiskManager, RiskConfig
from .metrics import calculate_full_metrics, calc_daily_returns
from .walk_forward import (
    WalkForwardConfig, FoldResult, walk_forward_split,
    aggregate_oos_returns, generate_wf_report
)
from .strategy_base import BaseStrategy, Signal, Position

# 策略注册
from .strategy_multi_factor import MultiFactorStrategy
from .strategy_mean_reversion import MeanReversionStrategy
from .strategy_trend_following import TrendFollowingStrategy
from .strategy_pairs_trading import PairsTradingStrategy
from .strategy_reversal import ReversalStrategy
from .strategy_adaptive import AdaptiveMultiFactorStrategy

logger = logging.getLogger(__name__)

STRATEGY_REGISTRY = {
    'multi_factor': MultiFactorStrategy,
    'mean_reversion': MeanReversionStrategy,
    'trend_following': TrendFollowingStrategy,
    'pairs_trading': PairsTradingStrategy,
    'reversal': ReversalStrategy,
    'adaptive': AdaptiveMultiFactorStrategy,
}


@dataclass
class BacktestConfig:
    """回测配置"""
    strategy_name: str = 'multi_factor'
    start_date: str = '2020-01-01'
    end_date: str = '2025-12-31'
    initial_capital: float = 1_000_000
    benchmark: str = '000300'  # 沪深300
    rebalance_freq: str = 'monthly'
    walk_forward: bool = True
    strategy_params: Optional[Dict] = None
    risk_config: Optional[RiskConfig] = None
    cost_model: Optional[AShareCostModel] = None
    wf_config: Optional[WalkForwardConfig] = None


def run_quant_backtest(
    strategy_name: str = 'multi_factor',
    start_date: str = '2020-01-01',
    end_date: str = '2025-12-31',
    initial_capital: float = 1_000_000,
    benchmark: str = '000300',
    rebalance_freq: str = 'monthly',
    walk_forward: bool = True,
    strategy_params: Optional[Dict] = None,
    top_n: int = 20,
) -> Dict[str, Any]:
    """
    量化回测主入口

    Args:
        strategy_name: 策略名称 (multi_factor/mean_reversion/trend_following/pairs_trading)
        start_date: 回测开始日期
        end_date: 回测结束日期
        initial_capital: 初始资金
        benchmark: 基准指数代码
        rebalance_freq: 再平衡频率 (weekly/monthly/quarterly)
        walk_forward: 是否使用 Walk-Forward 验证
        strategy_params: 策略参数覆盖
        top_n: 选股数量

    Returns:
        完整回测结果字典
    """
    logger.info(f"Starting quant backtest: {strategy_name} from {start_date} to {end_date}")

    # 1. 准备数据
    data_result = _prepare_data(strategy_name, start_date, end_date)
    if 'error' in data_result:
        return data_result

    price_data = data_result['price_data']
    snapshot = data_result['snapshot']
    benchmark_data = data_result['benchmark_data']

    # 2. 创建策略
    params = {'top_n': top_n, **(strategy_params or {})}
    strategy = _create_strategy(strategy_name, params)

    # 3. 创建风险管理器
    risk_config = RiskConfig()
    risk_manager = RiskManager(risk_config)

    # 4. 创建成本模型
    cost_model = DEFAULT_COST_MODEL

    # 5. 运行回测
    if walk_forward:
        result = _run_walk_forward_backtest(
            strategy=strategy,
            price_data=price_data,
            snapshot=snapshot,
            benchmark_data=benchmark_data,
            initial_capital=initial_capital,
            risk_manager=risk_manager,
            cost_model=cost_model,
            rebalance_freq=rebalance_freq,
        )
    else:
        result = _run_in_sample_backtest(
            strategy=strategy,
            price_data=price_data,
            snapshot=snapshot,
            benchmark_data=benchmark_data,
            initial_capital=initial_capital,
            risk_manager=risk_manager,
            cost_model=cost_model,
            rebalance_freq=rebalance_freq,
        )

    result['strategy'] = strategy_name
    result['params'] = params
    result['start_date'] = start_date
    result['end_date'] = end_date
    result['walk_forward'] = walk_forward

    logger.info(f"Backtest complete: annual_return={result.get('metrics', {}).get('annual_return', 0):.2%}")
    return result


def _prepare_data(strategy_name: str, start_date: str, end_date: str) -> Dict:
    """准备回测数据"""
    logger.info("Preparing backtest data...")

    # 构建股票池
    codes = build_stock_universe(max_stocks=300)
    if not codes:
        return {'error': 'Universe is empty'}

    logger.info(f"Universe: {len(codes)} stocks")

    # 获取历史数据（需要额外的历史用于因子计算）
    lookback_start = (pd.Timestamp(start_date) - timedelta(days=400)).strftime('%Y-%m-%d')

    # 批量获取 OHLCV
    price_data = get_batch_ohlcv(codes, lookback_start, end_date)

    logger.info(f"Price data: {len(price_data)} stocks with sufficient history")

    if len(price_data) < 20:
        return {'error': f'Insufficient stocks with data: {len(price_data)}'}

    # 获取快照
    snapshot = get_snapshot_for_universe(list(price_data.keys()))

    # 获取基准数据
    benchmark_data = get_index_daily('000300', lookback_start, end_date)

    return {
        'price_data': price_data,
        'snapshot': snapshot,
        'codes': list(price_data.keys()),
        'benchmark_data': benchmark_data,
    }


def _create_strategy(name: str, params: Dict) -> BaseStrategy:
    """创建策略实例"""
    if name not in STRATEGY_REGISTRY:
        raise ValueError(f"Unknown strategy: {name}. Available: {list(STRATEGY_REGISTRY.keys())}")
    return STRATEGY_REGISTRY[name](params)


def _run_in_sample_backtest(
    strategy: BaseStrategy,
    price_data: Dict[str, pd.DataFrame],
    snapshot: pd.DataFrame,
    benchmark_data: Optional[pd.DataFrame],
    initial_capital: float,
    risk_manager: RiskManager,
    cost_model: AShareCostModel,
    rebalance_freq: str,
) -> Dict[str, Any]:
    """运行样本内回测"""
    logger.info("Running in-sample backtest...")

    # 拟合策略
    strategy.fit(price_data, snapshot)

    # 获取所有交易日
    all_dates = _get_trading_dates(price_data)
    if not all_dates:
        return {'error': 'No trading dates found'}

    # 初始化
    capital = initial_capital
    positions = {}  # {code: {'shares': int, 'entry_price': float, 'entry_date': str, 'peak_price': float}}
    equity_curve = []
    daily_returns = []
    trade_log = []
    weights_history = []
    prev_value = initial_capital

    risk_manager.reset()
    risk_manager._peak_value = initial_capital

    # 确定再平衡日
    rebalance_dates = _get_rebalance_dates(all_dates, rebalance_freq)

    for i, date in enumerate(all_dates):
        date_str = str(date)[:10]

        # 更新持仓市值
        portfolio_value = capital
        for code, pos in list(positions.items()):
            if code in price_data:
                df = price_data[code]
                day_data = df[df['date'] == date]
                if not day_data.empty:
                    price = float(day_data['close'].iloc[0])
                    pos['peak_price'] = max(pos['peak_price'], price)
                    portfolio_value += pos['shares'] * price

                    # 止损检查
                    should_stop, reason = risk_manager.check_stop_loss(
                        pos['entry_price'], price, pos['peak_price']
                    )
                    if should_stop:
                        # 执行止损
                        sell_amount = pos['shares'] * price
                        cost = cost_model.calc_sell_cost(sell_amount)
                        capital += sell_amount - cost
                        trade_log.append({
                            'date': date_str, 'code': code, 'action': 'sell',
                            'shares': pos['shares'], 'price': price,
                            'amount': sell_amount, 'cost': cost, 'reason': reason,
                        })
                        del positions[code]

        # 回撤控制
        action, scale = risk_manager.check_drawdown_control(portfolio_value, initial_capital)
        if action == 'close':
            for code in list(positions.keys()):
                pos = positions[code]
                if code in price_data:
                    df = price_data[code]
                    day_data = df[df['date'] == date]
                    if not day_data.empty:
                        price = float(day_data['close'].iloc[0])
                        sell_amount = pos['shares'] * price
                        cost = cost_model.calc_sell_cost(sell_amount)
                        capital += sell_amount - cost
                        trade_log.append({
                            'date': date_str, 'code': code, 'action': 'sell',
                            'shares': pos['shares'], 'price': price,
                            'amount': sell_amount, 'cost': cost, 'reason': 'drawdown_control',
                        })
            positions.clear()
        elif action == 'reduce' and scale < 1.0:
            for code in list(positions.keys()):
                pos = positions[code]
                reduce_shares = int(pos['shares'] * (1 - scale) / 100) * 100
                if reduce_shares >= 100 and code in price_data:
                    df = price_data[code]
                    day_data = df[df['date'] == date]
                    if not day_data.empty:
                        price = float(day_data['close'].iloc[0])
                        sell_amount = reduce_shares * price
                        cost = cost_model.calc_sell_cost(sell_amount)
                        capital += sell_amount - cost
                        pos['shares'] -= reduce_shares
                        trade_log.append({
                            'date': date_str, 'code': code, 'action': 'sell',
                            'shares': reduce_shares, 'price': price,
                            'amount': sell_amount, 'cost': cost, 'reason': 'drawdown_reduce',
                        })

        # 再平衡
        if date_str in rebalance_dates:
            # 获取当日数据快照
            day_snapshot = snapshot.copy()

            # 生成信号
            signals = strategy.generate_signals(price_data, day_snapshot, date_str)

            # 构建目标组合
            target_positions = strategy.get_portfolio(signals, positions, capital)

            # 执行再平衡
            capital = _execute_rebalance(
                positions, target_positions, price_data, date_str,
                capital, cost_model, risk_manager, trade_log
            )

        # 记录每日净值
        portfolio_value = capital
        for code, pos in positions.items():
            if code in price_data:
                df = price_data[code]
                day_data = df[df['date'] == date]
                if not day_data.empty:
                    portfolio_value += pos['shares'] * float(day_data['close'].iloc[0])

        daily_ret = (portfolio_value - prev_value) / prev_value if prev_value > 0 else 0
        daily_returns.append(daily_ret)
        equity_curve.append(portfolio_value)
        prev_value = portfolio_value

        # 记录权重
        weights = {}
        for code, pos in positions.items():
            if portfolio_value > 0:
                if code in price_data:
                    df = price_data[code]
                    day_data = df[df['date'] == date]
                    if not day_data.empty:
                        mv = pos['shares'] * float(day_data['close'].iloc[0])
                        weights[code] = mv / portfolio_value
        weights_history.append(weights)

    # 计算基准净值
    benchmark_curve = None
    if benchmark_data is not None and not benchmark_data.empty:
        bench_close = benchmark_data['close'].values
        if len(bench_close) > 0:
            benchmark_curve = bench_close / bench_close[0] * initial_capital

    # 计算指标
    equity_arr = np.array(equity_curve)
    metrics = calculate_full_metrics(
        equity_arr,
        benchmark_curve=benchmark_curve,
        weights_history=weights_history,
    )

    return {
        'metrics': metrics,
        'equity_curve': equity_curve,
        'daily_returns': daily_returns,
        'trade_log': trade_log,
        'final_value': equity_curve[-1] if equity_curve else initial_capital,
    }


def _run_walk_forward_backtest(
    strategy: BaseStrategy,
    price_data: Dict[str, pd.DataFrame],
    snapshot: pd.DataFrame,
    benchmark_data: Optional[pd.DataFrame],
    initial_capital: float,
    risk_manager: RiskManager,
    cost_model: AShareCostModel,
    rebalance_freq: str,
) -> Dict[str, Any]:
    """运行 Walk-Forward 验证回测"""
    logger.info("Running walk-forward backtest...")

    # 获取所有交易日
    all_dates = _get_trading_dates(price_data)
    if len(all_dates) < 600:
        logger.warning("Insufficient data for walk-forward, falling back to in-sample")
        return _run_in_sample_backtest(
            strategy, price_data, snapshot, benchmark_data,
            initial_capital, risk_manager, cost_model, rebalance_freq
        )

    # Walk-Forward 配置
    wf_config = WalkForwardConfig(
        train_days=504,
        test_days=63,
        step_days=63,
        anchored=True,
    )

    splits = walk_forward_split(all_dates, wf_config)
    logger.info(f"Walk-forward: {len(splits)} folds")

    fold_results = []

    for fold_id, (train_start, train_end, test_start, test_end) in enumerate(splits):
        logger.info(f"Fold {fold_id}: train[{train_start}:{train_end}] test[{test_start}:{test_end}]")

        # 训练期数据
        train_dates = all_dates[train_start:train_end]
        test_dates = all_dates[test_start:test_end]

        # 在训练期拟合策略
        train_price_data = _filter_data_by_dates(price_data, train_dates)
        strategy.fit(train_price_data, snapshot)

        # 在测试期运行
        fold_result = _run_fold(
            strategy, price_data, test_dates, test_start,
            initial_capital / len(splits),  # 平均分配资金
            risk_manager, cost_model, rebalance_freq, fold_id,
            train_dates[0] if train_dates else '', train_dates[-1] if train_dates else '',
            test_dates[0] if test_dates else '', test_dates[-1] if test_dates else '',
        )

        if fold_result is not None:
            fold_results.append(fold_result)

    if not fold_results:
        return {'error': 'All walk-forward folds failed'}

    # 聚合OOS结果
    oos_metrics = aggregate_oos_returns(fold_results)

    # 生成报告
    report = generate_wf_report(fold_results, oos_metrics)

    return {
        'metrics': {
            'annual_return': oos_metrics['oos_annual_return'],
            'total_return': oos_metrics['oos_total_return'],
            'sharpe_ratio': oos_metrics['oos_sharpe'],
            'max_drawdown': oos_metrics['oos_max_drawdown'],
            'n_folds': oos_metrics['n_folds'],
            'fold_returns': oos_metrics['fold_returns'],
            'param_stability': oos_metrics.get('param_stability', {}),
        },
        'walk_forward_report': report,
        'fold_details': [
            {
                'fold_id': f.fold_id,
                'test_start': f.test_start,
                'test_end': f.test_end,
                'total_return': f.total_return,
                'sharpe_ratio': f.sharpe_ratio,
                'max_drawdown': f.max_drawdown,
                'trade_count': f.trade_count,
            }
            for f in fold_results
        ],
        'equity_curve': _build_wf_equity_curve(fold_results),
        'final_value': initial_capital * (1 + oos_metrics['oos_total_return']),
    }


def _run_fold(strategy, price_data, test_dates, test_start_idx,
              capital, risk_manager, cost_model, rebalance_freq, fold_id,
              train_start, train_end, test_start, test_end) -> Optional[FoldResult]:
    """运行单个 Walk-Forward 折"""
    positions = {}
    equity_curve = [capital]
    daily_returns = []
    trade_count = 0
    prev_value = capital

    risk_manager.reset()
    risk_manager._peak_value = capital

    rebalance_dates = _get_rebalance_dates(test_dates, rebalance_freq)
    snapshot = get_snapshot_for_universe(list(price_data.keys()))

    for date in test_dates:
        date_str = str(date)[:10]

        # 更新持仓
        portfolio_value = capital
        for code, pos in list(positions.items()):
            if code in price_data:
                df = price_data[code]
                day_data = df[df['date'] == date]
                if not day_data.empty:
                    price = float(day_data['close'].iloc[0])
                    pos['peak_price'] = max(pos.get('peak_price', price), price)
                    portfolio_value += pos['shares'] * price

                    # 止损
                    should_stop, _ = risk_manager.check_stop_loss(
                        pos['entry_price'], price, pos['peak_price']
                    )
                    if should_stop:
                        sell_amount = pos['shares'] * price
                        cost = cost_model.calc_sell_cost(sell_amount)
                        capital += sell_amount - cost
                        trade_count += 1
                        del positions[code]

        # 再平衡
        if date_str in rebalance_dates:
            signals = strategy.generate_signals(price_data, snapshot, date_str)
            target_positions = strategy.get_portfolio(signals, positions, capital)
            capital = _execute_rebalance(
                positions, target_positions, price_data, date_str,
                capital, cost_model, risk_manager, []
            )
            trade_count += len(target_positions)

        # 记录净值
        portfolio_value = capital
        for code, pos in positions.items():
            if code in price_data:
                df = price_data[code]
                day_data = df[df['date'] == date]
                if not day_data.empty:
                    portfolio_value += pos['shares'] * float(day_data['close'].iloc[0])

        daily_ret = (portfolio_value - prev_value) / prev_value if prev_value > 0 else 0
        daily_returns.append(daily_ret)
        equity_curve.append(portfolio_value)
        prev_value = portfolio_value

    if len(equity_curve) < 2:
        return None

    equity_arr = np.array(equity_curve)
    total_return = equity_arr[-1] / equity_arr[0] - 1
    years = len(daily_returns) / 252

    annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
    sharpe = 0
    max_dd = 0
    if len(daily_returns) > 20:
        dr = np.array(daily_returns)
        sharpe = float((np.mean(dr) - 0.02 / 252) / np.std(dr, ddof=1) * np.sqrt(252))
        peak = np.maximum.accumulate(equity_arr)
        dd = (equity_arr - peak) / peak
        max_dd = float(np.min(dd))

    return FoldResult(
        fold_id=fold_id,
        train_start=train_start,
        train_end=train_end,
        test_start=test_start,
        test_end=test_end,
        daily_returns=np.array(daily_returns),
        equity_curve=equity_arr,
        total_return=float(total_return),
        annual_return=float(annual_return),
        sharpe_ratio=float(sharpe),
        max_drawdown=float(max_dd),
        trade_count=trade_count,
    )


def _execute_rebalance(positions, target_positions, price_data, date_str,
                       capital, cost_model, risk_manager, trade_log) -> float:
    """执行再平衡交易"""
    # 先卖出不在目标中的持仓
    codes_to_sell = [c for c in positions if c not in target_positions]
    for code in codes_to_sell:
        pos = positions[code]
        if code in price_data:
            df = price_data[code]
            day_data = df[df['date'] == pd.Timestamp(date_str)]
            if not day_data.empty:
                price = float(day_data['close'].iloc[0])
                sell_amount = pos['shares'] * price
                cost = cost_model.calc_sell_cost(sell_amount)
                capital += sell_amount - cost
                trade_log.append({
                    'date': date_str, 'code': code, 'action': 'sell',
                    'shares': pos['shares'], 'price': price,
                    'amount': sell_amount, 'cost': cost,
                })
                del positions[code]

    # 再买入目标中的新持仓
    codes_to_buy = [c for c in target_positions if c not in positions]
    if codes_to_buy:
        per_stock = capital * 0.9 / len(codes_to_buy)  # 留10%现金
        for code in codes_to_buy:
            if code in price_data:
                df = price_data[code]
                day_data = df[df['date'] == pd.Timestamp(date_str)]
                if not day_data.empty:
                    price = float(day_data['close'].iloc[0])
                    if price > 0:
                        shares = int(per_stock / (price * 1.001) / 100) * 100
                        if shares >= 100:
                            buy_amount = shares * price
                            cost = cost_model.calc_buy_cost(buy_amount)
                            if buy_amount + cost <= capital:
                                capital -= buy_amount + cost
                                positions[code] = {
                                    'shares': shares,
                                    'entry_price': price,
                                    'entry_date': date_str,
                                    'peak_price': price,
                                }
                                trade_log.append({
                                    'date': date_str, 'code': code, 'action': 'buy',
                                    'shares': shares, 'price': price,
                                    'amount': buy_amount, 'cost': cost,
                                })

    return capital


def _get_trading_dates(price_data: Dict[str, pd.DataFrame]) -> List:
    """获取所有交易日（取最长的股票）"""
    max_len = 0
    dates = None
    for df in price_data.values():
        if len(df) > max_len:
            max_len = len(df)
            dates = df['date'].tolist()
    return dates or []


def _get_rebalance_dates(dates: List, freq: str) -> set:
    """确定再平衡日期"""
    rebalance_dates = set()
    prev_month = None
    prev_week = None

    for date in dates:
        date_str = str(date)[:10]
        ts = pd.Timestamp(date)

        if freq == 'monthly':
            if prev_month is not None and ts.month != prev_month:
                rebalance_dates.add(date_str)
            prev_month = ts.month
        elif freq == 'weekly':
            week = ts.isocalendar()[1]
            if prev_week is not None and week != prev_week:
                rebalance_dates.add(date_str)
            prev_week = week
        elif freq == 'quarterly':
            if prev_month is not None and ts.month != prev_month and ts.month in [1, 4, 7, 10]:
                rebalance_dates.add(date_str)
            prev_month = ts.month

    return rebalance_dates


def _filter_data_by_dates(price_data, dates):
    """按日期范围过滤数据"""
    if not dates:
        return price_data
    start = dates[0]
    end = dates[-1]
    filtered = {}
    for code, df in price_data.items():
        mask = (df['date'] >= start) & (df['date'] <= end)
        fdf = df[mask]
        if len(fdf) > 20:
            filtered[code] = fdf
    return filtered


def _build_wf_equity_curve(fold_results: List[FoldResult]) -> List[float]:
    """构建 Walk-Forward 净值曲线"""
    curve = [1.0]
    for fold in fold_results:
        for ret in fold.daily_returns:
            curve.append(curve[-1] * (1 + ret))
    return curve
