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

from app.core.cache import get_cache as _get_cached, set_cache as _set_cached
_CACHE_TTL = 300


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


# ============================================================
# 跨平台套利功能（Polymarket vs Opinion）
# ============================================================

# 延迟导入 Opinion 适配器
_opinion_source = None
_polymarket_source = None


def _get_opinion_source():
    """延迟获取 Opinion 数据源"""
    global _opinion_source
    if _opinion_source is None:
        try:
            from app.services.prediction_market.opinion import OpinionSource
            _opinion_source = OpinionSource()
        except Exception as e:
            print(f"Opinion source init error: {e}")
    return _opinion_source


def _get_polymarket_source():
    """延迟获取 Polymarket 数据源"""
    global _polymarket_source
    if _polymarket_source is None:
        try:
            from app.services.prediction_market.polymarket import PolymarketSource
            _polymarket_source = PolymarketSource()
        except Exception as e:
            print(f"Polymarket source init error: {e}")
    return _polymarket_source


def calculate_opinion_fee(price: float, amount: float) -> float:
    """
    Opinion 手续费计算

    规则：
    - 吃单（Taker）收费 0%～2%
    - 价格越接近 50%，手续费越高；接近 0 或 1 越低
    - 最低 0.5U

    简化模型：使用二次函数模拟
    fee_rate = 2% * (1 - |price - 0.5| * 2)^2
    """
    if amount <= 0:
        return 0

    # 计算费率：价格越接近0.5，费率越高
    price_from_center = abs(price - 0.5)  # 0 到 0.5
    fee_rate = 0.02 * (1 - 2 * price_from_center) ** 2

    # 确保费率在 0% 到 2% 之间
    fee_rate = max(0, min(0.02, fee_rate))

    # 计算手续费，最低 0.5U
    fee = amount * fee_rate
    fee = max(0.5, fee)

    return round(fee, 2)


def calculate_polymarket_fee(price: float, amount: float) -> float:
    """
    Polymarket 手续费计算
    基本无交易手续费，只需承担少量链上 Gas 费或滑点
    """
    return 0


def _normalize_question(question: str) -> str:
    """标准化问题文本，用于模糊匹配"""
    import re
    # 转小写
    q = question.lower().strip()
    # 移除多余空格
    q = re.sub(r'\s+', ' ', q)
    # 移除标点符号
    q = re.sub(r'[?？!！.。,，]', '', q)
    return q


def _find_matching_markets(pm_markets, op_markets):
    """
    匹配两个平台的相同事件

    使用模糊匹配：
    1. 精确匹配（标准化后完全相同）
    2. 包含匹配（一个包含另一个）
    3. 关键词匹配（提取关键实体进行匹配）
    """
    matches = []

    for pm in pm_markets:
        pm_q = _normalize_question(pm.question)
        if not pm_q:
            continue

        for op in op_markets:
            op_q = _normalize_question(op.question)
            if not op_q:
                continue

            # 精确匹配
            if pm_q == op_q:
                matches.append((pm, op, 'exact'))
                continue

            # 包含匹配
            if pm_q in op_q or op_q in pm_q:
                matches.append((pm, op, 'contains'))
                continue

            # 关键词匹配（至少70%的关键词重叠）
            pm_words = set(pm_q.split())
            op_words = set(op_q.split())
            if pm_words and op_words:
                overlap = len(pm_words & op_words)
                min_len = min(len(pm_words), len(op_words))
                if min_len > 0 and overlap / min_len >= 0.7:
                    matches.append((pm, op, 'keyword'))

    return matches


def find_cross_platform_arbitrage(
    min_profit: float = 0.5,
    budget: float = 100,
    pm_limit: int = 100,
    op_limit: int = 100
) -> List[Dict]:
    """
    跨平台套利检测（Polymarket vs Opinion）

    检测逻辑：
    1. 从两个平台获取市场列表
    2. 匹配相同事件
    3. 计算套利机会：
       - 策略1：Opinion买YES + Polymarket买NO
       - 策略2：Opinion买NO + Polymarket买YES
    4. 考虑手续费后的真实利润

    Args:
        min_profit: 最低利润率（%）
        budget: 总预算（U）
        pm_limit: Polymarket市场数量
        op_limit: Opinion市场数量

    Returns:
        套利机会列表
    """
    cache_key = f"cross_arb_{min_profit}_{budget}_{pm_limit}_{op_limit}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    # 获取两个平台的市场数据
    pm_source = _get_polymarket_source()
    op_source = _get_opinion_source()

    if not pm_source or not op_source:
        return []

    try:
        pm_markets = pm_source.get_markets(limit=pm_limit)
        op_markets = op_source.get_markets(limit=op_limit)
    except Exception as e:
        print(f"获取市场数据失败: {e}")
        return []

    if not pm_markets or not op_markets:
        return []

    # 匹配相同事件
    matches = _find_matching_markets(pm_markets, op_markets)

    opportunities = []
    for pm, op, match_type in matches:
        # 策略1：Opinion买YES + Polymarket买NO
        s1_yes = op.yes_price
        s1_no = pm.no_price
        s1_sum = s1_yes + s1_no
        s1_op_fee = calculate_opinion_fee(s1_yes, budget * s1_yes / s1_sum)
        s1_pm_fee = calculate_polymarket_fee(s1_no, budget * s1_no / s1_sum)
        s1_total_fee = s1_op_fee + s1_pm_fee

        # 策略2：Opinion买NO + Polymarket买YES
        s2_no = op.no_price
        s2_yes = pm.yes_price
        s2_sum = s2_no + s2_yes
        s2_op_fee = calculate_opinion_fee(s2_no, budget * s2_no / s2_sum)
        s2_pm_fee = calculate_polymarket_fee(s2_yes, budget * s2_yes / s2_sum)
        s2_total_fee = s2_op_fee + s2_pm_fee

        # 选择最优策略
        if s1_sum < 1 and s2_sum < 1:
            # 两个策略都可行，选择利润更高的
            s1_profit = (1 - s1_sum) * budget - s1_total_fee
            s2_profit = (1 - s2_sum) * budget - s2_total_fee
            if s1_profit > s2_profit:
                best = 'strategy_1'
                best_sum = s1_sum
                best_fee = s1_total_fee
                best_profit = s1_profit
            else:
                best = 'strategy_2'
                best_sum = s2_sum
                best_fee = s2_total_fee
                best_profit = s2_profit
        elif s1_sum < 1:
            best = 'strategy_1'
            best_sum = s1_sum
            best_fee = s1_total_fee
            best_profit = (1 - s1_sum) * budget - s1_total_fee
        elif s2_sum < 1:
            best = 'strategy_2'
            best_sum = s2_sum
            best_fee = s2_total_fee
            best_profit = (1 - s2_sum) * budget - s2_total_fee
        else:
            continue  # 没有套利机会

        # 计算利润率
        profit_rate = best_profit / budget * 100

        if profit_rate < min_profit:
            continue

        # 计算最优配资
        if best == 'strategy_1':
            allocation = calculate_optimal_allocation(
                yes_price=s1_yes,
                no_price=s1_no,
                budget=budget,
                yes_fee_rate=calculate_opinion_fee(s1_yes, 100) / 100,
                no_fee_rate=0
            )
        else:
            allocation = calculate_optimal_allocation(
                yes_price=s2_yes,
                no_price=s2_no,
                budget=budget,
                yes_fee_rate=0,
                no_fee_rate=calculate_opinion_fee(s2_no, 100) / 100
            )

        opportunities.append({
            'question': pm.question,
            'match_type': match_type,
            # 策略1详情
            'strategy_1': {
                'description': f'Opinion买YES + Polymarket买NO',
                'opinion_yes_price': round(s1_yes, 4),
                'polymarket_no_price': round(s1_no, 4),
                'price_sum': round(s1_sum, 4),
                'fee': round(s1_total_fee, 2),
            },
            # 策略2详情
            'strategy_2': {
                'description': f'Opinion买NO + Polymarket买YES',
                'opinion_no_price': round(s2_no, 4),
                'polymarket_yes_price': round(s2_yes, 4),
                'price_sum': round(s2_sum, 4),
                'fee': round(s2_total_fee, 2),
            },
            # 最优策略
            'best_strategy': best,
            'best_sum': round(best_sum, 4),
            'total_fee': round(best_fee, 2),
            'guaranteed_profit': round(best_profit, 2),
            'profit_rate': round(profit_rate, 2),
            # 配资建议
            'allocation': allocation,
            # 市场信息
            'polymarket': {
                'id': pm.id,
                'yes_price': round(pm.yes_price, 4),
                'no_price': round(pm.no_price, 4),
                'volume': pm.volume,
                'liquidity': pm.liquidity,
            },
            'opinion': {
                'id': op.id,
                'yes_price': round(op.yes_price, 4),
                'no_price': round(op.no_price, 4),
                'volume': op.volume,
                'liquidity': op.liquidity,
            },
            'end_date': pm.end_date or op.end_date,
            'volume': pm.volume + op.volume,
        })

    # 按利润率排序
    opportunities.sort(key=lambda x: x['profit_rate'], reverse=True)

    _set_cached(cache_key, opportunities)
    return opportunities


def calculate_optimal_allocation(
    yes_price: float,
    no_price: float,
    budget: float,
    yes_fee_rate: float = 0,
    no_fee_rate: float = 0
) -> Dict:
    """
    最优配资计算器

    让两边"赢的金额"完全相等，实现无风险套利。

    数学推导：
    设总预算为 B，YES投入为 x，NO投入为 B-x
    YES费率 f_y，NO费率 f_n

    事件发生时回款：
    R_yes = x / yes_price * 1 - x * (1 + f_y)
         = x * (1/yes_price - 1 - f_y)

    事件不发生时回款：
    R_no = (B-x) / no_price * 1 - (B-x) * (1 + f_n)
         = (B-x) * (1/no_price - 1 - f_n)

    令 R_yes = R_no：
    x * (1/yes_price - 1 - f_y) = (B-x) * (1/no_price - 1 - f_n)

    解得：
    x = B * (1/no_price - 1 - f_n) / [(1/yes_price - 1 - f_y) + (1/no_price - 1 - f_n)]

    Args:
        yes_price: YES价格 (0-1)
        no_price: NO价格 (0-1)
        budget: 总预算
        yes_fee_rate: YES平台费率 (0-1)
        no_fee_rate: NO平台费率 (0-1)

    Returns:
        配资方案和预期利润
    """
    if yes_price <= 0 or no_price <= 0 or budget <= 0:
        return {'error': '参数必须大于0'}

    # 计算净收益率（扣除费率后）
    yes_net_return = 1.0 / yes_price - 1 - yes_fee_rate
    no_net_return = 1.0 / no_price - 1 - no_fee_rate

    # 如果两边净收益率都为负，没有套利机会
    if yes_net_return <= 0 and no_net_return <= 0:
        return {
            'error': '无套利机会：两边净收益率均为负',
            'yes_net_return': round(yes_net_return * 100, 2),
            'no_net_return': round(no_net_return * 100, 2),
        }

    # 计算最优配资
    if yes_net_return + no_net_return == 0:
        yes_amount = budget / 2
    else:
        yes_amount = budget * no_net_return / (yes_net_return + no_net_return)

    no_amount = budget - yes_amount

    # 确保金额为正
    yes_amount = max(0, min(budget, yes_amount))
    no_amount = budget - yes_amount

    # 计算两种结果下的回款
    # 事件发生：YES兑付，NO归零
    yes_shares = yes_amount / yes_price if yes_price > 0 else 0
    yes_payout = yes_shares * 1.0  # 每份兑付1美元
    yes_fee = yes_amount * yes_fee_rate
    profit_if_yes = yes_payout - yes_amount - yes_fee - no_amount  # NO部分全损

    # 事件不发生：NO兑付，YES归零
    no_shares = no_amount / no_price if no_price > 0 else 0
    no_payout = no_shares * 1.0  # 每份兑付1美元
    no_fee = no_amount * no_fee_rate
    profit_if_no = no_payout - no_amount - no_fee - yes_amount  # YES部分全损

    # 保底利润（取两者最小值）
    guaranteed_profit = min(profit_if_yes, profit_if_no)
    profit_rate = guaranteed_profit / budget * 100

    return {
        'budget': round(budget, 2),
        'yes_price': round(yes_price, 4),
        'no_price': round(no_price, 4),
        'yes_fee_rate': round(yes_fee_rate * 100, 2),
        'no_fee_rate': round(no_fee_rate * 100, 2),
        # 配资方案
        'yes_amount': round(yes_amount, 2),
        'no_amount': round(no_amount, 2),
        'yes_ratio': round(yes_amount / budget * 100, 2),
        'no_ratio': round(no_amount / budget * 100, 2),
        # 预期收益
        'profit_if_yes': round(profit_if_yes, 2),
        'profit_if_no': round(profit_if_no, 2),
        'guaranteed_profit': round(guaranteed_profit, 2),
        'profit_rate': round(profit_rate, 2),
        # 手续费
        'yes_fee': round(yes_fee, 2),
        'no_fee': round(no_fee, 2),
        'total_fee': round(yes_fee + no_fee, 2),
        # 净收益率
        'yes_net_return': round(yes_net_return * 100, 2),
        'no_net_return': round(no_net_return * 100, 2),
    }
