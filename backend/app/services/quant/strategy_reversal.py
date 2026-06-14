"""
短期反转策略

A股最强因子之一：散户追涨杀跌导致的过度反应

逻辑：
- 买入过去1周跌幅最大的股票（超卖反弹）
- 持有1-2周
- 卖出反弹后的股票

学术支持：
- Liu, Stambaugh, Yuan (2019) "Size and Value in China"
- A股短期反转效应是美股的3-5倍
"""

import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Optional

from .strategy_base import BaseStrategy, Signal, Position

logger = logging.getLogger(__name__)


class ReversalStrategy(BaseStrategy):
    """短期反转策略"""

    name = 'reversal'
    description = 'A股短期反转：买入过去1周跌幅最大的股票'
    version = '1.0'

    DEFAULT_PARAMS = {
        'lookback': 5,           # 回望期（交易日，约1周）
        'holding_period': 10,    # 持有期（交易日，约2周）
        'top_n': 10,             # 选股数量
        'min_return': -0.30,     # 最低收益率（排除极端暴跌）
        'max_return': -0.01,     # 最高收益率（只要跌就买）
        'exclude_limit': True,   # 排除涨跌停股票
    }

    def __init__(self, params: Optional[Dict] = None):
        super().__init__({**self.DEFAULT_PARAMS, **(params or {})})
        self._reversal_scores = {}

    def fit(self, price_data: Dict[str, pd.DataFrame],
            fundamental_data=None) -> 'ReversalStrategy':
        """计算反转分数（fit不做实际计算，信号在generate_signals中实时生成）"""
        self._is_fitted = True
        return self

    def generate_signals(self, price_data, fundamental_data=None, current_date=None):
        """生成反转信号（每次再平衡时重新计算）"""
        signals = []
        top_n = self.params['top_n']
        lookback = self.params['lookback']
        min_ret = self.params['min_return']  # -0.30
        max_ret = self.params['max_return']  # -0.01

        # 实时计算反转分数
        reversal_scores = {}
        for code, df in price_data.items():
            if len(df) < lookback + 5:
                continue

            prices = df['close'].values.astype(float)

            # 找到current_date对应的索引
            if current_date:
                dates = df['date'].astype(str).values
                mask = dates <= current_date
                if mask.any():
                    idx = mask.sum() - 1
                    if idx < lookback:
                        continue
                    recent_return = (prices[idx] - prices[idx - lookback]) / prices[idx - lookback]
                else:
                    continue
            else:
                recent_return = (prices[-1] - prices[-lookback]) / prices[-lookback]

            # 条件：min_ret <= recent_return <= max_ret（例如 -30% <= ret <= -1%）
            if min_ret <= recent_return <= max_ret:
                reversal_scores[code] = -recent_return  # 跌得越多分数越高

        # 按反转分数排序
        sorted_stocks = sorted(
            reversal_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        for code, score in sorted_stocks[:top_n]:
            signals.append(Signal(
                code=code,
                direction=1,
                strength=float(score),
                reason=f"Reversal: past {lookback}d drop={-score:.1%}"
            ))

        return signals

    def get_portfolio(self, signals, current_positions, available_capital):
        """构建反转组合"""
        top_n = self.params['top_n']
        selected = [s for s in signals if s.direction == 1][:top_n]

        if not selected:
            return {}

        positions = {}
        weight = 1.0 / len(selected)

        for signal in selected:
            positions[signal.code] = Position(
                code=signal.code,
                shares=0,
                entry_price=0,
                entry_date='',
                weight=weight,
            )

        return positions
