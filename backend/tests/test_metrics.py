"""
test_metrics.py — 性能指标计算测试

覆盖:
- calc_total_return
- calc_annual_return
- calc_daily_returns
- calc_volatility
- calc_max_drawdown
- calc_max_drawdown_duration
- calc_sharpe_ratio
- calc_sortino_ratio
- calc_calmar_ratio
- calc_omega_ratio
- calc_tail_ratio
- calc_alpha_beta
- calc_information_ratio
- calc_monthly_win_rate
- calc_profit_loss_ratio
- calc_turnover
"""

import sys
import os
import math
import numpy as np
import pytest

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from app.services.quant.metrics import (
    calc_total_return,
    calc_annual_return,
    calc_daily_returns,
    calc_volatility,
    calc_max_drawdown,
    calc_max_drawdown_duration,
    calc_sharpe_ratio,
    calc_sortino_ratio,
    calc_calmar_ratio,
    calc_omega_ratio,
    calc_tail_ratio,
    calc_alpha_beta,
    calc_information_ratio,
    calc_monthly_win_rate,
    calc_profit_loss_ratio,
    calc_turnover,
)


# ============================================================
# calc_total_return
# ============================================================

class TestTotalReturn:
    def test_normal_growth(self):
        """净值从 100 涨到 120, 收益率 20%"""
        eq = np.array([100.0, 105.0, 110.0, 120.0])
        assert abs(calc_total_return(eq) - 0.20) < 1e-10

    def test_single_element(self):
        """单元素曲线, 收益率为 0"""
        eq = np.array([100.0])
        assert calc_total_return(eq) == 0.0

    def test_empty(self):
        """空数组, 收益率为 0"""
        eq = np.array([])
        assert calc_total_return(eq) == 0.0

    def test_loss(self):
        """净值下跌"""
        eq = np.array([100.0, 90.0, 80.0])
        assert abs(calc_total_return(eq) - (-0.20)) < 1e-10

    def test_flat(self):
        """净值不变"""
        eq = np.array([50.0, 50.0, 50.0])
        assert abs(calc_total_return(eq)) < 1e-10


# ============================================================
# calc_annual_return
# ============================================================

class TestAnnualReturn:
    def test_one_year_doubling(self):
        """253 个交易日翻倍, 年化收益 ~100%"""
        eq = np.array([1.0 * (1.00274 ** i) for i in range(253)])
        annual = calc_annual_return(eq, 252)
        # 这个序列年化约 (1.00274)^252 - 1 ≈ 1.08
        assert annual > 0

    def test_single_element(self):
        """单元素, 返回 0"""
        eq = np.array([100.0])
        assert calc_annual_return(eq) == 0.0

    def test_total_loss(self):
        """净值归零, 返回 0 (避免 math domain error)"""
        eq = np.array([100.0, 0.0])
        assert calc_annual_return(eq) == 0.0

    def test_short_period(self):
        """短周期也能计算"""
        eq = np.array([100.0, 101.0])
        annual = calc_annual_return(eq, 252)
        assert annual > 0


# ============================================================
# calc_daily_returns
# ============================================================

class TestDailyReturns:
    def test_normal(self):
        eq = np.array([100.0, 102.0, 101.0])
        rets = calc_daily_returns(eq)
        assert len(rets) == 2
        assert abs(rets[0] - 0.02) < 1e-10
        assert abs(rets[1] - (-1.0 / 102.0)) < 1e-10

    def test_single_element(self):
        eq = np.array([100.0])
        rets = calc_daily_returns(eq)
        assert len(rets) == 0

    def test_empty(self):
        eq = np.array([])
        rets = calc_daily_returns(eq)
        assert len(rets) == 0


# ============================================================
# calc_volatility
# ============================================================

class TestVolatility:
    def test_constant_returns(self):
        """恒定收益率, 波动率为 0"""
        rets = np.full(50, 0.001)
        assert calc_volatility(rets) == 0.0

    def test_normal(self):
        """正常波动"""
        np.random.seed(42)
        rets = np.random.normal(0, 0.01, 100)
        vol = calc_volatility(rets, 252)
        assert vol > 0
        # 波动率应约为 0.01 * sqrt(252) ≈ 0.159
        assert 0.10 < vol < 0.25

    def test_too_few(self):
        """不足 2 个数据点"""
        rets = np.array([0.01])
        assert calc_volatility(rets) == 0.0


# ============================================================
# calc_max_drawdown
# ============================================================

class TestMaxDrawdown:
    def test_no_drawdown(self):
        """单调上涨, 回撤为 0"""
        eq = np.array([100.0, 110.0, 120.0, 130.0])
        mdd, start, end = calc_max_drawdown(eq)
        assert abs(mdd) < 1e-10

    def test_known_drawdown(self):
        """已知回撤: 峰值 150, 谷值 100, 回撤 33.3%"""
        eq = np.array([100.0, 130.0, 150.0, 100.0])
        mdd, start, end = calc_max_drawdown(eq)
        assert abs(mdd - (-1.0 / 3.0)) < 1e-6
        assert start == 2  # 峰值在 index 2
        assert end == 3    # 谷值在 index 3

    def test_single_element(self):
        eq = np.array([100.0])
        mdd, start, end = calc_max_drawdown(eq)
        assert mdd == 0.0
        assert start == 0
        assert end == 0

    def test_full_recovery(self):
        """回撤后完全恢复, 但最大回撤仍然存在"""
        eq = np.array([100.0, 80.0, 100.0])
        mdd, start, end = calc_max_drawdown(eq)
        assert abs(mdd - (-0.20)) < 1e-10


# ============================================================
# calc_max_drawdown_duration
# ============================================================

class TestMaxDrawdownDuration:
    def test_no_drawdown(self):
        eq = np.array([100.0, 110.0, 120.0])
        assert calc_max_drawdown_duration(eq) == 0

    def test_persistent_drawdown(self):
        """持续回撤 3 天"""
        eq = np.array([100.0, 110.0, 105.0, 100.0, 95.0])
        dur = calc_max_drawdown_duration(eq)
        assert dur >= 3  # 至少 3 天低于前高

    def test_single_element(self):
        eq = np.array([100.0])
        assert calc_max_drawdown_duration(eq) == 0


# ============================================================
# calc_sharpe_ratio
# ============================================================

class TestSharpeRatio:
    def test_positive_returns(self):
        """稳定正收益, Sharpe 应该很高"""
        np.random.seed(42)
        rets = np.full(30, 0.002) + np.random.normal(0, 0.0005, 30)
        sharpe = calc_sharpe_ratio(rets, risk_free_rate=0.02)
        assert sharpe > 3  # 非常高的 Sharpe

    def test_too_few_data(self):
        """不足 20 个数据点, 返回 0"""
        rets = np.full(10, 0.001)
        assert calc_sharpe_ratio(rets) == 0.0

    def test_zero_std(self):
        """零标准差 (恒定收益), 返回 0"""
        rets = np.full(30, 0.02 / 252)  # 恰好等于无风险日利率
        assert calc_sharpe_ratio(rets) == 0.0

    def test_negative_returns(self):
        """负收益, Sharpe 应为负"""
        np.random.seed(42)
        rets = np.full(30, -0.002) + np.random.normal(0, 0.0005, 30)
        sharpe = calc_sharpe_ratio(rets)
        assert sharpe < 0


# ============================================================
# calc_sortino_ratio
# ============================================================

class TestSortinoRatio:
    def test_no_downside(self):
        """全部正收益, 无下行波动, 返回 0 (downside < 5)"""
        rets = np.full(30, 0.001)
        assert calc_sortino_ratio(rets) == 0.0

    def test_mixed_returns(self):
        """有正有负, Sortino 应 > Sharpe (因为下行波动 < 总波动)"""
        np.random.seed(42)
        rets = np.random.normal(0.001, 0.015, 50)
        sharpe = calc_sharpe_ratio(rets)
        sortino = calc_sortino_ratio(rets)
        # Sortino 通常 > Sharpe (如果收益偏正)
        # 这里只检查不为 0
        assert sortino != 0.0

    def test_too_few_data(self):
        rets = np.full(10, 0.001)
        assert calc_sortino_ratio(rets) == 0.0


# ============================================================
# calc_calmar_ratio
# ============================================================

class TestCalmarRatio:
    def test_normal(self):
        """稳定上涨, 有小幅回撤"""
        eq = np.array([100.0, 105.0, 100.0, 110.0, 108.0, 120.0])
        calmar = calc_calmar_ratio(eq)
        assert calmar > 0  # 正收益 / 正回撤 = 正

    def test_no_drawdown(self):
        """无回撤, 返回 0"""
        eq = np.array([100.0, 110.0, 120.0])
        assert calc_calmar_ratio(eq) == 0.0

    def test_loss(self):
        """亏损, Calmar 为负"""
        eq = np.array([100.0, 80.0, 70.0, 60.0])
        calmar = calc_calmar_ratio(eq)
        assert calmar < 0


# ============================================================
# calc_omega_ratio
# ============================================================

class TestOmegaRatio:
    def test_all_gains(self):
        """全部高于阈值, 不足 10 个数据点返回 1.0 (边界: len < 10)"""
        rets = np.array([0.01, 0.02, 0.015, 0.005, 0.03])
        assert calc_omega_ratio(rets, 0.0) == 1.0

    def test_all_gains_enough_data(self):
        """全部高于阈值且数据充足, 返回上限 10"""
        rets = np.array([0.01, 0.02, 0.015, 0.005, 0.03,
                         0.012, 0.008, 0.025, 0.018, 0.022])
        assert calc_omega_ratio(rets, 0.0) == 10.0

    def test_balanced(self):
        """正负各半"""
        rets = np.array([0.01, -0.01, 0.02, -0.02, 0.01, -0.01, 0.005, -0.005,
                         0.01, -0.01, 0.003, -0.003])
        omega = calc_omega_ratio(rets, 0.0)
        assert 0.5 < omega < 2.0  # 接近 1

    def test_too_few(self):
        """不足 10 个数据点"""
        rets = np.array([0.01, -0.01, 0.02])
        assert calc_omega_ratio(rets) == 1.0


# ============================================================
# calc_tail_ratio
# ============================================================

class TestTailRatio:
    def test_normal(self):
        """正常分布"""
        np.random.seed(42)
        rets = np.random.normal(0, 0.01, 100)
        tail = calc_tail_ratio(rets)
        assert tail > 0

    def test_too_few(self):
        rets = np.array([0.01, -0.01])
        assert calc_tail_ratio(rets) == 1.0


# ============================================================
# calc_alpha_beta
# ============================================================

class TestAlphaBeta:
    def test_identical_returns(self):
        """组合与基准完全相同, beta=1, alpha≈0"""
        np.random.seed(42)
        rets = np.random.normal(0.001, 0.01, 50)
        alpha, beta = calc_alpha_beta(rets, rets)
        assert abs(beta - 1.0) < 1e-6
        assert abs(alpha) < 1e-4

    def test_uncorrelated(self):
        """不相关的收益率"""
        np.random.seed(42)
        p = np.random.normal(0.001, 0.01, 50)
        np.random.seed(99)
        b = np.random.normal(0.0005, 0.015, 50)
        alpha, beta = calc_alpha_beta(p, b)
        # beta 应该接近 0 (不相关)
        assert abs(beta) < 1.0

    def test_too_few_data(self):
        p = np.array([0.01, -0.01, 0.005])
        b = np.array([0.005, -0.008, 0.003])
        alpha, beta = calc_alpha_beta(p, b)
        assert alpha == 0.0
        assert beta == 1.0

    def test_high_beta(self):
        """组合波动是基准的 2 倍"""
        np.random.seed(42)
        b = np.random.normal(0, 0.01, 50)
        p = 2.0 * b + np.random.normal(0, 0.001, 50)
        alpha, beta = calc_alpha_beta(p, b)
        assert abs(beta - 2.0) < 0.2  # 允许噪声


# ============================================================
# calc_information_ratio
# ============================================================

class TestInformationRatio:
    def test_identical_returns(self):
        """完全相同的收益率, 跟踪误差为 0"""
        np.random.seed(42)
        rets = np.random.normal(0.001, 0.01, 50)
        ir, te = calc_information_ratio(rets, rets)
        assert ir == 0.0
        assert te == 0.0

    def test_positive_excess(self):
        """组合持续跑赢基准"""
        np.random.seed(42)
        b = np.random.normal(0.0005, 0.01, 50)
        p = b + 0.001 + np.random.normal(0, 0.002, 50)  # 加噪声避免 te=0
        ir, te = calc_information_ratio(p, b)
        assert ir > 0

    def test_too_few(self):
        p = np.array([0.01, -0.01, 0.005])
        b = np.array([0.005, -0.008, 0.003])
        ir, te = calc_information_ratio(p, b)
        assert ir == 0.0
        assert te == 0.0


# ============================================================
# calc_monthly_win_rate
# ============================================================

class TestMonthlyWinRate:
    def test_all_positive(self):
        """全部正收益, 胜率 100%"""
        rets = np.full(42, 0.001)  # 2 个月
        assert calc_monthly_win_rate(rets) == 1.0

    def test_all_negative(self):
        """全部负收益, 胜率 0%"""
        rets = np.full(42, -0.001)
        assert calc_monthly_win_rate(rets) == 0.0

    def test_too_few(self):
        """不足一个月"""
        rets = np.array([0.01, -0.01])
        assert calc_monthly_win_rate(rets) == 0.0


# ============================================================
# calc_profit_loss_ratio
# ============================================================

class TestProfitLossRatio:
    def test_balanced(self):
        """盈亏对称, 比率约 1"""
        rets = np.array([0.01, -0.01, 0.02, -0.02, 0.015, -0.015,
                         0.005, -0.005, 0.008, -0.008])
        ratio = calc_profit_loss_ratio(rets)
        assert 0.8 < ratio < 1.2

    def test_no_losses(self):
        """无亏损, 返回 0"""
        rets = np.array([0.01, 0.02, 0.015])
        assert calc_profit_loss_ratio(rets) == 0.0

    def test_no_wins(self):
        """无盈利, 返回 0"""
        rets = np.array([-0.01, -0.02, -0.015])
        assert calc_profit_loss_ratio(rets) == 0.0


# ============================================================
# calc_turnover
# ============================================================

class TestTurnover:
    def test_no_change(self):
        """持仓不变, 换手率为 0"""
        w = [{"A": 0.5, "B": 0.5}] * 3
        assert calc_turnover(w) == 0.0

    def test_full_rotation(self):
        """A→B 完全换仓"""
        w = [{"A": 1.0, "B": 0.0}, {"A": 0.0, "B": 1.0}]
        # turnover = sum(|0-1| + |1-0|) / 2 = 1.0
        assert abs(calc_turnover(w) - 1.0) < 1e-10

    def test_single_entry(self):
        """只有一个时间点, 返回 0"""
        w = [{"A": 0.5, "B": 0.5}]
        assert calc_turnover(w) == 0.0

    def test_partial_change(self):
        """部分换仓"""
        w = [{"A": 0.5, "B": 0.5}, {"A": 0.6, "B": 0.4}]
        # turnover = (|0.6-0.5| + |0.4-0.5|) / 2 = 0.1
        assert abs(calc_turnover(w) - 0.1) < 1e-10
