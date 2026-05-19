from pydantic import BaseModel
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

    @classmethod
    def from_neodata(cls, data: dict, code: str):
        # 解析NeoData返回的数据
        # 实际实现需要根据NeoData的响应格式调整
        return cls(code=code, name="", pe=None, pb=None, roe=None)

class StockFinancials(BaseModel):
    """财务数据"""
    code: str
    name: str
    revenue: Optional[float] = None  # 营业收入 (亿)
    net_profit: Optional[float] = None  # 净利润 (亿)
    revenue_growth: Optional[float] = None  # 营收同比增长率 (%)
    profit_growth: Optional[float] = None  # 净利润同比增长率 (%)
    fcf: Optional[float] = None  # 自由现金流 (亿)
    report_date: Optional[str] = None  # 报告期

    @classmethod
    def from_neodata(cls, data: dict, code: str):
        return cls(code=code, name="")

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
