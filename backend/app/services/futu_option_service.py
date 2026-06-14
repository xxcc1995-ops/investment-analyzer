"""富途期权链服务 - 机构级期权分析引擎

功能清单:
- BSM定价 + 全Greeks (Delta/Gamma/Theta/Vega/Rho) + 股息率支持
- Newton-Raphson + Bisection 双重IV求解器
- IV曲面/偏斜/期限结构分析
- 7维度期权评分系统
- 组合策略: Covered Call / CSP / Credit Spread / Straddle / Strangle / Iron Condor
- P&L盈亏图数据生成
- Max Pain计算
- Theta衰减曲线
- 轮动建议引擎
"""

import math
import socket
import time
import requests as req
from math import log, sqrt, exp
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from dataclasses import dataclass

try:
    import futu
    from futu import OpenQuoteContext, RET_OK
    FUTU_AVAILABLE = True
except ImportError:
    FUTU_AVAILABLE = False

from app.core.cache import get_cache as _base_get_cache, set_cache as _set_cached

# ============================================================
# Cache
# ============================================================

_CACHE_TTL = 60  # 1 minute for real-time data

def _get_cached(key: str):
    return _base_get_cache(key, ttl_seconds=_CACHE_TTL)


# ============================================================
# BSM Model - 机构级定价引擎 (含Rho + 股息率)
# ============================================================

def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / sqrt(2.0)))

def _norm_pdf(x: float) -> float:
    return exp(-0.5 * x * x) / sqrt(2.0 * math.pi)

def bsm_price(S: float, K: float, T: float, r: float, sigma: float,
              option_type: str = 'put', q: float = 0.0) -> dict:
    """
    Black-Scholes-Merton pricing with continuous dividend yield.

    Args:
        S: Underlying price
        K: Strike price
        T: Time to expiry in years
        r: Risk-free rate (annualized)
        sigma: Volatility (annualized)
        option_type: 'put' or 'call'
        q: Continuous dividend yield (default 0)

    Returns:
        dict with price, delta, gamma, theta, vega, rho, d1, d2
    """
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return {'price': 0, 'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0, 'rho': 0, 'd1': 0, 'd2': 0}

    sqrt_T = sqrt(T)
    d1 = (log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T

    disc_r = exp(-r * T)
    disc_q = exp(-q * T)

    if option_type == 'put':
        price = K * disc_r * _norm_cdf(-d2) - S * disc_q * _norm_cdf(-d1)
        delta = -disc_q * _norm_cdf(-d1)
    else:
        price = S * disc_q * _norm_cdf(d1) - K * disc_r * _norm_cdf(d2)
        delta = disc_q * _norm_cdf(d1)

    # Gamma (same for call and put)
    gamma = disc_q * _norm_pdf(d1) / (S * sigma * sqrt_T)

    # Theta (per day)
    common_theta = -(S * disc_q * _norm_pdf(d1) * sigma) / (2 * sqrt_T)
    if option_type == 'call':
        theta = common_theta - r * K * disc_r * _norm_cdf(d2) + q * S * disc_q * _norm_cdf(d1)
    else:
        theta = common_theta + r * K * disc_r * _norm_cdf(-d2) - q * S * disc_q * _norm_cdf(-d1)
    theta /= 365

    # Vega (per 1% move)
    vega = S * disc_q * _norm_pdf(d1) * sqrt_T / 100

    # Rho (per 1% move in rate)
    if option_type == 'call':
        rho = K * T * disc_r * _norm_cdf(d2) / 100
    else:
        rho = -K * T * disc_r * _norm_cdf(-d2) / 100

    return {
        'price': round(price, 4), 'delta': round(delta, 4),
        'gamma': round(gamma, 6), 'theta': round(theta, 4),
        'vega': round(vega, 4), 'rho': round(rho, 4),
        'd1': round(d1, 4), 'd2': round(d2, 4),
    }


def solve_iv(market_price: float, S: float, K: float, T: float, r: float,
             option_type: str = 'put', q: float = 0.0) -> float:
    """
    Implied volatility solver: Newton-Raphson with bisection fallback.

    Newton-Raphson converges fast near ATM; bisection handles edge cases
    (deep OTM, very low/high IV) where Newton can overshoot or fail.
    """
    if market_price <= 0 or T <= 0 or S <= 0 or K <= 0:
        return 0.0

    # --- Phase 1: Newton-Raphson ---
    sigma = 0.3
    for _ in range(50):
        result = bsm_price(S, K, T, r, sigma, option_type, q)
        diff = result['price'] - market_price
        if abs(diff) < 1e-6:
            return round(sigma, 4)
        vega_native = result['vega'] * 100  # convert back from per-1%
        if vega_native < 1e-10:
            break
        sigma -= diff / vega_native
        sigma = max(sigma, 0.0001)

    # --- Phase 2: Bisection fallback ---
    lo, hi = 0.001, 5.0
    # Verify bounds bracket the solution
    p_lo = bsm_price(S, K, T, r, lo, option_type, q)['price']
    p_hi = bsm_price(S, K, T, r, hi, option_type, q)['price']
    if not (p_lo <= market_price <= p_hi):
        # Price outside model range; return best Newton guess
        return round(max(sigma, 0.001), 4)

    for _ in range(100):
        mid = (lo + hi) / 2
        p_mid = bsm_price(S, K, T, r, mid, option_type, q)['price']
        if abs(p_mid - market_price) < 1e-6:
            return round(mid, 4)
        if p_mid < market_price:
            lo = mid
        else:
            hi = mid

    return round((lo + hi) / 2, 4)


# ============================================================
# Historical Volatility
# ============================================================

def _fetch_hk_historical(code: str = '00700', days: int = 60) -> list:
    """Fetch HK stock historical close prices via Tencent Finance API."""
    try:
        clean_code = code.replace('HK.', '')
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days + 30)).strftime('%Y-%m-%d')
        url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get'
        params = {'param': f'hk{clean_code},day,{start_date},{end_date},{days + 30},qfq'}
        r = req.get(url, params=params, timeout=10)
        data = r.json()
        if 'data' in data and f'hk{clean_code}' in data['data']:
            klines = data['data'][f'hk{clean_code}']
            rows = klines.get('qfqday') or klines.get('day') or []
            return [float(row[2]) for row in rows if len(row) >= 3]
    except Exception:
        pass
    return []

def calculate_hv(prices: list, window: int = 20) -> float:
    """Annualized historical volatility from close prices."""
    if len(prices) < window + 1:
        return 0.3
    recent = prices[-(window + 1):]
    log_returns = [log(recent[i] / recent[i - 1]) for i in range(1, len(recent))]
    if not log_returns:
        return 0.3
    mean = sum(log_returns) / len(log_returns)
    variance = sum((r - mean) ** 2 for r in log_returns) / (len(log_returns) - 1)
    return round(sqrt(variance) * sqrt(252), 4)


# ============================================================
# IV Percentile / IV Rank - 判断IV在历史中的位置
# ============================================================

def calculate_iv_percentile(current_iv: float, historical_ivs: list) -> dict:
    """
    计算 IV Percentile 和 IV Rank

    IV Percentile: 过去 N 天中，有多少天的 IV 低于当前 IV
    IV Rank: (当前IV - 最低IV) / (最高IV - 最低IV)
    """
    if not historical_ivs or len(historical_ivs) < 10:
        return {
            'iv_percentile': 50,  # 默认中位数
            'iv_rank': 50,
            'interpretation': '数据不足，无法准确判断',
            'signal': 'neutral',
        }

    # IV Percentile
    lower_count = sum(1 for iv in historical_ivs if iv < current_iv)
    percentile = round(lower_count / len(historical_ivs) * 100, 1)

    # IV Rank
    min_iv = min(historical_ivs)
    max_iv = max(historical_ivs)
    if max_iv > min_iv:
        iv_rank = round((current_iv - min_iv) / (max_iv - min_iv) * 100, 1)
    else:
        iv_rank = 50

    # 解读
    if percentile >= 80:
        interpretation = 'IV 处于高位（>80%），卖期权收取高额权利金的好时机'
        signal = 'sell_premium'
    elif percentile >= 60:
        interpretation = 'IV 偏高（60-80%），适合卖期权'
        signal = 'sell_premium_ok'
    elif percentile >= 40:
        interpretation = 'IV 中性（40-60%），可正常交易'
        signal = 'neutral'
    elif percentile >= 20:
        interpretation = 'IV 偏低（20-40%），买期权性价比更高'
        signal = 'buy_premium'
    else:
        interpretation = 'IV 处于低位（<20%），买期权博取波动率上升'
        signal = 'buy_premium_good'

    return {
        'iv_percentile': percentile,
        'iv_rank': iv_rank,
        'min_iv': round(min_iv * 100, 1),
        'max_iv': round(max_iv * 100, 1),
        'interpretation': interpretation,
        'signal': signal,
    }

def fetch_historical_iv(stock_code: str, days: int = 252) -> list:
    """
    获取历史 IV 数据（简化版：用历史价格估算）
    实际应用中应该从数据源获取真实的历史 IV
    """
    prices = _fetch_hk_historical(stock_code, days)
    if len(prices) < 30:
        return []

    # 用滚动窗口计算历史波动率作为 IV 的近似
    ivs = []
    window = 20
    for i in range(window, len(prices)):
        window_prices = prices[i-window:i+1]
        hv = calculate_hv(window_prices, window)
        ivs.append(hv * 1.1)  # IV 通常略高于 HV

    return ivs


# ============================================================
# Bid-Ask Spread 分析 - 流动性指标
# ============================================================

def analyze_spread(bid: float, ask: float, mid: float, last: float) -> dict:
    """
    分析买卖价差，评估流动性和交易成本
    """
    if bid <= 0 or ask <= 0 or mid <= 0:
        return {
            'spread': 0, 'spread_pct': 0, 'spread_rating': 'unknown',
            'liquidity_score': 0, 'can_trade': False,
            'recommendation': '无报价数据，无法评估流动性',
        }

    spread = round(ask - bid, 4)
    spread_pct = round(spread / mid * 100, 2)

    # 流动性评分（0-100）
    if spread_pct <= 1:
        liquidity_score = 100
        spread_rating = 'excellent'
        recommendation = '价差极窄，流动性优秀，可立即交易'
    elif spread_pct <= 2:
        liquidity_score = 85
        spread_rating = 'good'
        recommendation = '价差合理，流动性良好，可正常交易'
    elif spread_pct <= 5:
        liquidity_score = 70
        spread_rating = 'fair'
        recommendation = '价差适中，建议限价单交易'
    elif spread_pct <= 10:
        liquidity_score = 50
        spread_rating = 'poor'
        recommendation = '价差较大，流动性一般，谨慎交易'
    else:
        liquidity_score = 25
        spread_rating = 'very_poor'
        recommendation = '价差过大，流动性差，不建议交易'

    return {
        'spread': spread,
        'spread_pct': spread_pct,
        'spread_rating': spread_rating,
        'liquidity_score': liquidity_score,
        'can_trade': spread_pct <= 10,
        'recommendation': recommendation,
    }


# ============================================================
# 组合策略分析
# ============================================================

def analyze_covered_call(spot: float, call_contracts: list, stock_qty: int = 100) -> dict:
    """
    Covered Call 策略分析：持有正股 + 卖 Call
    """
    if not call_contracts:
        return {'error': '无可用 Call 合约'}

    # 选择 OTM 5-15% 的 Call
    suitable = [c for c in call_contracts if 5 <= c.get('otm_pct', 0) <= 15 and c.get('last', 0) > 0]
    if not suitable:
        suitable = [c for c in call_contracts if c.get('otm_pct', 0) > 0 and c.get('last', 0) > 0]

    if not suitable:
        return {'error': '无合适的 Call 合约'}

    best = max(suitable, key=lambda x: x.get('score', 0))

    # 计算策略指标
    premium = best['last']
    strike = best['strike']
    contract_size = best.get('contract_size', 100)

    max_profit = (strike - spot + premium) * contract_size
    breakeven = spot - premium
    max_loss = spot * contract_size - premium * contract_size  # 股价跌到0

    # 年化收益
    dte = best.get('dte', 30)
    if dte > 0:
        annual_yield = (premium / spot) * (365 / dte) * 100
    else:
        annual_yield = 0

    return {
        'strategy': 'Covered Call（备兑看涨）',
        'description': '持有正股 + 卖出虚值 Call，收取权利金',
        'action': f'持有 {stock_qty} 股 + 卖出 1 手 Call',
        'contract': best,
        'entry_cost': round(spot * stock_qty, 2),
        'premium_received': round(premium * contract_size, 2),
        'max_profit': round(max_profit, 2),
        'max_loss': round(max_loss, 2),
        'breakeven': round(breakeven, 2),
        'annual_yield': round(annual_yield, 1),
        'risk_reward_ratio': round(max_profit / (spot * stock_qty - max_profit), 2) if max_profit > 0 else 0,
        'suitable_market': '温和看涨或横盘',
        'risk': '股价大跌时亏损无限（但有权利金缓冲）',
    }

def analyze_cash_secured_put(spot: float, put_contracts: list, cash_available: float = None) -> dict:
    """
    Cash Secured Put 策略分析：卖 Put + 准备现金接盘
    """
    if not put_contracts:
        return {'error': '无可用 Put 合约'}

    # 选择 OTM 5-15% 的 Put
    suitable = [c for c in put_contracts if 5 <= c.get('otm_pct', 0) <= 15 and c.get('last', 0) > 0]
    if not suitable:
        suitable = [c for c in put_contracts if c.get('otm_pct', 0) > 0 and c.get('last', 0) > 0]

    if not suitable:
        return {'error': '无合适的 Put 合约'}

    best = max(suitable, key=lambda x: x.get('score', 0))

    premium = best['last']
    strike = best['strike']
    contract_size = best.get('contract_size', 100)
    dte = best.get('dte', 30)

    # 计算策略指标
    collateral = strike * contract_size
    max_profit = premium * contract_size
    max_loss = collateral - max_profit  # 股价跌到0
    breakeven = strike - premium

    if dte > 0:
        annual_yield = (premium / strike) * (365 / dte) * 100
    else:
        annual_yield = 0

    # 检查资金是否足够
    if cash_available and cash_available < collateral:
        return {
            'error': f'资金不足，需要 ${collateral:,.0f}，可用 ${cash_available:,.0f}',
            'contract': best,
            'collateral_needed': collateral,
        }

    return {
        'strategy': 'Cash Secured Put（现金担保看跌）',
        'description': '卖出虚值 Put，准备资金以行权价买入标的',
        'action': f'卖出 1 手 Put，准备 ${collateral:,.0f} 现金',
        'contract': best,
        'collateral': round(collateral, 2),
        'premium_received': round(max_profit, 2),
        'max_profit': round(max_profit, 2),
        'max_loss': round(max_loss, 2),
        'breakeven': round(breakeven, 2),
        'annual_yield': round(annual_yield, 1),
        'risk_reward_ratio': round(max_profit / max_loss, 2) if max_loss > 0 else 0,
        'suitable_market': '温和看涨或横盘，愿意在低位买入',
        'risk': '股价大跌时需以行权价买入，可能大幅亏损',
    }

def analyze_credit_spread(spot: float, chain: list, spread_type: str = 'put') -> dict:
    """
    Credit Spread 策略分析：卖近价 + 买远价（限制风险）
    """
    if spread_type == 'put':
        # Put Credit Spread：卖高行权价 Put + 买低行权价 Put
        puts = [c for c in chain if c['option_type'] == 'put' and c.get('last', 0) > 0]
        puts.sort(key=lambda x: x['strike'], reverse=True)

        if len(puts) < 2:
            return {'error': 'Put 合约不足，无法构建价差'}

        # 找合适的组合：卖出 OTM 5-10%，买入更远 OTM
        sell_candidates = [c for c in puts if 5 <= c.get('otm_pct', 0) <= 15]
        if not sell_candidates:
            sell_candidates = puts[:3]

        sell_put = max(sell_candidates, key=lambda x: x.get('score', 0))

        # 买入更远 OTM 的 Put（行权价低 5-10%）
        buy_candidates = [c for c in puts if c['strike'] < sell_put['strike'] * 0.95]
        if not buy_candidates:
            buy_candidates = [c for c in puts if c['strike'] < sell_put['strike']]

        if not buy_candidates:
            return {'error': '无法找到合适的买入腿'}

        buy_put = max(buy_candidates, key=lambda x: x['strike'])

        # 计算策略指标
        net_credit = sell_put['last'] - buy_put['last']
        width = sell_put['strike'] - buy_put['strike']
        max_profit = net_credit * sell_put.get('contract_size', 100)
        max_loss = (width - net_credit) * sell_put.get('contract_size', 100)
        breakeven = sell_put['strike'] - net_credit

        dte = sell_put.get('dte', 30)
        if dte > 0:
            annual_yield = (net_credit / width) * (365 / dte) * 100
        else:
            annual_yield = 0

        return {
            'strategy': 'Put Credit Spread（看跌价差）',
            'description': '卖出高行权价 Put + 买入低行权价 Put，限制风险',
            'action': f'卖 K={sell_put["strike"]} Put + 买 K={buy_put["strike"]} Put',
            'sell_leg': sell_put,
            'buy_leg': buy_put,
            'net_credit': round(net_credit, 4),
            'max_profit': round(max_profit, 2),
            'max_loss': round(max_loss, 2),
            'breakeven': round(breakeven, 2),
            'risk_reward_ratio': round(max_loss / max_profit, 2) if max_profit > 0 else 0,
            'annual_yield': round(annual_yield, 1),
            'width': round(width, 2),
            'pop': round((1 - abs(sell_put.get('delta', 0))) * 100, 1),
            'suitable_market': '看涨或横盘',
            'risk': '最大亏损有限（宽度 - 净权利金）',
        }
    else:
        # Call Credit Spread：卖低行权价 Call + 买高行权价 Call
        calls = [c for c in chain if c['option_type'] == 'call' and c.get('last', 0) > 0]
        calls.sort(key=lambda x: x['strike'])

        if len(calls) < 2:
            return {'error': 'Call 合约不足，无法构建价差'}

        sell_candidates = [c for c in calls if 5 <= c.get('otm_pct', 0) <= 15]
        if not sell_candidates:
            sell_candidates = calls[:3]

        sell_call = max(sell_candidates, key=lambda x: x.get('score', 0))

        buy_candidates = [c for c in calls if c['strike'] > sell_call['strike'] * 1.05]
        if not buy_candidates:
            buy_candidates = [c for c in calls if c['strike'] > sell_call['strike']]

        if not buy_candidates:
            return {'error': '无法找到合适的买入腿'}

        buy_call = min(buy_candidates, key=lambda x: x['strike'])

        net_credit = sell_call['last'] - buy_call['last']
        width = buy_call['strike'] - sell_call['strike']
        max_profit = net_credit * sell_call.get('contract_size', 100)
        max_loss = (width - net_credit) * sell_call.get('contract_size', 100)
        breakeven = sell_call['strike'] + net_credit

        dte = sell_call.get('dte', 30)
        if dte > 0:
            annual_yield = (net_credit / width) * (365 / dte) * 100
        else:
            annual_yield = 0

        return {
            'strategy': 'Call Credit Spread（看涨价差）',
            'description': '卖出低行权价 Call + 买入高行权价 Call，限制风险',
            'action': f'卖 K={sell_call["strike"]} Call + 买 K={buy_call["strike"]} Call',
            'sell_leg': sell_call,
            'buy_leg': buy_call,
            'net_credit': round(net_credit, 4),
            'max_profit': round(max_profit, 2),
            'max_loss': round(max_loss, 2),
            'breakeven': round(breakeven, 2),
            'risk_reward_ratio': round(max_loss / max_profit, 2) if max_profit > 0 else 0,
            'annual_yield': round(annual_yield, 1),
            'width': round(width, 2),
            'pop': round((1 - abs(sell_call.get('delta', 0))) * 100, 1),
            'suitable_market': '看跌或横盘',
            'risk': '最大亏损有限（宽度 - 净权利金）',
        }


# ============================================================
# Theta 衰减曲线
# ============================================================

def calculate_theta_decay(spot: float, strike: float, premium: float,
                          dte: int, option_type: str, iv: float,
                          risk_free_rate: float = 0.04) -> dict:
    """
    计算 Theta 随时间衰减的曲线数据
    返回不同剩余天数下的期权价值
    """
    if dte <= 0 or premium <= 0:
        return {'error': '无效参数'}

    decay_curve = []
    for remaining in range(dte, -1, -1):
        if remaining <= 0:
            # 到期时，只有内在价值
            if option_type == 'put':
                intrinsic = max(strike - spot, 0)
            else:
                intrinsic = max(spot - strike, 0)
            decay_curve.append({
                'dte': 0,
                'value': round(intrinsic, 4),
                'time_value': 0,
                'theta_cumulative': round(premium - intrinsic, 4),
                'pct_decayed': 100,
            })
        else:
            T = remaining / 365
            greeks = bsm_price(spot, strike, T, risk_free_rate, iv, option_type)
            value = greeks['price']
            if option_type == 'put':
                intrinsic = max(strike - spot, 0)
            else:
                intrinsic = max(spot - strike, 0)
            time_value = value - intrinsic
            theta_cumulative = premium - value
            pct_decayed = round(theta_cumulative / (premium - intrinsic) * 100, 1) if premium > intrinsic else 0

            decay_curve.append({
                'dte': remaining,
                'value': round(value, 4),
                'time_value': round(time_value, 4),
                'theta_cumulative': round(theta_cumulative, 4),
                'pct_decayed': pct_decayed,
            })

    # 找出 Theta 衰减最快的区间
    if len(decay_curve) >= 2:
        max_decay_rate = 0
        best_roll_dte = 7
        for i in range(len(decay_curve) - 1):
            d1 = decay_curve[i]
            d2 = decay_curve[i + 1]
            if d1['dte'] > 0:
                rate = (d1['value'] - d2['value']) / d1['dte']
                if rate > max_decay_rate:
                    max_decay_rate = rate
                    best_roll_dte = d1['dte']
    else:
        best_roll_dte = 7

    return {
        'decay_curve': decay_curve,
        'best_roll_dte': best_roll_dte,
        'current_value': decay_curve[0]['value'] if decay_curve else 0,
        'current_time_value': decay_curve[0]['time_value'] if decay_curve else 0,
        'pct_decayed_so_far': decay_curve[0]['pct_decayed'] if decay_curve else 0,
    }


# ============================================================
# IV 曲面 / 偏斜 / 期限结构
# ============================================================

def build_iv_surface(chain: list) -> dict:
    """
    从期权链数据构建 IV 曲面 (strike x expiry)。

    Returns:
        {
            'expiries': [...],
            'strikes': [...],
            'surface': { 'call': [[iv...], ...], 'put': [[iv...], ...] },
            'atm_term_structure': [{'expiry': ..., 'dte': ..., 'iv': ...}, ...],
            'skew': [{'strike': ..., 'otm_pct': ..., 'put_iv': ..., 'call_iv': ...}, ...],
        }
    """
    if not chain:
        return {'error': '无期权链数据'}

    # Collect unique expiries and strikes
    expiries = sorted(set(c['expiry'] for c in chain))
    strikes = sorted(set(c['strike'] for c in chain))

    # Build surface matrices
    call_surface = {}
    put_surface = {}
    for c in chain:
        key = (c['expiry'], c['strike'])
        if c.get('iv', 0) > 0:
            if c['option_type'] == 'call':
                call_surface[key] = c['iv']
            else:
                put_surface[key] = c['iv']

    # Build 2D arrays (expiry x strike)
    call_matrix = []
    put_matrix = []
    for exp in expiries:
        call_row = []
        put_row = []
        for strike in strikes:
            call_row.append(call_surface.get((exp, strike), None))
            put_row.append(put_surface.get((exp, strike), None))
        call_matrix.append(call_row)
        put_matrix.append(put_row)

    # ATM term structure: for each expiry, find the IV at the closest strike to spot
    spot = chain[0].get('spot', 0) if chain else 0
    if not spot:
        # Try to infer spot from OTM=0 contracts
        atm_candidates = [c for c in chain if abs(c.get('otm_pct', 999)) < 1]
        if atm_candidates:
            spot = atm_candidates[0]['strike']

    atm_term = []
    for exp in expiries:
        exp_contracts = [c for c in chain if c['expiry'] == exp and c.get('iv', 0) > 0]
        if not exp_contracts:
            continue
        # Find closest to ATM
        closest = min(exp_contracts, key=lambda c: abs(c['strike'] - spot))
        dte = closest.get('dte', 0)
        atm_term.append({
            'expiry': exp, 'dte': dte,
            'iv': round(closest['iv'], 1),
            'strike': closest['strike'],
        })

    # Skew: for the nearest expiry, collect put/call IV across strikes
    skew = []
    if expiries:
        nearest_exp = min(expiries, key=lambda e: abs(
            (datetime.strptime(e, '%Y-%m-%d') - datetime.now()).days
        ))
        nearest_contracts = [c for c in chain if c['expiry'] == nearest_exp and c.get('iv', 0) > 0]
        strike_ivs: Dict[float, dict] = {}
        for c in nearest_contracts:
            s = c['strike']
            if s not in strike_ivs:
                strike_ivs[s] = {'strike': s, 'otm_pct': c.get('otm_pct', 0)}
            if c['option_type'] == 'put':
                strike_ivs[s]['put_iv'] = c['iv']
            else:
                strike_ivs[s]['call_iv'] = c['iv']
        skew = sorted(strike_ivs.values(), key=lambda x: x['strike'])

    return {
        'expiries': expiries,
        'strikes': strikes,
        'surface': {'call': call_matrix, 'put': put_matrix},
        'atm_term_structure': atm_term,
        'skew': skew,
        'spot': spot,
    }


# ============================================================
# Max Pain 计算
# ============================================================

def calculate_max_pain(chain: list, spot: float = 0) -> dict:
    """
    Max Pain: 使所有未平仓期权总内在价值最小化的行权价。
    这是期权到期时标的"最痛苦"的价格点。
    """
    if not chain:
        return {'error': '无数据'}

    strikes = sorted(set(c['strike'] for c in chain))
    if not strikes:
        return {'error': '无行权价数据'}

    # 对每个候选行权价，计算所有期权的总内在价值
    pain_by_strike = {}
    for test_strike in strikes:
        total_pain = 0
        for c in chain:
            oi = c.get('open_interest', 0)
            if oi <= 0:
                continue
            k = c['strike']
            if c['option_type'] == 'call':
                intrinsic = max(test_strike - k, 0) * oi
            else:
                intrinsic = max(k - test_strike, 0) * oi
            total_pain += intrinsic
        pain_by_strike[test_strike] = total_pain

    if not pain_by_strike:
        return {'error': '无未平仓数据'}

    max_pain_strike = min(pain_by_strike, key=pain_by_strike.get)
    max_pain_value = pain_by_strike[max_pain_strike]

    # 构建曲线数据
    curve = [{'strike': s, 'pain': v} for s, v in sorted(pain_by_strike.items())]

    return {
        'max_pain_strike': max_pain_strike,
        'max_pain_value': round(max_pain_value, 2),
        'spot': spot,
        'distance_pct': round((max_pain_strike - spot) / spot * 100, 1) if spot > 0 else 0,
        'curve': curve,
        'interpretation': f'Max Pain = {max_pain_strike}，'
                          f'距现价 {round((max_pain_strike - spot) / spot * 100, 1) if spot > 0 else "?"}%',
    }


# ============================================================
# 组合策略: Straddle (跨式) / Strangle (宽跨式)
# ============================================================

def analyze_straddle(spot: float, chain: list, direction: str = 'long') -> dict:
    """
    Straddle 策略分析: 同时买入/卖出相同行权价的 Call + Put。

    Args:
        spot: 标的现价
        chain: 期权链数据
        direction: 'long'(买入跨式) 或 'short'(卖出跨式)
    """
    if not chain:
        return {'error': '无期权链数据'}

    # Find ATM strike (closest to spot)
    active = [c for c in chain if c.get('last', 0) > 0 and c.get('dte', 0) > 7]
    if not active:
        return {'error': '无活跃合约'}

    strikes = sorted(set(c['strike'] for c in active))
    atm_strike = min(strikes, key=lambda s: abs(s - spot))

    atm_calls = [c for c in active if c['strike'] == atm_strike and c['option_type'] == 'call']
    atm_puts = [c for c in active if c['strike'] == atm_strike and c['option_type'] == 'put']

    if not atm_calls or not atm_puts:
        return {'error': f'行权价 {atm_strike} 缺少 Call 或 Put'}

    call = atm_calls[0]
    put = atm_puts[0]

    net_debit = call['last'] + put['last']
    dte = max(call.get('dte', 30), put.get('dte', 30))
    lot_size = call.get('contract_size', 100)

    # Breakevens
    upper_be = atm_strike + net_debit
    lower_be = atm_strike - net_debit

    # Max profit / loss
    if direction == 'long':
        # Long Straddle: 有限亏损，无限盈利
        max_loss = net_debit * lot_size
        max_profit = 'unlimited'
        # 盈利条件: |S - K| > net_debit
        breakeven_move = round(net_debit / spot * 100, 1)
    else:
        # Short Straddle: 有限盈利，潜在大亏损
        max_profit = net_debit * lot_size
        max_loss = 'unlimited'
        breakeven_move = round(net_debit / spot * 100, 1)

    # Combined Greeks
    combined_delta = round(call.get('delta', 0) + put.get('delta', 0), 4)
    combined_gamma = round(call.get('gamma', 0) + put.get('gamma', 0), 6)
    combined_theta = round(call.get('theta', 0) + put.get('theta', 0), 4)
    combined_vega = round(call.get('vega', 0) + put.get('vega', 0), 4)

    # Required move for profit
    move_required_pct = round(net_debit / spot * 100, 1)

    return {
        'strategy': f'{"Long" if direction == "long" else "Short"} Straddle（{"买入" if direction == "long" else "卖出"}跨式）',
        'description': f'{"买入" if direction == "long" else "卖出"} K={atm_strike} Call + Put',
        'direction': direction,
        'strike': atm_strike,
        'call_leg': call,
        'put_leg': put,
        'net_debit': round(net_debit, 4),
        'net_credit': round(net_debit, 4),
        'upper_breakeven': round(upper_be, 2),
        'lower_breakeven': round(lower_be, 2),
        'breakeven_range': f'{round(lower_be, 2)} - {round(upper_be, 2)}',
        'max_profit': max_profit if isinstance(max_profit, str) else round(max_profit, 2),
        'max_loss': max_loss if isinstance(max_loss, str) else round(max_loss, 2),
        'move_required_pct': move_required_pct,
        'dte': dte,
        'greeks': {
            'delta': combined_delta,
            'gamma': combined_gamma,
            'theta': combined_theta,
            'vega': combined_vega,
        },
        'suitable_market': '预期大幅波动（方向不确定）' if direction == 'long' else '预期横盘窄幅震荡',
        'risk': 'Long: 最大亏损=总权利金; Short: 标的大涨大跌时亏损无限',
    }


def analyze_strangle(spot: float, chain: list, direction: str = 'long') -> dict:
    """
    Strangle 策略分析: 买入/卖出不同行权价的 OTM Call + OTM Put。
    比 Straddle 成本更低，但需要更大波动才能盈利。
    """
    if not chain:
        return {'error': '无期权链数据'}

    active = [c for c in chain if c.get('last', 0) > 0 and c.get('dte', 0) > 7]
    if not active:
        return {'error': '无活跃合约'}

    # Find OTM put (5-10% below spot) and OTM call (5-10% above spot)
    otm_puts = sorted(
        [c for c in active if c['option_type'] == 'put' and c.get('otm_pct', 0) >= 3],
        key=lambda x: x.get('score', 0), reverse=True
    )
    otm_calls = sorted(
        [c for c in active if c['option_type'] == 'call' and c.get('otm_pct', 0) >= 3],
        key=lambda x: x.get('score', 0), reverse=True
    )

    if not otm_puts or not otm_calls:
        return {'error': '无法找到合适的 OTM 合约'}

    put = otm_puts[0]
    call = otm_calls[0]

    net_debit = call['last'] + put['last']
    dte = max(call.get('dte', 30), put.get('dte', 30))
    lot_size = call.get('contract_size', 100)

    upper_be = call['strike'] + net_debit
    lower_be = put['strike'] - net_debit

    if direction == 'long':
        max_loss = net_debit * lot_size
        max_profit = 'unlimited'
    else:
        max_profit = net_debit * lot_size
        max_loss = 'unlimited'

    combined_delta = round(call.get('delta', 0) + put.get('delta', 0), 4)
    combined_gamma = round(call.get('gamma', 0) + put.get('gamma', 0), 6)
    combined_theta = round(call.get('theta', 0) + put.get('theta', 0), 4)
    combined_vega = round(call.get('vega', 0) + put.get('vega', 0), 4)

    return {
        'strategy': f'{"Long" if direction == "long" else "Short"} Strangle（{"买入" if direction == "long" else "卖出"}宽跨式）',
        'description': f'{"买入" if direction == "long" else "卖出"} K={put["strike"]} Put + K={call["strike"]} Call',
        'direction': direction,
        'call_leg': call,
        'put_leg': put,
        'net_debit': round(net_debit, 4),
        'net_credit': round(net_debit, 4),
        'upper_breakeven': round(upper_be, 2),
        'lower_breakeven': round(lower_be, 2),
        'breakeven_range': f'{round(lower_be, 2)} - {round(upper_be, 2)}',
        'max_profit': max_profit if isinstance(max_profit, str) else round(max_profit, 2),
        'max_loss': max_loss if isinstance(max_loss, str) else round(max_loss, 2),
        'move_required_pct': round(net_debit / spot * 100, 1),
        'dte': dte,
        'greeks': {
            'delta': combined_delta,
            'gamma': combined_gamma,
            'theta': combined_theta,
            'vega': combined_vega,
        },
        'suitable_market': '预期大幅波动（方向不确定）' if direction == 'long' else '预期横盘',
        'risk': 'Long: 最大亏损=总权利金; Short: 标的大涨大跌时亏损无限',
    }


# ============================================================
# Iron Condor (铁鹰式)
# ============================================================

def analyze_iron_condor(spot: float, chain: list) -> dict:
    """
    Iron Condor: 卖出 OTM Put + 买入更低 OTM Put + 卖出 OTM Call + 买入更高 OTM Call。
    收取净权利金，标的在区间内时盈利。
    """
    if not chain:
        return {'error': '无期权链数据'}

    active = [c for c in chain if c.get('last', 0) > 0 and c.get('dte', 0) > 7]
    if not active:
        return {'error': '无活跃合约'}

    # Sell OTM put (5-10% below spot)
    sell_puts = [c for c in active if c['option_type'] == 'put' and 3 <= c.get('otm_pct', 0) <= 15]
    # Sell OTM call (5-10% above spot)
    sell_calls = [c for c in active if c['option_type'] == 'call' and 3 <= c.get('otm_pct', 0) <= 15]

    if not sell_puts or not sell_calls:
        return {'error': '无法找到合适的卖出腿合约'}

    sell_put = max(sell_puts, key=lambda x: x.get('score', 0))
    sell_call = max(sell_calls, key=lambda x: x.get('score', 0))

    # Buy protection legs (further OTM)
    buy_put_candidates = [c for c in active if c['option_type'] == 'put' and c['strike'] < sell_put['strike'] * 0.95]
    buy_call_candidates = [c for c in active if c['option_type'] == 'call' and c['strike'] > sell_call['strike'] * 1.05]

    if not buy_put_candidates or not buy_call_candidates:
        return {'error': '无法找到合适的保护腿合约'}

    buy_put = max(buy_put_candidates, key=lambda x: x['strike'])
    buy_call = min(buy_call_candidates, key=lambda x: x['strike'])

    lot_size = sell_put.get('contract_size', 100)

    # Net credit
    net_credit = (sell_put['last'] - buy_put['last']) + (sell_call['last'] - buy_call['last'])
    put_width = sell_put['strike'] - buy_put['strike']
    call_width = buy_call['strike'] - sell_call['strike']
    max_width = max(put_width, call_width)

    max_profit = net_credit * lot_size
    max_loss = (max_width - net_credit) * lot_size

    lower_be = sell_put['strike'] - net_credit
    upper_be = sell_call['strike'] + net_credit

    dte = max(sell_put.get('dte', 30), sell_call.get('dte', 30))
    if dte > 0:
        annual_yield = (net_credit / max_width) * (365 / dte) * 100
    else:
        annual_yield = 0

    return {
        'strategy': 'Iron Condor（铁鹰式）',
        'description': f'卖 K={sell_put["strike"]}P + 买 K={buy_put["strike"]}P + 卖 K={sell_call["strike"]}C + 买 K={buy_call["strike"]}C',
        'legs': {
            'sell_put': sell_put, 'buy_put': buy_put,
            'sell_call': sell_call, 'buy_call': buy_call,
        },
        'net_credit': round(net_credit, 4),
        'max_profit': round(max_profit, 2),
        'max_loss': round(max_loss, 2),
        'lower_breakeven': round(lower_be, 2),
        'upper_breakeven': round(upper_be, 2),
        'profit_zone': f'{round(lower_be, 2)} - {round(upper_be, 2)}',
        'profit_zone_width': round(upper_be - lower_be, 2),
        'width': round(max_width, 2),
        'risk_reward_ratio': round(max_loss / max_profit, 2) if max_profit > 0 else 0,
        'annual_yield': round(annual_yield, 1),
        'pop': round((1 - abs(sell_put.get('delta', 0))) * (1 - abs(sell_call.get('delta', 0))) * 100, 1),
        'dte': dte,
        'suitable_market': '预期标的在区间内横盘震荡',
        'risk': '最大亏损有限（宽度 - 净权利金），标的突破区间时亏损',
    }


# ============================================================
# P&L 盈亏图数据生成
# ============================================================

def generate_pnl_diagram(strategy_data: dict, spot: float, spot_range_pct: float = 30) -> dict:
    """
    为策略生成到期日 P&L 盈亏图数据。

    Args:
        strategy_data: 策略分析结果 (必须包含 legs 信息)
        spot: 当前标的价格
        spot_range_pct: 价格范围百分比 (±%)

    Returns:
        {'prices': [...], 'pnl': [...], 'breakevens': [...], 'max_profit': ..., 'max_loss': ...}
    """
    if not strategy_data or 'error' in strategy_data:
        return {'error': '无效策略数据'}

    lower = spot * (1 - spot_range_pct / 100)
    upper = spot * (1 + spot_range_pct / 100)
    step = (upper - lower) / 200
    prices = [round(lower + i * step, 2) for i in range(201)]

    strategy_name = strategy_data.get('strategy', '')

    # Generic P&L calculator for multi-leg strategies
    def calc_leg_pnl(leg: dict, price: float, sign: int = 1) -> float:
        """Calculate P&L for a single leg. sign: +1 for buy, -1 for sell."""
        strike = leg.get('strike', 0)
        premium = leg.get('last', 0) or leg.get('mid', 0)
        lot = leg.get('contract_size', 100)
        opt_type = leg.get('option_type', 'put')

        if opt_type == 'put':
            intrinsic = max(strike - price, 0)
        else:
            intrinsic = max(price - strike, 0)

        return sign * (premium - intrinsic) * lot

    pnl = []

    # Determine legs and signs from strategy data
    if 'sell_leg' in strategy_data and 'buy_leg' in strategy_data:
        # Credit Spread
        sell_leg = strategy_data['sell_leg']
        buy_leg = strategy_data['buy_leg']
        for price in prices:
            p = calc_leg_pnl(sell_leg, price, -1) + calc_leg_pnl(buy_leg, price, 1)
            pnl.append(round(p, 2))

    elif 'legs' in strategy_data:
        # Iron Condor or similar multi-leg
        legs = strategy_data['legs']
        for price in prices:
            p = 0
            for name, leg in legs.items():
                sign = -1 if 'sell' in name else 1
                p += calc_leg_pnl(leg, price, sign)
            pnl.append(round(p, 2))

    elif 'call_leg' in strategy_data and 'put_leg' in strategy_data:
        # Straddle / Strangle
        direction = strategy_data.get('direction', 'long')
        call_leg = strategy_data['call_leg']
        put_leg = strategy_data['put_leg']
        sign = 1 if direction == 'long' else -1
        for price in prices:
            p = sign * (calc_leg_pnl(call_leg, price, 1) + calc_leg_pnl(put_leg, price, 1))
            pnl.append(round(p, 2))

    elif 'contract' in strategy_data:
        # Single leg (Covered Call / CSP)
        contract = strategy_data['contract']
        opt_type = contract.get('option_type', 'put')
        premium = contract.get('last', 0) or contract.get('mid', 0)
        strike = contract.get('strike', 0)
        lot = contract.get('contract_size', 100)

        if 'Covered' in strategy_name:
            # Long stock + short call
            for price in prices:
                stock_pnl = (price - spot) * lot
                call_pnl = (premium - max(price - strike, 0)) * lot
                pnl.append(round(stock_pnl + call_pnl, 2))
        elif 'Cash Secured' in strategy_name or 'CSP' in strategy_name:
            # Short put
            for price in prices:
                p = (premium - max(strike - price, 0)) * lot
                pnl.append(round(p, 2))
        else:
            for price in prices:
                pnl.append(0)
    else:
        for price in prices:
            pnl.append(0)

    # Find breakevens (where P&L crosses zero)
    breakevens = []
    for i in range(len(pnl) - 1):
        if pnl[i] * pnl[i + 1] < 0:
            # Linear interpolation
            ratio = abs(pnl[i]) / (abs(pnl[i]) + abs(pnl[i + 1]))
            be = round(prices[i] + ratio * (prices[i + 1] - prices[i]), 2)
            breakevens.append(be)

    max_p = max(pnl)
    min_p = min(pnl)

    return {
        'prices': prices,
        'pnl': pnl,
        'breakevens': breakevens,
        'max_profit': max_p,
        'max_loss': min_p,
        'current_spot': spot,
    }


# ============================================================
# 改进的期权评分系统（满分100）
# ============================================================

def score_option(spot: float, strike: float, premium: float, dte: int,
                 option_type: str, iv: float, hv: float,
                 bid: float = 0, ask: float = 0, volume: int = 0,
                 iv_percentile: float = 50,
                 risk_free_rate: float = 0.04) -> tuple:
    """
    改进的期权评分系统（满分100）

    评分维度：
    1. IV/HV 溢价 (15分) - 隐含波动率相对历史波动率的溢价
    2. IV Percentile (15分) - IV 在历史中的位置
    3. 年化收益率 (20分) - 权利金收益率
    4. OTM 缓冲 (15分) - 虚值程度
    5. Theta 效率 (15分) - 每日时间衰减效率
    6. 盈利概率 (10分) - 基于 Delta
    7. 流动性 (10分) - 基于 Bid-Ask Spread
    """
    score = 0
    details = []

    # 1. IV vs HV premium (15 pts)
    if hv > 0:
        iv_ratio = iv / hv
        if iv_ratio >= 1.5: pts = 15
        elif iv_ratio >= 1.3: pts = 12
        elif iv_ratio >= 1.1: pts = 9
        elif iv_ratio >= 0.9: pts = 6
        else: pts = 3
    else:
        pts = 8; iv_ratio = 1.0
    score += pts
    details.append(f'IV/HV={iv_ratio:.2f}: +{pts}')

    # 2. IV Percentile (15 pts) - 卖期权时 IV 越高越好
    if iv_percentile >= 80: pts = 15
    elif iv_percentile >= 60: pts = 12
    elif iv_percentile >= 40: pts = 9
    elif iv_percentile >= 20: pts = 6
    else: pts = 3
    score += pts
    details.append(f'IV百分位={iv_percentile:.0f}%: +{pts}')

    # 3. Annualized yield (20 pts)
    if dte > 0:
        collateral = strike if option_type == 'put' else spot
        annual_yield = (premium / collateral) * (365 / dte) * 100
        if annual_yield >= 20: pts = 20
        elif annual_yield >= 15: pts = 17
        elif annual_yield >= 10: pts = 14
        elif annual_yield >= 7: pts = 11
        elif annual_yield >= 5: pts = 8
        elif annual_yield >= 3: pts = 5
        else: pts = 2
    else:
        annual_yield = 0; pts = 0
    score += pts
    details.append(f'年化收益={annual_yield:.1f}%: +{pts}')

    # 4. OTM buffer (15 pts)
    if option_type == 'put':
        otm_pct = (spot - strike) / spot * 100
    else:
        otm_pct = (strike - spot) / spot * 100
    if otm_pct >= 15: pts = 15
    elif otm_pct >= 10: pts = 13
    elif otm_pct >= 7: pts = 11
    elif otm_pct >= 5: pts = 9
    elif otm_pct >= 3: pts = 6
    elif otm_pct >= 0: pts = 3
    else: pts = 1
    score += pts
    details.append(f'OTM缓冲={otm_pct:.1f}%: +{pts}')

    # 5. Theta efficiency (15 pts)
    greeks = bsm_price(spot, strike, dte / 365, risk_free_rate, iv, option_type)
    daily_theta = abs(greeks['theta'])
    if premium > 0:
        theta_ratio = daily_theta / premium * 100
        if theta_ratio >= 3: pts = 15
        elif theta_ratio >= 2: pts = 12
        elif theta_ratio >= 1: pts = 9
        else: pts = 5
    else:
        theta_ratio = 0; pts = 0
    score += pts
    details.append(f'Theta效率={theta_ratio:.1f}%/天: +{pts}')

    # 6. Probability of profit (10 pts)
    abs_delta = abs(greeks['delta'])
    pop = (1 - abs_delta) * 100
    if pop >= 85: pts = 10
    elif pop >= 75: pts = 8
    elif pop >= 65: pts = 6
    elif pop >= 55: pts = 4
    else: pts = 2
    score += pts
    details.append(f'盈利概率={pop:.0f}%: +{pts}')

    # 7. 流动性评分 (10 pts)
    if bid > 0 and ask > 0 and premium > 0:
        spread_pct = (ask - bid) / premium * 100
        if spread_pct <= 5: pts = 10
        elif spread_pct <= 10: pts = 8
        elif spread_pct <= 20: pts = 6
        elif spread_pct <= 50: pts = 4
        else: pts = 2
        details.append(f'价差={spread_pct:.0f}%: +{pts}')
    else:
        pts = 5  # 无报价数据给中间分
        details.append(f'价差=N/A: +{pts}')
    score += pts

    return min(score, 100), ' | '.join(details)


# ============================================================
# Rolling Recommendation - 轮动建议
# ============================================================

def get_rolling_recommendation(spot: float, strike: float, premium: float,
                               dte_left: int, entry_dte: int,
                               option_type: str, hv: float,
                               current_iv: float = None,
                               risk_free_rate: float = 0.04) -> dict:
    """
    改进的轮动建议：使用真实 IV 而不是估算值
    """
    T = dte_left / 365 if dte_left > 0 else 0.001
    # 优先使用传入的真实 IV，否则用 HV 估算
    iv = current_iv if current_iv and current_iv > 0 else hv * 1.2
    greeks = bsm_price(spot, strike, T, risk_free_rate, iv, option_type)

    if option_type == 'put':
        otm_pct = (spot - strike) / spot * 100
    else:
        otm_pct = (strike - spot) / spot * 100

    current_value = greeks['price']
    if premium > 0:
        profit_pct = (premium - current_value) / premium * 100
    else:
        profit_pct = 0

    new_contract = None

    # 1. Take profit: captured 50%+ of premium
    if profit_pct >= 50 and dte_left > 0:
        return {
            'action': 'close',
            'reason': f'已锁定{profit_pct:.0f}%利润（权利金 {premium:.2f} -> 当前 {current_value:.2f}），建议平仓释放保证金',
            'current_otm': round(otm_pct, 1), 'current_delta': greeks['delta'],
            'current_value': round(current_value, 4), 'profit_pct': round(profit_pct, 1),
            'new_contract': None,
            'iv_used': round(iv * 100, 1),
        }

    # 2. Risk: OTM buffer too low
    if otm_pct < 5:
        return {
            'action': 'close',
            'reason': f'OTM缓冲仅{otm_pct:.1f}%，风险过高，建议平仓',
            'current_otm': round(otm_pct, 1), 'current_delta': greeks['delta'],
            'current_value': round(current_value, 4), 'profit_pct': round(profit_pct, 1),
            'new_contract': None,
            'iv_used': round(iv * 100, 1),
        }

    # 3. Roll: DTE <= 7 and still OTM
    if dte_left <= 7 and otm_pct > 5:
        reason = f'剩余{dte_left}天，Theta收益递减，建议展期到新合约'
        return {
            'action': 'roll', 'reason': reason,
            'current_otm': round(otm_pct, 1), 'current_delta': greeks['delta'],
            'current_value': round(current_value, 4), 'profit_pct': round(profit_pct, 1),
            'new_contract': None,
            'iv_used': round(iv * 100, 1),
        }

    # 4. Roll consideration: DTE <= 14
    if dte_left <= 14:
        theta_pct = abs(greeks['theta']) / current_value * 100 if current_value > 0 else 0
        if theta_pct < 1:
            return {
                'action': 'roll',
                'reason': f'Theta效率{theta_pct:.1f}%/天偏低，建议展期',
                'current_otm': round(otm_pct, 1), 'current_delta': greeks['delta'],
                'current_value': round(current_value, 4), 'profit_pct': round(profit_pct, 1),
                'new_contract': None,
                'iv_used': round(iv * 100, 1),
            }
        else:
            return {
                'action': 'hold',
                'reason': f'Theta效率{theta_pct:.1f}%/天良好，继续持有收取时间价值',
                'current_otm': round(otm_pct, 1), 'current_delta': greeks['delta'],
                'current_value': round(current_value, 4), 'profit_pct': round(profit_pct, 1),
                'new_contract': None,
                'iv_used': round(iv * 100, 1),
            }

    # 5. Hold
    if profit_pct > 0:
        reason = f'OTM缓冲{otm_pct:.1f}%安全，已获利{profit_pct:.0f}%，剩余{dte_left}天继续收取时间价值'
    else:
        reason = f'OTM缓冲{otm_pct:.1f}%安全，剩余{dte_left}天继续持有'
    return {
        'action': 'hold', 'reason': reason,
        'current_otm': round(otm_pct, 1), 'current_delta': greeks['delta'],
        'current_value': round(current_value, 4), 'profit_pct': round(profit_pct, 1),
        'new_contract': None,
        'iv_used': round(iv * 100, 1),
    }


# ============================================================
# Futu OpenD Connection
# ============================================================

OPEND_HOST = '127.0.0.1'
OPEND_PORT = 11111


def check_connection() -> dict:
    """检查 Futu OpenD 连接状态"""
    if not FUTU_AVAILABLE:
        return {
            'connected': False,
            'error': 'futu-api 未安装',
            'solution': '运行: pip install futu-api'
        }

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)

    try:
        result = sock.connect_ex((OPEND_HOST, OPEND_PORT))
        if result != 0:
            return {
                'connected': False,
                'error': f'无法连接到 {OPEND_HOST}:{OPEND_PORT}',
                'solution': '请启动 Futu OpenD 并确保监听端口 11111'
            }

        ctx = OpenQuoteContext(host=OPEND_HOST, port=OPEND_PORT)
        ret, data = ctx.get_global_state()

        if ret == RET_OK:
            ret2, _ = ctx.get_market_snapshot(['HK.00700'])
            ctx.close()

            if ret2 == RET_OK:
                return {
                    'connected': True,
                    'host': OPEND_HOST,
                    'port': OPEND_PORT,
                }
            else:
                return {
                    'connected': False,
                    'error': '需要同意 API 使用协议',
                    'solution': '请在 OpenD 中同意 API 用户协议',
                }
        else:
            error_msg = str(data)
            ctx.close()
            return {
                'connected': False,
                'error': error_msg[:100],
                'solution': '请检查 OpenD 是否正常运行'
            }
    except socket.timeout:
        return {
            'connected': False,
            'error': '连接超时',
            'solution': '请检查 OpenD 是否正常运行'
        }
    except Exception as e:
        return {
            'connected': False,
            'error': str(e)[:100],
            'solution': '请启动 Futu OpenD 并登录'
        }
    finally:
        sock.close()


# ============================================================
# 获取期权链数据（改进版）
# ============================================================

def get_option_chain_from_futu(
    stock_code: str = 'HK.00700',
    option_type: str = 'all',
    risk_free_rate: float = 0.04,
) -> dict:
    """
    从 Futu OpenD 获取真实期权链数据 + BSM Greeks + 改进评分

    改进点：
    1. 用 bid/ask 中间价求 IV（而不是 last_price）
    2. 添加 IV Percentile
    3. 添加 Bid-Ask Spread 分析
    4. 改进评分系统（7维度）
    """
    cache_key = f"futu_opt_{stock_code}_{option_type}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    # 检查连接
    conn_status = check_connection()
    if not conn_status.get('connected'):
        return {'error': conn_status.get('error', '无法连接'), 'chain': [], 'update_time': datetime.now().isoformat()}

    ctx = OpenQuoteContext(host=OPEND_HOST, port=OPEND_PORT)

    try:
        # 确保代码格式正确
        if not stock_code.startswith('HK.'):
            stock_code = f'HK.{stock_code}'

        # 1. 获取标的现价
        ret, data = ctx.get_market_snapshot([stock_code])
        if ret != RET_OK:
            return {'error': f'获取行情失败: {str(data)[:100]}', 'chain': [], 'update_time': datetime.now().isoformat()}

        spot_price = float(data.iloc[0]['last_price'])
        stock_name = data.iloc[0]['name']

        # 2. 获取历史波动率和 IV Percentile
        hist_prices = _fetch_hk_historical(stock_code, 60)
        hv = calculate_hv(hist_prices, 20) if hist_prices else 0.3

        # 获取历史 IV 用于计算 IV Percentile
        hist_ivs = fetch_historical_iv(stock_code, 252)

        # 3. 获取期权到期日
        ret, expiry_dates = ctx.get_option_expiration_date(stock_code)
        if ret != RET_OK:
            return {'error': f'获取到期日失败: {str(expiry_dates)[:100]}', 'chain': [], 'update_time': datetime.now().isoformat()}

        # 4. 获取期权链
        chain = []
        all_expiries = []
        all_strikes = set()
        all_ivs = []  # 收集所有 IV 用于计算 IV Percentile

        today = datetime.now().strftime('%Y-%m-%d')

        for _, row in expiry_dates.iterrows():
            expiry = row['strike_time']
            if expiry < today:
                continue
            all_expiries.append(expiry)

            ret, option_data = ctx.get_option_chain(
                stock_code, index_option_type='NORMAL',
                start=expiry, end=expiry, option_type='ALL',
            )
            if ret != RET_OK:
                continue

            option_codes = option_data['code'].tolist()
            for i in range(0, len(option_codes), 50):
                batch = option_codes[i:i+50]
                ret, quote_data = ctx.get_market_snapshot(batch)
                if ret != RET_OK:
                    continue

                for _, quote in quote_data.iterrows():
                    code = quote['code']
                    opt_info = option_data[option_data['code'] == code]
                    if opt_info.empty:
                        continue
                    opt_row = opt_info.iloc[0]

                    opt_type_raw = str(opt_row.get('option_type', '')).upper()
                    if opt_type_raw == 'CALL' or '.C' in code:
                        otype = 'call'
                    elif opt_type_raw == 'PUT' or '.P' in code:
                        otype = 'put'
                    else:
                        continue

                    if option_type != 'all' and otype != option_type:
                        continue

                    strike = float(opt_row.get('strike_price', 0))
                    expiry_date = opt_row.get('strike_time', expiry)
                    lot_size = int(opt_row.get('lot_size', 100))
                    all_strikes.add(strike)

                    try:
                        dte = (datetime.strptime(expiry_date, '%Y-%m-%d') - datetime.now()).days
                    except:
                        dte = 30

                    last_price = float(quote.get('last_price', 0))
                    bid = float(quote.get('bid_price', 0))
                    ask = float(quote.get('ask_price', 0))
                    volume = int(quote.get('volume', 0)) if quote.get('volume') else 0
                    open_interest = int(quote.get('open_interest', 0)) if quote.get('open_interest') else 0

                    if otype == 'put':
                        otm_pct = (spot_price - strike) / spot_price * 100
                        intrinsic = max(strike - spot_price, 0)
                        breakeven = strike - last_price
                    else:
                        otm_pct = (strike - spot_price) / spot_price * 100
                        intrinsic = max(spot_price - strike, 0)
                        breakeven = strike + last_price

                    time_value = last_price - intrinsic
                    collateral = strike if otype == 'put' else spot_price
                    annual_yield = round((last_price / collateral) * (365 / max(dte, 1)) * 100, 1) if last_price > 0 else 0

                    # === 改进的 BSM Greeks 计算 ===
                    T = dte / 365 if dte > 0 else 0.001

                    # 用 bid/ask 中间价求 IV（更准确）
                    mid_price = round((bid + ask) / 2, 4) if bid > 0 and ask > 0 else last_price
                    if mid_price > 0:
                        iv = solve_iv(mid_price, spot_price, strike, T, risk_free_rate, otype)
                    else:
                        iv = 0

                    if iv > 0:
                        all_ivs.append(iv)
                        greeks = bsm_price(spot_price, strike, T, risk_free_rate, iv, otype)
                    else:
                        greeks = {'price': 0, 'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0, 'rho': 0}

                    pop = round((1 - abs(greeks['delta'])) * 100, 1) if greeks['delta'] != 0 else 0

                    # Bid-Ask Spread 分析
                    spread_analysis = analyze_spread(bid, ask, mid_price, last_price)

                    # 计算 IV Percentile（先用默认值，后面统一更新）
                    iv_pct = 50

                    # 评分（改进版：7维度）
                    score_val, detail_str = score_option(
                        spot_price, strike, mid_price, dte, otype, iv, hv,
                        bid=bid, ask=ask, volume=volume,
                        iv_percentile=iv_pct,
                        risk_free_rate=risk_free_rate,
                    ) if mid_price > 0 else (0, '')

                    max_profit_val = round(mid_price * lot_size, 2)
                    max_loss_val = round((strike - mid_price) * lot_size, 2) if otype == 'put' else None

                    chain.append({
                        'symbol': stock_code, 'code': code, 'option_type': otype,
                        'strike': strike, 'expiry': expiry_date, 'dte': max(dte, 0),
                        'contract_size': lot_size, 'bid': bid, 'ask': ask,
                        'mid': mid_price, 'last': last_price,
                        'volume': volume, 'open_interest': open_interest,
                        'delta': greeks['delta'], 'gamma': greeks['gamma'],
                        'theta': greeks['theta'], 'vega': greeks['vega'],
                        'rho': greeks.get('rho', 0), 'spot': spot_price,
                        'iv': round(iv * 100, 1) if iv else 0,
                        'intrinsic': round(intrinsic, 4), 'time_value': round(time_value, 4),
                        'otm_pct': round(otm_pct, 1), 'breakeven': round(breakeven, 2),
                        'annual_yield': annual_yield, 'pop': pop,
                        'score': score_val, 'detail': detail_str,
                        'max_profit': max_profit_val, 'max_loss': max_loss_val,
                        'spread': spread_analysis['spread'],
                        'spread_pct': spread_analysis['spread_pct'],
                        'liquidity_score': spread_analysis['liquidity_score'],
                        'can_trade': spread_analysis['can_trade'],
                    })

        # 计算 IV Percentile 并更新评分
        if all_ivs:
            avg_iv = sum(all_ivs) / len(all_ivs)
            iv_pct_result = calculate_iv_percentile(avg_iv, hist_ivs)
            iv_percentile = iv_pct_result['iv_percentile']

            # 用真实 IV Percentile 重新计算评分
            for c in chain:
                if c['iv'] > 0:
                    score_val, detail_str = score_option(
                        spot_price, c['strike'], c['mid'], c['dte'], c['option_type'],
                        c['iv'] / 100, hv,
                        bid=c['bid'], ask=c['ask'], volume=c['volume'],
                        iv_percentile=iv_percentile,
                        risk_free_rate=risk_free_rate,
                    )
                    c['score'] = score_val
                    c['detail'] = detail_str
        else:
            iv_pct_result = {'iv_percentile': 50, 'iv_rank': 50, 'interpretation': '数据不足'}

        chain.sort(key=lambda x: x.get('score', 0), reverse=True)

        active_puts = [c for c in chain if c['option_type'] == 'put' and c['last'] > 0]
        active_calls = [c for c in chain if c['option_type'] == 'call' and c['last'] > 0]

        # Best by score
        best_put = max(active_puts, key=lambda x: x['score']) if active_puts else None
        best_call = max(active_calls, key=lambda x: x['score']) if active_calls else None
        best_yield = max(chain, key=lambda x: x['annual_yield']) if chain else None
        safest = max(chain, key=lambda x: x['otm_pct']) if chain else None

        result = {
            'spot_price': spot_price, 'stock_name': stock_name, 'stock_code': stock_code,
            'hv': round(hv * 100, 1),
            'iv_analysis': iv_pct_result,
            'contract_size': 100, 'option_type': option_type, 'chain': chain,
            'expiries': sorted(all_expiries), 'strikes': sorted(list(all_strikes)),
            'best_put': best_put, 'best_call': best_call,
            'best_yield': best_yield, 'safest': safest,
            'total': len(chain), 'update_time': datetime.now().isoformat(),
            'data_source': 'Futu OpenD (真实市场数据 + BSM Greeks + 改进评分)',
        }

        _set_cached(cache_key, result)
        return result

    except Exception as e:
        return {'error': f'获取数据失败: {str(e)}', 'chain': [], 'update_time': datetime.now().isoformat()}
    finally:
        ctx.close()


# ============================================================
# 获取期权报价详情
# ============================================================

def get_option_quote(option_code: str) -> dict:
    """获取单个期权合约的详细报价"""
    conn_status = check_connection()
    if not conn_status.get('connected'):
        return {'error': conn_status.get('error', '无法连接')}

    ctx = OpenQuoteContext(host=OPEND_HOST, port=OPEND_PORT)

    try:
        ret, data = ctx.get_market_snapshot([option_code])
        if ret != RET_OK:
            return {'error': f'获取报价失败: {str(data)[:100]}'}

        quote = data.iloc[0]
        return {
            'code': option_code,
            'last': float(quote.get('last_price', 0)),
            'bid': float(quote.get('bid_price', 0)),
            'ask': float(quote.get('ask_price', 0)),
            'volume': int(quote.get('volume', 0)) if quote.get('volume') else 0,
            'open_interest': int(quote.get('open_interest', 0)) if quote.get('open_interest') else 0,
            'high': float(quote.get('high_price', 0)),
            'low': float(quote.get('low_price', 0)),
            'update_time': str(quote.get('data_time', '')),
        }
    except Exception as e:
        return {'error': f'获取报价失败: {str(e)}'}
    finally:
        ctx.close()
