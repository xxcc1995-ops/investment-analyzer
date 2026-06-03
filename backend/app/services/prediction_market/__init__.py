"""预测市场适配器模块 - 支持多平台套利分析"""

from .base import MarketData, PredictionMarketSource
from .polymarket import PolymarketSource
from .opinion import OpinionSource

__all__ = ['MarketData', 'PredictionMarketSource', 'PolymarketSource', 'OpinionSource']
