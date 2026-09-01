"""
策略4：配对交易

灵感来源：D.E. Shaw 统计套利

核心逻辑：
1. 同行业股票协整检验（Engle-Granger）
2. 价差 Z-Score > 2 做空价差，< -2 做多价差
3. A股适配：仅做多腿（买被低估的那只）
4. 半衰期5-30天才交易

配对选择：
- 同行业（白酒-白酒，银行-银行）
- 协整 p-value < 0.05
- 半衰期 5-30 天
"""

import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Optional, Tuple
from itertools import combinations

from .strategy_base import BaseStrategy, Signal, Position

logger = logging.getLogger(__name__)

# 申万一级行业分类（简化版）
SW_SECTORS = {
    'bank': ['601398', '601939', '601288', '601328', '600036', '600016', '600015',
             '601166', '600000', '601818', '601998', '600010', '601229', '600919',
             '601009', '601169', '002142', '600926', '601838', '601577', '601128',
             '601860', '600908', '001227', '601665'],
    'liquor': ['600519', '000858', '000568', '600809', '002304', '603369',
               '000596', '600779', '000799', '603589', '600559', '600702'],
    'insurance': ['601318', '601628', '601601', '601336', '601319', '000627'],
    'real_estate': ['000002', '001979', '600048', '000069', '600340', '600383',
                    '601155', '002244', '600325', '000671'],
    'auto': ['600104', '601238', '000625', '600741', '002594', '601633',
             '000800', '600660', '002920', '601127'],
    'pharma': ['600276', '000538', '300760', '600196', '002001', '300015',
               '300347', '000963', '300529', '603259'],
    'tech': ['002415', '300750', '600703', '002236', '300408', '002475',
             '002371', '300014', '603501', '300033'],
}


def test_cointegration(price_a: np.ndarray, price_b: np.ndarray) -> Tuple[bool, float, float]:
    """
    Engle-Granger 协整检验

    Returns:
        (是否协整, p-value, hedge_ratio)
    """
    try:
        from statsmodels.tsa.stattools import coint as coint_test
        t_stat, p_value, critical_values = coint_test(price_a, price_b)
        is_cointegrated = p_value < 0.05

        # OLS 对冲比率: price_a = alpha + beta * price_b
        beta = np.polyfit(price_b, price_a, 1)[0]

        return is_cointegrated, float(p_value), float(beta)
    except ImportError:
        logger.warning("statsmodels not installed, using simplified test")
        # 简化版：相关性检验
        corr = np.corrcoef(price_a, price_b)[0, 1]
        beta = np.polyfit(price_b, price_a, 1)[0]
        return corr > 0.8, float(1 - corr), float(beta)


def calc_spread_zscore(price_a: np.ndarray, price_b: np.ndarray,
                       hedge_ratio: float, lookback: int = 60) -> np.ndarray:
    """
    计算价差 Z-Score

    spread = price_a - hedge_ratio * price_b
    zscore = (spread - rolling_mean) / rolling_std
    """
    spread = price_a - hedge_ratio * price_b
    n = len(spread)
    zscore = np.zeros(n)

    for t in range(lookback, n):
        window = spread[t - lookback:t]
        mean = np.mean(window)
        std = np.std(window, ddof=1)
        if std > 1e-10:
            zscore[t] = (spread[t] - mean) / std

    return zscore


def estimate_half_life(spread: np.ndarray) -> float:
    """估计均值回归半衰期"""
    if len(spread) < 10:
        return float('inf')

    spread_lag = spread[:-1]
    spread_diff = np.diff(spread)

    try:
        beta = np.polyfit(spread_lag, spread_diff, 1)[0]
        if beta >= 0:
            return float('inf')
        return float(-np.log(2) / beta)
    except Exception:
        return float('inf')


class PairsTradingStrategy(BaseStrategy):
    """配对交易策略"""

    name = 'pairs_trading'
    description = 'DE Shaw风格：协整配对交易（A股仅做多腿）'
    version = '1.0'

    DEFAULT_PARAMS = {
        'entry_zscore': 2.0,       # 入场阈值
        'exit_zscore': 0.0,        # 出场阈值
        'stop_zscore': 4.0,        # 止损阈值
        'max_holding_days': 20,    # 最大持有天数
        'min_half_life': 5,        # 最小半衰期
        'max_half_life': 30,       # 最大半衰期
        'lookback': 60,            # 价差计算窗口
        'coint_pvalue': 0.05,      # 协整检验p值阈值
        'min_history': 252,        # 最少历史数据
        'max_pairs': 10,           # 最大同时持有配对数
    }

    def __init__(self, params: Optional[Dict] = None):
        super().__init__({**self.DEFAULT_PARAMS, **(params or {})})
        self._pairs = []  # 协整配对列表
        self._zscores = {}  # {pair_key: zscore_array}

    def fit(self, price_data: Dict[str, pd.DataFrame],
            fundamental_data: Optional[pd.DataFrame] = None) -> 'PairsTradingStrategy':
        """
        拟合：发现协整配对

        1. 按行业分组
        2. 行业内两两协整检验
        3. 筛选半衰期合适的配对
        """
        self._pairs = []
        self._zscores = {}

        # 按行业分组
        industry_groups = self._group_by_industry(price_data)

        for industry, codes in industry_groups.items():
            if len(codes) < 2:
                continue

            # 行业内两两配对
            for code_a, code_b in combinations(codes, 2):
                if code_a not in price_data or code_b not in price_data:
                    continue

                df_a = price_data[code_a]
                df_b = price_data[code_b]

                # 对齐日期
                common_dates = set(df_a['date']).intersection(set(df_b['date']))
                if len(common_dates) < self.params['min_history']:
                    continue

                df_a_aligned = df_a[df_a['date'].isin(common_dates)].sort_values('date')
                df_b_aligned = df_b[df_b['date'].isin(common_dates)].sort_values('date')

                prices_a = df_a_aligned['close'].values.astype(float)
                prices_b = df_b_aligned['close'].values.astype(float)

                # 协整检验
                is_coint, pvalue, hedge_ratio = test_cointegration(prices_a, prices_b)

                if not is_coint or pvalue > self.params['coint_pvalue']:
                    continue

                # 半衰期检验
                spread = prices_a - hedge_ratio * prices_b
                hl = estimate_half_life(spread[-120:])

                if not (self.params['min_half_life'] <= hl <= self.params['max_half_life']):
                    continue

                # 计算 Z-Score
                zscore = calc_spread_zscore(
                    prices_a, prices_b, hedge_ratio, self.params['lookback']
                )

                pair_key = f"{code_a}_{code_b}"
                self._pairs.append({
                    'code_a': code_a,
                    'code_b': code_b,
                    'hedge_ratio': hedge_ratio,
                    'pvalue': pvalue,
                    'half_life': hl,
                    'industry': industry,
                })
                self._zscores[pair_key] = zscore

        logger.info(f"Found {len(self._pairs)} cointegrated pairs")
        self._is_fitted = True
        return self

    def generate_signals(self, price_data: Dict[str, pd.DataFrame],
                         fundamental_data: Optional[pd.DataFrame] = None,
                         current_date: Optional[str] = None) -> List[Signal]:
        """
        生成配对交易信号

        A股仅做多腿：当价差 Z-Score < -entry 时，买被低估的（code_a）
        当价差 Z-Score > entry 时，买被低估的（code_b）
        """
        signals = []
        entry_z = self.params['entry_zscore']

        for pair in self._pairs:
            pair_key = f"{pair['code_a']}_{pair['code_b']}"
            if pair_key not in self._zscores:
                continue

            zscore_arr = self._zscores[pair_key]
            if len(zscore_arr) < 2:
                continue

            current_z = zscore_arr[-1]

            if current_z <= -entry_z:
                # spread 太低：买 code_a（被低估的）
                signals.append(Signal(
                    code=pair['code_a'],
                    direction=1,
                    strength=float(abs(current_z) / entry_z),
                    reason=f"Pair {pair_key}: Z={current_z:.2f}, buy {pair['code_a']}"
                ))
            elif current_z >= entry_z:
                # spread 太高：买 code_b（被低估的）
                signals.append(Signal(
                    code=pair['code_b'],
                    direction=1,
                    strength=float(abs(current_z) / entry_z),
                    reason=f"Pair {pair_key}: Z={current_z:.2f}, buy {pair['code_b']}"
                ))

        signals.sort(key=lambda s: s.strength, reverse=True)
        return signals

    def get_portfolio(self, signals: List[Signal],
                      current_positions: Dict[str, Position],
                      available_capital: float) -> Dict[str, Position]:
        """配对交易组合"""
        max_pairs = self.params['max_pairs']
        selected = signals[:max_pairs]

        if not selected:
            return {}

        positions = {}
        weight = 1.0 / max(len(selected), 1)

        for signal in selected:
            if signal.code not in positions:
                positions[signal.code] = Position(
                    code=signal.code,
                    shares=0,
                    entry_price=0,
                    entry_date='',
                    weight=weight,
                )

        return positions

    def _group_by_industry(self, price_data: Dict[str, pd.DataFrame]) -> Dict[str, List[str]]:
        """按行业分组"""
        groups = {}
        for code in price_data.keys():
            industry = 'other'
            for sector, sector_codes in SW_SECTORS.items():
                if code in sector_codes:
                    industry = sector
                    break
            if industry not in groups:
                groups[industry] = []
            groups[industry].append(code)
        return groups

    def get_pairs_info(self) -> List[Dict]:
        """获取配对信息（用于分析）"""
        return self._pairs.copy()
