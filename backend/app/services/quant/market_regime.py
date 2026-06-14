"""
市场环境检测模块

判断当前市场状态：牛市/熊市/震荡
用于动态调整策略权重

方法：
1. 指数均线系统（MA20/MA60/MA120）
2. 市场宽度（上涨股票比例）
3. 波动率环境（VIX等价物）
"""

import numpy as np
import pandas as pd
import logging
from typing import Dict, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    BULL = 'bull'       # 牛市
    BEAR = 'bear'       # 熊市
    SIDEWAYS = 'sideways'  # 震荡


def detect_regime(index_prices: np.ndarray, lookback: int = 120) -> Tuple[MarketRegime, float]:
    """
    检测市场环境

    基于沪深300指数的均线系统和趋势强度

    Args:
        index_prices: 指数收盘价序列
        lookback: 回望窗口

    Returns:
        (市场环境, 置信度 0-1)
    """
    if len(index_prices) < lookback:
        return MarketRegime.SIDEWAYS, 0.5

    current = index_prices[-1]

    # 计算均线
    ma20 = np.mean(index_prices[-20:])
    ma60 = np.mean(index_prices[-60:])
    ma120 = np.mean(index_prices[-120:])

    # 趋势强度：价格相对120日均线的偏离度
    trend_strength = (current - ma120) / ma120

    # 均线排列
    bullish_alignment = ma20 > ma60 > ma120  # 多头排列
    bearish_alignment = ma20 < ma60 < ma120  # 空头排列

    # 近期动量（20日收益）
    recent_return = (current - index_prices[-20]) / index_prices[-20]

    # 波动率
    returns = np.diff(np.log(index_prices[-60:]))
    volatility = np.std(returns) * np.sqrt(252)

    # 综合判断
    bull_score = 0
    bear_score = 0

    # 均线排列
    if bullish_alignment:
        bull_score += 2
    elif bearish_alignment:
        bear_score += 2

    # 趋势强度
    if trend_strength > 0.05:
        bull_score += 1
    elif trend_strength < -0.05:
        bear_score += 1

    # 近期动量
    if recent_return > 0.03:
        bull_score += 1
    elif recent_return < -0.03:
        bear_score += 1

    # 价格位置
    if current > ma20:
        bull_score += 1
    else:
        bear_score += 1

    # 判断
    if bull_score >= 3:
        confidence = min(bull_score / 5, 1.0)
        return MarketRegime.BULL, confidence
    elif bear_score >= 3:
        confidence = min(bear_score / 5, 1.0)
        return MarketRegime.BEAR, confidence
    else:
        return MarketRegime.SIDEWAYS, 0.5


def get_regime_allocation(regime: MarketRegime, confidence: float) -> Dict[str, float]:
    """
    根据市场环境分配策略权重

    牛市：多因子为主（动量+价值）
    熊市：均值回归为主（防御）
    震荡：均衡分配

    Returns:
        {strategy_name: weight}
    """
    if regime == MarketRegime.BULL:
        return {
            'multi_factor': 0.40,
            'mean_reversion': 0.20,
            'trend_following': 0.30,
            'pairs_trading': 0.10,
        }
    elif regime == MarketRegime.BEAR:
        return {
            'multi_factor': 0.15,
            'mean_reversion': 0.50,
            'trend_following': 0.10,
            'pairs_trading': 0.25,
        }
    else:  # SIDEWAYS
        return {
            'multi_factor': 0.25,
            'mean_reversion': 0.35,
            'trend_following': 0.15,
            'pairs_trading': 0.25,
        }


def calc_regime_scale_factor(regime: MarketRegime, confidence: float,
                              current_drawdown: float) -> float:
    """
    根据市场环境计算仓位缩放因子

    牛市：满仓（1.0）
    熊市：减仓（0.5-0.7）
    震荡：正常（0.8）

    额外：如果组合回撤 > 10%，进一步减仓
    """
    base_scale = {
        MarketRegime.BULL: 1.0,
        MarketRegime.BEAR: 0.6,
        MarketRegime.SIDEWAYS: 0.8,
    }[regime]

    # 回撤调整
    if current_drawdown < -0.15:
        base_scale *= 0.5
    elif current_drawdown < -0.10:
        base_scale *= 0.7

    return base_scale
