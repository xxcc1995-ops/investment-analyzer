"""股票相关数据模型"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class StockBasicInfo(BaseModel):
    """股票基本面指标"""
    code: str
    name: str
    pe: Optional[float] = None  # 市盈率
    pb: Optional[float] = None  # 市净率
    roe: Optional[float] = None  # 净资产收益率 (%)
    market_cap: Optional[float] = None  # 总市值 (亿)
    updated_at: datetime = datetime.now()


class StockFinancials(BaseModel):
    """财务数据"""
    code: str
    name: str
    revenue: Optional[float] = None  # 营业收入 (亿)
    net_profit: Optional[float] = None  # 净利润 (亿)
    revenue_growth: Optional[float] = None  # 营收同比增长率 (%)
    profit_growth: Optional[float] = None  # 净利润同比增长率 (%)
    fcf: Optional[float] = Field(None, description="自由现金流 (亿)")
    report_date: Optional[str] = None  # 报告期


class DCFValuation(BaseModel):
    """DCF估值结果"""
    code: str
    name: str
    current_price: float
    intrinsic_value: float  # 内在价值
    buy_price: float  # 买点价格 (含安全边际)
    safety_margin: float  # 安全边际 (30%)
    upside: float  # 上行空间 (%)
    fcf_projections: list[float]  # 10年FCF预测
    terminal_value: float  # 终值
    discount_rate: float  # 折现率
    growth_rate: float  # 前10年增长率
    terminal_growth_rate: float  # 永续增长率


class IncomeStatement(BaseModel):
    """利润表"""
    report_date: str
    report_name: str
    report_type: str  # annual / q3 / semi / q1
    total_revenue: Optional[float] = None  # 营业总收入
    operating_cost: Optional[float] = None  # 营业成本
    sell_expense: Optional[float] = None  # 销售费用
    manage_expense: Optional[float] = None  # 管理费用
    research_expense: Optional[float] = None  # 研发费用
    finance_expense: Optional[float] = None  # 财务费用
    operate_profit: Optional[float] = None  # 营业利润
    total_profit: Optional[float] = None  # 利润总额
    income_tax: Optional[float] = None  # 所得税费用
    net_profit: Optional[float] = None  # 净利润
    parent_net_profit: Optional[float] = None  # 归母净利润
    # 衍生比率
    sell_expense_ratio: Optional[float] = None  # 销售费用率 (%)
    manage_expense_ratio: Optional[float] = None  # 管理费用率 (%)
    research_expense_ratio: Optional[float] = None  # 研发费用率 (%)
    finance_expense_ratio: Optional[float] = None  # 财务费用率 (%)
    gross_margin: Optional[float] = None  # 毛利率 (%)
    net_margin: Optional[float] = None  # 净利率 (%)
    operating_margin: Optional[float] = None  # 营业利润率 (%)


class BalanceSheet(BaseModel):
    """资产负债表"""
    report_date: str
    report_name: str
    report_type: str
    monetary_funds: Optional[float] = None  # 货币资金
    accounts_receivable: Optional[float] = None  # 应收账款
    inventory: Optional[float] = None  # 存货
    total_current_assets: Optional[float] = None  # 流动资产合计
    total_non_current_assets: Optional[float] = None  # 非流动资产合计
    total_assets: Optional[float] = None  # 资产总计
    short_term_borrowing: Optional[float] = None  # 短期借款
    long_term_borrowing: Optional[float] = None  # 长期借款
    total_current_liabilities: Optional[float] = None  # 流动负债合计
    total_non_current_liabilities: Optional[float] = None  # 非流动负债合计
    total_liabilities: Optional[float] = None  # 负债合计
    total_equity: Optional[float] = None  # 所有者权益合计
    parent_equity: Optional[float] = None  # 归母股东权益
    # 衍生比率
    debt_ratio: Optional[float] = None  # 资产负债率 (%)
    current_ratio: Optional[float] = None  # 流动比率
    quick_ratio: Optional[float] = None  # 速动比率


class CashFlowStatement(BaseModel):
    """现金流量表"""
    report_date: str
    report_name: str
    report_type: str
    netcash_operate: Optional[float] = None  # 经营活动现金流净额
    netcash_invest: Optional[float] = None  # 投资活动现金流净额
    netcash_finance: Optional[float] = None  # 筹资活动现金流净额
    cash_begin: Optional[float] = None  # 期初现金余额
    cash_end: Optional[float] = None  # 期末现金余额
    # 衍生指标
    capex: Optional[float] = None  # 资本开支（投资现金流负值近似）
    free_cashflow: Optional[float] = None  # 自由现金流
    depreciation_amortization: Optional[float] = None  # 折旧摊销合计
    operating_to_profit_ratio: Optional[float] = None  # 经营现金流/净利润 (%)


class FinancialStatementsResponse(BaseModel):
    """三大报表完整响应"""
    code: str
    income: list[IncomeStatement] = Field(default_factory=list)
    balance: list[BalanceSheet] = Field(default_factory=list)
    cashflow: list[CashFlowStatement] = Field(default_factory=list)
    fetch_time: str = ""
