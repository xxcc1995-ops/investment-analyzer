"""
A股交易成本模型

机构级成本建模：
- 佣金（双向，最低5元）
- 印花税（仅卖出，2023年减半后万五）
- 过户费
- 滑点（基于成交量的冲击模型）
"""

import numpy as np
from dataclasses import dataclass


@dataclass
class AShareCostModel:
    """A股交易成本配置"""
    commission_rate: float = 0.0003     # 佣金费率 万三（买卖双向）
    commission_min: float = 5.0         # 最低佣金 5元
    stamp_tax_rate: float = 0.0005      # 印花税 万五（仅卖出，2023年减半后）
    slippage_rate: float = 0.001        # 基础滑点 千一
    transfer_fee_rate: float = 0.00001  # 过户费 十万分之一（双向）
    impact_coefficient: float = 0.1     # 冲击成本系数（平方根模型）

    def calc_buy_cost(self, amount: float) -> float:
        """计算买入总成本（元）"""
        commission = max(amount * self.commission_rate, self.commission_min)
        slippage = amount * self.slippage_rate
        transfer = amount * self.transfer_fee_rate
        return commission + slippage + transfer

    def calc_sell_cost(self, amount: float) -> float:
        """计算卖出总成本（元）"""
        commission = max(amount * self.commission_rate, self.commission_min)
        stamp_tax = amount * self.stamp_tax_rate
        slippage = amount * self.slippage_rate
        transfer = amount * self.transfer_fee_rate
        return commission + stamp_tax + slippage + transfer

    def calc_round_trip_cost_rate(self) -> float:
        """一次完整买卖的成本占比"""
        buy = self.commission_rate + self.slippage_rate + self.transfer_fee_rate
        sell = self.commission_rate + self.stamp_tax_rate + self.slippage_rate + self.transfer_fee_rate
        return buy + sell

    def estimate_market_impact(self, order_amount: float, daily_volume_amount: float) -> float:
        """
        平方根市场冲击模型

        impact = coefficient * sqrt(order_amount / daily_volume_amount) * price

        参考：Almgren & Chriss (2000) 最优执行框架
        """
        if daily_volume_amount <= 0:
            return self.slippage_rate
        participation = order_amount / daily_volume_amount
        impact = self.impact_coefficient * np.sqrt(participation)
        return min(impact, 0.05)  # 上限5%

    def calc_trade_cost(self, amount: float, side: str, daily_volume_amount: float = 0) -> float:
        """
        计算交易成本（通用入口）

        Args:
            amount: 交易金额
            side: 'buy' 或 'sell'
            daily_volume_amount: 日成交额（用于冲击成本估算）
        """
        if side == 'buy':
            commission = max(amount * self.commission_rate, self.commission_min)
            slippage = amount * self.slippage_rate
            if daily_volume_amount > 0:
                impact = amount * self.estimate_market_impact(amount, daily_volume_amount)
            else:
                impact = 0
            transfer = amount * self.transfer_fee_rate
            return commission + slippage + impact + transfer
        else:
            commission = max(amount * self.commission_rate, self.commission_min)
            stamp_tax = amount * self.stamp_tax_rate
            slippage = amount * self.slippage_rate
            if daily_volume_amount > 0:
                impact = amount * self.estimate_market_impact(amount, daily_volume_amount)
            else:
                impact = 0
            transfer = amount * self.transfer_fee_rate
            return commission + stamp_tax + slippage + impact + transfer


# 默认成本模型实例
DEFAULT_COST_MODEL = AShareCostModel()
