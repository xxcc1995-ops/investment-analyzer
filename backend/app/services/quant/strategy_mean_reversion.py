"""
策略2：均值回归 Z-Score

灵感来源：Renaissance Technologies 统计套利方法

核心逻辑：
1. Kalman 滤波估计"公允价格"
2. Z-Score 度量偏离程度
3. 买入：Z < -2.0（超卖），卖出：Z > 0（回归均值）
4. 止损：Z < -3.5（避免接飞刀）

聚焦中盘股（20-500亿），散户过度反应最强
"""

import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Optional, Tuple

from .strategy_base import BaseStrategy, Signal, Position

logger = logging.getLogger(__name__)


def kalman_filter(prices: np.ndarray, process_noise: float = 0.01,
                  measurement_noise: float = 1.0) -> np.ndarray:
    """
    Kalman 滤波估计公允价格

    状态方程：x[t] = x[t-1] + w[t],  w ~ N(0, Q)
    观测方程：y[t] = x[t] + v[t],  v ~ N(0, R)

    Args:
        prices: 价格序列
        process_noise: 过程噪声 Q（越小滤波越平滑）
        measurement_noise: 观测噪声 R（越大越信任模型）

    Returns:
        滤波后的价格估计
    """
    n = len(prices)
    if n < 2:
        return prices.copy()

    x_est = np.zeros(n)
    P = np.zeros(n)

    x_est[0] = prices[0]
    P[0] = 1.0

    for t in range(1, n):
        # 预测
        x_pred = x_est[t - 1]
        P_pred = P[t - 1] + process_noise

        # 更新
        K = P_pred / (P_pred + measurement_noise)  # Kalman 增益
        x_est[t] = x_pred + K * (prices[t] - x_pred)
        P[t] = (1 - K) * P_pred

    return x_est


def compute_zscore(prices: np.ndarray, filtered: np.ndarray,
                   lookback: int = 20) -> np.ndarray:
    """
    计算价格偏离 Kalman 估计的 Z-Score

    z = (price - filtered) / rolling_std(price - filtered)

    Args:
        prices: 原始价格
        filtered: Kalman 滤波后的价格
        lookback: 滚动窗口

    Returns:
        Z-Score 序列
    """
    residual = prices - filtered
    zscore = np.zeros(len(prices))

    for t in range(lookback, len(prices)):
        window = residual[t - lookback:t]
        std = np.std(window, ddof=1)
        if std > 1e-10:
            zscore[t] = residual[t] / std

    return zscore


def estimate_half_life(spread: np.ndarray) -> float:
    """
    估计均值回归半衰期（Ornstein-Uhlenbeck 过程）

    dX = theta * (mu - X) * dt + sigma * dW
    half_life = ln(2) / theta

    Returns:
        半衰期（交易日），inf 表示不回归
    """
    if len(spread) < 10:
        return float('inf')

    spread_lag = spread[:-1]
    spread_diff = np.diff(spread)

    # OLS: spread_diff = beta * spread_lag + const
    try:
        beta = np.polyfit(spread_lag, spread_diff, 1)[0]
        if beta >= 0:
            return float('inf')
        return float(-np.log(2) / beta)
    except Exception:
        return float('inf')


class MeanReversionStrategy(BaseStrategy):
    """均值回归 Z-Score 策略"""

    name = 'mean_reversion'
    description = 'Renaissance风格：Kalman滤波+Z-Score均值回归'
    version = '1.0'

    DEFAULT_PARAMS = {
        'entry_zscore': -2.0,      # 买入阈值
        'exit_zscore': 0.0,        # 卖出阈值
        'stop_zscore': -3.5,       # 止损阈值
        'max_holding_days': 10,    # 最大持有天数
        'zscore_lookback': 20,     # Z-Score 计算窗口
        'kalman_process_noise': 0.01,
        'kalman_measurement_noise': 1.0,
        'min_half_life': 3,        # 最小半衰期
        'max_half_life': 30,       # 最大半衰期
        'top_n': 15,               # 同时持有数量
        'min_market_cap': 2e9,     # 最低市值
        'max_market_cap': 50e9,    # 最高市值（聚焦中盘）
    }

    def __init__(self, params: Optional[Dict] = None):
        super().__init__({**self.DEFAULT_PARAMS, **(params or {})})
        self._zscores = {}

    def fit(self, price_data: Dict[str, pd.DataFrame],
            fundamental_data: Optional[pd.DataFrame] = None) -> 'MeanReversionStrategy':
        """拟合：计算每只股票的 Z-Score"""
        self._zscores = {}

        for code, df in price_data.items():
            if len(df) < 60:
                continue

            prices = df['close'].values.astype(float)

            # Kalman 滤波
            filtered = kalman_filter(
                prices,
                self.params['kalman_process_noise'],
                self.params['kalman_measurement_noise']
            )

            # Z-Score
            zscore = compute_zscore(prices, filtered, self.params['zscore_lookback'])

            # 半衰期检验
            residual = prices - filtered
            hl = estimate_half_life(residual[-60:])
            if self.params['min_half_life'] <= hl <= self.params['max_half_life']:
                self._zscores[code] = zscore

        self._is_fitted = True
        return self

    def generate_signals(self, price_data: Dict[str, pd.DataFrame],
                         fundamental_data: Optional[pd.DataFrame] = None,
                         current_date: Optional[str] = None) -> List[Signal]:
        """
        生成均值回归信号

        买入：Z < entry_zscore（超卖）
        卖出：Z > exit_zscore（回归均值）
        """
        signals = []

        for code, df in price_data.items():
            if code not in self._zscores:
                continue
            if len(df) < 2:
                continue

            zscore_arr = self._zscores[code]
            current_z = zscore_arr[-1]
            prev_z = zscore_arr[-2]

            # 检查涨跌停
            pct_chg = df['pct_chg'].iloc[-1] if 'pct_chg' in df.columns else 0

            if current_z <= self.params['entry_zscore'] and abs(pct_chg) < 9.9:
                # 超卖信号
                signals.append(Signal(
                    code=code,
                    direction=1,
                    strength=float(abs(current_z) / abs(self.params['entry_zscore'])),
                    reason=f"Z-Score={current_z:.2f} (oversold)"
                ))
            elif current_z >= self.params['exit_zscore'] and prev_z < self.params['exit_zscore']:
                # 回归均值信号（从下方穿越0）
                signals.append(Signal(
                    code=code,
                    direction=-1,
                    strength=float(abs(current_z)),
                    reason=f"Z-Score={current_z:.2f} (mean reverted)"
                ))

        # 按信号强度排序
        signals.sort(key=lambda s: s.strength, reverse=True)

        return signals

    def get_portfolio(self, signals: List[Signal],
                      current_positions: Dict[str, Position],
                      available_capital: float) -> Dict[str, Position]:
        """构建均值回归组合"""
        buy_signals = [s for s in signals if s.direction == 1]
        sell_signals = {s.code for s in signals if s.direction == -1}

        # 先处理卖出
        new_positions = {}
        for code, pos in current_positions.items():
            if code not in sell_signals:
                new_positions[code] = pos

        # 再处理买入
        top_n = self.params['top_n']
        for signal in buy_signals[:top_n]:
            if signal.code not in new_positions:
                new_positions[signal.code] = Position(
                    code=signal.code,
                    shares=0,
                    entry_price=0,
                    entry_date='',
                    weight=1.0 / top_n,
                )

        return new_positions

    def get_current_zscores(self) -> Dict[str, float]:
        """获取当前 Z-Score（用于分析）"""
        result = {}
        for code, zscore_arr in self._zscores.items():
            if len(zscore_arr) > 0:
                result[code] = float(zscore_arr[-1])
        return result
