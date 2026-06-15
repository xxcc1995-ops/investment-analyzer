"""
test_dcf.py — DCF 估值测试

覆盖:
- DCFService.__init__ 参数校验
- DCFService.calculate_intrinsic_value (单阶段)
- DCFService.calculate_two_stage_dcf (两阶段)
- DCFService.calculate_staged_dcf (分阶段)
- DCFService.estimate_growth_rate
- calculate_graham_number
- estimate_wacc
- calc_ps_ratio
- calc_peg
- get_pe_level / get_pb_level / get_peg_level
- ddm_gordon (Gordon DDM)
"""

import sys
import os
import math
import pytest

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from app.services.dcf import (
    DCFService,
    DCFConfig,
    calculate_graham_number,
    estimate_wacc,
    calc_ps_ratio,
    calc_peg,
    get_pe_level,
    get_pb_level,
    get_peg_level,
    get_ps_level,
    get_ev_ebitda_level,
    ddm_gordon,
)


# ============================================================
# DCFService.__init__ 参数校验
# ============================================================

class TestDCFServiceInit:
    def test_valid_params(self):
        """正常参数, 不抛异常"""
        svc = DCFService(discount_rate=0.10, terminal_growth_rate=0.03)
        assert svc.discount_rate == 0.10
        assert svc.terminal_growth_rate == 0.03

    def test_discount_rate_too_low(self):
        """折现率 <= 永续增长率, 应抛 ValueError"""
        with pytest.raises(ValueError, match="折现率"):
            DCFService(discount_rate=0.03, terminal_growth_rate=0.03)

    def test_discount_rate_lower_than_terminal(self):
        """折现率 < 永续增长率"""
        with pytest.raises(ValueError):
            DCFService(discount_rate=0.02, terminal_growth_rate=0.05)

    def test_negative_terminal_growth(self):
        """负永续增长率"""
        with pytest.raises(ValueError, match="永续增长率"):
            DCFService(discount_rate=0.10, terminal_growth_rate=-0.01)

    def test_terminal_growth_too_high(self):
        """永续增长率 > 5%"""
        with pytest.raises(ValueError, match="永续增长率"):
            DCFService(discount_rate=0.15, terminal_growth_rate=0.06)

    def test_invalid_safety_margin(self):
        """安全边际不在 0-1 范围"""
        with pytest.raises(ValueError, match="安全边际"):
            DCFService(discount_rate=0.10, terminal_growth_rate=0.03, safety_margin=1.0)

    def test_negative_safety_margin(self):
        with pytest.raises(ValueError, match="安全边际"):
            DCFService(discount_rate=0.10, terminal_growth_rate=0.03, safety_margin=-0.1)


# ============================================================
# DCFService.calculate_intrinsic_value (单阶段)
# ============================================================

class TestIntrinsicValue:
    @pytest.fixture
    def dcf(self):
        return DCFService(discount_rate=0.10, terminal_growth_rate=0.03, safety_margin=0.30)

    def test_basic(self, dcf):
        """基本 DCF 计算"""
        result = dcf.calculate_intrinsic_value(
            current_fcf=10.0, growth_rate=0.10, shares=10.0
        )
        assert result["intrinsic_value"] > 0
        assert result["buy_price"] > 0
        assert result["buy_price"] < result["intrinsic_value"]
        assert len(result["fcf_projections"]) == 10

    def test_with_net_debt(self, dcf):
        """有净负债时, 股权价值 = 企业价值 - 净负债"""
        no_debt = dcf.calculate_intrinsic_value(
            current_fcf=10.0, growth_rate=0.10, shares=10.0, net_debt=0
        )
        with_debt = dcf.calculate_intrinsic_value(
            current_fcf=10.0, growth_rate=0.10, shares=10.0, net_debt=50.0
        )
        # 有负债时内在价值更低
        assert with_debt["intrinsic_value"] < no_debt["intrinsic_value"]

    def test_with_current_price(self, dcf):
        """提供当前价格, 应计算 upside"""
        result = dcf.calculate_intrinsic_value(
            current_fcf=10.0, growth_rate=0.10, shares=10.0, current_price=50.0
        )
        assert "upside_pct" in result
        assert "is_undervalued" in result
        assert "is_buy_zone" in result

    def test_zero_shares_raises(self, dcf):
        """总股本为 0, 应抛异常"""
        with pytest.raises(ValueError, match="总股本"):
            dcf.calculate_intrinsic_value(
                current_fcf=10.0, growth_rate=0.10, shares=0
            )

    def test_higher_growth_higher_value(self, dcf):
        """增长率越高, 内在价值越高"""
        low = dcf.calculate_intrinsic_value(current_fcf=10.0, growth_rate=0.05, shares=10.0)
        high = dcf.calculate_intrinsic_value(current_fcf=10.0, growth_rate=0.15, shares=10.0)
        assert high["intrinsic_value"] > low["intrinsic_value"]

    def test_terminal_pct_reasonable(self, dcf):
        """终值占比应在合理范围 (通常 50-80%)"""
        result = dcf.calculate_intrinsic_value(
            current_fcf=10.0, growth_rate=0.10, shares=10.0
        )
        assert 30 < result["terminal_pct"] < 95

    def test_safety_margin_applied(self, dcf):
        """买点 = 内在价值 * (1 - 安全边际)"""
        result = dcf.calculate_intrinsic_value(
            current_fcf=10.0, growth_rate=0.10, shares=10.0
        )
        expected_buy = result["intrinsic_value"] * (1 - 0.30)
        assert abs(result["buy_price"] - round(expected_buy, 2)) < 0.02


# ============================================================
# DCFService.calculate_two_stage_dcf (两阶段)
# ============================================================

class TestTwoStageDCF:
    @pytest.fixture
    def dcf(self):
        return DCFService(discount_rate=0.10, terminal_growth_rate=0.03, safety_margin=0.30)

    def test_basic(self, dcf):
        result = dcf.calculate_two_stage_dcf(
            current_fcf=10.0,
            high_growth_rate=0.20,
            stable_growth_rate=0.05,
            shares=10.0,
            high_growth_years=5,
        )
        assert result["intrinsic_value"] > 0
        assert result["model"] == "two_stage"
        assert len(result["fcf_projections"]) == 10  # 5 high + 5 stable

    def test_higher_than_single_stage(self, dcf):
        """两阶段模型 (高增长→稳定) 应给出不同于单阶段的结果"""
        single = dcf.calculate_intrinsic_value(
            current_fcf=10.0, growth_rate=0.20, shares=10.0
        )
        two_stage = dcf.calculate_two_stage_dcf(
            current_fcf=10.0,
            high_growth_rate=0.20,
            stable_growth_rate=0.05,
            shares=10.0,
            high_growth_years=5,
        )
        # 两阶段模型的稳定期增长率更低, 所以内在价值应低于单阶段 (高增长贯穿)
        assert two_stage["intrinsic_value"] < single["intrinsic_value"]

    def test_invalid_high_growth_years(self, dcf):
        """高增长年数超出范围"""
        with pytest.raises(ValueError, match="高增长年数"):
            dcf.calculate_two_stage_dcf(
                current_fcf=10.0,
                high_growth_rate=0.20,
                stable_growth_rate=0.05,
                shares=10.0,
                high_growth_years=0,
            )


# ============================================================
# DCFService.calculate_staged_dcf (分阶段)
# ============================================================

class TestStagedDCF:
    @pytest.fixture
    def dcf(self):
        return DCFService(discount_rate=0.10, terminal_growth_rate=0.03)

    def test_basic(self, dcf):
        rates = [0.20, 0.18, 0.15, 0.12, 0.10, 0.08, 0.06, 0.05, 0.04, 0.03]
        result = dcf.calculate_staged_dcf(
            current_fcf=10.0, growth_rates=rates, shares=10.0
        )
        assert result["intrinsic_value"] > 0
        assert result["model"] == "Staged DCF (达摩达兰)"
        assert len(result["fcf_projections"]) == 10
        assert len(result["pv_details"]) == 10

    def test_too_few_rates(self, dcf):
        """增长率列表不足 2 个"""
        with pytest.raises(ValueError, match="至少需要2个值"):
            dcf.calculate_staged_dcf(
                current_fcf=10.0, growth_rates=[0.10], shares=10.0
            )


# ============================================================
# DCFService.estimate_growth_rate
# ============================================================

class TestEstimateGrowthRate:
    @pytest.fixture
    def dcf(self):
        return DCFService(discount_rate=0.10, terminal_growth_rate=0.03)

    def test_normal(self, dcf):
        """正常历史 FCF"""
        hist = [10.0, 12.0, 14.0, 17.0, 20.0]
        rate = dcf.estimate_growth_rate(hist)
        assert 0.02 <= rate <= 0.25

    def test_too_few(self, dcf):
        """数据不足, 返回默认 5%"""
        assert dcf.estimate_growth_rate([10.0]) == 0.05

    def test_all_negative(self, dcf):
        """全部负 FCF, 返回 3%"""
        assert dcf.estimate_growth_rate([-1.0, -2.0, -3.0]) == 0.03

    def test_conservative(self, dcf):
        """估算值应低于实际 CAGR"""
        hist = [10.0, 15.0, 20.0, 25.0, 30.0]
        rate = dcf.estimate_growth_rate(hist)
        # CAGR ≈ (30/10)^(1/4) - 1 ≈ 31.6%
        cagr = (30 / 10) ** (1 / 4) - 1
        assert rate < cagr  # 保守处理


# ============================================================
# calculate_graham_number
# ============================================================

class TestGrahamNumber:
    def test_normal(self):
        """EPS=5, BVPS=20, graham_value = sqrt(22.5*5*20) = sqrt(2250) ≈ 47.43"""
        result = calculate_graham_number(5.0, 20.0)
        assert result["applicable"] is True
        assert abs(result["graham_value"] - 47.43) < 0.1
        assert result["implied_pe"] == round(47.43 / 5.0, 1)
        assert result["implied_pb"] == round(47.43 / 20.0, 1)

    def test_negative_eps(self):
        """EPS 为负, 不适用"""
        result = calculate_graham_number(-1.0, 20.0)
        assert result["applicable"] is False
        assert result["graham_value"] is None
        assert len(result["warnings"]) > 0

    def test_negative_bvps(self):
        """BVPS 为负, 不适用"""
        result = calculate_graham_number(5.0, -10.0)
        assert result["applicable"] is False
        assert result["graham_value"] is None

    def test_zero_eps(self):
        """EPS 为 0, 不适用"""
        result = calculate_graham_number(0.0, 20.0)
        assert result["applicable"] is False

    def test_high_growth_not_suitable(self):
        """高增长企业不适用 (但公式本身不校验, 只是计算)"""
        result = calculate_graham_number(5.0, 10.0)
        assert result["applicable"] is True
        # graham_value = sqrt(22.5 * 5 * 10) = sqrt(1125) ≈ 33.54
        assert result["graham_value"] > 0


# ============================================================
# estimate_wacc
# ============================================================

class TestEstimateWACC:
    def test_no_debt(self):
        """无负债, WACC = 股权成本"""
        wacc = estimate_wacc(
            risk_free_rate=0.025,
            market_risk_premium=0.06,
            beta=1.0,
            debt_ratio=0.0,
        )
        # Re = 0.025 + 1.0 * 0.06 = 0.085
        # WACC = 1.0 * 0.085 = 0.085, 但最低 0.08
        assert abs(wacc - 0.085) < 0.001

    def test_with_debt(self):
        """有负债"""
        wacc = estimate_wacc(
            risk_free_rate=0.025,
            market_risk_premium=0.06,
            beta=1.0,
            debt_ratio=50.0,
            cost_of_debt=0.05,
            tax_rate=0.25,
        )
        # Re = 0.085, Rd*(1-T) = 0.05*0.75 = 0.0375
        # WACC = 0.5*0.085 + 0.5*0.0375 = 0.06125, 但最低 0.08
        assert wacc >= 0.08

    def test_minimum_wacc(self):
        """WACC 最低 8%"""
        wacc = estimate_wacc(
            risk_free_rate=0.01,
            market_risk_premium=0.02,
            beta=0.5,
            debt_ratio=0.0,
        )
        assert wacc >= 0.08

    def test_high_beta(self):
        """高 beta 应导致更高的 WACC"""
        low_beta = estimate_wacc(beta=0.5, debt_ratio=0.0)
        high_beta = estimate_wacc(beta=2.0, debt_ratio=0.0)
        assert high_beta > low_beta


# ============================================================
# calc_ps_ratio / calc_peg
# ============================================================

class TestPSandPEG:
    def test_ps_normal(self):
        assert calc_ps_ratio(100.0, 20.0) == 5.0

    def test_ps_zero_revenue(self):
        assert calc_ps_ratio(100.0, 0) is None

    def test_ps_negative_price(self):
        assert calc_ps_ratio(-10.0, 20.0) is None

    def test_peg_normal(self):
        # PE=20, growth=0.20 (20%), PEG = 20/20 = 1.0
        assert calc_peg(20.0, 0.20) == 1.0

    def test_peg_negative_pe(self):
        assert calc_peg(-10.0, 0.20) is None

    def test_peg_zero_growth(self):
        assert calc_peg(20.0, 0.0) is None

    def test_peg_low_growth(self):
        """增长率 < 1%, PEG 无意义"""
        assert calc_peg(20.0, 0.005) is None


# ============================================================
# get_pe_level / get_pb_level / get_peg_level
# ============================================================

class TestValuationLevels:
    def test_pe_levels(self):
        assert get_pe_level(5.0) == "低估"
        assert get_pe_level(15.0) == "合理"
        assert get_pe_level(30.0) == "偏高"
        assert get_pe_level(60.0) == "高估"
        assert get_pe_level(-10.0) == "N/A"
        assert get_pe_level(None) == "N/A"

    def test_pb_levels(self):
        assert get_pb_level(0.5) == "低估"
        assert get_pb_level(1.5) == "合理"
        assert get_pb_level(3.0) == "偏高"
        assert get_pb_level(8.0) == "高估"
        assert get_pb_level(-1.0) == "N/A"

    def test_peg_levels(self):
        assert get_peg_level(0.3) == "显著低估"
        assert get_peg_level(0.8) == "低估"
        assert get_peg_level(1.2) == "合理"
        assert get_peg_level(1.8) == "偏高"
        assert get_peg_level(2.5) == "高估"

    def test_ps_levels(self):
        assert get_ps_level(0.5, "default") == "低估"
        assert get_ps_level(2.0, "default") == "合理"
        assert get_ps_level(5.0, "default") == "偏高"
        assert get_ps_level(10.0, "default") == "高估"

    def test_ps_tech_industry(self):
        """科技行业 PS 阈值更高"""
        assert get_ps_level(4.0, "tech") == "合理"
        assert get_ps_level(20.0, "tech") == "高估"

    def test_ev_ebitda_levels(self):
        assert get_ev_ebitda_level(5.0) == "低估"
        assert get_ev_ebitda_level(12.0) == "合理"
        assert get_ev_ebitda_level(20.0) == "偏高"
        assert get_ev_ebitda_level(35.0) == "高估"
        assert get_ev_ebitda_level(-1.0) == "N/A"


# ============================================================
# ddm_gordon (Gordon DDM)
# ============================================================

class TestDDMGordon:
    def test_basic(self):
        """DPS=2, growth=3%, discount=10%
        V = 2*(1.03) / (0.10-0.03) = 2.06/0.07 ≈ 29.43
        """
        result = ddm_gordon(dps=2.0, dividend_growth_rate=0.03, discount_rate=0.10)
        assert abs(result["intrinsic_value"] - 29.43) < 0.1
        assert result["dps_next"] == 2.06
        assert result["model"] == "Gordon DDM"

    def test_with_current_price(self):
        """提供当前价格, 应计算安全边际"""
        result = ddm_gordon(
            dps=2.0, dividend_growth_rate=0.03,
            discount_rate=0.10, current_price=20.0,
        )
        assert result["safety_margin"] > 0  # 内在价值 > 当前价
        assert result["upside"] > 0

    def test_discount_rate_too_low(self):
        """折现率 <= 增长率, 应抛异常"""
        with pytest.raises(ValueError, match="折现率"):
            ddm_gordon(dps=2.0, dividend_growth_rate=0.10, discount_rate=0.10)

    def test_zero_growth(self):
        """零增长 DDM (永续债券)"""
        result = ddm_gordon(dps=2.0, dividend_growth_rate=0.0, discount_rate=0.10)
        # V = 2.0 / 0.10 = 20.0
        assert abs(result["intrinsic_value"] - 20.0) < 0.01

    def test_buy_price_has_margin(self):
        """买点应低于内在价值"""
        result = ddm_gordon(dps=2.0, dividend_growth_rate=0.03, discount_rate=0.10)
        assert result["buy_price"] < result["intrinsic_value"]
