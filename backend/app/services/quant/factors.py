"""
因子计算库

实现 AQR/WorldQuant 风格的多因子模型：
- 价值因子：EP (Earnings/Price), BP (Book/Price)
- 动量因子：12-1 个月动量 (Jegadeesh-Titman 1993)
- 质量因子：ROE, 毛利率稳定性
- 低波因子：60日实现波动率
- 反转因子：短期反转（A股强特征）

每个因子输出截面 z-score，可直接用于组合评分
"""

import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================
# 单因子计算
# ============================================================

def calc_value_factor(pe_ttm: pd.Series, pb: pd.Series) -> pd.Series:
    """
    价值因子：EP + BP 的截面排名

    EP = 1 / PE_TTM（越高越便宜）
    BP = 1 / PB（越高越便宜）

    Returns:
        截面 z-score（正值 = 便宜，负值 = 贵）
    """
    ep = 1.0 / pe_ttm.replace(0, np.nan)
    bp = 1.0 / pb.replace(0, np.nan)

    ep_rank = ep.rank(pct=True)
    bp_rank = bp.rank(pct=True)

    composite = 0.5 * ep_rank + 0.5 * bp_rank
    return _zscore(composite)


def calc_momentum_factor(close_series: Dict[str, pd.Series],
                         lookback: int = 252,
                         skip: int = 21) -> pd.Series:
    """
    动量因子：12个月收益去掉最近1个月

    mom = close[t-skip] / close[t-lookback] - 1

    这是 Jegadeesh-Titman (1993) 的经典定义。
    跳过最近1个月是为了避免 A 股的短期反转效应。

    Args:
        close_series: {code: close_price_series}
        lookback: 回望周期（交易日），默认252天（约12个月）
        skip: 跳过最近天数，默认21天（约1个月）

    Returns:
        截面 z-score（正值 = 强势，负值 = 弱势）
    """
    momentum = {}
    for code, prices in close_series.items():
        if len(prices) >= lookback:
            old_price = prices.iloc[-lookback]
            recent_price = prices.iloc[-skip] if skip > 0 and len(prices) > skip else prices.iloc[-1]
            if old_price > 0:
                momentum[code] = recent_price / old_price - 1.0

    if not momentum:
        return pd.Series(dtype=float)

    return _zscore(pd.Series(momentum))


def calc_quality_factor(roe: pd.Series, gross_margin: pd.Series,
                        margin_stability: Optional[pd.Series] = None) -> pd.Series:
    """
    质量因子：ROE + 毛利率 + 稳定性

    质量 = 0.5 * rank(ROE) + 0.3 * rank(gross_margin) + 0.2 * rank(-margin_vol)

    Returns:
        截面 z-score（正值 = 高质量，负值 = 低质量）
    """
    roe_rank = roe.rank(pct=True)
    gm_rank = gross_margin.rank(pct=True)

    if margin_stability is not None:
        # 波动率越低越好
        stability_rank = (-margin_stability).rank(pct=True)
        composite = 0.5 * roe_rank + 0.3 * gm_rank + 0.2 * stability_rank
    else:
        composite = 0.6 * roe_rank + 0.4 * gm_rank

    return _zscore(composite)


def calc_low_vol_factor(daily_returns: Dict[str, pd.Series],
                        lookback: int = 60) -> pd.Series:
    """
    低波因子：60日实现波动率

    vol = std(daily_returns, 60) * sqrt(252)

    低波动率的股票排名更高（低波异象）

    Returns:
        截面 z-score（正值 = 低波，负值 = 高波）
    """
    volatility = {}
    for code, returns in daily_returns.items():
        if len(returns) >= lookback:
            recent = returns.iloc[-lookback:]
            vol = recent.std() * np.sqrt(252)
            if not np.isnan(vol):
                volatility[code] = vol

    if not volatility:
        return pd.Series(dtype=float)

    # 低波排名更高
    return _zscore(-pd.Series(volatility))


def calc_reversal_factor(close_series: Dict[str, pd.Series],
                         lookback: int = 21) -> pd.Series:
    """
    短期反转因子：过去1个月收益

    A股的短期反转效应非常强（散户追涨杀跌导致的过度反应）

    Returns:
        截面 z-score（正值 = 近期下跌（预期反弹），负值 = 近期上涨（预期回调））
    """
    reversal = {}
    for code, prices in close_series.items():
        if len(prices) >= lookback:
            old_price = prices.iloc[-lookback]
            curr_price = prices.iloc[-1]
            if old_price > 0:
                reversal[code] = curr_price / old_price - 1.0

    if not reversal:
        return pd.Series(dtype=float)

    # 反转：近期跌的排名高
    return _zscore(-pd.Series(reversal))


def calc_size_factor(market_cap: pd.Series) -> pd.Series:
    """
    小市值因子：A股小盘股溢价显著

    Returns:
        截面 z-score（正值 = 小盘，负值 = 大盘）
    """
    return _zscore(-np.log(market_cap.replace(0, np.nan)))


# ============================================================
# 复合因子
# ============================================================

def calc_multi_factor_score(
    pe_ttm: pd.Series,
    pb: pd.Series,
    momentum: pd.Series,
    roe: pd.Series,
    gross_margin: pd.Series,
    volatility: pd.Series,
    market_cap: Optional[pd.Series] = None,
    weights: Optional[Dict[str, float]] = None,
) -> pd.Series:
    """
    多因子复合评分

    默认权重（AQR 风格）：
    - 价值 25%
    - 动量 30%
    - 质量 25%
    - 低波 20%

    Returns:
        复合 z-score（正值 = 买入信号，负值 = 卖出信号）
    """
    if weights is None:
        weights = {
            'value': 0.25,
            'momentum': 0.30,
            'quality': 0.25,
            'low_vol': 0.20,
        }

    factors = {}

    # 价值因子
    factors['value'] = calc_value_factor(pe_ttm, pb)

    # 动量因子
    factors['momentum'] = momentum

    # 质量因子
    factors['quality'] = calc_quality_factor(roe, gross_margin)

    # 低波因子
    factors['low_vol'] = volatility  # 已经是 z-score

    # 加权合成
    composite = pd.Series(0.0, index=pe_ttm.index)
    total_weight = 0.0

    for name, weight in weights.items():
        if name in factors and not factors[name].empty:
            # 对齐索引
            aligned = factors[name].reindex(composite.index).fillna(0)
            composite += weight * aligned
            total_weight += weight

    if total_weight > 0:
        composite /= total_weight

    return composite


# ============================================================
# 工具函数
# ============================================================

def _zscore(series: pd.Series) -> pd.Series:
    """截面 z-score 标准化"""
    if series.empty:
        return series
    mean = series.mean()
    std = series.std()
    if std < 1e-10:
        return pd.Series(0.0, index=series.index)
    return (series - mean) / std


def rank_percentile(series: pd.Series) -> pd.Series:
    """截面百分位排名 [0, 1]"""
    if series.empty:
        return series
    return series.rank(pct=True)


def winsorize(series: pd.Series, lower: float = 0.01, upper: float = 0.99) -> pd.Series:
    """缩尾处理（去极值）"""
    if series.empty:
        return series
    q_low = series.quantile(lower)
    q_high = series.quantile(upper)
    return series.clip(q_low, q_high)


def calc_factor_ic(factor_values: pd.Series, forward_returns: pd.Series) -> float:
    """
    计算因子 IC（Information Coefficient）

    IC = rank_correlation(factor_t, return_{t+1})

    用于评估因子的预测能力
    """
    aligned = pd.DataFrame({
        'factor': factor_values,
        'returns': forward_returns
    }).dropna()

    if len(aligned) < 10:
        return 0.0

    return float(aligned['factor'].corr(aligned['returns'], method='spearman'))


def calc_factor_ir(ic_series: pd.Series) -> float:
    """
    计算因子 IR（Information Ratio）

    IR = mean(IC) / std(IC)

    IR > 0.5 表示因子稳定有效
    """
    if len(ic_series) < 5:
        return 0.0
    std = ic_series.std()
    if std < 1e-10:
        return 0.0
    return float(ic_series.mean() / std)
