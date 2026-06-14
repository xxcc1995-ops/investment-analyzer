"""
策略基类

所有量化策略的公共接口：
- fit(): 在训练数据上拟合参数
- generate_signals(): 生成交易信号
- get_portfolio(): 根据信号构建投资组合
- get_params(): 获取当前参数
- set_params(): 设置参数
"""

import numpy as np
import pandas as pd
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field


@dataclass
class Signal:
    """交易信号"""
    code: str
    direction: int       # 1=买入, -1=卖出, 0=持有
    strength: float      # 信号强度 [0, 1]
    reason: str = ''     # 信号原因


@dataclass
class Position:
    """持仓"""
    code: str
    shares: int
    entry_price: float
    entry_date: str
    weight: float        # 目标权重
    stop_loss: float = 0.0
    trailing_stop: float = 0.0


class BaseStrategy(ABC):
    """量化策略基类"""

    name: str = 'base'
    description: str = ''
    version: str = '1.0'

    def __init__(self, params: Optional[Dict] = None):
        self.params = params or {}
        self._is_fitted = False

    @abstractmethod
    def fit(self, price_data: Dict[str, pd.DataFrame],
            fundamental_data: Optional[pd.DataFrame] = None) -> 'BaseStrategy':
        """
        在训练数据上拟合策略参数

        Args:
            price_data: {code: OHLCV DataFrame}
            fundamental_data: 基本面快照 DataFrame

        Returns:
            self
        """
        pass

    @abstractmethod
    def generate_signals(self, price_data: Dict[str, pd.DataFrame],
                         fundamental_data: Optional[pd.DataFrame] = None,
                         current_date: Optional[str] = None) -> List[Signal]:
        """
        生成交易信号

        Args:
            price_data: {code: OHLCV DataFrame}
            fundamental_data: 基本面快照
            current_date: 当前日期（用于walk-forward）

        Returns:
            信号列表
        """
        pass

    @abstractmethod
    def get_portfolio(self, signals: List[Signal],
                      current_positions: Dict[str, Position],
                      available_capital: float) -> Dict[str, Position]:
        """
        根据信号构建目标组合

        Args:
            signals: 交易信号
            current_positions: 当前持仓
            available_capital: 可用资金

        Returns:
            目标持仓字典
        """
        pass

    def get_params(self) -> Dict[str, Any]:
        """获取当前参数"""
        return self.params.copy()

    def set_params(self, params: Dict[str, Any]):
        """设置参数"""
        self.params.update(params)
        self._is_fitted = False

    @property
    def is_fitted(self) -> bool:
        return self._is_fitted

    def __repr__(self):
        return f"{self.name}({self.params})"


def equal_weight_portfolio(codes: List[str], available_capital: float,
                           prices: Dict[str, float],
                           cost_rate: float = 0.001,
                           reserve_pct: float = 0.05) -> Dict[str, Position]:
    """
    等权组合构建

    Args:
        codes: 选中的股票代码列表
        available_capital: 可用资金
        prices: {code: current_price}
        cost_rate: 预估交易成本率
        reserve_pct: 现金储备比例

    Returns:
        {code: Position}
    """
    if not codes:
        return {}

    # 扣除现金储备
    investable = available_capital * (1 - reserve_pct)
    per_stock = investable / len(codes)

    positions = {}
    for code in codes:
        price = prices.get(code, 0)
        if price <= 0:
            continue

        # 计算可买股数（100股整数倍）
        shares = int(per_stock / (price * (1 + cost_rate)) / 100) * 100
        if shares < 100:
            continue

        cost = shares * price
        positions[code] = Position(
            code=code,
            shares=shares,
            entry_price=price,
            entry_date='',
            weight=1.0 / len(codes),
        )

    return positions


def volatility_weighted_portfolio(codes: List[str], available_capital: float,
                                  prices: Dict[str, float],
                                  volatilities: Dict[str, float],
                                  target_vol: float = 0.20,
                                  cost_rate: float = 0.001,
                                  reserve_pct: float = 0.05) -> Dict[str, Position]:
    """
    波动率加权组合（Man AHL 风格）

    每只股票的权重与其波动率成反比，使得组合中每只股票贡献相等的风险。

    Args:
        codes: 选中的股票代码列表
        available_capital: 可用资金
        prices: {code: current_price}
        volatilities: {code: annualized_volatility}
        target_vol: 目标组合波动率
        cost_rate: 预估交易成本率
        reserve_pct: 现金储备比例

    Returns:
        {code: Position}
    """
    if not codes:
        return {}

    investable = available_capital * (1 - reserve_pct)

    # 计算波动率倒数权重
    inv_vols = {}
    for code in codes:
        vol = volatilities.get(code, 0.30)  # 默认30%
        if vol > 0:
            inv_vols[code] = 1.0 / vol

    if not inv_vols:
        return equal_weight_portfolio(codes, available_capital, prices, cost_rate, reserve_pct)

    # 归一化权重
    total_inv_vol = sum(inv_vols.values())
    weights = {code: iv / total_inv_vol for code, iv in inv_vols.items()}

    # 应用波动率目标缩放
    # 组合波动率 ≈ sum(w_i * vol_i)，需要缩放到目标
    portfolio_vol = sum(weights[c] * volatilities.get(c, 0.30) for c in codes)
    if portfolio_vol > 0:
        scale = min(target_vol / portfolio_vol, 2.0)  # 最大2倍杠杆
        weights = {c: w * scale for c, w in weights.items()}

    # 构建持仓
    positions = {}
    for code in codes:
        price = prices.get(code, 0)
        weight = weights.get(code, 0)
        if price <= 0 or weight <= 0:
            continue

        alloc = investable * weight
        shares = int(alloc / (price * (1 + cost_rate)) / 100) * 100
        if shares < 100:
            continue

        positions[code] = Position(
            code=code,
            shares=shares,
            entry_price=price,
            entry_date='',
            weight=weight,
        )

    return positions
