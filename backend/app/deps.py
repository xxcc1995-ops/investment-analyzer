"""FastAPI依赖注入模块

集中管理服务实例的依赖注入，提高可测试性。
"""

from functools import lru_cache
from app.services.data_service import DataService
from app.services.bonds_service import get_bond_yields
from app.services.dividend_service import get_dividend_screener


@lru_cache()
def get_data_service() -> DataService:
    """获取DataService单例"""
    return DataService()


# 可以在这里添加更多依赖：
# @lru_cache()
# def get_fund_service() -> FundService:
#     return FundService()
#
# @lru_cache()
# def get_vi_service() -> VIService:
#     return VIService()
