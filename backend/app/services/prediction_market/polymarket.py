"""Polymarket 数据源适配器"""

import logging
import requests
import os
from typing import Optional, List, Dict
from .base import MarketData, PredictionMarketSource

logger = logging.getLogger(__name__)


class PolymarketSource(PredictionMarketSource):
    """Polymarket 平台适配器"""

    GAMMA_API = "https://gamma-api.polymarket.com"
    CLOB_API = "https://clob.polymarket.com"

    def __init__(self):
        self.proxy = os.environ.get(
            'POLYMARKET_PROXY',
            os.environ.get('HTTP_PROXY', os.environ.get('HTTPS_PROXY', ''))
        )
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        }

    @property
    def name(self) -> str:
        return 'Polymarket'

    @property
    def base_url(self) -> str:
        return self.GAMMA_API

    def _get_proxies(self):
        if self.proxy:
            return {'http': self.proxy, 'https': self.proxy}
        return None

    def get_markets(self, limit: int = 100, offset: int = 0,
                    tag: str = None) -> List[MarketData]:
        """获取活跃市场列表"""
        params = {
            'limit': limit,
            'offset': offset,
            'active': 'true',
            'closed': 'false',
            'order': 'volume',
            'ascending': 'false',
        }
        if tag:
            params['tag'] = tag

        try:
            r = requests.get(
                f"{self.GAMMA_API}/markets",
                params=params,
                headers=self.headers,
                timeout=15,
                proxies=self._get_proxies()
            )
            r.raise_for_status()
            markets = r.json()

            result = []
            for m in markets:
                parsed = self._parse_market(m)
                if parsed:
                    result.append(parsed)
            return result
        except Exception as e:
            logger.error(f"Polymarket API error: {e}")
            return []

    def get_market_detail(self, market_id: str) -> Optional[MarketData]:
        """获取单个市场详情"""
        try:
            r = requests.get(
                f"{self.GAMMA_API}/markets/{market_id}",
                headers=self.headers,
                timeout=15,
                proxies=self._get_proxies()
            )
            r.raise_for_status()
            return self._parse_market(r.json())
        except Exception as e:
            logger.error(f"Polymarket market detail error: {e}")
            return None

    def get_price_history(self, market_id: str,
                          interval: str = '1d') -> List[Dict]:
        """获取市场价格历史"""
        params = {
            'market': market_id,
            'interval': interval,
            'fidelity': 100,
        }

        try:
            r = requests.get(
                f"{self.GAMMA_API}/prices-history",
                params=params,
                headers=self.headers,
                timeout=15,
                proxies=self._get_proxies()
            )
            r.raise_for_status()
            data = r.json()

            history = []
            if isinstance(data, dict) and 'history' in data:
                for point in data['history']:
                    history.append({
                        'timestamp': point.get('t', ''),
                        'price': float(point.get('p', 0)),
                    })
            elif isinstance(data, list):
                for point in data:
                    if isinstance(point, dict):
                        history.append({
                            'timestamp': point.get('t', point.get('timestamp', '')),
                            'price': float(point.get('p', point.get('price', 0))),
                        })
            return history
        except Exception as e:
            logger.error(f"Polymarket price history error: {e}")
            return []

    def get_order_book(self, token_id: str) -> Optional[Dict]:
        """获取订单簿"""
        try:
            r = requests.get(
                f"{self.CLOB_API}/book",
                params={'token_id': token_id},
                headers=self.headers,
                timeout=10,
                proxies=self._get_proxies()
            )
            r.raise_for_status()
            data = r.json()

            result = {
                'bids': data.get('bids', []),
                'asks': data.get('asks', []),
                'spread': 0,
                'midpoint': 0,
            }

            bids = data.get('bids', [])
            asks = data.get('asks', [])
            if bids and asks:
                best_bid = float(bids[0].get('price', 0))
                best_ask = float(asks[0].get('price', 0))
                result['spread'] = round(best_ask - best_bid, 4)
                result['midpoint'] = round((best_bid + best_ask) / 2, 4)

            return result
        except Exception as e:
            logger.error(f"Polymarket order book error: {e}")
            return None

    def calculate_fee(self, price: float, amount: float) -> float:
        """
        Polymarket 手续费计算
        基本无交易手续费，只需承担少量链上 Gas 费或滑点
        """
        # Polymarket 基本无手续费，返回0
        return 0

    def _parse_market(self, m: dict) -> Optional[MarketData]:
        """解析市场数据"""
        try:
            outcomes = m.get('outcomes', [])
            outcome_prices = m.get('outcomePrices', [])
            tokens = m.get('tokens', [])

            # Parse prices
            prices = []
            for p in outcome_prices:
                try:
                    prices.append(float(p))
                except (ValueError, TypeError):
                    prices.append(0)

            # Parse token IDs
            token_map = {}
            for t in tokens:
                outcome = t.get('outcome', '')
                token_id = t.get('token_id', '')
                if outcome and token_id:
                    token_map[outcome] = token_id

            yes_price = prices[0] if len(prices) > 0 else 0
            no_price = prices[1] if len(prices) > 1 else 0
            volume = float(m.get('volume', 0) or 0)
            liquidity = float(m.get('liquidity', 0) or 0)

            return MarketData(
                id=m.get('id', ''),
                question=m.get('question', ''),
                yes_price=yes_price,
                no_price=no_price,
                volume=round(volume, 2),
                liquidity=round(liquidity, 2),
                end_date=m.get('endDate', ''),
                source='polymarket',
                tag=m.get('tag', ''),
                slug=m.get('slug', ''),
                description=(m.get('description', '') or '')[:200],
                image=m.get('image', ''),
                active=m.get('active', False),
                outcomes=outcomes,
                tokens=token_map,
                raw_data=m,
            )
        except Exception:
            return None
