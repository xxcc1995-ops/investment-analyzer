# -*- coding: utf-8 -*-
"""拖拉机套利数据模型

Pydantic模型，用于请求验证和响应序列化。
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


# ==================== 枚举 ====================

class OperationType(str, Enum):
    LOGIN_ONLY = "仅登录查询"
    SUBSCRIBE = "场内申购"
    SELL = "卖出"
    REDEEM = "赎回"
    CANCEL = "全部撤单"
    REVERSE_REPO = "逆回购"
    TRANSFER = "转账回银行"


class BrokerType(str, Enum):
    HUABAO = "huabao"
    YINHE = "yinhe"


class ArbitrageDirection(str, Enum):
    PREMIUM = "溢价"    # 溢价套利: 场内申购 -> 卖出
    DISCOUNT = "折价"   # 折价套利: 买入 -> 赎回
    NONE = "none"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ==================== 账户相关 ====================

class TractorAccount(BaseModel):
    account_id: str
    name: str = ""
    broker_type: BrokerType = BrokerType.HUABAO
    enabled: bool = True


class AccountWithBalance(TractorAccount):
    """带资金信息的账户"""
    available_cash: float = 0.0       # 可用资金
    total_assets: float = 0.0         # 总资产
    fund_shares: int = 0              # 持有基金份额
    fund_cost: float = 0.0            # 持仓成本
    fund_profit: float = 0.0          # 持仓浮盈
    last_query_time: Optional[str] = None


class AccountCreateRequest(BaseModel):
    account_id: str = Field(..., min_length=1, max_length=20)
    password: str = Field(..., min_length=1)
    broker_type: BrokerType = BrokerType.HUABAO
    name: str = ""


class AccountUpdateRequest(BaseModel):
    password: Optional[str] = None
    broker_type: Optional[BrokerType] = None
    name: Optional[str] = None
    enabled: Optional[bool] = None
    available_cash: Optional[float] = None


# ==================== 套利机会 ====================

class ArbitrageOpportunity(BaseModel):
    """LOF套利机会"""
    fund_code: str
    fund_name: str
    direction: ArbitrageDirection
    premium_pct: float = 0.0              # 溢价率 %
    est_nav: float = 0.0                  # 估算净值
    fund_price: float = 0.0               # 场内价格
    official_nav: float = 0.0             # 官方净值
    apply_limit: str = ""                 # 限购金额
    apply_status: str = ""                # 申购状态
    turnover: float = 0.0                 # 成交额(万)
    apply_fee: float = 0.0               # 申购费率 %
    redeem_fee: float = 0.0              # 赎回费率 %
    net_profit_pct: float = 0.0          # 扣费后净收益 %
    risk_level: RiskLevel = RiskLevel.MEDIUM
    est_confidence: str = "unknown"
    arb_eval: Optional[dict] = None


class ScanRequest(BaseModel):
    min_premium: float = Field(2.0, ge=0, description="最低溢价率绝对值%")
    min_amount: float = Field(1000, ge=0, description="最低成交额(万元)")
    direction: str = Field("all", description="方向: all/溢价/折价")


# ==================== 资金分配 ====================

class AccountAllocation(BaseModel):
    """单个账户的资金分配方案"""
    account_id: str
    account_name: str
    broker_type: str
    available_cash: float = 0.0           # 账户可用资金
    recommended_amount: float = 0.0       # 推荐申购/卖出金额
    max_amount: float = 0.0              # 可申购上限(考虑限购和余额)
    shares_to_sell: int = 0              # 卖出数量(卖出操作时)
    notes: List[str] = Field(default_factory=list)


class AllocationPlan(BaseModel):
    """资金分配方案"""
    fund_code: str
    fund_name: str
    direction: ArbitrageDirection
    premium_pct: float = 0.0
    apply_limit_per_account: float = 0.0  # 每户限购金额
    total_accounts: int = 0
    enabled_accounts: int = 0
    allocations: List[AccountAllocation] = Field(default_factory=list)
    total_amount: float = 0.0             # 总分配金额
    estimated_profit: float = 0.0         # 预估总利润
    warnings: List[str] = Field(default_factory=list)


# ==================== 风险控制 ====================

class RiskSettings(BaseModel):
    """风控参数"""
    min_premium_pct: float = Field(2.0, ge=0, description="最低溢价率%")
    max_single_amount: float = Field(500000, ge=0, description="单账户最大申购金额")
    max_total_amount: float = Field(2000000, ge=0, description="全部账户最大总金额")
    min_cash_reserve: float = Field(10000, ge=0, description="每账户最低保留资金")
    max_daily_operations: int = Field(10, ge=1, description="每日最大操作次数")
    require_trading_hours: bool = Field(True, description="是否要求在交易时段操作")
    block_low_liquidity: bool = Field(True, description="是否屏蔽低流动性基金")
    min_turnover: float = Field(1000, ge=0, description="最低成交额(万元)")


class RiskCheckResult(BaseModel):
    """风控检查结果"""
    passed: bool
    level: RiskLevel = RiskLevel.LOW
    checks: List[dict] = Field(default_factory=list)  # [{name, passed, message, level}]
    warnings: List[str] = Field(default_factory=list)
    blocked_reasons: List[str] = Field(default_factory=list)


# ==================== 操作记录 ====================

class OperationRecord(BaseModel):
    """操作记录"""
    id: str = ""
    timestamp: str = ""
    operation: OperationType
    fund_code: str = ""
    fund_name: str = ""
    direction: ArbitrageDirection = ArbitrageDirection.NONE
    account_ids: List[str] = Field(default_factory=list)
    premium_pct: float = 0.0              # 执行时溢价率
    est_nav: float = 0.0                  # 执行时估算净值
    fund_price: float = 0.0               # 执行时价格
    amounts: List[float] = Field(default_factory=list)  # 每账户金额
    sell_price: float = 0.0
    sell_quantity: int = 0
    success: bool = False
    message: str = ""
    elapsed_seconds: float = 0.0
    # P&L (卖出/赎回后回填)
    realized_pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    entry_price: Optional[float] = None   # 买入价(申购时净值)
    exit_price: Optional[float] = None    # 卖出价


class PnLSummary(BaseModel):
    """损益汇总"""
    total_operations: int = 0
    total_subscribes: int = 0
    total_sells: int = 0
    total_redeems: int = 0
    total_realized_pnl: float = 0.0
    total_estimated_pnl: float = 0.0
    win_rate: float = 0.0
    avg_pnl_per_trade: float = 0.0
    best_trade_pnl: float = 0.0
    worst_trade_pnl: float = 0.0
    operations: List[OperationRecord] = Field(default_factory=list)


# ==================== 策略建议 ====================

class StrategyRecommendation(BaseModel):
    """策略建议"""
    fund_code: str
    fund_name: str
    direction: ArbitrageDirection
    action: str                           # 建议操作: "立即申购"/"等待"/"卖出"
    confidence: str                       # high/medium/low
    premium_pct: float = 0.0
    net_profit_pct: float = 0.0
    apply_limit: str = ""
    apply_status: str = ""
    reasons: List[str] = Field(default_factory=list)
    risk_warnings: List[str] = Field(default_factory=list)
    allocation_plan: Optional[AllocationPlan] = None


class StrategyOverview(BaseModel):
    """策略总览"""
    scan_time: str = ""
    market_status: str = ""               # 开盘/收盘/午休
    opportunities: List[ArbitrageOpportunity] = Field(default_factory=list)
    recommendations: List[StrategyRecommendation] = Field(default_factory=list)
    risk_settings: RiskSettings = Field(default_factory=RiskSettings)
    account_count: int = 0
    total_available_cash: float = 0.0
