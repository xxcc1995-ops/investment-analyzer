"""
量化回测 API

端点：
- GET /quant/strategies — 策略列表
- POST /quant/backtest — 单策略回测
- POST /quant/ensemble — 多策略集成回测
- GET /quant/factor-analysis — 因子分析
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Dict, List, Optional, Any
import logging
import traceback
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/quant", tags=["quant"])


@router.get("/strategies")
async def list_quant_strategies():
    """获取可用策略列表"""
    from ..services.quant.strategy_multi_factor import MultiFactorStrategy
    from ..services.quant.strategy_mean_reversion import MeanReversionStrategy
    from ..services.quant.strategy_trend_following import TrendFollowingStrategy
    from ..services.quant.strategy_pairs_trading import PairsTradingStrategy
    from ..services.quant.strategy_reversal import ReversalStrategy
    from ..services.quant.strategy_ensemble import run_ensemble_backtest

    strategies = [
        {
            "name": "multi_factor",
            "display_name": "多因子Alpha",
            "description": "AQR/WorldQuant风格：价值25% + 动量30% + 质量25% + 低波20%",
            "version": "1.0",
            "params": MultiFactorStrategy.DEFAULT_PARAMS,
            "inspiration": "AQR Capital (Cliff Asness) + WorldQuant (Igor Tulchinsky)",
        },
        {
            "name": "mean_reversion",
            "display_name": "均值回归Z-Score",
            "description": "Renaissance风格：Kalman滤波估计公允价格，Z-Score度量偏离",
            "version": "1.0",
            "params": MeanReversionStrategy.DEFAULT_PARAMS,
            "inspiration": "Renaissance Technologies (Jim Simons)",
        },
        {
            "name": "trend_following",
            "display_name": "趋势跟踪多周期",
            "description": "Man AHL风格：三层EMA(10/50/200) + 波动率目标仓位",
            "version": "1.0",
            "params": TrendFollowingStrategy.DEFAULT_PARAMS,
            "inspiration": "Man AHL (Systematic Trend Following)",
        },
        {
            "name": "pairs_trading",
            "display_name": "配对交易",
            "description": "DE Shaw风格：同行业协整配对，价差Z-Score交易",
            "version": "1.0",
            "params": PairsTradingStrategy.DEFAULT_PARAMS,
            "inspiration": "D.E. Shaw (Statistical Arbitrage)",
        },
        {
            "name": "reversal",
            "display_name": "短期反转",
            "description": "A股最强因子：买入过去1周跌幅最大的股票，持有1-2周反弹",
            "version": "1.0",
            "params": ReversalStrategy.DEFAULT_PARAMS,
            "inspiration": "Liu, Stambaugh, Yuan (2019) - A股短期反转效应",
        },
        {
            "name": "ensemble",
            "display_name": "多策略集成",
            "description": "Citadel/Millennium风格：风险平价分配 + 动态权重 + 相关性监控",
            "version": "1.0",
            "params": {},
            "inspiration": "Citadel (Ken Griffin) + Millennium (Izzy Englander)",
        },
    ]

    return {"strategies": strategies}


@router.post("/backtest")
async def run_quant_backtest_api(request: Dict[str, Any]):
    """
    运行量化策略回测

    请求体：
    {
        "strategy": "multi_factor",
        "start_date": "2020-01-01",
        "end_date": "2025-12-31",
        "initial_capital": 1000000,
        "benchmark": "000300",
        "rebalance_freq": "monthly",
        "walk_forward": true,
        "top_n": 20,
        "strategy_params": {}
    }
    """
    try:
        strategy = request.get('strategy', 'multi_factor')

        if strategy == 'ensemble':
            # 集成策略
            from ..services.quant.strategy_ensemble import run_ensemble_backtest
            result = run_ensemble_backtest(
                strategy_names=request.get('strategies', ['multi_factor', 'mean_reversion', 'trend_following']),
                start_date=request.get('start_date', '2020-01-01'),
                end_date=request.get('end_date', '2025-12-31'),
                initial_capital=request.get('initial_capital', 1_000_000),
                benchmark=request.get('benchmark', '000300'),
                allocation_method=request.get('allocation_method', 'risk_parity'),
                walk_forward=request.get('walk_forward', True),
            )
        else:
            # 单策略
            from ..services.quant.backtest_engine import run_quant_backtest
            result = run_quant_backtest(
                strategy_name=strategy,
                start_date=request.get('start_date', '2020-01-01'),
                end_date=request.get('end_date', '2025-12-31'),
                initial_capital=request.get('initial_capital', 1_000_000),
                benchmark=request.get('benchmark', '000300'),
                rebalance_freq=request.get('rebalance_freq', 'monthly'),
                walk_forward=request.get('walk_forward', True),
                strategy_params=request.get('strategy_params'),
                top_n=request.get('top_n', 20),
            )

        if 'error' in result:
            raise HTTPException(status_code=400, detail=result['error'])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Quant backtest error: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ensemble")
async def run_ensemble_api(request: Dict[str, Any]):
    """
    运行多策略集成回测

    请求体：
    {
        "strategies": ["multi_factor", "mean_reversion", "trend_following"],
        "start_date": "2020-01-01",
        "end_date": "2025-12-31",
        "initial_capital": 1000000,
        "benchmark": "000300",
        "allocation_method": "risk_parity",
        "walk_forward": true
    }
    """
    try:
        from ..services.quant.strategy_ensemble import run_ensemble_backtest

        result = run_ensemble_backtest(
            strategy_names=request.get('strategies', ['multi_factor', 'mean_reversion', 'trend_following']),
            start_date=request.get('start_date', '2020-01-01'),
            end_date=request.get('end_date', '2025-12-31'),
            initial_capital=request.get('initial_capital', 1_000_000),
            benchmark=request.get('benchmark', '000300'),
            allocation_method=request.get('allocation_method', 'risk_parity'),
            walk_forward=request.get('walk_forward', True),
        )

        if 'error' in result:
            raise HTTPException(status_code=400, detail=result['error'])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ensemble backtest error: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/factor-analysis")
async def factor_analysis(
    factor: str = Query('momentum', description="因子名称"),
    start_date: str = Query('2020-01-01'),
    end_date: str = Query('2025-12-31'),
):
    """
    单因子分析

    分析单个因子的IC、分组收益、换手率等
    """
    try:
        from ..services.quant.factors import (
            calc_momentum_factor, calc_value_factor,
            calc_low_vol_factor, calc_reversal_factor,
            calc_factor_ic, calc_factor_ir
        )
        from ..services.quant.data_provider import get_stock_snapshot, get_batch_ohlcv
        from ..services.quant.universe import build_universe

        # 获取数据
        snapshot = get_stock_snapshot()
        if snapshot is None:
            raise HTTPException(status_code=500, detail="Failed to fetch snapshot")

        universe = build_universe()
        codes = universe['code'].tolist()[:100]  # 限制数量

        # 获取价格数据
        price_data = get_batch_ohlcv(codes, start_date, end_date)

        if not price_data:
            raise HTTPException(status_code=500, detail="No price data available")

        # 计算因子值
        snapshot_filtered = snapshot[snapshot['code'].isin(price_data.keys())]

        if factor == 'momentum':
            close_series = {c: df['close'] for c, df in price_data.items()}
            factor_values = calc_momentum_factor(close_series)
        elif factor == 'value':
            pe = snapshot_filtered.set_index('code')['pe_ttm']
            pb = snapshot_filtered.set_index('code')['pb']
            factor_values = calc_value_factor(pe, pb)
        elif factor == 'low_vol':
            returns = {c: df['close'].pct_change().dropna() for c, df in price_data.items()}
            factor_values = calc_low_vol_factor(returns)
        elif factor == 'reversal':
            close_series = {c: df['close'] for c, df in price_data.items()}
            factor_values = calc_reversal_factor(close_series)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown factor: {factor}")

        # 计算分组收益
        n_groups = 5
        quantile_returns = {}
        if len(factor_values) > 0:
            factor_df = pd.DataFrame({'factor': factor_values})
            factor_df['quantile'] = pd.qcut(factor_df['factor'], n_groups, labels=False, duplicates='drop')

            for q in range(n_groups):
                group_codes = factor_df[factor_df['quantile'] == q].index.tolist()
                # 计算该组的平均收益
                group_returns = []
                for code in group_codes:
                    if code in price_data:
                        df = price_data[code]
                        if len(df) > 21:
                            ret = df['close'].iloc[-1] / df['close'].iloc[-21] - 1
                            group_returns.append(ret)
                if group_returns:
                    quantile_returns[f'Q{q+1}'] = float(np.mean(group_returns))

        return {
            'factor': factor,
            'n_stocks': len(factor_values),
            'quantile_returns': quantile_returns,
            'factor_mean': float(factor_values.mean()) if len(factor_values) > 0 else 0,
            'factor_std': float(factor_values.std()) if len(factor_values) > 0 else 0,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Factor analysis error: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))
