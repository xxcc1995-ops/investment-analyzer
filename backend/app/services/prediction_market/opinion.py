"""Opinion 数据源适配器"""

import logging
import requests
import os
from typing import Optional, List, Dict
from .base import MarketData, PredictionMarketSource

logger = logging.getLogger(__name__)


class OpinionSource(PredictionMarketSource):
    """
    Opinion 平台适配器

    Opinion 是一个预测市场平台，支持多种事件的 YES/NO 交易。

    手续费规则：
    - 吃单（Taker）收费 0%～2%
    - 价格越接近 50%，手续费越高；接近 0 或 1 越低
    - 最低 0.5U

    API 配置：
    - 环境变量 OPINION_API_URL: API基础URL
    - 环境变量 OPINION_PROXY: 代理地址
    """

    # 默认API地址（可通过环境变量覆盖）
    DEFAULT_API = "https://api.opinion.trading"

    def __init__(self):
        self.api_base = os.environ.get('OPINION_API_URL', self.DEFAULT_API)
        self.proxy = os.environ.get(
            'OPINION_PROXY',
            os.environ.get('HTTP_PROXY', os.environ.get('HTTPS_PROXY', ''))
        )
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }

    @property
    def name(self) -> str:
        return 'Opinion'

    @property
    def base_url(self) -> str:
        return self.api_base

    def _get_proxies(self):
        if self.proxy:
            return {'http': self.proxy, 'https': self.proxy}
        return None

    def get_markets(self, limit: int = 100, offset: int = 0,
                    tag: str = None) -> List[MarketData]:
        """
        获取市场列表

        Opinion API 端点（待确认）：
        - GET /markets: 获取市场列表
        - GET /events: 获取事件列表
        """
        params = {
            'limit': limit,
            'offset': offset,
            'active': 'true',
        }
        if tag:
            params['tag'] = tag

        try:
            # 尝试多个可能的API端点
            endpoints = ['/markets', '/events', '/api/markets', '/api/events']
            data = None

            for endpoint in endpoints:
                try:
                    r = requests.get(
                        f"{self.api_base}{endpoint}",
                        params=params,
                        headers=self.headers,
                        timeout=15,
                        proxies=self._get_proxies()
                    )
                    if r.status_code == 200:
                        data = r.json()
                        break
                except Exception:
                    continue

            if data is None:
                logger.error(f"Opinion API: 无法连接到 {self.api_base}")
                return []

            # 解析数据（根据实际API响应格式调整）
            markets_raw = data if isinstance(data, list) else data.get('markets', data.get('events', data.get('data', [])))

            result = []
            for m in markets_raw:
                parsed = self._parse_market(m)
                if parsed:
                    result.append(parsed)
            return result

        except Exception as e:
            logger.error(f"Opinion API error: {e}")
            return []

    def get_market_detail(self, market_id: str) -> Optional[MarketData]:
        """获取单个市场详情"""
        try:
            endpoints = [f'/markets/{market_id}', f'/events/{market_id}',
                        f'/api/markets/{market_id}', f'/api/events/{market_id}']

            for endpoint in endpoints:
                try:
                    r = requests.get(
                        f"{self.api_base}{endpoint}",
                        headers=self.headers,
                        timeout=15,
                        proxies=self._get_proxies()
                    )
                    if r.status_code == 200:
                        return self._parse_market(r.json())
                except Exception:
                    continue

            return None
        except Exception as e:
            logger.error(f"Opinion market detail error: {e}")
            return None

    def get_price_history(self, market_id: str,
                          interval: str = '1d') -> List[Dict]:
        """获取价格历史"""
        try:
            endpoints = [
                f'/markets/{market_id}/history',
                f'/events/{market_id}/history',
                f'/prices-history?market={market_id}',
            ]

            for endpoint in endpoints:
                try:
                    r = requests.get(
                        f"{self.api_base}{endpoint}",
                        params={'interval': interval},
                        headers=self.headers,
                        timeout=15,
                        proxies=self._get_proxies()
                    )
                    if r.status_code == 200:
                        data = r.json()
                        return self._parse_price_history(data)
                except Exception:
                    continue

            return []
        except Exception as e:
            logger.error(f"Opinion price history error: {e}")
            return []

    def calculate_fee(self, price: float, amount: float) -> float:
        """
        Opinion 手续费计算

        规则：
        - 吃单（Taker）收费 0%～2%
        - 价格越接近 50%，手续费越高；接近 0 或 1 越低
        - 最低 0.5U

        简化模型：使用二次函数模拟
        fee_rate = 2% * (1 - |price - 0.5| * 2)^2
        即价格为0.5时费率最高(2%)，价格为0或1时费率最低(0%)
        """
        if amount <= 0:
            return 0

        # 计算费率：价格越接近0.5，费率越高
        # 使用二次函数：fee_rate = 0.02 * (1 - 2*|price-0.5|)^2
        price_from_center = abs(price - 0.5)  # 0 到 0.5
        fee_rate = 0.02 * (1 - 2 * price_from_center) ** 2

        # 确保费率在 0% 到 2% 之间
        fee_rate = max(0, min(0.02, fee_rate))

        # 计算手续费，最低 0.5U
        fee = amount * fee_rate
        fee = max(0.5, fee)

        return round(fee, 2)

    def _parse_market(self, m: dict) -> Optional[MarketData]:
        """
        解析市场数据

        根据Opinion API响应格式解析（需要根据实际API调整）
        """
        try:
            # 尝试多种可能的字段名
            question = (m.get('question', '') or m.get('title', '') or
                       m.get('name', '') or m.get('description', ''))

            if not question:
                return None

            # 解析价格
            yes_price = 0
            no_price = 0

            # 方式1：直接有 yes_price/no_price 字段
            if 'yes_price' in m:
                yes_price = float(m.get('yes_price', 0))
                no_price = float(m.get('no_price', 0))
            # 方式2：outcomePrices 数组
            elif 'outcomePrices' in m:
                prices = m.get('outcomePrices', [])
                if len(prices) >= 2:
                    yes_price = float(prices[0])
                    no_price = float(prices[1])
            # 方式3：prices 数组
            elif 'prices' in m:
                prices = m.get('prices', [])
                if len(prices) >= 2:
                    yes_price = float(prices[0])
                    no_price = float(prices[1])
            # 方式4：outcomes 中包含价格
            elif 'outcomes' in m:
                outcomes = m.get('outcomes', [])
                for o in outcomes:
                    if isinstance(o, dict):
                        outcome_name = o.get('name', o.get('outcome', '')).lower()
                        price = float(o.get('price', 0))
                        if 'yes' in outcome_name:
                            yes_price = price
                        elif 'no' in outcome_name:
                            no_price = price

            # 解析成交量和流动性
            volume = float(m.get('volume', 0) or m.get('totalVolume', 0) or 0)
            liquidity = float(m.get('liquidity', 0) or m.get('totalLiquidity', 0) or 0)

            # 解析token IDs
            tokens = {}
            if 'tokens' in m:
                for t in m.get('tokens', []):
                    if isinstance(t, dict):
                        outcome = t.get('outcome', t.get('name', ''))
                        token_id = t.get('token_id', t.get('id', ''))
                        if outcome and token_id:
                            tokens[outcome] = token_id

            return MarketData(
                id=str(m.get('id', m.get('market_id', ''))),
                question=question,
                yes_price=yes_price,
                no_price=no_price,
                volume=round(volume, 2),
                liquidity=round(liquidity, 2),
                end_date=m.get('endDate', m.get('end_date', '')),
                source='opinion',
                tag=m.get('tag', m.get('category', '')),
                slug=m.get('slug', ''),
                description=(m.get('description', '') or '')[:200],
                image=m.get('image', m.get('imageUrl', '')),
                active=m.get('active', True),
                outcomes=m.get('outcomes', ['Yes', 'No']),
                tokens=tokens,
                raw_data=m,
            )
        except Exception as e:
            logger.error(f"Opinion parse error: {e}")
            return None

    def _parse_price_history(self, data) -> List[Dict]:
        """解析价格历史数据"""
        history = []

        if isinstance(data, list):
            for point in data:
                if isinstance(point, dict):
                    history.append({
                        'timestamp': point.get('t', point.get('timestamp', '')),
                        'price': float(point.get('p', point.get('price', 0))),
                    })
        elif isinstance(data, dict):
            # 尝试不同的数据结构
            history_data = data.get('history', data.get('prices', data.get('data', [])))
            for point in history_data:
                if isinstance(point, dict):
                    history.append({
                        'timestamp': point.get('t', point.get('timestamp', '')),
                        'price': float(point.get('p', point.get('price', 0))),
                    })

        return history
