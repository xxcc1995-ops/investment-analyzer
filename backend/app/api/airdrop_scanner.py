"""
空投机会扫描器 - API路由
未发币协议扫描 · 交易所活动 · 链上打新 · 测试网 · Twitter大V · 空投资讯 · 机会评分
"""
from fastapi import APIRouter
from app.services.airdrop_scanner_service import AirdropScannerService

router = APIRouter()
svc = AirdropScannerService()


@router.get("/untokenized-protocols")
async def untokenized_protocols():
    """DefiLlama 未发币高TVL协议扫描，带空投概率评分"""
    return svc.get_untokenized_protocols()


@router.get("/exchange-activities")
async def exchange_activities():
    """交易所活动汇总（币安/OKX/Bybit/Gate）"""
    return svc.get_exchange_activities()


@router.get("/launchpad-projects")
async def launchpad_projects():
    """链上打新/IDO项目追踪"""
    return svc.get_launchpad_projects()


@router.get("/testnet-projects")
async def testnet_projects():
    """测试网/激励测试网项目追踪"""
    return svc.get_testnet_projects()


@router.get("/defillama-airdrops")
async def defillama_airdrops():
    """DeFiLlama 已公布空投 + 高概率空投协议"""
    return svc.get_defillama_airdrops()


@router.get("/twitter-kol")
async def twitter_kol_feed():
    """Twitter空投大V推文监控（via RSSHub）"""
    return svc.get_twitter_kol_feed()


@router.get("/news")
async def airdrop_news():
    """空投资讯聚合（12源RSS）"""
    return svc.get_airdrop_news()


@router.get("/opportunity-scores")
async def opportunity_scores():
    """综合机会评分 - 多维度加权排序"""
    return svc.get_opportunity_scores()
