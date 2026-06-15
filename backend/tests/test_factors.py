"""
test_factors.py — 因子计算测试

覆盖:
- calc_value_factor
- calc_momentum_factor
- calc_quality_factor
- calc_low_vol_factor
- calc_reversal_factor
- calc_size_factor
- calc_multi_factor_score
- _zscore (内部工具)
- winsorize
- calc_factor_ic
- calc_factor_ir
"""

import sys
import os
import numpy as np
import pandas as pd
import pytest

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from app.services.quant.factors import (
    calc_value_factor,
    calc_momentum_factor,
    calc_quality_factor,
    calc_low_vol_factor,
    calc_reversal_factor,
    calc_size_factor,
    calc_multi_factor_score,
    _zscore,
    winsorize,
    calc_factor_ic,
    calc_factor_ir,
)


# ============================================================
# _zscore (内部工具函数)
# ============================================================

class TestZscore:
    def test_standard_normal(self):
        """标准正态数据, z-score 均值应接近 0"""
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        z = _zscore(s)
        assert abs(z.mean()) < 1e-10

    def test_constant(self):
        """常数序列, 标准差为 0, 返回全 0"""
        s = pd.Series([5.0, 5.0, 5.0])
        z = _zscore(s)
        assert (z == 0.0).all()

    def test_empty(self):
        """空序列"""
        s = pd.Series(dtype=float)
        z = _zscore(s)
        assert z.empty


# ============================================================
# calc_value_factor
# ============================================================

class TestValueFactor:
    def test_normal(self, stock_universe):
        """正常计算, 应返回 z-score"""
        vf = calc_value_factor(stock_universe["pe_ttm"], stock_universe["pb"])
        assert len(vf) == 5
        assert abs(vf.mean()) < 1e-10  # z-score 均值为 0

    def test_zero_pe(self):
        """PE=0 应被替换为 NaN 并跳过"""
        pe = pd.Series([10.0, 0.0, 15.0], index=["A", "B", "C"])
        pb = pd.Series([1.0, 2.0, 1.5], index=["A", "B", "C"])
        vf = calc_value_factor(pe, pb)
        # B 的 EP = 1/NaN = NaN, 排名时跳过
        assert len(vf) == 3

    def test_higher_pe_lower_value(self):
        """PE 越高, 价值因子越低 (负 z-score)"""
        pe = pd.Series([5.0, 50.0], index=["cheap", "expensive"])
        pb = pd.Series([0.5, 5.0], index=["cheap", "expensive"])
        vf = calc_value_factor(pe, pb)
        assert vf["cheap"] > vf["expensive"]


# ============================================================
# calc_momentum_factor
# ============================================================

class TestMomentumFactor:
    def test_normal(self, price_series_dict):
        """正常计算动量因子"""
        mf = calc_momentum_factor(price_series_dict, lookback=252, skip=21)
        assert len(mf) > 0
        assert abs(mf.mean()) < 1e-6  # z-score 均值接近 0

    def test_short_series_skipped(self):
        """价格序列太短, 被跳过"""
        short = {"A": pd.Series([10.0, 11.0, 12.0])}
        mf = calc_momentum_factor(short, lookback=252)
        assert len(mf) == 0

    def test_empty(self):
        """空字典"""
        mf = calc_momentum_factor({})
        assert len(mf) == 0

    def test_stronger_momentum_higher_score(self):
        """涨得多的股票, 动量因子更高"""
        np.random.seed(42)
        up = pd.Series(10 * np.cumprod(np.concatenate([[1], np.full(260, 1.003)])))
        flat = pd.Series(10 * np.ones(261))
        mf = calc_momentum_factor({"up": up, "flat": flat}, lookback=252, skip=21)
        assert mf["up"] > mf["flat"]


# ============================================================
# calc_quality_factor
# ============================================================

class TestQualityFactor:
    def test_normal(self, stock_universe):
        """正常计算质量因子"""
        qf = calc_quality_factor(
            stock_universe["roe"],
            stock_universe["gross_margin"],
        )
        assert len(qf) == 5
        assert abs(qf.mean()) < 1e-10

    def test_with_stability(self, stock_universe):
        """带毛利率稳定性输入"""
        stability = pd.Series([0.01, 0.05, 0.03, 0.08, 0.02],
                              index=stock_universe.index)
        qf = calc_quality_factor(
            stock_universe["roe"],
            stock_universe["gross_margin"],
            stability,
        )
        assert len(qf) == 5

    def test_higher_roe_higher_quality(self):
        """ROE 越高, 质量因子越高"""
        roe = pd.Series([0.05, 0.25], index=["low", "high"])
        gm = pd.Series([0.20, 0.20], index=["low", "high"])
        qf = calc_quality_factor(roe, gm)
        assert qf["high"] > qf["low"]


# ============================================================
# calc_low_vol_factor
# ============================================================

class TestLowVolFactor:
    def test_normal(self, returns_series_dict):
        """正常计算低波因子"""
        lvf = calc_low_vol_factor(returns_series_dict, lookback=60)
        assert len(lvf) > 0

    def test_short_series_skipped(self):
        """收益率序列太短, 被跳过"""
        short = {"A": pd.Series(np.random.normal(0, 0.01, 10))}
        lvf = calc_low_vol_factor(short, lookback=60)
        assert len(lvf) == 0

    def test_lower_vol_higher_score(self):
        """波动率越低, 低波因子越高"""
        np.random.seed(42)
        low_vol = pd.Series(np.random.normal(0, 0.005, 100))
        high_vol = pd.Series(np.random.normal(0, 0.03, 100))
        lvf = calc_low_vol_factor({"low": low_vol, "high": high_vol}, lookback=60)
        assert lvf["low"] > lvf["high"]


# ============================================================
# calc_reversal_factor
# ============================================================

class TestReversalFactor:
    def test_normal(self, price_series_dict):
        """正常计算反转因子"""
        rf = calc_reversal_factor(price_series_dict, lookback=21)
        assert len(rf) > 0

    def test_short_series_skipped(self):
        short = {"A": pd.Series([10.0, 11.0])}
        rf = calc_reversal_factor(short, lookback=21)
        assert len(rf) == 0

    def test_recent_decline_higher_score(self):
        """近期下跌的股票, 反转因子更高 (预期反弹)"""
        # 股票 A: 近 21 天从 10 跌到 8
        down = pd.Series(np.concatenate([np.full(280, 10.0), np.linspace(10, 8, 21)]))
        # 股票 B: 近 21 天从 10 涨到 12
        up = pd.Series(np.concatenate([np.full(280, 10.0), np.linspace(10, 12, 21)]))
        rf = calc_reversal_factor({"down": down, "up": up}, lookback=21)
        assert rf["down"] > rf["up"]


# ============================================================
# calc_size_factor
# ============================================================

class TestSizeFactor:
    def test_normal(self):
        """正常计算小市值因子"""
        cap = pd.Series([100, 1000, 10000], index=["small", "mid", "large"])
        sf = calc_size_factor(cap)
        assert len(sf) == 3
        # 小市值排名更高
        assert sf["small"] > sf["large"]

    def test_zero_market_cap(self):
        """市值为 0, 被替换为 NaN"""
        cap = pd.Series([100, 0, 10000], index=["A", "B", "C"])
        sf = calc_size_factor(cap)
        assert len(sf) == 3


# ============================================================
# calc_multi_factor_score
# ============================================================

class TestMultiFactorScore:
    def test_normal(self, stock_universe, returns_series_dict):
        """正常计算多因子复合评分"""
        momentum = calc_momentum_factor(
            {k: pd.Series(np.cumprod(np.concatenate([[1], 1 + v.values])))
             for k, v in returns_series_dict.items()},
            lookback=min(50, len(next(iter(returns_series_dict.values())))),
            skip=5,
        )
        volatility = calc_low_vol_factor(returns_series_dict, lookback=50)
        result = calc_multi_factor_score(
            pe_ttm=stock_universe["pe_ttm"],
            pb=stock_universe["pb"],
            momentum=momentum.reindex(stock_universe.index).fillna(0),
            roe=stock_universe["roe"],
            gross_margin=stock_universe["gross_margin"],
            volatility=volatility.reindex(stock_universe.index).fillna(0),
        )
        assert len(result) == 5

    def test_custom_weights(self, stock_universe):
        """自定义权重"""
        dummy = pd.Series(0.0, index=stock_universe.index)
        result = calc_multi_factor_score(
            pe_ttm=stock_universe["pe_ttm"],
            pb=stock_universe["pb"],
            momentum=dummy,
            roe=stock_universe["roe"],
            gross_margin=stock_universe["gross_margin"],
            volatility=dummy,
            weights={"value": 1.0, "momentum": 0.0, "quality": 0.0, "low_vol": 0.0},
        )
        # 只有 value 因子
        vf = calc_value_factor(stock_universe["pe_ttm"], stock_universe["pb"])
        # 结果应等于 value 因子 (因为权重 100% 给 value)
        pd.testing.assert_series_equal(result, vf, atol=1e-10)


# ============================================================
# winsorize
# ============================================================

class TestWinsorize:
    def test_normal(self):
        """正常缩尾"""
        s = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 100])
        w = winsorize(s, 0.1, 0.9)
        assert w.max() <= 100  # 上限
        assert w.min() >= 1    # 下限

    def test_empty(self):
        s = pd.Series(dtype=float)
        assert winsorize(s).empty

    def test_extremes_clipped(self):
        """极端值被截断"""
        s = pd.Series([1] * 90 + [1, 1, 1, 1, 1, 1, 1, 1, 1, 1000])
        w = winsorize(s, 0.05, 0.95)
        assert w.max() < 1000


# ============================================================
# calc_factor_ic
# ============================================================

class TestFactorIC:
    def test_positive_correlation(self):
        """因子与未来收益正相关, IC > 0"""
        np.random.seed(42)
        factor = pd.Series(np.random.normal(0, 1, 50))
        returns = factor * 0.3 + np.random.normal(0, 0.5, 50)
        ic = calc_factor_ic(factor, returns)
        assert ic > 0

    def test_negative_correlation(self):
        """因子与未来收益负相关, IC < 0"""
        np.random.seed(42)
        factor = pd.Series(np.random.normal(0, 1, 50))
        returns = -factor * 0.3 + np.random.normal(0, 0.5, 50)
        ic = calc_factor_ic(factor, returns)
        assert ic < 0

    def test_too_few(self):
        """数据不足, 返回 0"""
        factor = pd.Series([1, 2, 3])
        returns = pd.Series([0.1, 0.2, 0.3])
        assert calc_factor_ic(factor, returns) == 0.0


# ============================================================
# calc_factor_ir
# ============================================================

class TestFactorIR:
    def test_stable_ic(self):
        """稳定 IC, IR 应该高"""
        ic = pd.Series([0.05, 0.06, 0.04, 0.05, 0.06, 0.05])
        ir = calc_factor_ir(ic)
        assert ir > 1.0  # 稳定的正 IC

    def test_too_few(self):
        ic = pd.Series([0.05, 0.06])
        assert calc_factor_ir(ic) == 0.0

    def test_constant_ic(self):
        """恒定 IC, 标准差为 0, 返回 0"""
        ic = pd.Series([0.05, 0.05, 0.05, 0.05, 0.05])
        assert calc_factor_ir(ic) == 0.0
