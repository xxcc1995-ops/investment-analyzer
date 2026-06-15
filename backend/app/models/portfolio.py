"""组合管理数据模型"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class Transaction(BaseModel):
    """交易记录"""
    id: str
    code: str
    name: str
    market: str = "A"  # A / HK / US
    type: str  # buy / sell / dividend / split
    shares: float  # 交易股数（买入为正，卖出为负）
    price: float  # 交易价格
    amount: float  # 交易金额
    fee: float = 0.0  # 手续费（佣金+印花税+过户费）
    reason: str = ""  # 交易理由
    decision_id: str = ""  # 关联的Decision Guard决策ID
    created_at: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class Position(BaseModel):
    """持仓"""
    code: str
    name: str
    market: str = "A"
    shares: float = 0  # 持股数量
    avg_cost: float = 0  # 持仓成本价
    current_price: float = 0  # 当前价格
    market_value: float = 0  # 持仓市值
    unrealized_pnl: float = 0  # 浮动盈亏金额
    unrealized_pnl_pct: float = 0  # 浮动盈亏比例 (%)
    position_pct: float = 0  # 占总仓位比例 (%)
    total_cost: float = 0  # 总投入成本
    buy_date: str = ""  # 首次买入日期
    holding_days: int = 0  # 持有天数
    decision_id: str = ""  # 关联决策ID


class PortfolioSummary(BaseModel):
    """组合概览"""
    total_cost: float = 0  # 总投入
    total_value: float = 0  # 总市值
    total_pnl: float = 0  # 总盈亏
    total_pnl_pct: float = 0  # 总收益率 (%)
    cash: float = 0  # 现金余额
    position_count: int = 0  # 持仓数量
    positions: list[Position] = Field(default_factory=list)
    sector_exposure: dict = Field(default_factory=dict)  # 行业暴露
    today_pnl: float = 0  # 今日盈亏


class PerformancePoint(BaseModel):
    """收益曲线数据点"""
    date: str
    value: float  # 组合净值
    pnl: float  # 累计盈亏
    pnl_pct: float  # 累计收益率 (%)


class RiskExposure(BaseModel):
    """风险暴露"""
    sector_exposure: dict = Field(default_factory=dict)  # 行业占比
    top_holdings: list[dict] = Field(default_factory=list)  # 前N大持仓
    concentration_warnings: list[str] = Field(default_factory=list)  # 集中度警告
    max_single_pct: float = 0  # 最大单一持仓占比
    max_sector_pct: float = 0  # 最大行业占比


class StressTestScenario(BaseModel):
    """压力测试场景"""
    name: str  # 场景名称
    type: str  # market / rate
    shock: float  # 冲击幅度
    total_loss: float = 0  # 总损失金额
    total_loss_pct: float = 0  # 总损失比例(%)
    portfolio_after: float = 0  # 冲击后组合市值
    position_impacts: list[dict] = Field(default_factory=list)  # 各持仓影响


class PortfolioRiskAnalysis(BaseModel):
    """组合风险分析结果"""
    has_data: bool = False
    message: str = ""
    total_value: float = 0
    position_count: int = 0
    # VaR
    var_95: dict = Field(default_factory=dict)  # {var_pct, var_amount, confidence, data_days}
    var_99: dict = Field(default_factory=dict)
    # CVaR
    cvar_95: dict = Field(default_factory=dict)  # {cvar_pct, cvar_amount, confidence}
    # 波动率 & 回撤
    volatility_annual: float = 0  # 年化波动率(%)
    max_drawdown: float = 0  # 最大回撤(%)
    sharpe_ratio: float = 0  # 夏普比率
    # 集中度
    concentration_hhi: float = 0  # HHI指数
    top3_pct: float = 0  # 前3大持仓占比(%)
    # 压力测试
    stress_test: list[StressTestScenario] = Field(default_factory=list)
    data_days: int = 0  # 使用的历史数据天数
