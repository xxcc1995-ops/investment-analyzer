"""
QuantDinger AI分析 API
提供股票AI分析、历史查询、绩效统计等接口
"""

import httpx
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from ..services.quantdinger_service import quantdinger_service

router = APIRouter(prefix="/api/quantdinger", tags=["QuantDinger AI分析"])


@router.get("/health")
async def check_health():
    """检查QuantDinger服务是否可用"""
    is_healthy = await quantdinger_service.check_health()
    return {
        "available": is_healthy,
        "base_url": quantdinger_service.base_url
    }


@router.post("/analyze/{code}")
async def analyze_stock(
    code: str,
    timeframe: str = Query("1D", description="分析周期: 1H/4H/1D/1W"),
    language: str = Query("zh-CN", description="返回语言: zh-CN/en-US"),
    model: Optional[str] = Query(None, description="指定LLM模型")
):
    """
    对股票进行AI分析

    返回:
    - decision: BUY/SELL/HOLD
    - confidence: 置信度 0-100
    - scores: 技术/基本面/情绪/综合评分
    - trading_plan: 入场价/止损/止盈
    - reasons: 买入/卖出理由
    - risks: 风险提示
    - trend_outlook: 趋势展望
    - detailed_analysis: 详细分析文本
    """
    try:
        result = await quantdinger_service.analyze_stock(
            code=code,
            timeframe=timeframe,
            language=language,
            model=model
        )

        return {
            "code": 1,
            "msg": "success",
            "data": {
                "symbol": result.symbol,
                "market": result.market,
                "decision": result.decision,
                "confidence": result.confidence,
                "summary": result.summary,

                "scores": {
                    "technical": result.technical_score,
                    "fundamental": result.fundamental_score,
                    "sentiment": result.sentiment_score,
                    "overall": result.overall_score,
                },

                "trading_plan": {
                    "entry_price": result.entry_price,
                    "stop_loss": result.stop_loss,
                    "take_profit": result.take_profit,
                    "position_size_pct": result.position_size_pct,
                },

                "reasons": result.reasons,
                "risks": result.risks,

                "trend_outlook": result.trend_outlook,
                "trend_outlook_summary": result.trend_outlook_summary,

                "consensus": result.consensus,

                "market_data": result.market_data,

                "detailed_analysis": result.detailed_analysis,

                "model": result.model,
                "analysis_time_ms": result.analysis_time_ms,
                "analyzed_at": result.analyzed_at,
            }
        }

    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="QuantDinger服务不可用，请确认服务已启动 (http://localhost:8888)"
        )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="QuantDinger分析超时，请稍后重试"
        )
    except Exception as e:
        error_msg = str(e)
        if "Insufficient credits" in error_msg:
            raise HTTPException(status_code=402, detail="QuantDinger积分不足")
        raise HTTPException(status_code=500, detail=f"分析失败: {error_msg}")


@router.get("/history/{code}")
async def get_analysis_history(
    code: str,
    days: int = Query(7, description="查询天数", ge=1, le=90),
    limit: int = Query(10, description="返回条数", ge=1, le=50)
):
    """获取股票的历史AI分析记录"""
    try:
        history = await quantdinger_service.get_analysis_history(
            code=code,
            days=days,
            limit=limit
        )
        return {
            "code": 1,
            "msg": "success",
            "data": history
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance")
async def get_performance_stats(
    code: Optional[str] = Query(None, description="股票代码（可选）"),
    days: int = Query(30, description="统计天数", ge=1, le=365)
):
    """获取AI分析的绩效统计"""
    try:
        stats = await quantdinger_service.get_performance_stats(
            code=code,
            days=days
        )
        return {
            "code": 1,
            "msg": "success",
            "data": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
