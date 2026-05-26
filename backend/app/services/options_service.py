"""期权轮动服务 - 卖期权评分、BSM定价、轮动推荐"""

import math
import time
import requests as req
from math import log, sqrt, exp
from typing import Optional
from datetime import datetime, timedelta

from app.services.vi_service import _get_hk_stock_data

# ============================================================
# Cache
# ============================================================

_cache = {}
_CACHE_TTL = 600


def _get_cached(key: str):
    if key in _cache:
        entry = _cache[key]
        if time.time() - entry['ts'] < _CACHE_TTL:
            return entry['data']
        del _cache[key]
    return None


def _set_cached(key: str, data):
    _cache[key] = {'data': data, 'ts': time.time()}


# ============================================================
# BSM Model
# ============================================================

def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return exp(-0.5 * x * x) / sqrt(2.0 * math.pi)


def bsm_price(S: float, K: float, T: float, r: float, sigma: float,
              option_type: str = 'put') -> dict:
    """Black-Scholes-Merton pricing. Returns price + Greeks."""
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return {'price': 0, 'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0, 'd1': 0, 'd2': 0}

    d1 = (log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt(T))
    d2 = d1 - sigma * sqrt(T)

    if option_type == 'put':
        price = K * exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1)
        delta = _norm_cdf(d1) - 1
    else:
        price = S * _norm_cdf(d1) - K * exp(-r * T) * _norm_cdf(d2)
        delta = _norm_cdf(d1)

    gamma = _norm_pdf(d1) / (S * sigma * sqrt(T))
    theta = (-(S * _norm_pdf(d1) * sigma) / (2 * sqrt(T))
             - r * K * exp(-r * T) * (_norm_cdf(d2) if option_type == 'call' else _norm_cdf(-d2)))
    theta /= 365  # per day
    vega = S * _norm_pdf(d1) * sqrt(T) / 100  # per 1% vol change

    return {
        'price': round(price, 4),
        'delta': round(delta, 4),
        'gamma': round(gamma, 6),
        'theta': round(theta, 4),
        'vega': round(vega, 4),
        'd1': round(d1, 4),
        'd2': round(d2, 4),
    }


# ============================================================
# Historical Volatility
# ============================================================

def _fetch_hk_historical(code: str = '00700', days: int = 60) -> list[float]:
    """Fetch HK stock historical close prices via Tencent Finance API."""
    try:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days + 30)).strftime('%Y-%m-%d')
        url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get'
        params = {'param': f'hk{code},day,{start_date},{end_date},{days + 30},qfq'}
        r = req.get(url, params=params, timeout=10)
        data = r.json()
        if 'data' in data and f'hk{code}' in data['data']:
            klines = data['data'][f'hk{code}']
            rows = klines.get('qfqday') or klines.get('day') or []
            return [float(row[2]) for row in rows if len(row) >= 3]
    except Exception:
        pass
    return []


def calculate_hv(prices: list[float], window: int = 20) -> float:
    """Annualized historical volatility from close prices."""
    if len(prices) < window + 1:
        return 0.3  # default 30%

    recent = prices[-(window + 1):]
    log_returns = [log(recent[i] / recent[i - 1]) for i in range(1, len(recent))]
    if not log_returns:
        return 0.3

    mean = sum(log_returns) / len(log_returns)
    variance = sum((r - mean) ** 2 for r in log_returns) / (len(log_returns) - 1)
    daily_vol = sqrt(variance)
    annual_vol = daily_vol * sqrt(252)
    return round(annual_vol, 4)


# ============================================================
# IV Solver
# ============================================================

def solve_iv(market_price: float, S: float, K: float, T: float, r: float,
             option_type: str = 'put') -> float:
    """Newton-Raphson implied volatility solver."""
    if market_price <= 0 or T <= 0:
        return 0.0

    sigma = 0.3
    for _ in range(100):
        result = bsm_price(S, K, T, r, sigma, option_type)
        diff = result['price'] - market_price
        if abs(diff) < 1e-6:
            return round(sigma, 4)
        vega = result['vega'] * 100  # undo /100
        if vega < 1e-10:
            break
        sigma -= diff / vega
        if sigma <= 0.001:
            sigma = 0.001

    return round(sigma, 4)


# ============================================================
# Option Scoring
# ============================================================

def score_option(spot: float, strike: float, premium: float, dte: int,
                 option_type: str, iv: float, hv: float) -> tuple[int, str]:
    """Score an option for selling. Returns (score, detail)."""
    score = 0
    details = []

    # 1. IV vs HV premium (20 pts)
    if hv > 0:
        iv_ratio = iv / hv
        if iv_ratio >= 1.5:
            pts = 20
        elif iv_ratio >= 1.3:
            pts = 16
        elif iv_ratio >= 1.1:
            pts = 12
        elif iv_ratio >= 0.9:
            pts = 8
        else:
            pts = 4
    else:
        pts = 10
        iv_ratio = 1.0
    score += pts
    details.append(f'IV/HV={iv_ratio:.2f}: +{pts}')

    # 2. Annualized yield (25 pts)
    if dte > 0:
        collateral = strike if option_type == 'put' else spot
        annual_yield = (premium / collateral) * (365 / dte) * 100
        if annual_yield >= 20:
            pts = 25
        elif annual_yield >= 15:
            pts = 22
        elif annual_yield >= 10:
            pts = 18
        elif annual_yield >= 7:
            pts = 14
        elif annual_yield >= 5:
            pts = 10
        elif annual_yield >= 3:
            pts = 6
        else:
            pts = 3
    else:
        annual_yield = 0
        pts = 0
    score += pts
    details.append(f'年化收益={annual_yield:.1f}%: +{pts}')

    # 3. OTM buffer (20 pts)
    if option_type == 'put':
        otm_pct = (spot - strike) / spot * 100
    else:
        otm_pct = (strike - spot) / spot * 100

    if otm_pct >= 15:
        pts = 20
    elif otm_pct >= 10:
        pts = 17
    elif otm_pct >= 7:
        pts = 14
    elif otm_pct >= 5:
        pts = 11
    elif otm_pct >= 3:
        pts = 8
    elif otm_pct >= 0:
        pts = 5
    else:
        pts = 2  # ITM
    score += pts
    details.append(f'OTM缓冲={otm_pct:.1f}%: +{pts}')

    # 4. Theta efficiency (15 pts)
    greeks = bsm_price(spot, strike, dte / 365, 0.04, iv, option_type)
    daily_theta = abs(greeks['theta'])
    if premium > 0:
        theta_ratio = daily_theta / premium * 100
        if theta_ratio >= 3:
            pts = 15
        elif theta_ratio >= 2:
            pts = 12
        elif theta_ratio >= 1:
            pts = 9
        else:
            pts = 5
    else:
        theta_ratio = 0
        pts = 0
    score += pts
    details.append(f'Theta效率={theta_ratio:.1f}%/天: +{pts}')

    # 5. Probability of profit (20 pts) - based on delta
    abs_delta = abs(greeks['delta'])
    pop = (1 - abs_delta) * 100
    if pop >= 85:
        pts = 20
    elif pop >= 75:
        pts = 17
    elif pop >= 65:
        pts = 14
    elif pop >= 55:
        pts = 10
    else:
        pts = 6
    score += pts
    details.append(f'盈利概率={pop:.0f}%: +{pts}')

    detail_str = ' | '.join(details)
    return min(score, 100), detail_str


# ============================================================
# Candidate Generation
# ============================================================

def generate_option_candidates(spot_price: float, hv: float,
                               iv_override: float = None) -> list[dict]:
    """Generate grid of candidate options to sell."""
    iv = iv_override if iv_override else hv * 1.2
    iv = max(iv, 0.1)  # min 10%

    put_strikes = [spot_price * m for m in [0.85, 0.88, 0.90, 0.92, 0.95]]
    call_strikes = [spot_price * m for m in [1.05, 1.08, 1.10, 1.12, 1.15]]
    expiries = [7, 14, 21, 30, 45, 60]

    candidates = []

    for option_type, strikes in [('put', put_strikes), ('call', call_strikes)]:
        for strike in strikes:
            strike = round(strike, 2)
            for dte in expiries:
                T = dte / 365
                greeks = bsm_price(spot_price, strike, T, 0.04, iv, option_type)
                premium = greeks['price']

                if premium <= 0:
                    continue

                score, detail = score_option(spot_price, strike, premium, dte,
                                             option_type, iv, hv)

                if option_type == 'put':
                    otm_pct = round((spot_price - strike) / spot_price * 100, 1)
                    breakeven = round(strike - premium, 2)
                else:
                    otm_pct = round((strike - spot_price) / spot_price * 100, 1)
                    breakeven = round(strike + premium, 2)

                collateral = strike if option_type == 'put' else spot_price
                annual_yield = round((premium / collateral) * (365 / dte) * 100, 1)

                candidates.append({
                    'option_type': option_type,
                    'strike': strike,
                    'dte': dte,
                    'premium': round(premium, 4),
                    'annual_yield': annual_yield,
                    'delta': greeks['delta'],
                    'gamma': greeks['gamma'],
                    'theta': greeks['theta'],
                    'vega': greeks['vega'],
                    'otm_pct': otm_pct,
                    'breakeven': breakeven,
                    'iv': round(iv * 100, 1),
                    'hv': round(hv * 100, 1),
                    'score': score,
                    'detail': detail,
                    'pop': round((1 - abs(greeks['delta'])) * 100, 1),
                    'max_profit': round(premium * 100, 2),  # per contract (100 shares)
                    'max_loss': round(strike * 100 - premium * 100, 2) if option_type == 'put' else 'unlimited',
                })

    candidates.sort(key=lambda x: x['score'], reverse=True)
    return candidates


# ============================================================
# Rolling Recommendation
# ============================================================

def get_rolling_recommendation(spot: float, strike: float, premium: float,
                               dte_left: int, entry_dte: int,
                               option_type: str, hv: float) -> dict:
    """Recommend hold/roll/close for current position."""
    T = dte_left / 365 if dte_left > 0 else 0.001
    iv = hv * 1.2
    greeks = bsm_price(spot, strike, T, 0.04, iv, option_type)

    if option_type == 'put':
        otm_pct = (spot - strike) / spot * 100
    else:
        otm_pct = (strike - spot) / spot * 100

    # Decision logic
    if otm_pct < 2:
        action = 'close'
        reason = f'OTM缓冲仅{otm_pct:.1f}%，风险过高，建议平仓'
    elif dte_left <= 7 and otm_pct > 8:
        action = 'roll'
        reason = f'剩余{dte_left}天，Theta收益递减，建议展期到新合约'
        # Find best new contract
        new_candidates = generate_option_candidates(spot, hv)
        same_type = [c for c in new_candidates if c['option_type'] == option_type and c['dte'] >= 21]
        if same_type:
            best = same_type[0]
            reason += f' -> 推荐: {best["strike"]} {best["dte"]}天 年化{best["annual_yield"]}%'
        else:
            best = None
        return {
            'action': action,
            'reason': reason,
            'current_otm': round(otm_pct, 1),
            'current_delta': greeks['delta'],
            'new_contract': best,
        }
    elif dte_left <= 14:
        theta_pct = abs(greeks['theta']) / premium * 100 if premium > 0 else 0
        if theta_pct < 1:
            action = 'roll'
            reason = f'Theta效率{theta_pct:.1f}%/天偏低，建议展期'
        else:
            action = 'hold'
            reason = f'Theta效率{theta_pct:.1f}%/天良好，继续持有收取时间价值'
    else:
        action = 'hold'
        reason = f'OTM缓冲{otm_pct:.1f}%安全，剩余{dte_left}天继续收取时间价值'

    return {
        'action': action,
        'reason': reason,
        'current_otm': round(otm_pct, 1),
        'current_delta': greeks['delta'],
        'new_contract': None,
    }


# ============================================================
# Main Analysis
# ============================================================

def analyze_options_rotation(
    stock_code: str = '00700',
    option_type: str = 'put',
    risk_free_rate: float = 0.04,
    iv_override: float = None,
) -> dict:
    """Main entry point for options rotation analysis."""
    cache_key = f"opt_{stock_code}_{option_type}_{iv_override}_{risk_free_rate}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    # Get spot price
    hk_data = _get_hk_stock_data(stock_code)
    if not hk_data:
        return {'error': f'无法获取 {stock_code} 实时行情', 'stocks': [], 'update_time': datetime.now().isoformat()}

    spot_price = hk_data['price']

    # Get historical prices for HV
    hist_prices = _fetch_hk_historical(stock_code, 60)
    if not hist_prices:
        hv = 0.3
    else:
        hv = calculate_hv(hist_prices, 20)

    # Generate and score candidates
    candidates = generate_option_candidates(spot_price, hv, iv_override)

    # Best picks
    puts = [c for c in candidates if c['option_type'] == 'put']
    calls = [c for c in candidates if c['option_type'] == 'call']

    best_put = puts[0] if puts else None
    best_call = calls[0] if calls else None
    best_yield = max(candidates, key=lambda x: x['annual_yield']) if candidates else None
    safest = max(candidates, key=lambda x: x['otm_pct']) if candidates else None

    result = {
        'spot_price': spot_price,
        'stock_name': hk_data['name'],
        'hv': round(hv * 100, 1),
        'iv': round((iv_override if iv_override else hv * 1.2) * 100, 1),
        'option_type': option_type,
        'candidates': candidates,
        'best_put': best_put,
        'best_call': best_call,
        'best_yield': best_yield,
        'safest': safest,
        'total': len(candidates),
        'update_time': datetime.now().isoformat(),
    }

    _set_cached(cache_key, result)
    return result


def get_philosophy() -> dict:
    """Options selling methodology."""
    return {
        'title': '卖期权轮动策略',
        'subtitle': '系统化卖出期权，收取时间价值',
        'concepts': [
            {
                'name': '卖Put（卖出看跌期权）',
                'desc': '收取权利金，承诺在特定价格买入标的。相当于"被付费等待抄底"。',
                'suitable': '看好标的但想以更低价格买入时',
            },
            {
                'name': '卖Call（卖出看涨期权）',
                'desc': '收取权利金，承诺在特定价格卖出标的。相当于"出租持仓收取租金"。',
                'suitable': '持有标的但认为短期不会大涨时',
            },
        ],
        'scoring': {
            'title': '期权评分维度（满分100）',
            'dimensions': [
                {'name': 'IV/HV溢价', 'weight': 20, 'desc': '隐含波动率高于历史波动率越多，权利金越贵'},
                {'name': '年化收益率', 'weight': 25, 'desc': '权利金/保证金 × 365/到期天数'},
                {'name': 'OTM缓冲', 'weight': 20, 'desc': '行权价距现价越远越安全'},
                {'name': 'Theta效率', 'weight': 15, 'desc': '每日时间衰减占权利金比例'},
                {'name': '盈利概率', 'weight': 20, 'desc': '基于Delta估算的到期盈利概率'},
            ],
        },
        'risks': [
            '卖出看跌期权：标的大跌时需以行权价买入，可能大幅亏损',
            '卖出看涨期权：标的大涨时错失上涨收益（裸卖Call风险无限）',
            '波动率骤升：IV上升导致期权价格上升，浮亏增加',
            '提前行权风险：美式期权可能被提前行权',
            '流动性风险：深度OTM期权可能流动性不足',
        ],
        'rules': [
            '单笔仓位不超过总资金的5%',
            '优先选择30-45天到期的合约（Theta衰减最快区间）',
            'OTM缓冲至少5%，优选10%以上',
            '临近到期7天内考虑展期（Roll）',
            'IV显著高于HV时是卖期权的好时机',
        ],
    }
