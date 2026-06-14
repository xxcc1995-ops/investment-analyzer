"""API响应模型 - 用于OpenAPI文档生成和响应验证"""

from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import datetime


# ============ 通用响应模型 ============

class ErrorResponse(BaseModel):
    """错误响应"""
    error: str = Field(..., description="错误信息")
    type: str = Field(..., description="错误类型")


class SuccessResponse(BaseModel):
    """成功响应"""
    message: str = Field(default="操作成功")


# ============ 股票相关响应模型 ============

class SearchItem(BaseModel):
    """搜索结果项"""
    code: str = Field(..., description="股票代码")
    name: str = Field(..., description="股票名称")
    market: Optional[str] = Field(None, description="市场: A/HK/US")


class SearchResponse(BaseModel):
    """搜索响应"""
    results: List[SearchItem] = Field(default_factory=list)


class StockBasicResponse(BaseModel):
    """股票基本信息响应"""
    code: str
    name: str
    market: Optional[str] = None
    price: float = Field(..., description="当前价格")
    open: float = Field(..., description="开盘价")
    high: float = Field(..., description="最高价")
    low: float = Field(..., description="最低价")
    pre_close: float = Field(..., description="昨收价")
    change_pct: float = Field(..., description="涨跌幅(%)")
    change_amount: Optional[float] = Field(None, description="涨跌额")
    volume: float = Field(..., description="成交量")
    amount: float = Field(..., description="成交额")
    pe: Optional[float] = Field(None, description="市盈率")
    pe_type: Optional[str] = Field(None, description="市盈率类型: TTM")
    pb: Optional[float] = Field(None, description="市净率")
    dividend_yield: Optional[float] = Field(None, description="股息率(%)")
    turnover_rate: Optional[float] = Field(None, description="换手率(%)")
    market_cap: float = Field(..., description="总市值(亿)")
    trade_date: Optional[str] = None
    trade_time: Optional[str] = None
    data_source: Optional[str] = Field(None, description="数据来源")
    fetch_time: Optional[str] = None


class FinancialReport(BaseModel):
    """财务报告"""
    date: str
    report_name: str
    eps: Optional[float] = None
    bps: Optional[float] = None
    roe: Optional[float] = None
    revenue: Optional[float] = None
    net_profit: Optional[float] = None
    revenue_growth: Optional[float] = None
    profit_growth: Optional[float] = None
    gross_margin: Optional[float] = None
    net_margin: Optional[float] = None
    debt_ratio: Optional[float] = None
    report_period: Optional[str] = Field(None, description="报告期分类: 年报/中报/三季报/一季报")
    is_annual: Optional[bool] = Field(None, description="是否为年报")


class FinancialsResponse(BaseModel):
    """财务数据响应"""
    reports: List[FinancialReport] = Field(default_factory=list)
    latest_report_date: Optional[str] = None
    latest_bps: Optional[float] = Field(None, description="最新BPS(每股净资产)")
    latest_bps_date: Optional[str] = Field(None, description="最新BPS报告期")
    fetch_time: Optional[str] = Field(None, description="数据获取时间")


# ============ 国债收益率响应模型 ============

class BondYield(BaseModel):
    """国债收益率"""
    date: str
    yield_: float = Field(..., alias="yield", description="收益率(%)")
    change: float = Field(..., description="变动")
    open: float
    high: float
    low: float
    pe: Optional[float] = Field(None, description="对应指数PE")
    stock_bond_ratio: Optional[float] = Field(None, description="股债比")
    earnings_yield: Optional[float] = Field(None, description="盈利收益率(%)")

    class Config:
        populate_by_name = True


class BondYieldsResponse(BaseModel):
    """国债收益率响应"""
    cn: Optional[BondYield] = Field(None, description="中国十年期国债")
    us: Optional[BondYield] = Field(None, description="美国十年期国债")
    error: Optional[str] = None


# ============ 基金套利响应模型 ============

class FundArbitrage(BaseModel):
    """基金套利数据"""
    fund_id: str = Field(..., description="基金代码")
    fund_nm: str = Field(..., description="基金名称")
    price: float = Field(..., description="场内价格")
    fund_nav: float = Field(..., description="场外净值")
    nav_discount_rt: float = Field(..., description="折溢价率(%)")
    increase_rt: float = Field(..., description="涨跌幅(%)")
    volume: float = Field(..., description="成交量")
    turnover: float = Field(..., description="成交额(万)")
    amount: float = Field(..., description="成交额")
    direction: str = Field(..., description="套利方向: 溢价/折价/none")
    apply_fee: str = Field(default="", description="申购费率")
    redeem_fee: str = Field(default="", description="赎回费率")
    apply_status: str = Field(default="", description="申购状态")
    redeem_status: str = Field(default="", description="赎回状态")
    apply_limit: str = Field(default="", description="限购金额")
    nav_dt: str = Field(default="", description="净值日期")
    price_dt: str = Field(default="", description="价格日期")
    issuer_nm: str = Field(default="", description="基金公司")
    estimated_profit: float = Field(default=0, description="预估收益(%)")
    est_nav: Optional[float] = Field(None, description="估算净值")
    est_discount_rt: Optional[float] = Field(None, description="估算折溢价率(%)")
    underlying_name: Optional[str] = Field(None, description="底层资产名称")
    underlying_change: Optional[float] = Field(None, description="底层资产涨跌幅(%)")
    price_fetch_time: Optional[str] = Field(None, description="价格获取时间")
    est_nav_date: Optional[str] = Field(None, description="估算净值日期")
    ref_est_nav: Optional[float] = Field(None, description="参考估算净值")
    ref_est_discount_rt: Optional[float] = Field(None, description="参考估算折溢价率(%)")


class FundArbitrageResponse(BaseModel):
    """基金套利响应"""
    funds: List[FundArbitrage] = Field(default_factory=list)
    fetch_time: str = Field(default="", description="数据获取时间")
    data_source: str = Field(default="", description="数据来源")
    total_before_filter: int = Field(default=0, description="筛选前总数")
    logged_in: bool = Field(default=False, description="是否已登录集思录")


# ============ 可转债响应模型 ============

class ConvertibleBond(BaseModel):
    """可转债数据"""
    bond_id: str = Field(..., description="转债代码")
    bond_nm: str = Field(..., description="转债名称")
    stock_id: str = Field(..., description="正股代码")
    stock_nm: str = Field(..., description="正股名称")
    price: float = Field(..., description="转债价格")
    convert_price: float = Field(..., description="转股价")
    convert_value: float = Field(..., description="转股价值")
    premium_rt: float = Field(..., description="转股溢价率(%)")
    double_low: float = Field(..., description="双低值")
    maturity_dt: str = Field(..., description="到期日")
    year_left: float = Field(..., description="剩余年限")
    rating_cd: str = Field(..., description="信用评级")
    curr_iss_amt: float = Field(..., description="剩余规模(亿)")
    turnover: float = Field(..., description="成交额(万)")
    stock_price: float = Field(..., description="正股价格")
    stock_change: float = Field(..., description="正股涨跌幅(%)")
    bond_change: float = Field(..., description="转债涨跌幅(%)")
    force_redeem: str = Field(default="", description="强赎状态")
    is_matured: bool = Field(default=False, description="是否已到期")


class ConvertibleBondResponse(BaseModel):
    """可转债响应"""
    bonds: List[ConvertibleBond] = Field(default_factory=list)
    fetch_time: str = Field(default="", description="数据获取时间")
    total_before_filter: int = Field(default=0, description="筛选前总数")
    total: int = Field(default=0, description="筛选后总数")
    logged_in: bool = Field(default=False, description="是否已登录集思录")


# ============ 指数估值响应模型 ============

class IndexValuation(BaseModel):
    """指数估值数据"""
    code: str = Field(..., description="指数代码")
    name: str = Field(..., description="指数名称")
    name_en: str = Field(default="", description="英文名称")
    category: str = Field(..., description="类别: 宽基/红利")
    country: str = Field(default="CN", description="国家")
    pe: Optional[float] = Field(None, description="市盈率")
    pe_percentile: Optional[float] = Field(None, description="PE百分位(%)")
    pb: Optional[float] = Field(None, description="市净率")
    pb_percentile: Optional[float] = Field(None, description="PB百分位(%)")
    roe: Optional[float] = Field(None, description="ROE(%)")
    dividend_yield: Optional[float] = Field(None, description="股息率(%)")
    dividend_percentile: Optional[float] = Field(None, description="股息率百分位(%)")
    fund_code: str = Field(default="", description="跟踪基金代码")
    fund_name: Optional[str] = Field(None, description="跟踪基金名称")
    fund_type: Optional[str] = Field(None, description="基金类型")
    fund_channel: Optional[str] = Field(None, description="购买渠道")
    fund_fee: Optional[str] = Field(None, description="基金费率")
    fund_purchase_fee: Optional[str] = Field(None, description="申购费率")
    fund_holdings_url: str = Field(default="", description="持仓详情URL")
    return_1y: Optional[float] = Field(None, description="近1年收益(%)")
    return_3y: Optional[float] = Field(None, description="近3年收益(%)")
    return_5y: Optional[float] = Field(None, description="近5年收益(%)")
    cagr: Optional[float] = Field(None, description="年化收益率(%)")
    max_drawdown: Optional[float] = Field(None, description="最大回撤(%)")
    risk_premium: Optional[float] = Field(None, description="股权风险溢价(%)")
    investment_signal: Optional[Dict] = Field(None, description="综合投资信号")


class IndexValuationResponse(BaseModel):
    """指数估值响应"""
    indices: List[IndexValuation] = Field(default_factory=list)
    update_time: str = Field(default="", description="数据更新时间")


# ============ 攒股收息响应模型 ============

class DividendStock(BaseModel):
    """收息股票"""
    code: str
    name: str
    price: Optional[float] = None
    pe: Optional[float] = None
    pb: Optional[float] = None
    roe: Optional[float] = None
    dividend_yield: Optional[float] = None
    consecutive_years: Optional[int] = None
    dividend_ratio: Optional[float] = None
    debt_ratio: Optional[float] = None
    gross_margin: Optional[float] = None
    net_margin: Optional[float] = None
    operating_cashflow: Optional[float] = None
    score: Optional[int] = None
    match_level: Optional[str] = None


class DividendScreenerResponse(BaseModel):
    """攒股收息筛选响应"""
    stocks: List[DividendStock] = Field(default_factory=list)
    update_time: str = Field(default="")
    master: str = Field(default="combined", description="筛选标准")
    total: int = Field(default=0)


# ============ 宏观数据响应模型 ============

class MacroDataPoint(BaseModel):
    """宏观数据点"""
    date: str
    value: float
    growth: Optional[float] = None


class MacroIndicator(BaseModel):
    """宏观指标"""
    latest: Optional[dict] = None
    series: List[dict] = Field(default_factory=list)


class MacroOverviewResponse(BaseModel):
    """宏观概览响应"""
    gdp: Optional[MacroIndicator] = None
    cpi: Optional[MacroIndicator] = None
    pmi: Optional[MacroIndicator] = None
    money_supply: Optional[MacroIndicator] = None
    lpr: Optional[MacroIndicator] = None
    industrial_production: Optional[MacroIndicator] = None
    trade_balance: Optional[MacroIndicator] = None
    retail_sales: Optional[MacroIndicator] = None
    housing_price: Optional[MacroIndicator] = None
    unemployment: Optional[MacroIndicator] = None
    us_fed_rate: Optional[MacroIndicator] = None
    us_gdp: Optional[MacroIndicator] = None
    us_ism_pmi: Optional[MacroIndicator] = None
    us_non_farm: Optional[MacroIndicator] = None
    yield_spread: Optional[MacroIndicator] = None
