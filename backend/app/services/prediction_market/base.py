"""预测市场抽象基类和统一数据结构"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from datetime import datetime


@dataclass
class MarketData:
    """统一的市场数据结构"""
    id: str
    question: str
    yes_price: float
    no_price: float
    volume: float = 0
    liquidity: float = 0
    end_date: str = ''
    source: str = ''  # 'polymarket' | 'opinion'
    tag: str = ''
    slug: str = ''
    description: str = ''
    image: str = ''
    active: bool = True
    outcomes: List[str] = field(default_factory=lambda: ['Yes', 'No'])
    tokens: Dict[str, str] = field(default_factory=dict)
    raw_data: Dict = field(default_factory=dict)

    @property
    def price_sum(self) -> float:
        """YES + NO 价格总和"""
        return round(self.yes_price + self.no_price, 4)

    @property
    def has_self_arbitrage(self) -> bool:
        """单平台套利机会（Yes+No < 1）"""
        return self.price_sum > 0 and self.price_sum < 0.98

    @property
    def self_arbitrage_profit(self) -> float:
        """单平台套利利润率（%）"""
        if self.has_self_arbitrage:
            return round((1.0 - self.price_sum) / self.price_sum * 100, 2)
        return 0


@dataclass
class ArbitrageOpportunity:
    """跨平台套利机会"""
    question: str
    # 平台A（如Opinion）买YES
    platform_a: str
    platform_a_yes_price: float
    platform_a_fee_rate: float = 0
    # 平台B（如Polymarket）买NO
    platform_b: str
    platform_b_no_price: float
    platform_b_fee_rate: float = 0
    # 或者反过来
    alt_platform_a_no_price: float = 0
    alt_platform_b_yes_price: float = 0
    # 基本信息
    market_id_a: str = ''
    market_id_b: str = ''
    volume: float = 0
    end_date: str = ''

    @property
    def strategy_1_sum(self) -> float:
        """策略1：A买YES + B买NO"""
        return round(self.platform_a_yes_price + self.platform_b_no_price, 4)

    @property
    def strategy_2_sum(self) -> float:
        """策略2：A买NO + B买YES"""
        return round(self.alt_platform_a_no_price + self.alt_platform_b_yes_price, 4)

    @property
    def best_strategy(self) -> str:
        """最优策略"""
        s1 = self.strategy_1_sum
        s2 = self.strategy_2_sum
        if s1 < 1 and s2 < 1:
            return 'strategy_1' if s1 < s2 else 'strategy_2'
        elif s1 < 1:
            return 'strategy_1'
        elif s2 < 1:
            return 'strategy_2'
        return 'none'

    @property
    def best_sum(self) -> float:
        """最优策略的价格总和"""
        if self.best_strategy == 'strategy_1':
            return self.strategy_1_sum
        elif self.best_strategy == 'strategy_2':
            return self.strategy_2_sum
        return 1.0

    @property
    def raw_profit_rate(self) -> float:
        """未扣除手续费的利润率（%）"""
        best = self.best_sum
        if best < 1:
            return round((1.0 - best) / best * 100, 2)
        return 0


class PredictionMarketSource(ABC):
    """预测市场数据源抽象基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """平台名称"""
        pass

    @property
    @abstractmethod
    def base_url(self) -> str:
        """API基础URL"""
        pass

    @abstractmethod
    def get_markets(self, limit: int = 100, offset: int = 0,
                    tag: str = None) -> List[MarketData]:
        """获取市场列表"""
        pass

    @abstractmethod
    def get_market_detail(self, market_id: str) -> Optional[MarketData]:
        """获取单个市场详情"""
        pass

    @abstractmethod
    def get_price_history(self, market_id: str,
                          interval: str = '1d') -> List[Dict]:
        """获取价格历史"""
        pass

    @abstractmethod
    def calculate_fee(self, price: float, amount: float) -> float:
        """
        计算手续费

        Args:
            price: 价格 (0-1)
            amount: 交易金额

        Returns:
            手续费金额
        """
        pass
