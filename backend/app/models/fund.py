"""基金套利数据模型"""

from pydantic import BaseModel
from typing import Optional, List


class FundArbitrage(BaseModel):
    """单只基金的套利机会"""
    fund_id: str           # 基金代码
    fund_nm: str           # 基金名称
    price: float           # 场内价格
    fund_nav: float        # 场外净值
    nav_discount_rt: float # 折溢价率(%), 正=溢价, 负=折价
    increase_rt: float     # 场内涨跌幅(%)
    volume: float          # 成交量(万份)
    turnover: float        # 成交额(万元)
    amount: int            # 份额(万份)
    direction: str         # 套利方向: "溢价" / "折价"
    apply_fee: str         # 申购费率
    redeem_fee: str        # 赎回费率
    apply_status: str      # 申购状态
    redeem_status: str     # 赎回状态
    apply_limit: str       # 申购限额
    nav_dt: str            # 净值日期
    price_dt: str          # 价格日期
    issuer_nm: str         # 基金公司
    estimated_profit: float  # 预估收益率(%), 扣除费用后
    est_nav: Optional[float] = None          # 实时EST估算净值
    est_discount_rt: Optional[float] = None   # EST溢价率(%)
    underlying_name: Optional[str] = None     # 底层资产名称
    underlying_change: Optional[float] = None # 底层资产涨跌幅(%)


class ArbitrageResponse(BaseModel):
    """套利机会响应"""
    funds: List[FundArbitrage]
    total: int
    total_before_filter: int
    min_threshold: float
    min_turnover: float
    fetch_time: str
    data_source: str
    logged_in: bool
