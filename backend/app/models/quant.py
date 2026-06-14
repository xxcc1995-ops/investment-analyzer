"""
量化回测 API 数据模型
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime


class QuantBacktestRequest(BaseModel):
    """量化回测请求"""
    strategy: str = Field('multi_factor', description="策略名称")
    start_date: str = Field('2020-01-01', description="开始日期")
    end_date: str = Field('2025-12-31', description="结束日期")
    initial_capital: float = Field(1_000_000, description="初始资金")
    benchmark: str = Field('000300', description="基准指数代码")
    rebalance_freq: str = Field('monthly', description="再平衡频率")
    walk_forward: bool = Field(True, description="Walk-Forward验证")
    top_n: int = Field(20, description="选股数量")
    strategy_params: Optional[Dict[str, Any]] = Field(None, description="策略参数覆盖")


class EnsembleBacktestRequest(BaseModel):
    """集成策略回测请求"""
    strategies: List[str] = Field(
        default=['multi_factor', 'mean_reversion', 'trend_following'],
        description="策略列表"
    )
    start_date: str = Field('2020-01-01')
    end_date: str = Field('2025-12-31')
    initial_capital: float = Field(1_000_000)
    benchmark: str = Field('000300')
    allocation_method: str = Field('risk_parity', description="分配方法")
    walk_forward: bool = Field(True)


class StrategyInfo(BaseModel):
    """策略信息"""
    name: str
    display_name: str
    description: str
    version: str
    params: Dict[str, Any]
    inspiration: str


class PerformanceMetrics(BaseModel):
    """绩效指标"""
    total_return: Optional[float] = None
    annual_return: Optional[float] = None
    volatility: Optional[float] = None
    max_drawdown: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    calmar_ratio: Optional[float] = None
    alpha: Optional[float] = None
    beta: Optional[float] = None
    information_ratio: Optional[float] = None
    monthly_win_rate: Optional[float] = None
    profit_loss_ratio: Optional[float] = None
    benchmark_total_return: Optional[float] = None
    benchmark_annual_return: Optional[float] = None
    excess_return: Optional[float] = None
    n_folds: Optional[int] = None
    fold_returns: Optional[List[float]] = None
    param_stability: Optional[Dict[str, float]] = None
    yearly_returns: Optional[Dict[str, float]] = None


class BacktestResponse(BaseModel):
    """回测响应"""
    strategy: str
    params: Dict[str, Any]
    start_date: str
    end_date: str
    walk_forward: bool
    metrics: PerformanceMetrics
    equity_curve: List[float]
    final_value: float
    trade_log: Optional[List[Dict[str, Any]]] = None
    walk_forward_report: Optional[str] = None
    fold_details: Optional[List[Dict[str, Any]]] = None


class EnsembleResponse(BaseModel):
    """集成策略响应"""
    strategy: str
    allocation_method: str
    metrics: PerformanceMetrics
    equity_curve: List[float]
    final_value: float
    strategy_contributions: Dict[str, Dict[str, float]]
    weights: Dict[str, float]
    correlation_matrix: List[List[float]]
    high_correlation_warning: bool


class FactorAnalysisRequest(BaseModel):
    """因子分析请求"""
    factor: str = Field('momentum', description="因子名称")
    start_date: str = Field('2020-01-01')
    end_date: str = Field('2025-12-31')
    n_quantiles: int = Field(5, description="分组数")
