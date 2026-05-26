"""
币圈信息源API
"""
from fastapi import APIRouter
from app.services.crypto_service import crypto_info_service

router = APIRouter()


@router.get("/sources")
def get_all_sources():
    """获取所有信息源，按类别分组"""
    return crypto_info_service.get_all_sources()


@router.get("/sources/{category}")
def get_sources_by_category(category: str):
    """按类别获取信息源"""
    all_sources = crypto_info_service.get_all_sources()
    if category not in all_sources:
        return {"error": f"未知类别: {category}，可用: {', '.join(all_sources.keys())}"}
    return {"category": category, "sources": all_sources[category]}


@router.get("/tips")
def get_info_tips():
    """获取信息筛选方法论"""
    return {"tips": crypto_info_service.get_info_tips()}
