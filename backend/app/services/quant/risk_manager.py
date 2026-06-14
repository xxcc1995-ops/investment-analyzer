"""
风险管理框架

三层止损 + Kelly仓位 + 组合回撤控制 + A股规则

参考：
- Renaissance: 波动率调整仓位
- Citadel: 实时P&L监控
- Bridgewater: 阶梯式减仓
- AQR: 动量崩盘保护
"""

import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RiskConfig:
    """风险管理配置"""
    # 个股止损
    stop_loss_pct: float = -0.08        # 硬止损 -8%
    trailing_stop_pct: float = -0.12    # 移动止损 -12%

    # 组合回撤控制
    drawdown_warn: float = -0.05        # 警戒线 -5%
    drawdown_reduce: float = -0.10      # 减仓线 -10%
    drawdown_close: float = -0.15       # 清仓线 -15%

    # 仓位限制
    max_single_pct: float = 0.15        # 单只最大仓位 15%
    max_sector_pct: float = 0.30        # 单行业最大仓位 30%
    max_total_exposure: float = 0.95    # 最大总仓位 95%

    # Kelly 参数
    kelly_fraction: float = 0.5         # 半Kelly
    kelly_cap: float = 0.15            # Kelly上限 15%

    # A股规则
    round_lot: int = 100               # 整手
    t_plus_1: bool = True              # T+1


class RiskManager:
    """风险管理器"""

    def __init__(self, config: Optional[RiskConfig] = None):
        self.config = config or RiskConfig()
        self._peak_value = 0.0
        self._current_drawdown = 0.0

    def kelly_position_size(self, win_rate: float, avg_win: float,
                            avg_loss: float) -> float:
        """
        Kelly准则仓位计算（半Kelly）

        f* = (bp - q) / b
        f = f* × kelly_fraction

        Args:
            win_rate: 胜率
            avg_win: 平均盈利幅度
            avg_loss: 平均亏损幅度（正数）

        Returns:
            建议仓位比例 [0, kelly_cap]
        """
        if avg_loss <= 0 or win_rate <= 0:
            return 0.0

        b = avg_win / avg_loss  # 赔率
        kelly = (win_rate * b - (1 - win_rate)) / b

        # 半Kelly
        position = kelly * self.config.kelly_fraction

        return max(0, min(position, self.config.kelly_cap))

    def check_stop_loss(self, entry_price: float, current_price: float,
                        peak_price: float) -> Tuple[bool, str]:
        """
        三层止损检查

        Returns:
            (是否触发止损, 原因)
        """
        pnl_pct = (current_price - entry_price) / entry_price
        from_peak_pct = (current_price - peak_price) / peak_price

        # 1. 硬止损
        if pnl_pct <= self.config.stop_loss_pct:
            return True, f"Hard stop: PnL={pnl_pct:.1%}"

        # 2. 移动止损
        if from_peak_pct <= self.config.trailing_stop_pct:
            return True, f"Trailing stop: from peak={from_peak_pct:.1%}"

        return False, ""

    def check_drawdown_control(self, current_value: float,
                               initial_value: float) -> Tuple[str, float]:
        """
        组合回撤控制

        Returns:
            (动作, 缩放比例)
            动作: 'hold', 'reduce', 'close'
        """
        # 更新峰值
        if current_value > self._peak_value:
            self._peak_value = current_value

        if self._peak_value <= 0:
            return 'hold', 1.0

        self._current_drawdown = (current_value - self._peak_value) / self._peak_value

        if self._current_drawdown <= self.config.drawdown_close:
            logger.warning(f"Drawdown {self._current_drawdown:.1%} hit close threshold")
            return 'close', 0.0
        elif self._current_drawdown <= self.config.drawdown_reduce:
            logger.warning(f"Drawdown {self._current_drawdown:.1%} hit reduce threshold")
            return 'reduce', 0.5
        elif self._current_drawdown <= self.config.drawdown_warn:
            logger.info(f"Drawdown {self._current_drawdown:.1%} hit warn threshold")
            return 'reduce', 0.8

        return 'hold', 1.0

    def check_position_limit(self, position_value: float,
                             total_value: float) -> bool:
        """检查单只仓位是否超限"""
        if total_value <= 0:
            return False
        return (position_value / total_value) <= self.config.max_single_pct

    def check_sector_limit(self, sector_values: Dict[str, float],
                           total_value: float) -> Dict[str, float]:
        """
        检查行业集中度

        Returns:
            需要减仓的行业及其缩放比例
        """
        if total_value <= 0:
            return {}

        adjustments = {}
        for sector, value in sector_values.items():
            pct = value / total_value
            if pct > self.config.max_sector_pct:
                scale = self.config.max_sector_pct / pct
                adjustments[sector] = scale
                logger.warning(f"Sector {sector} at {pct:.1%}, reducing to {self.config.max_sector_pct:.1%}")

        return adjustments

    def calc_position_shares(self, target_value: float, price: float,
                             commission_rate: float = 0.0003) -> int:
        """
        计算整手股数

        Args:
            target_value: 目标金额
            price: 当前价格
            commission_rate: 佣金率

        Returns:
            100的整数倍股数
        """
        if price <= 0:
            return 0

        # 扣除预估佣金
        effective_value = target_value * (1 - commission_rate * 2)
        shares = int(effective_value / price / self.config.round_lot) * self.config.round_lot

        return max(shares, 0)

    def adjust_for_t_plus_1(self, positions: Dict[str, Dict],
                            new_positions: Dict[str, Dict],
                            buy_date: str) -> Dict[str, Dict]:
        """
        T+1 规则调整

        今天买入的股票不能卖出
        """
        if not self.config.t_plus_1:
            return new_positions

        adjusted = {}
        for code, pos in new_positions.items():
            if code in positions:
                old_pos = positions[code]
                # 如果是今天买入的，不能卖出
                if old_pos.get('entry_date') == buy_date and pos.get('shares', 0) < old_pos.get('shares', 0):
                    adjusted[code] = old_pos  # 保持原仓位
                    continue
            adjusted[code] = pos

        return adjusted

    def scale_positions(self, positions: Dict[str, Dict],
                        scale: float) -> Dict[str, Dict]:
        """缩放所有仓位"""
        scaled = {}
        for code, pos in positions.items():
            new_pos = pos.copy()
            new_pos['shares'] = int(pos.get('shares', 0) * scale / self.config.round_lot) * self.config.round_lot
            if new_pos['shares'] > 0:
                scaled[code] = new_pos
        return scaled

    def reset(self):
        """重置状态（新回测开始时）"""
        self._peak_value = 0.0
        self._current_drawdown = 0.0
