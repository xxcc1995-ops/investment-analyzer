"""
策略3：趋势跟踪多周期

灵感来源：Man AHL 系统化趋势跟踪

信号生成：
- 短期：10日EMA vs 50日EMA
- 中期：50日EMA vs 200日EMA
- 长期：价格 > 200日EMA 且 200日EMA上升

波动率目标：
- 仓位 = 目标波动率 / 实现波动率
- 低波时加仓，高波时减仓

月度再平衡，选趋势最强的15-20只
"""

import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Optional, Tuple

from .strategy_base import BaseStrategy, Signal, Position

logger = logging.getLogger(__name__)


def ema(prices: np.ndarray, span: int) -> np.ndarray:
    """指数移动平均线"""
    n = len(prices)
    if n < span:
        return prices.copy()

    alpha = 2.0 / (span + 1)
    result = np.zeros(n)
    result[0] = prices[0]

    for i in range(1, n):
        result[i] = alpha * prices[i] + (1 - alpha) * result[i - 1]

    return result


def sma(prices: np.ndarray, window: int) -> np.ndarray:
    """简单移动平均线"""
    n = len(prices)
    result = np.full(n, np.nan)
    for i in range(window - 1, n):
        result[i] = np.mean(prices[i - window + 1:i + 1])
    return result


def calc_trend_signal(prices: np.ndarray) -> float:
    """
    多周期趋势信号

    短期 (0.3): EMA10 > EMA50 → +1, 否则 -1
    中期 (0.4): EMA50 > EMA200 → +1, 否则 -1
    长期 (0.3): 价格 > EMA200 且 EMA200上升 → +1, 否则 -1

    Returns:
        综合信号 [-1, 1]
    """
    if len(prices) < 200:
        return 0.0

    ema10 = ema(prices, 10)
    ema50 = ema(prices, 50)
    ema200 = ema(prices, 200)

    # 短期
    short = 1.0 if ema10[-1] > ema50[-1] else -1.0

    # 中期
    medium = 1.0 if ema50[-1] > ema200[-1] else -1.0

    # 长期（价格在200日线上方且200日线在上升）
    long = 1.0 if (prices[-1] > ema200[-1] and ema200[-1] > ema200[-5]) else -1.0

    return 0.3 * short + 0.4 * medium + 0.3 * long


def calc_realized_vol(daily_returns: np.ndarray, lookback: int = 20) -> float:
    """计算实现波动率（年化）"""
    if len(daily_returns) < lookback:
        return 0.30  # 默认30%
    recent = daily_returns[-lookback:]
    return float(np.std(recent, ddof=1) * np.sqrt(252))


def volatility_target_weight(realized_vol: float, target_vol: float = 0.20) -> float:
    """
    波动率目标仓位缩放

    当市场平静时加仓，波动时减仓。这是 Man AHL 的核心机制。
    """
    if realized_vol < 0.01:
        return 2.0  # 最大2倍
    return min(target_vol / realized_vol, 2.0)


class TrendFollowingStrategy(BaseStrategy):
    """趋势跟踪多周期策略"""

    name = 'trend_following'
    description = 'Man AHL风格：三层EMA+波动率目标趋势跟踪'
    version = '1.0'

    DEFAULT_PARAMS = {
        'top_n': 20,               # 选股数量
        'target_vol': 0.20,        # 目标波动率
        'ema_fast': 10,            # 快速EMA周期
        'ema_medium': 50,          # 中速EMA周期
        'ema_slow': 200,           # 慢速EMA周期
        'vol_lookback': 20,        # 波动率计算期
        'min_signal': 0.3,         # 最小信号强度
    }

    def __init__(self, params: Optional[Dict] = None):
        super().__init__({**self.DEFAULT_PARAMS, **(params or {})})
        self._trend_signals = {}
        self._volatilities = {}

    def fit(self, price_data: Dict[str, pd.DataFrame],
            fundamental_data: Optional[pd.DataFrame] = None) -> 'TrendFollowingStrategy':
        """拟合：计算趋势信号和波动率"""
        self._trend_signals = {}
        self._volatilities = {}

        for code, df in price_data.items():
            if len(df) < 200:
                continue

            prices = df['close'].values.astype(float)
            daily_returns = np.diff(np.log(prices))

            # 趋势信号
            signal = calc_trend_signal(prices)
            self._trend_signals[code] = signal

            # 波动率
            vol = calc_realized_vol(daily_returns, self.params['vol_lookback'])
            self._volatilities[code] = vol

        self._is_fitted = True
        return self

    def generate_signals(self, price_data: Dict[str, pd.DataFrame],
                         fundamental_data: Optional[pd.DataFrame] = None,
                         current_date: Optional[str] = None) -> List[Signal]:
        """
        生成趋势跟踪信号

        只买趋势信号为正且强度超过阈值的股票
        """
        signals = []
        min_signal = self.params['min_signal']

        for code, df in price_data.items():
            if code not in self._trend_signals:
                continue

            trend = self._trend_signals[code]
            vol = self._volatilities.get(code, 0.30)

            if trend >= min_signal:
                # 波动率加权的信号强度
                vol_weight = volatility_target_weight(vol, self.params['target_vol'])
                strength = abs(trend) * min(vol_weight, 1.5)

                signals.append(Signal(
                    code=code,
                    direction=1,
                    strength=float(strength),
                    reason=f"Trend={trend:.2f}, Vol={vol:.1%}, VolWeight={vol_weight:.2f}"
                ))

        # 按信号强度排序
        signals.sort(key=lambda s: s.strength, reverse=True)

        return signals

    def get_portfolio(self, signals: List[Signal],
                      current_positions: Dict[str, Position],
                      available_capital: float) -> Dict[str, Position]:
        """波动率加权组合"""
        top_n = self.params['top_n']
        selected = [s for s in signals if s.direction == 1][:top_n]

        if not selected:
            return {}

        # 计算波动率加权
        total_strength = sum(s.strength for s in selected)
        if total_strength <= 0:
            return {}

        positions = {}
        for signal in selected:
            weight = signal.strength / total_strength
            positions[signal.code] = Position(
                code=signal.code,
                shares=0,
                entry_price=0,
                entry_date='',
                weight=weight,
            )

        return positions

    def get_trend_signals(self) -> Dict[str, float]:
        """获取趋势信号（用于分析）"""
        return self._trend_signals.copy()

    def get_volatilities(self) -> Dict[str, float]:
        """获取波动率（用于分析）"""
        return self._volatilities.copy()
