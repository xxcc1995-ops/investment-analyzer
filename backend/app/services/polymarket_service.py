"""Polymarket 智能分析服务 - 套利检测、价值发现、趋势追踪"""

import requests
import time
import os
from typing import Optional, List, Dict
from datetime import datetime, timedelta

# ============================================================
# Polymarket API Config
# ============================================================

GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"

# 代理配置 - 设置环境变量 HTTP_PROXY / HTTPS_PROXY 或直接修改这里
PROXY = os.environ.get('POLYMARKET_PROXY', os.environ.get('HTTP_PROXY', os.environ.get('HTTPS_PROXY', '')))

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json',
}


def _get_proxies():
    if PROXY:
        return {'http': PROXY, 'https': PROXY}
    return None

# ============================================================
# Cache
# ============================================================

_cache = {}
_CACHE_TTL = 300  # 5 minutes


def _get_cached(key: str):
    if key in _cache:
        data, ts = _cache[key]
        if time.time() - ts < _CACHE_TTL:
            return data
    return None


def _set_cached(key: str, data):
    _cache[key] = (data, time.time())


# ============================================================
# Gamma API - 市场数据（免费，无需认证）
# ============================================================

def get_active_markets(limit: int = 100, offset: int = 0,
                       order: str = 'volume', ascending: bool = False,
                       tag: str = None) -> List[Dict]:
    """获取活跃市场列表"""
    cache_key = f"markets_{limit}_{offset}_{order}_{ascending}_{tag}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    params = {
        'limit': limit,
        'offset': offset,
        'active': 'true',
        'closed': 'false',
        'order': order,
        'ascending': str(ascending).lower(),
    }
    if tag:
        params['tag'] = tag

    try:
        r = requests.get(f"{GAMMA_API}/markets", params=params,
                         headers=HEADERS, timeout=15, proxies=_get_proxies())
        r.raise_for_status()
        markets = r.json()

        result = []
        for m in markets:
            parsed = _parse_market(m)
            if parsed:
                result.append(parsed)

        _set_cached(cache_key, result)
        return result
    except Exception as e:
        print(f"Polymarket API error: {e}")
        return []


def get_market_detail(market_id: str) -> Optional[Dict]:
    """获取单个市场详情"""
    cache_key = f"market_{market_id}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        r = requests.get(f"{GAMMA_API}/markets/{market_id}",
                         headers=HEADERS, timeout=15, proxies=_get_proxies())
        r.raise_for_status()
        market = r.json()
        parsed = _parse_market(market)
        if parsed:
            _set_cached(cache_key, parsed)
        return parsed
    except Exception as e:
        print(f"Polymarket market detail error: {e}")
        return None


def get_price_history(market_id: str, interval: str = '1d',
                      fidelity: int = 100) -> List[Dict]:
    """获取市场价格历史"""
    cache_key = f"prices_{market_id}_{interval}_{fidelity}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    params = {
        'market': market_id,
        'interval': interval,
        'fidelity': fidelity,
    }

    try:
        r = requests.get(f"{GAMMA_API}/prices-history", params=params,
                         headers=HEADERS, timeout=15, proxies=_get_proxies())
        r.raise_for_status()
        data = r.json()

        # Parse price history
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

        _set_cached(cache_key, history)
        return history
    except Exception as e:
        print(f"Polymarket price history error: {e}")
        return []


def get_order_book(token_id: str) -> Optional[Dict]:
    """获取订单簿（CLOB API公开端点）"""
    cache_key = f"book_{token_id}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        r = requests.get(f"{CLOB_API}/book",
                         params={'token_id': token_id},
                         headers=HEADERS, timeout=10, proxies=_get_proxies())
        r.raise_for_status()
        data = r.json()

        result = {
            'bids': data.get('bids', []),
            'asks': data.get('asks', []),
            'spread': 0,
            'midpoint': 0,
        }

        # Calculate spread and midpoint
        bids = data.get('bids', [])
        asks = data.get('asks', [])
        if bids and asks:
            best_bid = float(bids[0].get('price', 0))
            best_ask = float(asks[0].get('price', 0))
            result['spread'] = round(best_ask - best_bid, 4)
            result['midpoint'] = round((best_bid + best_ask) / 2, 4)

        _set_cached(cache_key, result)
        return result
    except Exception as e:
        print(f"Polymarket order book error: {e}")
        return None


# ============================================================
# Market Parser
# ============================================================

def _parse_market(m: dict) -> Optional[Dict]:
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

        # Calculate price deviation (for binary markets)
        price_sum = sum(prices) if prices else 0
        price_deviation = abs(price_sum - 1.0) if price_sum > 0 else 0

        # Determine if there's an arbitrage opportunity
        # If Yes + No < 1.0, buy both for guaranteed profit
        has_arbitrage = price_sum > 0 and price_sum < 0.98
        arbitrage_profit = round((1.0 - price_sum) * 100, 2) if has_arbitrage else 0

        # Get volume and liquidity
        volume = float(m.get('volume', 0) or 0)
        liquidity = float(m.get('liquidity', 0) or 0)

        return {
            'id': m.get('id', ''),
            'condition_id': m.get('condition_id', ''),
            'question': m.get('question', ''),
            'outcomes': outcomes,
            'prices': prices,
            'price_sum': round(price_sum, 4),
            'price_deviation': round(price_deviation, 4),
            'has_arbitrage': has_arbitrage,
            'arbitrage_profit': arbitrage_profit,
            'tokens': token_map,
            'volume': round(volume, 2),
            'liquidity': round(liquidity, 2),
            'end_date': m.get('endDate', ''),
            'active': m.get('active', False),
            'neg_risk': m.get('neg_risk', False),
            'tag': m.get('tag', ''),
            'slug': m.get('slug', ''),
            'description': m.get('description', '')[:200],
            'image': m.get('image', ''),
        }
    except Exception:
        return None


# ============================================================
# 分析功能
# ============================================================

def find_arbitrage_opportunities(min_profit: float = 0.5) -> List[Dict]:
    """
    检测套利机会
    当同一市场Yes+No价格<$1.00时，买入双方即可锁定利润
    例：Yes=$0.55, No=$0.40, 合计$0.95, 利润=$0.05 (5.26%)
    """
    cache_key = f"arbitrage_{min_profit}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    # Fetch high-volume markets (more likely to have arbitrage)
    markets = get_active_markets(limit=200, order='volume')

    opportunities = []
    for m in markets:
        if m.get('has_arbitrage') and m.get('arbitrage_profit', 0) >= min_profit:
            opportunities.append(m)

    # Also check for neg-risk markets where outcomes don't sum to 1.0
    neg_risk_markets = [m for m in markets if m.get('neg_risk') and len(m.get('outcomes', [])) > 2]
    for m in neg_risk_markets:
        prices = m.get('prices', [])
        if prices and len(prices) > 2:
            total = sum(prices)
            if total < 0.97 or total > 1.03:
                deviation = abs(total - 1.0) * 100
                if deviation >= min_profit:
                    m['arbitrage_profit'] = round(deviation, 2)
                    m['has_arbitrage'] = True
                    m['arb_type'] = 'neg-risk-deviation'
                    opportunities.append(m)

    opportunities.sort(key=lambda x: x.get('arbitrage_profit', 0), reverse=True)
    _set_cached(cache_key, opportunities)
    return opportunities


def find_value_markets() -> Dict:
    """
    价值发现 - 找到极端定价的市场
    - 便宜市场：Yes<10% 或 No<10%（可能是被低估的长尾事件）
    - 高价市场：Yes>90% 或 No>90%（接近确定的事件）
    - 大价差市场：买卖价差大（做市机会）
    """
    cache_key = "value_markets"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    markets = get_active_markets(limit=200, order='volume')

    cheap_yes = []  # Yes < 15%，可能是低估
    cheap_no = []   # No < 15%，可能是低估
    near_certain = []  # > 90%，接近确定
    high_volume_low_price = []  # 高成交量+低价格

    for m in markets:
        prices = m.get('prices', [])
        if len(prices) < 2:
            continue

        yes_price = prices[0] if len(prices) > 0 else 0
        no_price = prices[1] if len(prices) > 1 else 0
        volume = m.get('volume', 0)

        # Cheap Yes (< 15%)
        if 0 < yes_price < 0.15 and volume > 1000:
            m['signal'] = 'cheap_yes'
            m['potential_return'] = round((1.0 - yes_price) / yes_price * 100, 1)
            cheap_yes.append(m)

        # Cheap No (< 15%)
        if 0 < no_price < 0.15 and volume > 1000:
            m['signal'] = 'cheap_no'
            m['potential_return'] = round((1.0 - no_price) / no_price * 100, 1)
            cheap_no.append(m)

        # Near certain (> 90%)
        if yes_price > 0.90 or no_price > 0.90:
            near_certain.append(m)

        # High volume + low price (potential value)
        if volume > 50000 and (yes_price < 0.20 or no_price < 0.20):
            high_volume_low_price.append(m)

    result = {
        'cheap_yes': sorted(cheap_yes, key=lambda x: x.get('potential_return', 0), reverse=True)[:20],
        'cheap_no': sorted(cheap_no, key=lambda x: x.get('potential_return', 0), reverse=True)[:20],
        'near_certain': sorted(near_certain, key=lambda x: x.get('volume', 0), reverse=True)[:20],
        'high_volume_low_price': sorted(high_volume_low_price, key=lambda x: x.get('volume', 0), reverse=True)[:20],
    }

    _set_cached(cache_key, result)
    return result


def find_trending_markets() -> List[Dict]:
    """
    趋势追踪 - 找到价格快速变动的市场
    通过对比短期和长期价格历史来检测
    """
    cache_key = "trending"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    # Get high-volume markets
    markets = get_active_markets(limit=100, order='volume')

    trending = []
    for m in markets[:30]:  # Check top 30 by volume
        market_id = m.get('id', '')
        if not market_id:
            continue

        # Get recent price history
        history = get_price_history(market_id, interval='1d', fidelity=7)
        if not history or len(history) < 2:
            continue

        # Calculate price change
        first_price = history[0].get('price', 0)
        last_price = history[-1].get('price', 0)
        if first_price > 0:
            change_pct = round((last_price - first_price) / first_price * 100, 2)
            m['price_change_7d'] = change_pct
            m['price_direction'] = 'up' if change_pct > 0 else 'down'
            if abs(change_pct) > 5:  # > 5% change
                trending.append(m)

    trending.sort(key=lambda x: abs(x.get('price_change_7d', 0)), reverse=True)
    _set_cached(cache_key, trending)
    return trending


def calculate_kelly(price: float, estimated_prob: float,
                    bankroll: float = 1000, fraction: float = 0.25) -> Dict:
    """
    Kelly仓位计算器

    Args:
        price: 市场价格 (0.01-0.99)
        estimated_prob: 你估计的真实概率 (0.01-0.99)
        bankroll: 总资金
        fraction: Kelly分数 (0.25 = 1/4 Kelly，更保守)
    """
    if price <= 0 or price >= 1 or estimated_prob <= 0 or estimated_prob >= 1:
        return {'error': '价格和概率必须在0.01-0.99之间'}

    # Kelly formula: f* = (b*p - q) / b
    # b = net odds = (1/price - 1)
    # p = estimated probability
    # q = 1 - p
    b = (1.0 / price) - 1.0
    p = estimated_prob
    q = 1.0 - p

    kelly_full = (b * p - q) / b if b > 0 else 0
    kelly_fractional = kelly_full * fraction

    # Expected value
    ev = p * (1.0 - price) - q * price  # EV per dollar
    ev_pct = ev * 100

    # Position sizing
    position_full = max(0, kelly_full * bankroll)
    position_fractional = max(0, kelly_fractional * bankroll)

    # Risk assessment
    if kelly_full <= 0:
        risk_level = 'negative_edge'
        risk_msg = '没有优势，不应该下注'
    elif kelly_full < 0.1:
        risk_level = 'low'
        risk_msg = '微弱优势，小仓位试探'
    elif kelly_full < 0.3:
        risk_level = 'medium'
        risk_msg = '中等优势，适度仓位'
    elif kelly_full < 0.5:
        risk_level = 'high'
        risk_msg = '较强优势，较大仓位'
    else:
        risk_level = 'very_high'
        risk_msg = '极强优势，但要注意过度自信的可能'

    return {
        'price': price,
        'estimated_prob': estimated_prob,
        'implied_prob': round(price, 4),
        'edge': round(estimated_prob - price, 4),
        'edge_pct': round((estimated_prob - price) * 100, 2),
        'ev_per_dollar': round(ev, 4),
        'ev_pct': round(ev_pct, 2),
        'kelly_full': round(kelly_full, 4),
        'kelly_full_pct': round(kelly_full * 100, 2),
        'kelly_fractional': round(kelly_fractional, 4),
        'kelly_fractional_pct': round(kelly_fractional * 100, 2),
        'bankroll': bankroll,
        'fraction': fraction,
        'position_full': round(position_full, 2),
        'position_fractional': round(position_fractional, 2),
        'risk_level': risk_level,
        'risk_msg': risk_msg,
        'potential_profit': round(position_fractional * (1.0 / price - 1), 2) if price > 0 else 0,
    }


def analyze_market(market_id: str) -> Dict:
    """综合分析单个市场"""
    market = get_market_detail(market_id)
    if not market:
        return {'error': '市场未找到'}

    # Get price history
    history = get_price_history(market_id, interval='1d', fidelity=30)

    # Get order book for first token
    tokens = market.get('tokens', {})
    first_token = list(tokens.values())[0] if tokens else None
    order_book = get_order_book(first_token) if first_token else None

    # Price trend analysis
    trend = 'neutral'
    price_change_7d = 0
    price_change_30d = 0
    if history and len(history) >= 2:
        first_7d = history[0].get('price', 0)
        last = history[-1].get('price', 0)
        if first_7d > 0:
            price_change_7d = round((last - first_7d) / first_7d * 100, 2)
        if len(history) >= 7:
            first_30d = history[-7].get('price', 0) if len(history) >= 7 else history[0].get('price', 0)
            if first_30d > 0:
                price_change_30d = round((last - first_30d) / first_30d * 100, 2)

        if price_change_7d > 5:
            trend = 'bullish'
        elif price_change_7d < -5:
            trend = 'bearish'

    # Liquidity assessment
    liquidity = market.get('liquidity', 0)
    volume = market.get('volume', 0)
    liquidity_score = 'low'
    if liquidity > 100000:
        liquidity_score = 'high'
    elif liquidity > 10000:
        liquidity_score = 'medium'

    return {
        'market': market,
        'history': history[-30:],  # Last 30 data points
        'order_book': order_book,
        'analysis': {
            'trend': trend,
            'price_change_7d': price_change_7d,
            'price_change_30d': price_change_30d,
            'liquidity_score': liquidity_score,
            'volume_liquidity_ratio': round(volume / liquidity, 2) if liquidity > 0 else 0,
        },
    }
