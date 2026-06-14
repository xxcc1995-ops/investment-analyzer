"""国债收益率 & 股债比 API 路由"""

from fastapi import APIRouter
from app.services.bonds_service import get_bond_yields

router = APIRouter()


@router.get("/yields")
def get_bond_yields_api():
    """获取中美十年期国债收益率及股债比"""
    return get_bond_yields()
