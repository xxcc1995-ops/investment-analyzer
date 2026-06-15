"""
test_cost_model.py — 交易成本模型测试

覆盖:
- AShareCostModel.calc_buy_cost
- AShareCostModel.calc_sell_cost
- AShareCostModel.calc_round_trip_cost_rate
- AShareCostModel.estimate_market_impact
- AShareCostModel.calc_trade_cost
"""

import sys
import os
import pytest

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from app.services.quant.cost_model import AShareCostModel, DEFAULT_COST_MODEL


# ============================================================
# AShareCostModel.calc_buy_cost
# ============================================================

class TestBuyCost:
    def test_normal_amount(self):
        """正常金额: 100000 元买入"""
        model = AShareCostModel()
        cost = model.calc_buy_cost(100000)
        # 佣金: max(100000*0.0003, 5) = 30
        # 滑点: 100000*0.001 = 100
        # 过户费: 100000*0.00001 = 1
        # 总计: 30 + 100 + 1 = 131
        assert abs(cost - 131.0) < 0.01

    def test_small_amount_min_commission(self):
        """小额交易触发最低佣金"""
        model = AShareCostModel()
        cost = model.calc_buy_cost(1000)
        # 佣金: max(1000*0.0003, 5) = 5 (最低佣金)
        # 滑点: 1000*0.001 = 1
        # 过户费: 1000*0.00001 = 0.01
        # 总计: 5 + 1 + 0.01 = 6.01
        assert abs(cost - 6.01) < 0.01

    def test_zero_amount(self):
        """零金额, 佣金取最低值"""
        model = AShareCostModel()
        cost = model.calc_buy_cost(0)
        # 佣金: max(0, 5) = 5
        # 滑点: 0
        # 过户费: 0
        assert cost == 5.0

    def test_large_amount(self):
        """大额交易, 佣金不触发最低值"""
        model = AShareCostModel()
        cost = model.calc_buy_cost(10000000)
        # 佣金: max(10000000*0.0003, 5) = 3000
        # 滑点: 10000000*0.001 = 10000
        # 过户费: 10000000*0.00001 = 100
        assert cost == 3000 + 10000 + 100


# ============================================================
# AShareCostModel.calc_sell_cost
# ============================================================

class TestSellCost:
    def test_normal_amount(self):
        """正常金额卖出 (含印花税)"""
        model = AShareCostModel()
        cost = model.calc_sell_cost(100000)
        # 佣金: max(100000*0.0003, 5) = 30
        # 印花税: 100000*0.0005 = 50
        # 滑点: 100000*0.001 = 100
        # 过户费: 100000*0.00001 = 1
        # 总计: 30 + 50 + 100 + 1 = 181
        assert abs(cost - 181.0) < 0.01

    def test_sell_more_expensive_than_buy(self):
        """卖出成本应高于买入成本 (因为有印花税)"""
        model = AShareCostModel()
        amount = 100000
        assert model.calc_sell_cost(amount) > model.calc_buy_cost(amount)

    def test_small_amount(self):
        """小额卖出, 触发最低佣金"""
        model = AShareCostModel()
        cost = model.calc_sell_cost(1000)
        # 佣金: max(0.3, 5) = 5
        # 印花税: 0.5
        # 滑点: 1
        # 过户费: 0.01
        assert abs(cost - 6.51) < 0.01


# ============================================================
# AShareCostModel.calc_round_trip_cost_rate
# ============================================================

class TestRoundTripCostRate:
    def test_default_model(self):
        """默认参数下的往返成本率"""
        model = AShareCostModel()
        rate = model.calc_round_trip_cost_rate()
        # buy: 0.0003 + 0.001 + 0.00001 = 0.00131
        # sell: 0.0003 + 0.0005 + 0.001 + 0.00001 = 0.00181
        # total: 0.00312
        expected = 0.0003 + 0.001 + 0.00001 + 0.0003 + 0.0005 + 0.001 + 0.00001
        assert abs(rate - expected) < 1e-8

    def test_custom_model(self):
        """自定义费率"""
        model = AShareCostModel(
            commission_rate=0.0005,
            stamp_tax_rate=0.001,
            slippage_rate=0.002,
            transfer_fee_rate=0.00002,
        )
        rate = model.calc_round_trip_cost_rate()
        # buy: 0.0005 + 0.002 + 0.00002 = 0.00252
        # sell: 0.0005 + 0.001 + 0.002 + 0.00002 = 0.00352
        # total: 0.00604
        assert abs(rate - 0.00604) < 1e-8


# ============================================================
# AShareCostModel.estimate_market_impact
# ============================================================

class TestMarketImpact:
    def test_small_order(self):
        """小单占日成交 1%, 冲击应很小"""
        model = AShareCostModel()
        impact = model.estimate_market_impact(100000, 10000000)
        # participation = 0.01
        # impact = 0.1 * sqrt(0.01) = 0.01
        assert abs(impact - 0.01) < 1e-6

    def test_large_order(self):
        """大单占日成交 25%"""
        model = AShareCostModel()
        impact = model.estimate_market_impact(2500000, 10000000)
        # participation = 0.25
        # impact = 0.1 * sqrt(0.25) = 0.05
        assert abs(impact - 0.05) < 1e-6

    def test_capped_at_5_percent(self):
        """冲击成本上限 5%"""
        model = AShareCostModel()
        impact = model.estimate_market_impact(9000000, 10000000)
        # participation = 0.9, sqrt = 0.949, impact = 0.0949, 但上限 0.05
        assert impact == 0.05

    def test_zero_volume(self):
        """日成交为 0, 返回基础滑点率"""
        model = AShareCostModel()
        impact = model.estimate_market_impact(100000, 0)
        assert impact == model.slippage_rate

    def test_zero_order(self):
        """零订单"""
        model = AShareCostModel()
        impact = model.estimate_market_impact(0, 10000000)
        assert impact == 0.0  # participation = 0, sqrt(0) = 0


# ============================================================
# AShareCostModel.calc_trade_cost
# ============================================================

class TestTradeCost:
    def test_buy_without_impact(self):
        """买入 (无冲击成本)"""
        model = AShareCostModel()
        cost = model.calc_trade_cost(100000, "buy")
        # 等同于 calc_buy_cost
        assert cost == model.calc_buy_cost(100000)

    def test_sell_without_impact(self):
        """卖出 (无冲击成本)"""
        model = AShareCostModel()
        cost = model.calc_trade_cost(100000, "sell")
        assert cost == model.calc_sell_cost(100000)

    def test_buy_with_impact(self):
        """买入 (含冲击成本)"""
        model = AShareCostModel()
        cost_no_impact = model.calc_trade_cost(100000, "buy")
        cost_with_impact = model.calc_trade_cost(100000, "buy", daily_volume_amount=5000000)
        # 含冲击成本应更高
        assert cost_with_impact > cost_no_impact

    def test_sell_with_impact(self):
        """卖出 (含冲击成本)"""
        model = AShareCostModel()
        cost_no_impact = model.calc_trade_cost(100000, "sell")
        cost_with_impact = model.calc_trade_cost(100000, "sell", daily_volume_amount=5000000)
        assert cost_with_impact > cost_no_impact


# ============================================================
# DEFAULT_COST_MODEL
# ============================================================

class TestDefaultCostModel:
    def test_default_instance(self):
        """默认实例应使用默认参数"""
        assert DEFAULT_COST_MODEL.commission_rate == 0.0003
        assert DEFAULT_COST_MODEL.stamp_tax_rate == 0.0005
        assert DEFAULT_COST_MODEL.commission_min == 5.0


# ============================================================
# 自定义参数
# ============================================================

class TestCustomParams:
    def test_custom_commission(self):
        """自定义佣金费率"""
        model = AShareCostModel(commission_rate=0.001)
        cost = model.calc_buy_cost(100000)
        # 佣金: max(100000*0.001, 5) = 100
        # 滑点: 100
        # 过户费: 1
        assert cost == 201.0

    def test_custom_stamp_tax(self):
        """自定义印花税"""
        model = AShareCostModel(stamp_tax_rate=0.001)
        cost = model.calc_sell_cost(100000)
        # 印花税: 100000*0.001 = 100 (而非默认 50)
        default_model = AShareCostModel()
        assert cost > default_model.calc_sell_cost(100000)

    def test_zero_slippage(self):
        """零滑点"""
        model = AShareCostModel(slippage_rate=0)
        cost = model.calc_buy_cost(100000)
        # 佣金: 30, 滑点: 0, 过户费: 1
        assert cost == pytest.approx(31.0, abs=0.01)
