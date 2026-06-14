"""
策略1：多因子Alpha

灵感来源：AQR "Value and Momentum Everywhere" + WorldQuant 多因子方法

因子组合：
- 价值因子 (25%): EP=1/PE + BP=1/PB
- 动量因子 (30%): 12-1个月动量 (Jegadeesh-Titman)
- 质量因子 (25%): ROE + 毛利率
- 低波因子 (20%): 60日实现波动率

月度再平衡，选前N只，等权持仓
"""

import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Optional, Tuple

from .strategy_base import BaseStrategy, Signal, Position, equal_weight_portfolio
from .factors import (
    calc_value_factor, calc_momentum_factor, calc_quality_factor,
    calc_low_vol_factor, calc_multi_factor_score, _zscore
)

logger = logging.getLogger(__name__)


class MultiFactorStrategy(BaseStrategy):
    """多因子Alpha策略"""

    name = 'multi_factor'
    description = 'AQR/WorldQuant风格多因子：价值+动量+质量+低波'
    version = '1.0'

    DEFAULT_PARAMS = {
        'top_n': 20,               # 选股数量
        'rebalance_freq': 'monthly',  # 再平衡频率
        'weight_value': 0.25,      # 价值因子权重
        'weight_momentum': 0.30,   # 动量因子权重
        'weight_quality': 0.25,    # 质量因子权重
        'weight_low_vol': 0.20,    # 低波因子权重
        'momentum_lookback': 252,  # 动量回望期（交易日）
        'momentum_skip': 21,       # 动量跳过期（交易日）
        'vol_lookback': 60,        # 波动率计算期
        'min_market_cap': 2e9,     # 最低市值
    }

    def __init__(self, params: Optional[Dict] = None):
        super().__init__({**self.DEFAULT_PARAMS, **(params or {})})
        self._factor_scores = {}

    def fit(self, price_data: Dict[str, pd.DataFrame],
            fundamental_data: Optional[pd.DataFrame] = None) -> 'MultiFactorStrategy':
        """
        拟合策略（计算因子）

        对于多因子策略，fit 主要是计算截面因子值。
        参数在 walk-forward 中可以优化。
        """
        self._is_fitted = True
        return self

    def generate_signals(self, price_data: Dict[str, pd.DataFrame],
                         fundamental_data: Optional[pd.DataFrame] = None,
                         current_date: Optional[str] = None) -> List[Signal]:
        """
        生成多因子信号

        流程：
        1. 计算每只股票的四个因子值
        2. 截面 z-score 标准化
        3. 加权合成
        4. 选前 N 只
        """
        if fundamental_data is None or fundamental_data.empty:
            return []

        codes = list(price_data.keys())
        if not codes:
            return []

        # 从基本面数据获取因子输入
        fund = fundamental_data[fundamental_data['code'].isin(codes)].copy()
        if fund.empty:
            return []

        fund = fund.set_index('code')

        # 1. 价值因子
        pe = fund.get('pe_ttm', pd.Series(dtype=float))
        pb = fund.get('pb', pd.Series(dtype=float))
        value_score = calc_value_factor(pe, pb)

        # 2. 动量因子
        close_series = {}
        for code in codes:
            if code in price_data and len(price_data[code]) > 0:
                close_series[code] = price_data[code]['close']

        momentum_score = calc_momentum_factor(
            close_series,
            lookback=self.params['momentum_lookback'],
            skip=self.params['momentum_skip']
        )

        # 3. 质量因子
        roe = fund.get('roe', pd.Series(dtype=float))
        gross_margin = fund.get('gross_margin', pd.Series(dtype=float))
        quality_score = calc_quality_factor(roe, gross_margin)

        # 4. 低波因子
        daily_returns = {}
        for code in codes:
            if code in price_data and len(price_data[code]) > self.params['vol_lookback']:
                daily_returns[code] = price_data[code]['close'].pct_change().dropna()

        low_vol_score = calc_low_vol_factor(daily_returns, self.params['vol_lookback'])

        # 5. 复合评分
        composite = pd.Series(0.0, index=fund.index)
        weights = {
            'value': self.params['weight_value'],
            'momentum': self.params['weight_momentum'],
            'quality': self.params['weight_quality'],
            'low_vol': self.params['weight_low_vol'],
        }

        factor_map = {
            'value': value_score,
            'momentum': momentum_score,
            'quality': quality_score,
            'low_vol': low_vol_score,
        }

        for name, weight in weights.items():
            factor = factor_map.get(name)
            if factor is not None and not factor.empty:
                aligned = factor.reindex(fund.index).fillna(0)
                composite += weight * aligned

        self._factor_scores = composite.to_dict()

        # 6. 选前 N 只
        top_n = self.params['top_n']
        ranked = composite.sort_values(ascending=False)
        selected = ranked.head(top_n)

        # 7. 生成信号
        signals = []
        for code, score in selected.items():
            if score > 0:  # 只买正分的
                signals.append(Signal(
                    code=str(code),
                    direction=1,
                    strength=float(abs(score)),
                    reason=f"Multi-factor score: {score:.3f}"
                ))

        return signals

    def get_portfolio(self, signals: List[Signal],
                      current_positions: Dict[str, Position],
                      available_capital: float) -> Dict[str, Position]:
        """等权组合构建"""
        codes = [s.code for s in signals if s.direction == 1]
        prices = {}  # 需要从外部传入

        # 简化：返回目标权重，实际价格由回测引擎填充
        if not codes:
            return {}

        positions = {}
        weight = 1.0 / len(codes)
        for code in codes:
            positions[code] = Position(
                code=code,
                shares=0,  # 由回测引擎计算
                entry_price=0,
                entry_date='',
                weight=weight,
            )

        return positions

    def get_factor_scores(self) -> Dict[str, float]:
        """获取因子评分（用于分析）"""
        return self._factor_scores.copy()
