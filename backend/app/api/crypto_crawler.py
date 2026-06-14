"""
币圈情报搜集器API
自动从互联网各角落搜集币圈实用信息
"""
from fastapi import APIRouter, Query
from app.services.crypto_crawler_service import CryptoCrawlerService

router = APIRouter()
svc = CryptoCrawlerService()


@router.get("/latest")
async def latest(
    category: str = Query(None, description="分类过滤: news/btc/defi/research/onchain"),
    impact: str = Query(None, description="影响力过滤: high/medium/low"),
    limit: int = Query(50, ge=1, le=200),
):
    """获取最新搜集的情报"""
    return svc.get_latest(category=category, impact=impact, limit=limit)


@router.get("/high-impact")
async def high_impact(limit: int = 20):
    """获取高影响力情报"""
    return svc.get_high_impact(limit=limit)


@router.get("/trending")
async def trending():
    """分析当前热门话题"""
    return svc.get_trending_topics()


@router.get("/sources")
async def sources():
    """获取数据源状态"""
    return svc.get_sources_status()


@router.post("/crawl")
async def crawl():
    """手动触发搜集"""
    return svc.force_crawl()


@router.get("/category/{category}")
async def by_category(category: str, limit: int = 30):
    """按分类获取: news/btc/defi/research/onchain"""
    return svc.get_by_category(category, limit=limit)
