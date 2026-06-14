"""
每日信息服务 API 路由
提供每日投资简报、市场动态、宏观经济数据
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
from app.services.daily_info_service import daily_info_service

router = APIRouter()


@router.get("/briefing", response_model=Dict[str, Any])
async def get_daily_briefing():
    """获取每日投资简报（综合所有信息）"""
    try:
        return daily_info_service.get_daily_briefing()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取每日简报失败: {str(e)}")


@router.get("/market/china", response_model=Dict[str, Any])
async def get_china_market():
    """获取中国市场摘要（A股、港股）"""
    try:
        return daily_info_service.get_china_market_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取中国市场摘要失败: {str(e)}")


@router.get("/market/us", response_model=Dict[str, Any])
async def get_us_market():
    """获取美国市场摘要"""
    try:
        return daily_info_service.get_us_market_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取美国市场摘要失败: {str(e)}")


@router.get("/market/global", response_model=Dict[str, Any])
async def get_global_market():
    """获取全球市场概览"""
    try:
        return daily_info_service.get_global_market_overview()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取全球市场概览失败: {str(e)}")


@router.get("/macro/china", response_model=Dict[str, Any])
async def get_china_macro():
    """获取中国宏观经济指标"""
    try:
        return daily_info_service.get_macro_indicators()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取中国宏观经济指标失败: {str(e)}")


@router.get("/macro/us", response_model=Dict[str, Any])
async def get_us_macro():
    """获取美国宏观经济指标"""
    try:
        return daily_info_service.get_us_macro_indicators()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取美国宏观经济指标失败: {str(e)}")


@router.get("/sectors", response_model=list)
async def get_sector_performance():
    """获取行业板块表现"""
    try:
        return daily_info_service.get_sector_performance()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取行业板块表现失败: {str(e)}")


@router.get("/insights", response_model=list)
async def get_investment_insights():
    """获取投资观点摘要"""
    try:
        return daily_info_service.get_investment_insights()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取投资观点摘要失败: {str(e)}")


@router.get("/sentiment", response_model=Dict[str, Any])
async def get_market_sentiment():
    """获取市场情绪分析（v3: 含多维评分0-100分）"""
    try:
        return daily_info_service.get_market_sentiment()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取市场情绪分析失败: {str(e)}")


@router.get("/verify-sources", response_model=Dict[str, Any])
async def verify_data_sources():
    """验证数据源可用性"""
    try:
        return daily_info_service.verify_data_sources()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"验证数据源失败: {str(e)}")


@router.get("/summary", response_model=Dict[str, Any])
async def get_daily_summary():
    """获取每日摘要（简化版）"""
    try:
        briefing = daily_info_service.get_daily_briefing()

        # 提取关键信息
        china_market = briefing.get("market_overview", {}).get("china", {})
        us_market = briefing.get("market_overview", {}).get("us", {})
        sentiment = briefing.get("market_sentiment", {})
        summary = briefing.get("investment_summary", {})

        # 生成摘要文本
        a_share_summary = []
        for idx in china_market.get("a_share", []):
            change_pct = idx.get("change_pct", 0)
            direction = "↑" if change_pct > 0 else "↓" if change_pct < 0 else "→"
            a_share_summary.append(f"{idx['name']}: {idx['close']:.2f} {direction}{abs(change_pct):.2f}%")

        us_summary = []
        for idx in us_market.get("indices", []):
            change_pct = idx.get("change_pct", 0)
            direction = "↑" if change_pct > 0 else "↓" if change_pct < 0 else "→"
            us_summary.append(f"{idx['name']}: {idx['close']:.2f} {direction}{abs(change_pct):.2f}%")

        return {
            "title": briefing.get("title", ""),
            "market_summary": {
                "a_share": " | ".join(a_share_summary) if a_share_summary else "暂无数据",
                "us": " | ".join(us_summary) if us_summary else "暂无数据",
            },
            "sentiment": sentiment.get("sentiment", "未知"),
            "sentiment_description": sentiment.get("description", ""),
            "investment_advice": summary.get("investment_advice", ""),
            "macro_highlights": summary.get("macro_analysis", []),
            "sector_highlights": summary.get("sector_analysis", []),
            "update_time": briefing.get("update_time", ""),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取每日摘要失败: {str(e)}")


# ==================== 五大大师模块 API ====================

@router.get("/value-investing", response_model=Dict[str, Any])
async def get_value_investing_insights():
    """获取价值投资大师信息源"""
    try:
        return daily_info_service.get_value_investing_insights()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取价值投资信息失败: {str(e)}")


@router.get("/arbitrage", response_model=Dict[str, Any])
async def get_arbitrage_opportunities():
    """获取套利机会信息"""
    try:
        return daily_info_service.get_arbitrage_opportunities()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取套利机会失败: {str(e)}")


@router.get("/convertible-bonds", response_model=Dict[str, Any])
async def get_convertible_bond_insights():
    """获取可转债大师信息源"""
    try:
        return daily_info_service.get_convertible_bond_insights()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取可转债信息失败: {str(e)}")


@router.get("/crypto", response_model=Dict[str, Any])
async def get_crypto_insights():
    """获取币圈大师信息源"""
    try:
        return daily_info_service.get_crypto_insights()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取币圈信息失败: {str(e)}")


@router.get("/airdrops", response_model=Dict[str, Any])
async def get_airdrop_opportunities():
    """获取空投机会信息"""
    try:
        return daily_info_service.get_airdrop_opportunities()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取空投信息失败: {str(e)}")


@router.get("/overseas-news", response_model=Dict[str, Any])
async def get_overseas_news():
    """获取海外高质量新闻（美股/加密市场）"""
    try:
        return daily_info_service.get_overseas_news()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取海外新闻失败: {str(e)}")


@router.get("/critical-events", response_model=list)
async def get_critical_events():
    """获取重大事件列表（自动检测：行情异动/板块分化/资金冲击/宏观预警/海外事件）"""
    try:
        briefing = daily_info_service.get_daily_briefing()
        return briefing.get("critical_events", [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取重大事件失败: {str(e)}")


@router.get("/cross-validated-news", response_model=list)
async def get_cross_validated_news():
    """获取多源交叉验证新闻（多个信源同时报道 → 置信度更高）"""
    try:
        briefing = daily_info_service.get_daily_briefing()
        return briefing.get("cross_validated_news", [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取交叉验证新闻失败: {str(e)}")