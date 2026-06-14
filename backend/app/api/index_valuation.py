"""指数估值 API 路由 - 全球指数PE/PB/ROE/股息率及历史收益"""

from fastapi import APIRouter
from app.services.index_valuation_service import get_all_indices_data, get_index_history

router = APIRouter()


@router.get("/data")
def get_index_valuation():
    """获取全球指数估值数据（19个指数，含历史收益率和基金推荐）"""
    return get_all_indices_data()


@router.get("/history/{code}")
def get_index_valuation_history(code: str):
    """获取单个指数的PE/PB历史时间序列（用于估值走势图）"""
    return get_index_history(code)
