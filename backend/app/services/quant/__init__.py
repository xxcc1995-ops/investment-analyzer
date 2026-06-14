"""
机构级量化策略模块

实现全球顶级量化机构的核心策略：
- Multi-Factor Alpha (AQR / WorldQuant)
- Mean Reversion Z-Score (Renaissance Technologies)
- Trend Following Multi-Timeframe (Man AHL)
- Pairs Trading (D.E. Shaw)
- Multi-Strategy Ensemble (Citadel / Millennium)
"""

from .backtest_engine import run_quant_backtest
from .strategy_ensemble import run_ensemble_backtest

__all__ = ['run_quant_backtest', 'run_ensemble_backtest']
