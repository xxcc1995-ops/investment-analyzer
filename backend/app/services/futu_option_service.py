"""富途期权链服务 - 机构级期权分析引擎

============================== 期权入门速成 ==============================

【什么是期权？】
期权就像一份"保险合同"或"预购券"：
- Call（看涨期权）= 你付一笔"保险费"（权利金），获得在未来以约定价格买入股票的权利
- Put（看跌期权）= 你付一笔"保险费"，获得在未来以约定价格卖出股票的权利

【两个角色】
- 买方：付权利金，获得权利（最大亏损就是权利金，像买保险）
- 卖方：收权利金，承担义务（赚的是保险费，但可能要赔大钱，像开保险公司）

【关键术语】
- 行权价(K)：约定的买卖价格
- 权利金(Premium)：期权的价格，买方付给卖方的钱
- 到期日(DTE)：期权还剩多少天到期
- 虚值(OTM)：当前股价离行权价还有距离，暂时不值钱
- 实值(ITM)：当前股价已经超过行权价，已经有内在价值
- 平值(ATM)：行权价≈当前股价

【Greeks是什么？】
Greeks是期权价格对各种因素的敏感度，帮你理解风险：
- Delta：股价涨1块钱，期权价格变多少（方向风险）
- Gamma：Delta的变化速度（加速度）
- Theta：每过一天，期权贬值多少（时间是卖方的朋友）
- Vega：波动率变1%，期权价格变多少（恐慌/贪婪指标）
- Rho：利率变1%，期权价格变多少（通常可忽略）

【本模块能帮你做什么？】
1. 查看完整期权链 + 自动计算Greeks和评分
2. 评估单个期权合约是否值得交易
3. 构建经典策略（备兑看涨、现金担保、价差、跨式等）
4. 生成盈亏图，直观看到"在什么价格赚钱/亏钱"
5. 计算Max Pain（期权到期时股价最可能停在哪）
6. 轮动建议（什么时候该平仓/展期/继续持有）

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
# 【小白必读】什么是BSM模型？
# BSM (Black-Scholes-Merton) 是全世界最经典的期权定价公式。
# 它告诉你：给定5个条件，一个期权"应该"值多少钱。
#
# 5个输入参数：
#   S = 股票现价（比如腾讯现在300块）
#   K = 行权价（比如你约定320块买）
#   T = 还剩多少年到期（30天 = 30/365 ≈ 0.082年）
#   r = 无风险利率（一般用4%，即银行理财收益）
#   sigma = 波动率（股票一年内波动多剧烈，越高期权越贵）
#
# 输出：期权的理论价格 + 5个Greeks指标
# ============================================================

def _norm_cdf(x: float) -> float:
    """标准正态分布的累积概率函数 - BSM公式的核心数学工具"""
    return 0.5 * (1.0 + math.erf(x / sqrt(2.0)))

def _norm_pdf(x: float) -> float:
    """标准正态分布的概率密度函数 - 用于计算Greeks"""
    return exp(-0.5 * x * x) / sqrt(2.0 * math.pi)

def bsm_price(S: float, K: float, T: float, r: float, sigma: float,
              option_type: str = 'put', q: float = 0.0) -> dict:
    """
    BSM期权定价 - 计算期权理论价格和所有Greeks指标

    【通俗理解】
    这个函数回答一个问题："这个期权到底值多少钱？"
    同时告诉你：如果股价涨1块(delta)、时间过1天(theta)、
    波动率变1%(vega)，期权价格会怎么变。

    Args:
        S: 股票现价（比如300）
        K: 行权价（比如320）
        T: 剩余时间（年），30天 = 30/365
        r: 无风险利率，一般0.04（4%）
        sigma: 年化波动率，一般0.2~0.5
        option_type: 'put'(看跌) 或 'call'(看涨)
        q: 股息率，港股一般0.02~0.04

    Returns:
        dict: {
            price: 期权理论价格,
            delta: 股价涨1块，期权变多少（-1到1之间）,
            gamma: delta的变化速度（越大越敏感）,
            theta: 每天贬值多少（负数=你在亏钱）,
            vega: 波动率变1%，价格变多少,
            rho: 利率变1%，价格变多少,
        }
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
    隐含波动率(IV)求解器 - 从市场价格反推波动率

    【通俗理解】
    BSM公式是"已知波动率→算价格"，但实际交易中我们反过来：
    "已知市场价格→反推市场认为的波动率是多少"。

    为什么IV重要？
    - IV高 = 市场恐慌，期权贵（适合卖期权赚钱）
    - IV低 = 市场平静，期权便宜（适合买期权博波动）

    实现方式：先用牛顿法快速逼近，如果失败再用二分法兜底。
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
# Historical Volatility（历史波动率）
# ============================================================
# 【小白必读】历史波动率(HV) vs 隐含波动率(IV)
# - HV = 股票过去实际波动了多少（看后视镜）
# - IV = 市场预期未来会波动多少（看前方）
# - 当IV > HV：期权"贵"了，卖期权有利可图
# - 当IV < HV：期权"便宜"了，买期权有利可图
# ============================================================

def _fetch_hk_historical(code: str = '00700', days: int = 60) -> list:
    """获取港股历史收盘价（通过腾讯财经API）"""
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
    """
    计算历史波动率(HV) - 用过去20天的股价变动来衡量波动

    【通俗理解】
    历史波动率就是"这只股票最近有多颠簸"。
    HV=30%意味着这只股票一年内大概涨跌30%。
    数字越大=越颠簸=期权越贵。
    """
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
    计算 IV 百分位和 IV 排名 - 判断当前IV在历史中处于什么位置

    【通俗理解】
    想象IV是一只股票的"恐慌温度计"：
    - IV百分位 = 80%：历史上80%的时候都没现在这么恐慌 → 期权很贵，适合卖
    - IV百分位 = 20%：历史上80%的时候都比现在恐慌 → 期权便宜，适合买

    【交易决策】
    - IV百分位 > 70%：卖期权收权利金（开保险公司）
    - IV百分位 < 30%：买期权博波动（买保险等出事）
    - IV百分位 30-70%：中性，按其他指标决策
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
    分析买卖价差 - 评估这个期权好不好交易

    【通俗理解】
    买价(Bid)是你能立刻卖出的价格，卖价(Ask)是你能立刻买入的价格。
    价差越小=流动性越好=买卖越容易=交易成本越低。

    【怎么看？】
    - 价差 < 1%：优秀，随时可以买卖
    - 价差 1-5%：良好，正常交易
    - 价差 5-10%：一般，建议用限价单
    - 价差 > 10%：差，谨慎交易（可能卖不掉）
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
# 组合策略分析 - 6种经典期权策略
# ============================================================
# 【小白必读】什么是组合策略？
# 单独买/卖一个期权风险很大。组合策略是把多个期权搭配起来，
# 就像配药一样，不同的组合有不同的"疗效"和"副作用"。
#
# 6种策略速查表：
# ┌─────────────────┬──────────┬──────────┬──────────────────┐
# │ 策略            │ 方向     │ 风险     │ 适合场景         │
# ├─────────────────┼──────────┼──────────┼──────────────────┤
# │ Covered Call    │ 温和看涨 │ 有限     │ 持股想赚额外收入 │
# │ Cash Secured Put│ 温和看涨 │ 较大     │ 想低价买入股票   │
# │ Credit Spread   │ 横盘     │ 有限     │ 稳健收权利金     │
# │ Straddle        │ 大波动   │ 有限/无限│ 预期大行情       │
# │ Strangle        │ 大波动   │ 有限/无限│ 搏大行情成本更低 │
# │ Iron Condor     │ 横盘     │ 有限     │ 预期窄幅震荡     │
# └─────────────────┴──────────┴──────────┴──────────────────┘
# ============================================================

def analyze_covered_call(spot: float, call_contracts: list, stock_qty: int = 100) -> dict:
    """
    Covered Call（备兑看涨）策略分析

    【通俗理解】
    你已经持有100股腾讯（300块/股），觉得短期不会大涨。
    那就卖出一个Call（行权价320），收一笔权利金（比如5块/股=500块）。

    结果：
    - 如果到期股价 < 320：你白赚500块权利金，股票还在手
    - 如果到期股价 > 320：你的股票被以320卖掉，但你还是赚了（320-300+5）*100

    【适合谁？】
    长期持股的人，想在不卖股票的情况下赚点"租金"。
    就像把房子出租，收租金但放弃了涨价的全部收益。

    【风险】
    股价大跌时你还是会亏（但比纯持股少亏一个权利金）。
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
    Cash Secured Put（现金担保看跌）策略分析

    【通俗理解】
    你觉得腾讯300块太贵了，想在280块买入。
    那就卖出一个Put（行权价280），收一笔权利金（比如4块/股=400块）。

    结果：
    - 如果到期股价 > 280：你白赚400块，不用买股票
    - 如果到期股价 < 280：你必须以280块买入，但你的实际成本是280-4=276

    【适合谁？】
    想买某只股票但觉得现在太贵，愿意等跌到某个价位再买。
    就像在二手市场挂个"求购价"，等卖家来找你。

    【风险】
    股价暴跌到100块，你还得按280块买（但这种情况很少见）。
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
    Credit Spread（信用价差）策略分析

    【通俗理解】
    卖期权很赚钱但风险大，Credit Spread就是"给自己买个保险"。

    Put Credit Spread举例：
    1. 卖一个行权价280的Put（收权利金6块）
    2. 同时买一个行权价260的Put（付权利金2块）
    3. 净收权利金 = 6-2 = 4块

    结果：
    - 股价 > 280：你白赚4块
    - 股价在260-280：你赚的部分减少
    - 股价 < 260：你最多亏（280-260-4）*100 = 1600块（有上限！）

    【适合谁？】
    想卖期权收权利金，但又怕风险的人。
    就像开保险公司但给自己也买了再保险。

    【优势】
    风险有限（最多亏宽度-权利金），不像裸卖期权可能亏到破产。
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
# Theta 衰减曲线 - 期权的"保质期"
# ============================================================
# 【小白必读】Theta衰减是什么？
# 期权就像牛奶，有"保质期"。离到期越近，时间价值流失越快。
# 这就是为什么卖期权的人喜欢"时间流逝"——每过一天他们就赚一点。
#
# 重要规律：
# - 前30天：时间价值慢慢流失
# - 最后7天：时间价值加速流失（就像牛奶快过期时变质更快）
# - 到期日：时间价值归零，只剩内在价值
#
# 【交易启示】
# 卖期权：选30-45天到期的，Theta收益最佳
# 买期权：避免买快到期的（Theta会吃掉你的利润）
# ============================================================

def calculate_theta_decay(spot: float, strike: float, premium: float,
                          dte: int, option_type: str, iv: float,
                          risk_free_rate: float = 0.04) -> dict:
    """
    计算Theta衰减曲线 - 看看你的期权每天贬值多少

    【通俗理解】
    这个函数画了一张图：X轴是剩余天数，Y轴是期权价值。
    你会看到一条"越来越陡"的曲线——越接近到期，跌得越快。

    返回值包含：
    - decay_curve: 每天的期权价值（用来画图）
    - best_roll_dte: 建议在还剩几天时展期（Theta最快衰减点）
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
# IV 曲面 / 偏斜 / 期限结构 - 波动率的"地形图"
# ============================================================
# 【小白必读】IV曲面是什么？
# 想象一张3D地图：
# - X轴 = 行权价（从左到右）
# - Y轴 = 到期日（从近到远）
# - Z轴（高度） = IV（波动率）
#
# 这张图告诉你：
# 1. IV偏斜(Skew)：同一到期日，不同行权价的IV差异
#    - 通常Put的IV > Call的IV（因为大家更怕跌）
# 2. 期限结构(Term Structure)：同一行权价，不同到期日的IV差异
#    - 通常远期IV > 近期IV（远期不确定性更大）
#
# 【交易启示】
# - 左高右低的Skew → 市场恐慌下跌，Put贵
# - 远高近低的Term → 市场预期长期波动
# ============================================================

def build_iv_surface(chain: list) -> dict:
    """
    构建IV曲面 - 把所有期权的波动率画成一张"地形图"

    【通俗理解】
    这个函数把所有期权的IV数据整理成一个表格：
    - 横轴是行权价（260, 280, 300, 320, 340...）
    - 纵轴是到期日（7天后, 14天后, 30天后...）
    - 每个格子里是对应的IV值

    通过这张表你可以看出：
    1. 哪个方向的期权更贵（Skew）
    2. 近期还是远期的期权更贵（Term Structure）

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
            (datetime.strptime(e, '%Y-%m-%d').date() - datetime.now().date()).days
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
# Max Pain（最大痛苦点）- 期权到期时股价最可能停在哪
# ============================================================
# 【小白必读】什么是Max Pain？
# Max Pain是一个神奇的指标：期权到期时，股价往往会停在
# 让最多期权买家亏钱的价格——也就是让期权卖家赚最多的位置。
#
# 为什么？因为：
# - 期权卖方（大机构）有能力影响股价
# - 他们会让股价停在对自己最有利的位置
# - 这个位置就是"最大痛苦点"——让买方最痛苦的价格
#
# 【怎么用？】
# - 如果Max Pain = 300，现价 = 310 → 到期前股价可能跌向300
# - 如果Max Pain = 300，现价 = 290 → 到期前股价可能涨向300
# - 越接近到期日，Max Pain的预测越准确
# ============================================================

def calculate_max_pain(chain: list, spot: float = 0) -> dict:
    """
    计算Max Pain（最大痛苦点）

    【通俗理解】
    这个函数回答："期权到期时，股价最可能停在哪个价位？"

    算法：对每个可能的到期价格，计算所有期权买家总共亏多少钱。
    亏最多的价格就是Max Pain——因为这是让买家最"痛苦"的价格。

    返回值：
    - max_pain_strike: 最大痛苦点的价格
    - distance_pct: 离现价有多远（百分比）
    - curve: 每个价格对应的"痛苦值"（画图用）
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
    Straddle（跨式）策略分析

    【通俗理解】
    你觉得腾讯要出大事（财报/政策），但不知道是涨还是跌。
    Long Straddle = 同时买一个Call + 买一个Put（都是300行权价）。

    结果：
    - 股价暴涨到350：Call大赚，Put归零，总体赚钱
    - 股价暴跌到250：Put大赚，Call归零，总体赚钱
    - 股价不动（还在300附近）：两个都归零，你亏了全部权利金

    【适合谁？】
    预期有大行情但不确定方向的人（比如财报前、重大事件前）。

    【风险】
    最大亏损 = 付出的全部权利金。股价不动你就全亏了。
    就像买彩票，中了赚很多，不中就全没了。
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
    Strangle（宽跨式）策略分析

    【通俗理解】
    Strangle是Straddle的"便宜版"：
    买一个OTM Call（行权价320）+ 买一个OTM Put（行权价280）。

    和Straddle的区别：
    - Straddle买的是300+300（贵，但容易触发）
    - Strangle买的是320+280（便宜，但需要更大波动才赚钱）

    【适合谁？】
    同样是赌大行情，但预算有限的人。
    成本更低，但需要股价波动更大才能回本。

    【风险】
    和Straddle一样，最大亏损=全部权利金。
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
    Iron Condor（铁鹰式）策略分析

    【通俗理解】
    Iron Condor = Put Credit Spread + Call Credit Spread 的组合。
    同时卖一个OTM Put和一个OTM Call，两边都收权利金。

    举例（腾讯300块）：
    1. 卖280 Put + 买260 Put（下方保护）
    2. 卖320 Call + 买340 Call（上方保护）
    3. 净收权利金 = 两边权利金之和

    结果：
    - 股价在280-320之间：你白赚全部权利金（最大利润）
    - 股价跌破260或涨破340：你开始亏钱（但有上限）

    【适合谁？】
    觉得股价会在某个区间内震荡的人。
    就像开赌场，赌股价不会大涨大跌。

    【优势】
    胜率高（股价大部分时间在震荡），风险有限。
    【劣势】
    收益有限，一次大行情可能吃掉多次小利润。
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
# P&L 盈亏图 - 一眼看懂"在什么价格赚钱/亏钱"
# ============================================================
# 【小白必读】什么是P&L图？
# P&L(Profit & Loss)图是一张"盈亏地图"：
# - X轴 = 到期时的股价
# - Y轴 = 你的盈亏金额
# - 零线以上 = 赚钱（绿色区域）
# - 零线以下 = 亏钱（红色区域）
#
# 看懂P&L图你就能知道：
# 1. 最多能赚多少？（最高点）
# 2. 最多能亏多少？（最低点）
# 3. 在什么价格开始赚钱？（盈亏平衡点）
# 4. 在什么价格开始亏钱？
# ============================================================

def generate_pnl_diagram(strategy_data: dict, spot: float, spot_range_pct: float = 30) -> dict:
    """
    生成策略的P&L盈亏图数据 - 用来看"在什么价格赚钱/亏钱"

    【通俗理解】
    这个函数帮你画一张图：
    - 横轴是到期时股价可能的范围（比如210-390）
    - 纵轴是对应的盈亏金额
    - 你会看到一条曲线，穿过零线的地方就是"盈亏平衡点"

    用法：把返回的prices和pnl数据传给前端画图即可。
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
# 期权评分系统（满分100）- 帮你快速找到最佳合约
# ============================================================
# 【小白必读】为什么需要评分？
# 一个到期日可能有几十个行权价的期权，怎么选？
# 评分系统从7个维度给每个期权打分，帮你快速筛选。
#
# 7个维度及权重：
# ┌────┬──────────────┬──────┬────────────────────────────┐
# │ #  │ 维度         │ 权重 │ 什么含义                   │
# ├────┼──────────────┼──────┼────────────────────────────┤
# │ 1  │ IV/HV溢价    │ 15分 │ 期权比实际波动贵多少       │
# │ 2  │ IV百分位      │ 15分 │ 当前IV在历史中的位置       │
# │ 3  │ 年化收益率    │ 20分 │ 卖这个期权能赚多少（最重要）│
# │ 4  │ OTM缓冲      │ 15分 │ 离行权价有多远（安全垫）   │
# │ 5  │ Theta效率    │ 15分 │ 每天能赚多少时间价值       │
# │ 6  │ 盈利概率      │ 10分 │ 到期时赚钱的可能性         │
# │ 7  │ 流动性        │ 10分 │ 容不容易买卖               │
# └────┴──────────────┴──────┴────────────────────────────┘
#
# 怎么用？
# - 80分以上：优秀，可以考虑交易
# - 60-80分：良好，可以关注
# - 60分以下：一般，谨慎考虑
# ============================================================

def score_option(spot: float, strike: float, premium: float, dte: int,
                 option_type: str, iv: float, hv: float,
                 bid: float = 0, ask: float = 0, volume: int = 0,
                 iv_percentile: float = 50,
                 risk_free_rate: float = 0.04) -> tuple:
    """
    期权评分系统 - 从7个维度给期权打分（满分100）

    【通俗理解】
    这个函数就像一个"期权选美比赛"的评委，从7个角度给每个期权打分。
    分数越高，说明这个期权越值得交易。

    返回值：
    - score: 总分（0-100）
    - details: 每个维度的得分明细（用来了解为什么得这个分）
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
# 轮动建议 - 什么时候该平仓/展期/继续持有？
# ============================================================
# 【小白必读】什么是轮动(Rolling)？
# 期权有到期日，你不能永远持有。轮动就是"换一个新合约继续做"。
#
# 三种操作：
# ┌──────────┬──────────────────────────────────────────────────┐
# │ 操作     │ 什么情况                                         │
# ├──────────┼──────────────────────────────────────────────────┤
# │ 平仓     │ 赚够了（50%+利润）或 风险太大了（OTM太小）       │
# │ 展期     │ 快到期了但还想继续做，换一个更远到期日的合约      │
# │ 持有     │ 还安全，继续收时间价值                           │
# └──────────┴──────────────────────────────────────────────────┘
#
# 经验法则：
# - 赚了50%就平仓（不要贪心）
# - 剩7天就展期（Theta衰减太快）
# - OTM < 5%就平仓（风险太高）
# ============================================================

def get_rolling_recommendation(spot: float, strike: float, premium: float,
                               dte_left: int, entry_dte: int,
                               option_type: str, hv: float,
                               current_iv: float = None,
                               risk_free_rate: float = 0.04) -> dict:
    """
    轮动建议 - 告诉你该平仓、展期还是继续持有

    【通俗理解】
    你卖了一个Put，现在过了20天，还剩10天到期。
    这个函数会告诉你：
    - "已经赚了60%利润，建议平仓" 或
    - "还剩7天，Theta收益下降，建议展期到下个月" 或
    - "OTM缓冲15%安全，继续持有"

    返回值：
    - action: 'close'(平仓) / 'roll'(展期) / 'hold'(持有)
    - reason: 为什么建议这么做
    - profit_pct: 当前赚了百分之多少
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
# Futu OpenD 连接管理
# ============================================================
# 【小白必读】什么是OpenD？
# OpenD是富途的行情数据网关。你需要：
# 1. 下载并安装 OpenD（https://www.futunn.com/download/OpenAPI）
# 2. 用富途账号登录 OpenD
# 3. OpenD会在本地 127.0.0.1:11111 开一个服务
# 4. 本程序通过这个服务获取实时期权数据
#
# 如果连接失败，检查：
# - OpenD是否已启动并登录？
# - 是否同意了API使用协议？
# - 防火墙是否阻止了11111端口？
# ============================================================

OPEND_HOST = '127.0.0.1'
OPEND_PORT = 11111


def check_connection() -> dict:
    """
    检查 Futu OpenD 连接状态

    【通俗理解】
    这个函数测试"能不能和OpenD说上话"。
    返回 connected=true 就是连上了，可以获取数据了。
    返回 connected=false 就是没连上，看看错误信息是什么原因。
    """
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
    获取完整期权链数据 - 这是整个模块的核心函数

    【通俗理解】
    这个函数做了一件大事：把富途的所有期权数据"加工"成你需要的格式。

    它的工作流程：
    1. 连接OpenD，获取腾讯的所有期权合约
    2. 获取每个合约的实时报价（买价、卖价、成交量等）
    3. 用BSM公式计算每个合约的Greeks（Delta/Gamma/Theta/Vega）
    4. 用7维度评分系统给每个合约打分
    5. 分析流动性（买卖价差）
    6. 找出最佳Put、最佳Call、最高收益、最安全的合约

    返回值包含：
    - spot_price: 股票现价
    - chain: 所有期权合约（已评分+已计算Greeks）
    - best_put: 评分最高的Put
    - best_call: 评分最高的Call
    - iv_analysis: 波动率分析（IV百分位等）

    改进点：
    1. 用 bid/ask 中间价求 IV（而不是 last_price，更准确）
    2. 添加 IV Percentile（判断IV在历史中的位置）
    3. 添加 Bid-Ask Spread 分析（判断流动性）
    4. 改进评分系统（7维度，满分100）
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
                        dte = (datetime.strptime(expiry_date, '%Y-%m-%d').date() - datetime.now().date()).days
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
            '_dte_fix': 'v2_date_only',
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
    """
    获取单个期权合约的详细报价

    【通俗理解】
    当你对某个具体的期权合约感兴趣时，用这个函数查看它的详细信息：
    - 最新价、买价、卖价
    - 今天成交了多少手
    - 还有多少未平仓合约

    用法：传入期权代码（如 HK.00700@240628P00280000），返回报价详情。
    """
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
