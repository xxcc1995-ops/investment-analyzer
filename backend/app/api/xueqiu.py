"""雪球大V API"""

from fastapi import APIRouter
from app.services.xueqiu_service import get_all_gurus, get_guru_data

router = APIRouter()


@router.get("/gurus")
def gurus():
    """获取所有大V数据"""
    return get_all_gurus()


@router.get("/guru/{uid}")
def guru(uid: str):
    """获取单个大V数据"""
    data = get_guru_data(uid)
    if not data:
        return {'error': '未找到该用户'}
    return data
