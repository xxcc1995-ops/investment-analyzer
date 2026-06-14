"""
QuantDinger AI分析服务
调用QuantDinger的Fast Analysis API，为股票提供AI驱动的技术分析
"""

import os
import httpx
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass

QUANTDINGER_BASE_URL = os.getenv("QUANTDINGER_API_URL", "http://localhost:8888")
QUANTDINGER_USERNAME = os.getenv("QUANTDINGER_USERNAME", "quantdinger")
QUANTDINGER_PASSWORD = os.getenv("QUANTDINGER_PASSWORD", "")
if not QUANTDINGER_PASSWORD:
    import logging
    logging.getLogger(__name__).warning(
        "QUANTDINGER_PASSWORD未设置，QuantDinger API认证将失败。"
        "请设置环境变量: export QUANTDINGER_PASSWORD=your_password"
    )


@dataclass
class AIAnalysisResult:
    """AI分析结果"""
    symbol: str
    market: str
    decision: str  # BUY / SELL / HOLD
    confidence: int  # 0-100
    summary: str

    # 评分
    technical_score: int
    fundamental_score: int
    sentiment_score: int
    overall_score: int

    # 交易计划
    entry_price: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    position_size_pct: Optional[int]

    # 理由与风险
    reasons: list[str]
    risks: list[str]

    # 趋势展望
    trend_outlook: Dict[str, Any]
    trend_outlook_summary: str

    # 多周期共识
    consensus: Dict[str, Any]

    # 市场数据
    market_data: Dict[str, Any]

    # 详细分析
    detailed_analysis: Dict[str, str]

    # 元数据
    model: str
    analysis_time_ms: int
    analyzed_at: str


class QuantDingerService:
    """QuantDinger AI分析服务"""

    def __init__(self):
        self.base_url = QUANTDINGER_BASE_URL
        self.token: Optional[str] = None
        self.token_expires: Optional[datetime] = None

    async def _get_token(self) -> str:
        """获取JWT Token，带缓存"""
        if self.token and self.token_expires and datetime.now() < self.token_expires:
            return self.token

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.base_url}/api/auth/login",
                json={
                    "username": QUANTDINGER_USERNAME,
                    "password": QUANTDINGER_PASSWORD
                }
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != 1:
                raise Exception(f"QuantDinger登录失败: {data.get('msg')}")

            self.token = data["data"]["token"]
            # Token有效期设为50分钟（假设1小时过期）
            from datetime import timedelta
            self.token_expires = datetime.now() + timedelta(minutes=50)
            return self.token

    def _convert_symbol_to_quantdinger(self, code: str) -> tuple[str, str]:
        """
        将A股代码转换为QuantDinger格式
        返回 (market, symbol)
        """
        code = code.strip()

        # A股代码格式：600xxx, 000xxx, 300xxx, 688xxx 等
        if code.startswith(('6', '9')):
            # 上交所
            return "CNStock", f"{code}.SS"
        elif code.startswith(('0', '3', '2')):
            # 深交所
            return "CNStock", f"{code}.SZ"
        elif code.startswith(('4', '8')):
            # 北交所
            return "CNStock", f"{code}.BJ"
        else:
            # 默认当作A股
            return "CNStock", code

    async def analyze_stock(
        self,
        code: str,
        timeframe: str = "1D",
        language: str = "zh-CN",
        model: Optional[str] = None
    ) -> AIAnalysisResult:
        """
        对股票进行AI分析

        Args:
            code: 股票代码，如 600519, 000858
            timeframe: 分析周期，1H/4H/1D/1W
            language: 返回语言
            model: 指定LLM模型

        Returns:
            AIAnalysisResult 分析结果
        """
        token = await self._get_token()
        market, symbol = self._convert_symbol_to_quantdinger(code)

        payload = {
            "market": market,
            "symbol": symbol,
            "language": language,
            "timeframe": timeframe,
        }
        if model:
            payload["model"] = model

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url}/api/fast-analysis/analyze",
                headers={"Authorization": f"Bearer {token}"},
                json=payload
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != 1:
                raise Exception(f"QuantDinger分析失败: {data.get('msg')}")

            result = data["data"]

            # 解析交易计划
            trading_plan = result.get("trading_plan", {})
            scores = result.get("scores", {})

            return AIAnalysisResult(
                symbol=code,
                market=market,
                decision=result.get("decision", "HOLD"),
                confidence=result.get("confidence", 0),
                summary=result.get("summary", ""),

                technical_score=scores.get("technical", 0),
                fundamental_score=scores.get("fundamental", 0),
                sentiment_score=scores.get("sentiment", 0),
                overall_score=scores.get("overall", 0),

                entry_price=trading_plan.get("entry_price"),
                stop_loss=trading_plan.get("stop_loss"),
                take_profit=trading_plan.get("take_profit"),
                position_size_pct=trading_plan.get("position_size_pct"),

                reasons=result.get("reasons", []),
                risks=result.get("risks", []),

                trend_outlook=result.get("trend_outlook", {}),
                trend_outlook_summary=result.get("trend_outlook_summary", ""),

                consensus=result.get("consensus", {}),

                market_data=result.get("market_data", {}),

                detailed_analysis=result.get("detailed_analysis", {}),

                model=result.get("model", ""),
                analysis_time_ms=result.get("analysis_time_ms", 0),
                analyzed_at=datetime.now().isoformat()
            )

    async def get_analysis_history(
        self,
        code: str,
        days: int = 7,
        limit: int = 10
    ) -> list[Dict]:
        """获取某股票的历史分析记录"""
        token = await self._get_token()
        market, symbol = self._convert_symbol_to_quantdinger(code)

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.base_url}/api/fast-analysis/history",
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "market": market,
                    "symbol": symbol,
                    "days": days,
                    "limit": limit
                }
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != 1:
                return []

            return data.get("data", [])

    async def get_performance_stats(
        self,
        code: Optional[str] = None,
        days: int = 30
    ) -> Dict:
        """获取AI分析的绩效统计"""
        token = await self._get_token()

        params = {"days": days}
        if code:
            market, symbol = self._convert_symbol_to_quantdinger(code)
            params["market"] = market
            params["symbol"] = symbol

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.base_url}/api/fast-analysis/performance",
                headers={"Authorization": f"Bearer {token}"},
                params=params
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != 1:
                return {}

            return data.get("data", {})

    async def check_health(self) -> bool:
        """检查QuantDinger服务是否可用"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self.base_url}/api/health")
                return resp.status_code == 200
        except Exception:
            return False


# 全局单例
quantdinger_service = QuantDingerService()
