"""右侧交易判断服务 - 五维度评分系统 + 假右侧排除"""

import logging
import requests
from datetime import datetime, timedelta

from app.core.cache import get_cache, set_cache, cached

logger = logging.getLogger(__name__)

# ============================================================
# 1. 数据获取层
# ============================================================

def _is_hk_code(code: str) -> bool:
    return len(code) == 5 and code.isdigit()


def fetch_a_share_ohlcv(stock_code: str, days: int = 500) -> list[dict]:
    """获取A股OHLCV数据（前复权）- 使用腾讯财经API"""
    cache_key = f"ohlcv_a_{stock_code}_{days}"
    cached_data = get_cache(cache_key, 300)
    if cached_data:
        return cached_data
    try:
        # 判断市场前缀：6开头=上海(sh)，0/3开头=深圳(sz)
        if stock_code.startswith('6'):
            symbol = f'sh{stock_code}'
        else:
            symbol = f'sz{stock_code}'
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=int(days * 1.6))).strftime('%Y-%m-%d')
        url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get'
        params = {'param': f'{symbol},day,{start_date},{end_date},{days + 30},qfq'}
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        if 'data' in data and symbol in data['data']:
            klines = data['data'][symbol]
            rows = klines.get('qfqday') or klines.get('day') or []
            records = []
            for row in rows:
                if len(row) >= 6:
                    records.append({
                        'date': str(row[0]),
                        'open': float(row[1]),
                        'high': float(row[3]),
                        'low': float(row[4]),
                        'close': float(row[2]),
                        'volume': float(row[5]),
                    })
            result = records[-days:]
            set_cache(cache_key, result)
            return result
    except Exception as e:
        logger.error(f"fetch_a_share_ohlcv failed for {stock_code}: {e}")
    return []


def fetch_hk_ohlcv(stock_code: str, days: int = 500) -> list[dict]:
    """获取港股OHLCV数据"""
    cache_key = f"ohlcv_hk_{stock_code}_{days}"
    cached_data = get_cache(cache_key, 300)
    if cached_data:
        return cached_data
    try:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days + 30)).strftime('%Y-%m-%d')
        url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get'
        params = {'param': f'hk{stock_code},day,{start_date},{end_date},{days + 30},qfq'}
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if 'data' in data and f'hk{stock_code}' in data['data']:
            klines = data['data'][f'hk{stock_code}']
            rows = klines.get('qfqday') or klines.get('day') or []
            records = []
            for row in rows:
                if len(row) >= 6:
                    records.append({
                        'date': str(row[0]),
                        'open': float(row[1]),
                        'high': float(row[3]),
                        'low': float(row[4]),
                        'close': float(row[2]),
                        'volume': float(row[5]),
                    })
            result = records[-days:]
            set_cache(cache_key, result)
            return result
    except Exception as e:
        logger.error(f"fetch_hk_ohlcv failed for {stock_code}: {e}")
    return []


def fetch_ohlcv(stock_code: str, days: int = 500) -> list[dict]:
    """自动分发：港股/A股"""
    if _is_hk_code(stock_code):
        return fetch_hk_ohlcv(stock_code, days)
    return fetch_a_share_ohlcv(stock_code, days)


def fetch_weekly_ohlcv(stock_code: str, weeks: int = 200) -> list[dict]:
    """获取周线OHLCV数据"""
    cache_key = f"ohlcv_weekly_{stock_code}_{weeks}"
    cached_data = get_cache(cache_key, 600)
    if cached_data:
        return cached_data
    try:
        if _is_hk_code(stock_code):
            symbol = f'hk{stock_code}'
        elif stock_code.startswith('6'):
            symbol = f'sh{stock_code}'
        else:
            symbol = f'sz{stock_code}'
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=weeks * 8)).strftime('%Y-%m-%d')
        url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get'
        params = {'param': f'{symbol},week,{start_date},{end_date},{weeks + 10},qfq'}
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        if 'data' in data and symbol in data['data']:
            klines = data['data'][symbol]
            rows = klines.get('qfqweek') or klines.get('week') or []
            records = []
            for row in rows:
                if len(row) >= 6:
                    records.append({
                        'date': str(row[0]),
                        'open': float(row[1]),
                        'high': float(row[3]),
                        'low': float(row[4]),
                        'close': float(row[2]),
                        'volume': float(row[5]),
                    })
            result = records[-weeks:]
            set_cache(cache_key, result)
            return result
    except Exception as e:
        logger.error(f"fetch_weekly_ohlcv failed for {stock_code}: {e}")
    return []


def compute_timeframe_alignment(daily_verdict: str, daily_score: int,
                                weekly_verdict: str, weekly_score: int) -> dict:
    """多时间框架对齐评分"""
    aligned = False
    conflict = False
    alignment_score = 0
    signals = []

    verdict_rank = {'右侧确认': 3, '疑似右侧': 2, '非右侧': 1, '左侧下跌': 0}
    d_rank = verdict_rank.get(daily_verdict, 0)
    w_rank = verdict_rank.get(weekly_verdict, 0)

    if d_rank >= 3 and w_rank >= 3:
        alignment_score = 20
        aligned = True
        signals.append("日线+周线双时间框架共振确认（强信号）")
    elif d_rank >= 3 and w_rank == 2:
        alignment_score = 12
        aligned = True
        signals.append("日线确认+周线疑似右侧，趋势基本一致")
    elif d_rank >= 3 and w_rank <= 1:
        alignment_score = 0
        conflict = True
        signals.append("日线看多但周线趋势不佳，信号冲突")
    elif d_rank == 2 and w_rank >= 3:
        alignment_score = 15
        aligned = True
        signals.append("周线确认右侧，日线正在确认中")
    elif d_rank == 2 and w_rank == 2:
        alignment_score = 8
        signals.append("日线+周线均为疑似右侧")
    elif d_rank <= 1 and w_rank >= 3:
        alignment_score = 5
        signals.append("周线趋势向上但日线尚未确认")
    else:
        alignment_score = 0

    return {
        'aligned': aligned,
        'conflict': conflict,
        'alignment_score': alignment_score,
        'alignment_signals': signals,
        'weekly_verdict': weekly_verdict,
        'weekly_score': weekly_score,
    }


# ============================================================
# 2. 技术指标计算层
# ============================================================

def compute_ma(closes: list, period: int) -> list:
    """简单移动平均"""
    result = [None] * (period - 1)
    for i in range(period - 1, len(closes)):
        result.append(sum(closes[i - period + 1:i + 1]) / period)
    return result


def compute_ema(values: list, period: int) -> list:
    """指数移动平均"""
    if len(values) < period:
        return values[:]
    k = 2.0 / (period + 1)
    ema = [0.0] * len(values)
    ema[period - 1] = sum(values[:period]) / period
    for i in range(period, len(values)):
        ema[i] = values[i] * k + ema[i - 1] * (1 - k)
    return ema


def compute_macd(closes: list, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    """MACD: DIF/DEA/柱状图"""
    ema_fast = compute_ema(closes, fast)
    ema_slow = compute_ema(closes, slow)
    dif = [ema_fast[i] - ema_slow[i] for i in range(len(closes))]
    dea = compute_ema(dif, signal)
    histogram = [(dif[i] - dea[i]) * 2 for i in range(len(closes))]
    return {'dif': dif, 'dea': dea, 'histogram': histogram}


def compute_rsi(closes: list, period: int = 14) -> list:
    """RSI"""
    result = [None] * period
    if len(closes) < period + 1:
        return [None] * len(closes)
    gains = []
    losses = []
    for i in range(1, len(closes)):
        change = closes[i] - closes[i - 1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    if avg_loss == 0:
        result.append(100.0)
    else:
        result.append(100.0 - 100.0 / (1 + avg_gain / avg_loss))
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            result.append(100.0)
        else:
            result.append(round(100.0 - 100.0 / (1 + avg_gain / avg_loss), 2))
    return result


def compute_kdj(highs: list, lows: list, closes: list, n: int = 9, m1: int = 3, m2: int = 3) -> dict:
    """KDJ指标"""
    length = len(closes)
    k_vals = [50.0] * length
    d_vals = [50.0] * length
    j_vals = [50.0] * length
    for i in range(n - 1, length):
        window_high = max(highs[i - n + 1:i + 1])
        window_low = min(lows[i - n + 1:i + 1])
        if window_high == window_low:
            rsv = 50.0
        else:
            rsv = (closes[i] - window_low) / (window_high - window_low) * 100
        if i == n - 1:
            k_vals[i] = rsv
            d_vals[i] = rsv
        else:
            k_vals[i] = (m1 - 1) / m1 * k_vals[i - 1] + 1 / m1 * rsv
            d_vals[i] = (m2 - 1) / m2 * d_vals[i - 1] + 1 / m2 * k_vals[i]
        j_vals[i] = 3 * k_vals[i] - 2 * d_vals[i]
    return {'k': k_vals, 'd': d_vals, 'j': j_vals}


def compute_atr(highs: list, lows: list, closes: list, period: int = 14) -> float:
    """ATR: Average True Range (最新值)"""
    if len(closes) < period + 1:
        return 0.0
    trs = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1])
        )
        trs.append(tr)
    if len(trs) < period:
        return 0.0
    atr = sum(trs[:period]) / period
    for i in range(period, len(trs)):
        atr = (atr * (period - 1) + trs[i]) / period
    return round(atr, 4)


def compute_atr_series(highs: list, lows: list, closes: list, period: int = 14) -> list:
    """ATR序列（用于图表和回测）"""
    if len(closes) < period + 1:
        return [None] * len(closes)
    trs = [None]
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1])
        )
        trs.append(tr)
    result = [None] * period
    valid_trs = [t for t in trs[1:period + 1] if t is not None]
    if len(valid_trs) < period:
        return [None] * len(closes)
    atr = sum(valid_trs) / period
    result.append(atr)
    for i in range(period + 1, len(trs)):
        if trs[i] is not None:
            atr = (atr * (period - 1) + trs[i]) / period
        result.append(atr)
    return result


def compute_adx(highs: list, lows: list, closes: list, period: int = 14) -> dict:
    """ADX: Average Directional Index.
    返回 {'adx': list, 'plus_di': list, 'minus_di': list}
    """
    n = len(closes)
    if n < period * 2 + 1:
        return {'adx': [None] * n, 'plus_di': [None] * n, 'minus_di': [None] * n}

    # True Range
    tr_list = [0.0]
    plus_dm = [0.0]
    minus_dm = [0.0]
    for i in range(1, n):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        tr_list.append(tr)
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]
        if up_move > down_move and up_move > 0:
            plus_dm.append(up_move)
        else:
            plus_dm.append(0.0)
        if down_move > up_move and down_move > 0:
            minus_dm.append(down_move)
        else:
            minus_dm.append(0.0)

    # Wilder smoothing
    smoothed_tr = [None] * period
    smoothed_pdm = [None] * period
    smoothed_mdm = [None] * period
    smoothed_tr.append(sum(tr_list[1:period + 1]))
    smoothed_pdm.append(sum(plus_dm[1:period + 1]))
    smoothed_mdm.append(sum(minus_dm[1:period + 1]))
    for i in range(period + 1, n):
        smoothed_tr.append(smoothed_tr[-1] - smoothed_tr[-1] / period + tr_list[i])
        smoothed_pdm.append(smoothed_pdm[-1] - smoothed_pdm[-1] / period + plus_dm[i])
        smoothed_mdm.append(smoothed_mdm[-1] - smoothed_mdm[-1] / period + minus_dm[i])

    # DI
    plus_di = [None] * n
    minus_di = [None] * n
    dx_list = [None] * n
    for i in range(period, n):
        if smoothed_tr[i] and smoothed_tr[i] > 0:
            plus_di[i] = 100 * smoothed_pdm[i] / smoothed_tr[i]
            minus_di[i] = 100 * smoothed_mdm[i] / smoothed_tr[i]
            di_sum = plus_di[i] + minus_di[i]
            if di_sum > 0:
                dx_list[i] = 100 * abs(plus_di[i] - minus_di[i]) / di_sum

    # ADX = Wilder smooth of DX
    adx_vals = [None] * n
    dx_start = period
    valid_dx = [dx_list[i] for i in range(dx_start, min(dx_start + period, n)) if dx_list[i] is not None]
    if len(valid_dx) >= period:
        adx_start_idx = dx_start + period - 1
        if adx_start_idx < n:
            adx_vals[adx_start_idx] = sum(valid_dx) / period
            for i in range(adx_start_idx + 1, n):
                if dx_list[i] is not None and adx_vals[i - 1] is not None:
                    adx_vals[i] = (adx_vals[i - 1] * (period - 1) + dx_list[i]) / period

    return {'adx': adx_vals, 'plus_di': plus_di, 'minus_di': minus_di}


def compute_bollinger_bands(closes: list, period: int = 20, num_std: float = 2.0) -> dict:
    """布林带 返回 {'upper': list, 'middle': list, 'lower': list, 'bandwidth': list}"""
    n = len(closes)
    upper = [None] * n
    middle = [None] * n
    lower = [None] * n
    bandwidth = [None] * n
    for i in range(period - 1, n):
        window = closes[i - period + 1:i + 1]
        sma = sum(window) / period
        variance = sum((x - sma) ** 2 for x in window) / period
        std = variance ** 0.5
        middle[i] = round(sma, 4)
        upper[i] = round(sma + num_std * std, 4)
        lower[i] = round(sma - num_std * std, 4)
        if sma > 0:
            bandwidth[i] = round((upper[i] - lower[i]) / sma * 100, 4)
    return {'upper': upper, 'middle': middle, 'lower': lower, 'bandwidth': bandwidth}


def compute_obv(closes: list, volumes: list) -> dict:
    """OBV: On-Balance Volume 返回 {'obv': list, 'obv_ma20': list}"""
    n = len(closes)
    obv = [0.0]
    for i in range(1, n):
        if closes[i] > closes[i - 1]:
            obv.append(obv[-1] + volumes[i])
        elif closes[i] < closes[i - 1]:
            obv.append(obv[-1] - volumes[i])
        else:
            obv.append(obv[-1])
    obv_ma20 = compute_ma(obv, 20) if n >= 20 else [None] * n
    return {'obv': obv, 'obv_ma20': obv_ma20}


def compute_cci(highs: list, lows: list, closes: list, period: int = 20) -> list:
    """CCI: Commodity Channel Index"""
    n = len(closes)
    result = [None] * (period - 1)
    for i in range(period - 1, n):
        tp = [(highs[j] + lows[j] + closes[j]) / 3 for j in range(i - period + 1, i + 1)]
        sma_tp = sum(tp) / period
        mean_dev = sum(abs(t - sma_tp) for t in tp) / period
        if mean_dev == 0:
            result.append(0.0)
        else:
            result.append(round((tp[-1] - sma_tp) / (0.015 * mean_dev), 2))
    return result


def compute_parabolic_sar(highs: list, lows: list, af_start: float = 0.02,
                          af_step: float = 0.02, af_max: float = 0.20) -> dict:
    """抛物线SAR 返回 {'sar': list, 'is_long': list[bool]}"""
    n = len(highs)
    if n < 2:
        return {'sar': [None] * n, 'is_long': [True] * n}

    sar = [None] * n
    is_long = [True] * n

    # 初始方向：前两根K线
    is_long[0] = True
    if n >= 2:
        is_long[1] = highs[1] >= highs[0]

    # 初始化
    if is_long[1]:
        ep = highs[1]
        sar_val = lows[0]
        af = af_start
    else:
        ep = lows[1]
        sar_val = highs[0]
        af = af_start

    sar[1] = sar_val

    for i in range(2, n):
        prev_sar = sar[i - 1]
        if is_long[i - 1]:
            new_sar = prev_sar + af * (ep - prev_sar)
            new_sar = min(new_sar, lows[i - 1], lows[i - 2] if i >= 2 else lows[i - 1])
            if lows[i] < new_sar:
                is_long[i] = False
                new_sar = ep
                ep = lows[i]
                af = af_start
            else:
                is_long[i] = True
                if highs[i] > ep:
                    ep = highs[i]
                    af = min(af + af_step, af_max)
        else:
            new_sar = prev_sar + af * (ep - prev_sar)
            new_sar = max(new_sar, highs[i - 1], highs[i - 2] if i >= 2 else highs[i - 1])
            if highs[i] > new_sar:
                is_long[i] = True
                new_sar = ep
                ep = highs[i]
                af = af_start
            else:
                is_long[i] = False
                if lows[i] < ep:
                    ep = lows[i]
                    af = min(af + af_step, af_max)
        sar[i] = round(new_sar, 4)

    return {'sar': sar, 'is_long': is_long}


# ============================================================
# 2b. 市场环境判断 & Weinstein阶段分析
# ============================================================

def detect_market_regime(adx_values: list, plus_di: list, minus_di: list) -> dict:
    """ADX市场环境判断"""
    cur = len(adx_values) - 1
    adx_val = adx_values[cur] if cur >= 0 and adx_values[cur] is not None else None
    pdi = plus_di[cur] if cur >= 0 and plus_di[cur] is not None else None
    mdi = minus_di[cur] if cur >= 0 and minus_di[cur] is not None else None

    if adx_val is None:
        return {'regime': 'no_data', 'adx_value': 0, 'di_spread': 0,
                'trend_direction': 'neutral', 'confidence': 'low'}

    di_spread = (pdi or 0) - (mdi or 0)
    # 趋势方向
    if di_spread > 5:
        direction = 'up'
    elif di_spread < -5:
        direction = 'down'
    else:
        direction = 'neutral'

    # ADX趋势（上升/下降）
    adx_rising = False
    if cur >= 5 and adx_values[cur - 5] is not None:
        adx_rising = adx_val > adx_values[cur - 5]

    if adx_val >= 25:
        regime = 'trending'
        confidence = 'high' if adx_rising else 'medium'
    elif adx_val >= 20:
        regime = 'developing'
        confidence = 'medium'
    else:
        regime = 'ranging'
        confidence = 'high' if not adx_rising else 'medium'

    return {
        'regime': regime,
        'adx_value': round(adx_val, 2),
        'di_spread': round(di_spread, 2),
        'trend_direction': direction,
        'confidence': confidence,
    }


def get_dynamic_weights(regime: str) -> dict:
    """根据市场环境返回动态权重（总和100）"""
    if regime == 'trending':
        return {'ma': 28, 'macd': 22, 'volume': 18, 'pattern': 15, 'rsi_kdj': 7, 'new_ind': 10}
    elif regime == 'developing':
        return {'ma': 25, 'macd': 20, 'volume': 20, 'pattern': 18, 'rsi_kdj': 7, 'new_ind': 10}
    else:  # ranging
        return {'ma': 15, 'macd': 12, 'volume': 15, 'pattern': 20, 'rsi_kdj': 18, 'new_ind': 20}


def detect_weinstein_stage(highs: list, lows: list, closes: list, volumes: list, ma_period: int = 30) -> dict:
    """Stan Weinstein四阶段分析"""
    n = len(closes)
    if n < max(60, ma_period + 10):
        return {'stage': 0, 'stage_name': '数据不足', 'signals': [], 'confidence': 0}

    ma30 = compute_ma(closes, ma_period)
    cur = n - 1

    if ma30[cur] is None:
        return {'stage': 0, 'stage_name': '数据不足', 'signals': [], 'confidence': 0}

    # MA30斜率（过去10周≈50个交易日）
    slope_window = min(50, cur)
    if cur >= slope_window and ma30[cur - slope_window] is not None:
        ma30_slope = (ma30[cur] - ma30[cur - slope_window]) / ma30[cur - slope_window] * 100
    else:
        ma30_slope = 0

    # 价格相对MA30位置
    price_vs_ma30 = (closes[cur] - ma30[cur]) / ma30[cur] * 100

    # 成交量趋势（近20日 vs 前20日）
    if cur >= 40:
        recent_vol = sum(volumes[cur - 19:cur + 1]) / 20
        prev_vol = sum(volumes[cur - 39:cur - 19]) / 20
        vol_trend = (recent_vol - prev_vol) / prev_vol * 100 if prev_vol > 0 else 0
    else:
        vol_trend = 0

    # ATR趋势（波动率收窄/扩张）
    atr_series = compute_atr_series(highs, lows, closes, 14)
    if cur >= 30 and atr_series[cur] is not None and atr_series[cur - 30] is not None:
        atr_trend = (atr_series[cur] - atr_series[cur - 30]) / atr_series[cur - 30] * 100
    else:
        atr_trend = 0

    signals = []
    confidence = 0.5

    # Stage判定
    if price_vs_ma30 > 5 and ma30_slope > 2:
        # 价格在MA30上方且MA30上升 → Stage 2
        stage = 2
        if ma30_slope > 5:
            stage_name = '上升趋势(强势)'
            signals.append(f"MA30斜率+{ma30_slope:.1f}%，强势上升")
        else:
            stage_name = '上升趋势(初期)'
            signals.append(f"MA30斜率+{ma30_slope:.1f}%，上升趋势形成")
        if vol_trend > 20:
            signals.append("成交量放大确认上涨")
            confidence = 0.8
        else:
            confidence = 0.6
    elif price_vs_ma30 < -5 and ma30_slope < -2:
        # 价格在MA30下方且MA30下降 → Stage 4
        stage = 4
        stage_name = '下降趋势'
        signals.append(f"MA30斜率{ma30_slope:.1f}%，持续下降")
        signals.append(f"价格低于MA30 {abs(price_vs_ma30):.1f}%")
        confidence = 0.8
    elif abs(ma30_slope) <= 2 and abs(price_vs_ma30) <= 8:
        # MA30平坦，价格附近 → Stage 1
        stage = 1
        stage_name = '底部蓄势'
        signals.append(f"MA30斜率{ma30_slope:.1f}%，横盘整理")
        if atr_trend < -10:
            signals.append("波动率收窄，蓄势待发")
        confidence = 0.6
    elif ma30_slope > 0 and price_vs_ma30 < 5 and price_vs_ma30 > -5:
        # MA30上升但价格开始回落 → Stage 3初期
        stage = 3
        stage_name = '顶部派发(初期)'
        signals.append("价格开始靠近MA30，上涨动能减弱")
        if vol_trend < -10:
            signals.append("成交量萎缩，派发特征")
        confidence = 0.5
    elif ma30_slope < 0 and price_vs_ma30 > -5:
        # MA30开始下降但价格还在附近 → Stage 3后期
        stage = 3
        stage_name = '顶部派发(后期)'
        signals.append(f"MA30斜率{ma30_slope:.1f}%，开始转弱")
        confidence = 0.6
    else:
        # 默认：根据MA30斜率判断
        if ma30_slope >= 0:
            stage = 2 if price_vs_ma30 > 0 else 1
            stage_name = '上升趋势' if stage == 2 else '底部蓄势'
        else:
            stage = 4 if price_vs_ma30 < 0 else 3
            stage_name = '下降趋势' if stage == 4 else '顶部派发'
        confidence = 0.4

    return {
        'stage': stage,
        'stage_name': stage_name,
        'signals': signals,
        'confidence': round(confidence, 2),
        'ma30_slope': round(ma30_slope, 2),
        'price_vs_ma30': round(price_vs_ma30, 2),
    }


# ============================================================
# 2c. 经典形态识别
# ============================================================

def detect_turtle_breakout(highs: list, closes: list) -> dict:
    """海龟交易突破检测（20日/55日高点突破）"""
    n = len(closes)
    cur = n - 1
    score = 0
    signals = []

    if cur < 55:
        return {'score': 0, 'signals': [], 'breakout_20': False, 'breakout_55': False}

    high_20 = max(highs[cur - 20:cur])
    high_55 = max(highs[cur - 55:cur])

    breakout_20 = closes[cur] > high_20
    breakout_55 = closes[cur] > high_55

    if breakout_55:
        score = 8
        signals.append(f"突破55日高点({high_55:.2f})，海龟强突破")
    elif breakout_20:
        score = 5
        signals.append(f"突破20日高点({high_20:.2f})，海龟突破")

    return {
        'score': score,
        'signals': signals,
        'breakout_20': breakout_20,
        'breakout_55': breakout_55,
        'high_20': round(high_20, 2),
        'high_55': round(high_55, 2),
    }


def detect_vcp(highs: list, lows: list, closes: list, volumes: list) -> dict:
    """VCP波动收缩形态检测（Minervini）"""
    n = len(closes)
    cur = n - 1
    score = 0
    signals = []

    if cur < 120:
        return {'score': 0, 'signals': [], 'found': False}

    # 找过去120日的最高价
    lookback = min(120, cur)
    high_idx = cur - lookback + highs[cur - lookback:cur + 1].index(max(highs[cur - lookback:cur + 1]))

    if high_idx >= cur - 10:
        return {'score': 0, 'signals': [], 'found': False}

    # 从高点开始寻找连续收缩
    contractions = []
    start = high_idx
    while start < cur - 5:
        # 找这一段的最低点
        segment_end = min(start + 30, cur)
        segment_low = min(lows[start:segment_end + 1])
        segment_high = max(highs[start:segment_end + 1])
        contraction_range = (segment_high - segment_low) / segment_high * 100

        if contraction_range > 0:
            contractions.append(contraction_range)

        # 找下一个反弹高点
        next_high = start + 5
        for i in range(start + 1, min(start + 30, cur)):
            if highs[i] > highs[i - 1] and (i + 1 >= cur or highs[i] > highs[i + 1]):
                next_high = i
                break
        start = next_high

    if len(contractions) >= 2:
        # 检查收缩是否递减
        decreasing = all(contractions[i] > contractions[i + 1] * 0.7 for i in range(len(contractions) - 1))
        final_ratio = contractions[-1] / contractions[0] if contractions[0] > 0 else 1

        if decreasing and final_ratio < 0.5:
            score = 7
            signals.append(f"VCP形态确认：{len(contractions)}次收缩，最终振幅为首次的{final_ratio:.0%}")
        elif decreasing and final_ratio < 0.7:
            score = 4
            signals.append(f"VCP形态初步：{len(contractions)}次收缩")

    return {
        'score': score,
        'signals': signals,
        'found': score > 0,
        'contraction_count': len(contractions),
    }


def detect_cup_and_handle(highs: list, lows: list, closes: list) -> dict:
    """杯柄形态检测（O'Neil）"""
    n = len(closes)
    cur = n - 1
    score = 0
    signals = []

    if cur < 120:
        return {'score': 0, 'signals': [], 'found': False}

    # 在过去250日（约1年）内寻找杯形态
    lookback = min(250, cur)
    search_start = max(0, cur - lookback)

    # 找左杯沿（高点）
    left_rim_idx = search_start
    left_rim = highs[search_start]
    for i in range(search_start, min(search_start + lookback // 3, cur)):
        if highs[i] > left_rim:
            left_rim = highs[i]
            left_rim_idx = i

    # 找杯底
    cup_bottom_idx = left_rim_idx
    cup_bottom = lows[left_rim_idx]
    for i in range(left_rim_idx, min(left_rim_idx + lookback * 2 // 3, cur)):
        if lows[i] < cup_bottom:
            cup_bottom = lows[i]
            cup_bottom_idx = i

    if cup_bottom_idx <= left_rim_idx + 15:
        return {'score': 0, 'signals': [], 'found': False}

    # 杯深度
    cup_depth = (left_rim - cup_bottom) / left_rim * 100
    if cup_depth < 12 or cup_depth > 40:
        return {'score': 0, 'signals': [], 'found': False}

    # 找右杯沿
    right_rim_idx = cup_bottom_idx
    right_rim = lows[cup_bottom_idx]
    for i in range(cup_bottom_idx + 5, cur):
        if highs[i] > right_rim:
            right_rim = highs[i]
            right_rim_idx = i

    # 检查右杯沿接近左杯沿
    rim_diff = abs(left_rim - right_rim) / left_rim * 100
    if rim_diff > 10:
        return {'score': 0, 'signals': [], 'found': False}

    # 杯柄检测（右杯沿后的回调）
    handle_start = right_rim_idx
    if handle_start >= cur - 5:
        # 右杯沿太近当前，检查是否已突破
        neckline = max(left_rim, right_rim)
        if closes[cur] > neckline:
            score = 7
            signals.append(f"杯柄形态突破颈线({neckline:.2f})，杯深{cup_depth:.1f}%")
        else:
            score = 3
            signals.append(f"杯形态形成，待突破颈线({neckline:.2f})")
    else:
        # 检查柄部
        handle_high = max(highs[handle_start:cur + 1])
        handle_low = min(lows[handle_start:cur + 1])
        handle_depth = (handle_high - handle_low) / handle_high * 100

        if handle_depth < 15 and handle_depth > 3:
            neckline = max(left_rim, right_rim)
            if closes[cur] > neckline:
                score = 7
                signals.append(f"杯柄形态确认突破，杯深{cup_depth:.1f}%，柄深{handle_depth:.1f}%")
            else:
                score = 3
                signals.append(f"杯柄形态形成中，柄深{handle_depth:.1f}%")

    return {
        'score': score,
        'signals': signals,
        'found': score > 0,
        'cup_depth': round(cup_depth, 1),
        'neckline': round(max(left_rim, right_rim), 2),
    }


# ============================================================
# 2d. 新指标评分维度
# ============================================================

def detect_new_indicators_signals(closes: list, highs: list, lows: list, volumes: list) -> dict:
    """布林带/OBV/CCI/SAR综合评分（满分18）"""
    score = 0
    signals = []
    cur = len(closes) - 1

    # 布林带
    bb = compute_bollinger_bands(closes)
    if bb['upper'][cur] is not None:
        # 布林带挤压突破
        bw = bb['bandwidth']
        recent_bw = [b for b in bw[max(0, cur - 120):cur + 1] if b is not None]
        if recent_bw:
            min_bw = min(recent_bw)
            cur_bw = bw[cur]
            if cur_bw and min_bw and cur_bw > min_bw * 1.5 and closes[cur] > bb['upper'][cur]:
                score += 4
                signals.append("布林带挤压后突破上轨（强信号）")
            elif closes[cur] > bb['upper'][cur]:
                score += 2
                signals.append("价格突破布林带上轨")

        # 布林带沿轨运行
        upper_touches = sum(1 for i in range(max(0, cur - 4), cur + 1)
                           if bb['upper'][i] is not None and closes[i] > bb['upper'][i] * 0.99)
        if upper_touches >= 3:
            score += 3
            signals.append("价格沿布林带上轨运行（强势趋势）")

    # OBV
    obv_data = compute_obv(closes, volumes)
    if obv_data['obv_ma20'][cur] is not None:
        obv_val = obv_data['obv'][cur]
        obv_ma = obv_data['obv_ma20'][cur]
        if obv_val > obv_ma:
            score += 4
            signals.append("OBV高于均量线，资金流入确认")
        elif cur >= 5 and obv_val < obv_ma and closes[cur] > closes[cur - 5]:
            score -= 2
            signals.append("OBV背离：价格上涨但资金流出")

    # CCI
    cci_vals = compute_cci(highs, lows, closes)
    if cci_vals[cur] is not None:
        cci = cci_vals[cur]
        if cci > 200:
            score -= 2
            signals.append(f"CCI={cci:.0f}超买，注意风险")
        elif cci > 100:
            score += 4
            signals.append(f"CCI={cci:.0f}突破+100，动量强势")

    # 抛物线SAR
    sar_data = compute_parabolic_sar(highs, lows)
    if sar_data['sar'][cur] is not None:
        if sar_data['is_long'][cur]:
            score += 3
            signals.append("抛物线SAR多头信号")
        else:
            score = max(0, score - 1)
            signals.append("抛物线SAR空头，注意趋势反转")

    score = max(0, min(18, score))
    return {
        'score': score,
        'max': 18,
        'signals': signals,
        'detail': f"综合指标得分 {score}/18",
    }


# ============================================================
# 2e. 风险管理
# ============================================================

def compute_risk_management(closes: list, highs: list, lows: list, atr_value: float) -> dict:
    """ATR风险管理建议"""
    cur = len(closes) - 1
    price = closes[cur]

    if atr_value <= 0 or price <= 0:
        return {'atr': 0, 'atr_pct': 0, 'volatility_level': 'unknown',
                'stop_loss': {}, 'position_sizing': {}, 'risk_reward': {}, 'signals': []}

    atr_pct = atr_value / price * 100

    # 波动率等级
    if atr_pct < 1.5:
        vol_level = 'low'
    elif atr_pct < 3:
        vol_level = 'medium'
    elif atr_pct < 5:
        vol_level = 'high'
    else:
        vol_level = 'extreme'

    # 止损位
    stop_loss = {
        'tight': round(price - 1.5 * atr_value, 2),
        'normal': round(price - 2.0 * atr_value, 2),
        'wide': round(price - 3.0 * atr_value, 2),
    }

    # 风险收益比目标位
    risk_reward = {
        'target_1r': round(price + 1.0 * atr_value, 2),
        'target_2r': round(price + 2.0 * atr_value, 2),
        'target_3r': round(price + 3.0 * atr_value, 2),
    }

    # 仓位建议（假设10万资金）
    base_capital = 100000
    risk_1pct = base_capital * 0.01 / (2 * atr_value)
    risk_2pct = base_capital * 0.02 / (2 * atr_value)

    position_sizing = {
        'risk_1pct_shares': int(risk_1pct),
        'risk_2pct_shares': int(risk_2pct),
        'risk_1pct_amount': round(risk_1pct * price, 0),
        'risk_2pct_amount': round(risk_2pct * price, 0),
        'suggested_pct': '5-10%' if vol_level == 'low' else ('3-5%' if vol_level == 'medium' else '1-3%'),
    }

    signals = []
    if vol_level == 'extreme':
        signals.append(f"波动率极高(ATR={atr_pct:.1f}%)，建议降低仓位或观望")
    elif vol_level == 'high':
        signals.append(f"波动率偏高(ATR={atr_pct:.1f}%)，注意控制仓位")

    return {
        'atr': round(atr_value, 4),
        'atr_pct': round(atr_pct, 2),
        'volatility_level': vol_level,
        'stop_loss': stop_loss,
        'position_sizing': position_sizing,
        'risk_reward': risk_reward,
        'signals': signals,
    }


# ============================================================
# 3. 信号检测层
# ============================================================

def detect_ma_signals(closes: list, dates: list) -> dict:
    """均线系统检测（满分25）"""
    ma5 = compute_ma(closes, 5)
    ma10 = compute_ma(closes, 10)
    ma20 = compute_ma(closes, 20)
    ma60 = compute_ma(closes, 60)
    ma120 = compute_ma(closes, 120)
    score = 0
    signals = []

    # 当前值
    cur = len(closes) - 1
    m5 = ma5[cur] if cur < len(ma5) and ma5[cur] is not None else None
    m10 = ma10[cur] if cur < len(ma10) and ma10[cur] is not None else None
    m20 = ma20[cur] if cur < len(ma20) and ma20[cur] is not None else None
    m60 = ma60[cur] if cur < len(ma60) and ma60[cur] is not None else None
    m120 = ma120[cur] if cur < len(ma120) and ma120[cur] is not None else None

    # 1. 多头排列程度（0-10分）
    alignment = 0
    if m5 and m10 and m5 > m10:
        alignment += 1
    if m10 and m20 and m10 > m20:
        alignment += 1
    if m20 and m60 and m20 > m60:
        alignment += 1
    if m5 and m60 and m5 > m60:
        alignment += 1
    alignment_score = [0, 2, 4, 7, 10][alignment]
    score += alignment_score
    if alignment >= 3:
        signals.append(f"均线多头排列({alignment}/4)")
    elif alignment <= 1:
        signals.append(f"均线空头排列({alignment}/4)")

    # 2. 近期金叉（0-5分）
    golden_cross = False
    for i in range(max(1, cur - 9), cur + 1):
        if (ma5[i] and ma20[i] and ma5[i - 1] and ma20[i - 1] and
                ma5[i - 1] <= ma20[i - 1] and ma5[i] > ma20[i]):
            golden_cross = True
            break
    if golden_cross:
        score += 5
        signals.append("MA5上穿MA20金叉")
    # 检查MA10上穿MA60
    for i in range(max(1, cur - 9), cur + 1):
        if (ma10[i] and ma60[i] and ma10[i - 1] and ma60[i - 1] and
                ma10[i - 1] <= ma60[i - 1] and ma10[i] > ma60[i]):
            score += min(3, 5 - (5 if golden_cross else 0))
            signals.append("MA10上穿MA60金叉")
            break

    # 3. 价格站上MA60（0-5分）
    if m60 and closes[cur] > m60:
        score += 5
        signals.append(f"价格站上MA60({m60:.2f})")
    elif m60:
        signals.append(f"价格在MA60下方({m60:.2f})")

    # 4. 价格站上MA120（0-5分）
    if m120 and closes[cur] > m120:
        score += 5
        signals.append(f"价格站上MA120({m120:.2f})")

    score = min(25, score)
    return {
        'score': score,
        'signals': signals,
        'detail': f"均线得分 {score}/25",
        'ma_data': {
            'ma5': ma5, 'ma10': ma10, 'ma20': ma20,
            'ma60': ma60, 'ma120': ma120,
        }
    }


def detect_macd_signals(closes: list, dates: list) -> dict:
    """MACD信号检测（满分20）"""
    macd = compute_macd(closes)
    dif = macd['dif']
    dea = macd['dea']
    hist = macd['histogram']
    score = 0
    signals = []
    cur = len(closes) - 1

    # 1. 近期MACD金叉（0-6分）
    golden_cross_at = None
    for i in range(max(1, cur - 9), cur + 1):
        if dif[i - 1] <= dea[i - 1] and dif[i] > dea[i]:
            golden_cross_at = i
            break
    if golden_cross_at is not None:
        cross_score = 4
        # 零轴附近或以上金叉加分
        if dif[golden_cross_at] >= 0:
            cross_score += 2
            signals.append("MACD零轴上方金叉（强信号）")
        elif abs(dif[golden_cross_at]) < abs(max(dif[-60:]) - min(dif[-60:])) * 0.1:
            cross_score += 1
            signals.append("MACD零轴附近金叉")
        else:
            signals.append("MACD零轴下方金叉")
        score += cross_score

    # 2. 柱状图由负转正（0-4分）
    if cur >= 1 and hist[cur] > 0 and hist[cur - 1] <= 0:
        score += 4
        signals.append("MACD柱状图由负转正")
    elif cur >= 2 and hist[cur] > 0 and hist[cur - 1] > 0 and hist[cur - 2] <= 0:
        score += 2
        signals.append("MACD柱状图连续为正")

    # 3. 底背离检测（0-6分）
    divergence = _detect_bottom_divergence(closes, dif)
    if divergence['confirmed']:
        score += 6
        signals.append("MACD底背离确认（强信号）")

    # 4. DIF趋势向上（0-4分）
    if cur >= 5:
        dif_slope = dif[cur] - dif[cur - 5]
        if dif_slope > 0:
            if dif[cur] >= 0:
                score += 4
                signals.append("DIF趋势向上（零轴上方）")
            else:
                score += 2
                signals.append("DIF趋势向上（零轴下方）")
        elif dif_slope < 0:
            signals.append("DIF趋势向下")

    score = min(20, score)
    return {
        'score': score,
        'signals': signals,
        'detail': f"MACD得分 {score}/20",
        'macd_data': macd,
    }


def _detect_bottom_divergence(closes: list, dif: list, lookback: int = 120) -> dict:
    """底背离检测：价格新低但DIF不新低"""
    start = max(0, len(closes) - lookback)
    recent_closes = closes[start:]
    recent_dif = dif[start:]
    # 找局部极小值（窗口10）
    price_mins = []
    for i in range(10, len(recent_closes) - 10):
        window = recent_closes[i - 10:i + 11]
        if recent_closes[i] == min(window):
            price_mins.append((i, recent_closes[i], recent_dif[i]))
    if len(price_mins) < 2:
        return {'confirmed': False}
    _, p1, d1 = price_mins[-2]
    _, p2, d2 = price_mins[-1]
    if p2 < p1 and d2 > d1:
        return {'confirmed': True, 'price_low1': p1, 'price_low2': p2,
                'dif_low1': d1, 'dif_low2': d2}
    return {'confirmed': False}


def detect_volume_signals(volumes: list, closes: list) -> dict:
    """成交量信号检测（满分20）"""
    score = 0
    signals = []
    cur = len(closes) - 1

    if cur < 20:
        return {'score': 0, 'signals': ['数据不足'], 'detail': '成交量数据不足'}

    # 1. 放量突破（0-8分）
    vol_ma20 = sum(volumes[cur - 19:cur + 1]) / 20
    if vol_ma20 > 0:
        vol_ratio = volumes[cur] / vol_ma20
        if vol_ratio > 2.0:
            score += 8
            signals.append(f"显著放量({vol_ratio:.1f}倍于20日均量)")
        elif vol_ratio > 1.5:
            score += 6
            signals.append(f"明显放量({vol_ratio:.1f}倍于20日均量)")
        elif vol_ratio > 1.2:
            score += 3
            signals.append(f"温和放量({vol_ratio:.1f}倍于20日均量)")
        else:
            signals.append(f"成交量平淡({vol_ratio:.1f}倍)")

    # 2. 量价配合（0-7分）
    up_vol = []
    down_vol = []
    for i in range(max(1, cur - 19), cur + 1):
        if closes[i] > closes[i - 1]:
            up_vol.append(volumes[i])
        else:
            down_vol.append(volumes[i])
    if up_vol and down_vol:
        avg_up = sum(up_vol) / len(up_vol)
        avg_down = sum(down_vol) / len(down_vol)
        if avg_down > 0:
            vol_price_ratio = avg_up / avg_down
            if vol_price_ratio > 1.3:
                score += 7
                signals.append("量价配合良好（上涨放量，下跌缩量）")
            elif vol_price_ratio > 1.0:
                score += 4
                signals.append("量价基本配合")
            else:
                signals.append("量价背离（上涨缩量，下跌放量）")

    # 3. 底部放量特征（0-5分）
    if cur >= 60:
        low_idx = cur - 60 + volumes[cur - 60:cur + 1].index(min(volumes[cur - 60:cur + 1]))
        recent_avg = sum(volumes[cur - 9:cur + 1]) / 10
        if low_idx < cur - 10 and recent_avg > volumes[low_idx] * 1.5:
            score += 5
            signals.append("底部区域出现放量特征")

    score = min(20, score)
    return {
        'score': score,
        'signals': signals,
        'detail': f"成交量得分 {score}/20",
    }


def detect_pattern_signals(highs: list, lows: list, closes: list, volumes: list = None) -> dict:
    """价格形态检测（满分30，含经典形态）"""
    score = 0
    signals = []
    cur = len(closes) - 1

    # 1. W底检测（0-8分）
    w_bottom = _detect_w_bottom(highs, lows, closes)
    if w_bottom['found'] and w_bottom['confirmed']:
        score += 8
        signals.append(f"W底确认突破颈线({w_bottom['neckline']:.2f})")
    elif w_bottom['found']:
        score += 3
        signals.append(f"W底形态出现，待突破颈线({w_bottom['neckline']:.2f})")

    # 2. 回踩不破支撑（0-4分）
    if cur >= 10:
        recent_high = max(highs[cur - 10:cur])
        recent_low_after_high = min(lows[cur - 5:cur + 1])
        if closes[cur] > recent_high * 0.97 and recent_low_after_high > recent_high * 0.95:
            score += 4
            signals.append("回踩支撑有效")

    # 3. 突破近期高点（0-4分）
    if cur >= 60:
        high_60 = max(highs[cur - 60:cur])
        if closes[cur] > high_60:
            score += 4
            signals.append(f"突破60日高点({high_60:.2f})")
        elif closes[cur] > high_60 * 0.97:
            score += 2
            signals.append(f"接近60日高点({high_60:.2f})")

    # 4. 海龟突破（0-8分）
    turtle = detect_turtle_breakout(highs, closes)
    score += turtle['score']
    signals.extend(turtle['signals'])

    # 5. VCP波动收缩（0-7分）
    if volumes:
        vcp = detect_vcp(highs, lows, closes, volumes)
        score += vcp['score']
        signals.extend(vcp['signals'])

    # 6. 杯柄形态（0-7分）
    cup = detect_cup_and_handle(highs, lows, closes)
    score += cup['score']
    signals.extend(cup['signals'])

    score = min(30, score)
    return {
        'score': score,
        'signals': signals,
        'detail': f"价格形态得分 {score}/30",
        'w_bottom': w_bottom,
    }


def _detect_w_bottom(highs: list, lows: list, closes: list, lookback: int = 120) -> dict:
    """W底（双底）检测"""
    start = max(0, len(lows) - lookback)
    recent_lows = lows[start:]
    recent_highs = highs[start:]
    offset = start

    # 找局部极小值（窗口5）
    local_mins = []
    for i in range(5, len(recent_lows) - 5):
        window = recent_lows[i - 5:i + 6]
        if recent_lows[i] == min(window):
            local_mins.append((i, recent_lows[i]))

    # 找配对：60根K线内，价差3%以内
    for j in range(len(local_mins) - 1):
        for k_idx in range(j + 1, len(local_mins)):
            idx1, price1 = local_mins[j]
            idx2, price2 = local_mins[k_idx]
            if idx2 - idx1 > 60:
                continue
            if idx2 - idx1 < 10:
                continue
            avg_price = (price1 + price2) / 2
            if abs(price1 - price2) / avg_price > 0.03:
                continue
            # 找颈线（两个低点之间的最高点）
            neckline = max(recent_highs[idx1:idx2 + 1])
            # 检查是否突破颈线
            confirmed = closes[-1] > neckline
            return {
                'found': True,
                'neckline': round(neckline, 2),
                'confirmed': confirmed,
                'low1_idx': offset + idx1,
                'low2_idx': offset + idx2,
                'low1': round(price1, 2),
                'low2': round(price2, 2),
            }
    return {'found': False, 'confirmed': False}


def detect_rsi_kdj_signals(closes: list, highs: list, lows: list) -> dict:
    """RSI/KDJ信号检测（满分15）"""
    score = 0
    signals = []
    cur = len(closes) - 1

    rsi = compute_rsi(closes)
    kdj = compute_kdj(highs, lows, closes)

    cur_rsi = rsi[cur] if cur < len(rsi) and rsi[cur] is not None else None

    # 1. RSI从超卖区回升（0-6分）
    if cur_rsi is not None:
        min_rsi_20 = min((v for v in rsi[max(0, cur - 19):cur + 1] if v is not None), default=50)
        if min_rsi_20 < 30 and cur_rsi > 40:
            score += 6
            signals.append(f"RSI从超卖区({min_rsi_20:.0f})回升至{cur_rsi:.0f}")
        elif min_rsi_20 < 35 and cur_rsi > 45:
            score += 3
            signals.append(f"RSI从低位({min_rsi_20:.0f})回升")

    # 2. KDJ金叉（0-5分）
    k_vals = kdj['k']
    d_vals = kdj['d']
    if cur >= 1 and cur < len(k_vals):
        for i in range(max(1, cur - 5), cur + 1):
            if k_vals[i - 1] <= d_vals[i - 1] and k_vals[i] > d_vals[i]:
                cross_score = 5 if k_vals[i] < 50 else 3
                score += cross_score
                signals.append(f"KDJ金叉(K={k_vals[i]:.0f},D={d_vals[i]:.0f})")
                break

    # 3. RSI超买惩罚（-4分）
    if cur_rsi is not None and cur_rsi > 70:
        score -= 4
        signals.append(f"RSI超买({cur_rsi:.0f})，注意追高风险")

    score = max(0, min(15, score))
    return {
        'score': score,
        'signals': signals,
        'detail': f"RSI/KDJ得分 {score}/15",
    }


# ============================================================
# 4. 假右侧排除层
# ============================================================

def anti_fake_checks(ma_result: dict, macd_result: dict, vol_result: dict,
                     closes: list, rsi_val: float = None, highs: list = None,
                     lows: list = None, volumes: list = None, macd_data: dict = None) -> list:
    """假右侧信号检测 — 12项深度检查"""
    warnings = []
    cur = len(closes) - 1

    # === 第一类：趋势结构类 ===

    # 1. 下跌趋势中的反弹（均线仍空头）
    ma_data = ma_result.get('ma_data', {})
    m5 = ma_data.get('ma5', [None] * (cur + 1))
    m10 = ma_data.get('ma10', [None] * (cur + 1))
    m20 = ma_data.get('ma20', [None] * (cur + 1))
    m60 = ma_data.get('ma60', [None] * (cur + 1))
    if (cur < len(m5) and cur < len(m10) and cur < len(m20) and
            m5[cur] and m10[cur] and m20[cur] and
            m5[cur] < m10[cur] < m20[cur]):
        warnings.append({
            'type': 'bearish_bounce',
            'severity': 'high',
            'message': '均线仍为空头排列(MA5<MA10<MA20)，当前上涨可能只是下跌趋势中的反弹',
        })

    # 2. 死猫跳：大跌后快速反弹但无量能支撑
    if cur >= 60 and highs is not None and volumes is not None:
        drop_60d = (closes[cur] - max(closes[cur - 60:cur])) / max(closes[cur - 60:cur]) * 100
        bounce_10d = (closes[cur] - min(closes[cur - 10:cur + 1])) / min(closes[cur - 10:cur + 1]) * 100 if min(closes[cur - 10:cur + 1]) > 0 else 0
        if drop_60d < -15 and bounce_10d > 8:
            # 大跌后反弹，检查量能
            recent_vol_avg = sum(volumes[cur - 9:cur + 1]) / 10
            prev_vol_avg = sum(volumes[cur - 30:cur - 10]) / 20 if cur >= 30 else recent_vol_avg
            if prev_vol_avg > 0 and recent_vol_avg / prev_vol_avg < 1.2:
                warnings.append({
                    'type': 'dead_cat_bounce',
                    'severity': 'high',
                    'message': f'近60日下跌{abs(drop_60d):.1f}%后反弹{bounce_10d:.1f}%，但成交量未明显放大，疑似死猫跳',
                })

    # 3. 均线粘合陷阱：多条均线纠缠，突破方向不确定
    if cur >= 20 and m5[cur] and m10[cur] and m20[cur]:
        ma_range = max(m5[cur], m10[cur], m20[cur]) - min(m5[cur], m10[cur], m20[cur])
        ma_center = (m5[cur] + m10[cur] + m20[cur]) / 3
        if ma_center > 0 and ma_range / ma_center < 0.01:
            warnings.append({
                'type': 'ma_convergence_trap',
                'severity': 'medium',
                'message': 'MA5/MA10/MA20均线粘合（振幅<1%），突破方向不确定，需等待均线发散',
            })

    # === 第二类：量价关系类 ===

    # 4. 缩量突破
    signals_text = ' '.join(vol_result.get('signals', []))
    if '成交量平淡' in signals_text or '量价背离' in signals_text:
        if ma_result.get('score', 0) < 10:
            warnings.append({
                'type': 'low_volume_breakout',
                'severity': 'high',
                'message': '突破时成交量不足且均线弱势，可能是假突破',
            })
        else:
            warnings.append({
                'type': 'low_volume_breakout',
                'severity': 'medium',
                'message': '突破时成交量偏低，需观察后续量能配合',
            })

    # 5. 顶部量价背离：价格新高但成交量递减
    if cur >= 30 and highs is not None and volumes is not None:
        recent_high_idx = cur - 10 + highs[cur - 10:cur + 1].index(max(highs[cur - 10:cur + 1]))
        if recent_high_idx >= cur - 3:  # 近3天创新高
            # 检查成交量是否递减
            vol_recent_3 = volumes[cur - 2:cur + 1]
            vol_prev_3 = volumes[cur - 5:cur - 2]
            if len(vol_prev_3) == 3 and all(v > 0 for v in vol_prev_3):
                avg_recent = sum(vol_recent_3) / 3
                avg_prev = sum(vol_prev_3) / 3
                if avg_prev > 0 and avg_recent / avg_prev < 0.7:
                    warnings.append({
                        'type': 'volume_price_divergence_top',
                        'severity': 'high',
                        'message': '价格创新高但成交量较前期萎缩30%以上，顶部量价背离',
                    })

    # 6. 反弹逐次缩量：每次反弹量能递减
    if cur >= 60 and volumes is not None:
        rallies = 0
        declining_rallies = 0
        for i in range(cur - 50, cur - 10, 10):
            if i + 10 <= cur and closes[i + 5] > closes[i]:
                rallies += 1
                vol_start = sum(volumes[i:i + 3]) / 3
                vol_end = sum(volumes[i + 5:i + 8]) / 3 if i + 8 <= cur else vol_start
                if vol_start > 0 and vol_end / vol_start < 0.8:
                    declining_rallies += 1
        if rallies >= 2 and declining_rallies >= rallies - 1:
            warnings.append({
                'type': 'declining_rally_volume',
                'severity': 'medium',
                'message': '反弹过程中成交量逐次递减，买盘力度持续减弱',
            })

    # === 第三类：MACD信号类 ===

    # 7. MACD底背离未确认
    macd_signals = ' '.join(macd_result.get('signals', []))
    if '零轴下方金叉' in macd_signals and '底背离' not in macd_signals:
        warnings.append({
            'type': 'weak_macd',
            'severity': 'medium',
            'message': 'MACD在零轴下方金叉且无底背离确认，信号较弱',
        })

    # 8. MACD顶背离：价格新高但MACD未新高
    if macd_data and cur >= 60:
        dif_list = macd_data.get('dif', [])
        if len(dif_list) > cur:
            # 找近60日价格高点和DIF高点
            price_high_60 = max(closes[cur - 60:cur + 1])
            price_high_30 = max(closes[cur - 30:cur + 1])
            dif_at_60_high = max(dif_list[max(0, cur - 60):cur + 1]) if any(d is not None for d in dif_list[max(0, cur - 60):cur + 1]) else None
            dif_at_30_high = max(dif_list[max(0, cur - 30):cur + 1]) if any(d is not None for d in dif_list[max(0, cur - 30):cur + 1]) else None
            if (dif_at_60_high is not None and dif_at_30_high is not None and
                    price_high_30 >= price_high_60 * 0.99 and dif_at_30_high < dif_at_60_high * 0.8):
                warnings.append({
                    'type': 'macd_top_divergence',
                    'severity': 'high',
                    'message': '价格接近前期高点但MACD DIF明显低于前高，顶背离风险',
                })

    # === 第四类：突破可靠性类 ===

    # 9. 连续假突破检测
    if cur >= 60 and highs is not None:
        false_breakouts = 0
        for i in range(cur - 59, cur - 5):
            if i >= 20:
                prev_high = max(highs[i - 20:i])
                if closes[i] > prev_high and closes[i + 5] < closes[i] * 0.98:
                    false_breakouts += 1
        if false_breakouts >= 2:
            warnings.append({
                'type': 'consecutive_false_breakout',
                'severity': 'high',
                'message': f'近60日出现{false_breakouts}次假突破（突破后快速回落），需谨慎',
            })

    # 10. 长上影线拒绝：连续出现长上影线表示卖压沉重
    if cur >= 5 and highs is not None and lows is not None:
        long_shadows = 0
        for i in range(max(0, cur - 9), cur + 1):
            body = abs(closes[i] - (closes[i - 1] if i > 0 else closes[i]))
            upper_shadow = highs[i] - max(closes[i], (closes[i - 1] if i > 0 else closes[i]))
            total_range = highs[i] - lows[i]
            if total_range > 0 and upper_shadow / total_range > 0.5 and upper_shadow > body * 2:
                long_shadows += 1
        if long_shadows >= 3:
            warnings.append({
                'type': 'long_upper_shadow_rejection',
                'severity': 'high',
                'message': f'近10日出现{long_shadows}根长上影线，上方卖压沉重',
            })

    # 11. 接近强阻力位：前高、整数关口、密集成交区
    if cur >= 120 and highs is not None:
        # 找过去120日的重要高点
        major_high = max(highs[cur - 120:cur])
        dist_to_resistance = (major_high - closes[cur]) / closes[cur] * 100
        if 0 < dist_to_resistance < 3:
            # 接近前高，检查是否曾多次受阻
            resistance_touches = sum(1 for i in range(cur - 120, cur)
                                     if highs[i] >= major_high * 0.98)
            if resistance_touches >= 3:
                warnings.append({
                    'type': 'strong_resistance_nearby',
                    'severity': 'medium',
                    'message': f'价格距120日前高({major_high:.2f})仅{dist_to_resistance:.1f}%，该位置曾{resistance_touches}次受阻',
                })

    # === 第五类：动量指标类 ===

    # 12. RSI超买
    if rsi_val is not None and rsi_val > 70:
        warnings.append({
            'type': 'rsi_overbought',
            'severity': 'medium',
            'message': f'RSI={rsi_val:.0f}已进入超买区，追高风险较大',
        })

    return warnings


# ============================================================
# 5. 主分析函数
# ============================================================

@cached(ttl_seconds=300, key_prefix="right_side")
def analyze_right_side(stock_code: str) -> dict:
    """右侧交易综合分析 V2：多时间框架 + ADX环境 + 新指标 + Weinstein"""
    try:
        # 1. 获取日线+周线数据
        ohlcv = fetch_ohlcv(stock_code, 500)
        weekly_ohlcv = fetch_weekly_ohlcv(stock_code, 200)

        if not ohlcv or len(ohlcv) < 60:
            return {'error': f'无法获取{stock_code}的历史数据或数据不足', 'code': stock_code}

        dates = [d['date'] for d in ohlcv]
        opens = [d['open'] for d in ohlcv]
        highs = [d['high'] for d in ohlcv]
        lows = [d['low'] for d in ohlcv]
        closes = [d['close'] for d in ohlcv]
        volumes = [d['volume'] for d in ohlcv]

        # 2. ADX市场环境判断
        adx_data = compute_adx(highs, lows, closes)
        regime_info = detect_market_regime(adx_data['adx'], adx_data['plus_di'], adx_data['minus_di'])
        weights = get_dynamic_weights(regime_info['regime'])

        # 3. Weinstein阶段分析
        weinstein = detect_weinstein_stage(highs, lows, closes, volumes)

        # 4. 六维度检测
        ma_result = detect_ma_signals(closes, dates)
        macd_result = detect_macd_signals(closes, dates)
        vol_result = detect_volume_signals(volumes, closes)
        pattern_result = detect_pattern_signals(highs, lows, closes, volumes)
        rsi_kdj_result = detect_rsi_kdj_signals(closes, highs, lows)
        new_ind_result = detect_new_indicators_signals(closes, highs, lows, volumes)

        # 5. 动态权重转换为百分制
        def weighted_score(raw_score, raw_max, weight):
            if raw_max <= 0:
                return 0
            return round(raw_score / raw_max * weight, 1)

        total_score = (
            weighted_score(ma_result['score'], 25, weights['ma']) +
            weighted_score(macd_result['score'], 20, weights['macd']) +
            weighted_score(vol_result['score'], 20, weights['volume']) +
            weighted_score(pattern_result['score'], 30, weights['pattern']) +
            weighted_score(rsi_kdj_result['score'], 15, weights['rsi_kdj']) +
            weighted_score(new_ind_result['score'], new_ind_result['max'], weights['new_ind'])
        )

        # 6. 周线分析
        weekly_result = None
        weekly_score = 0
        weekly_verdict = '数据不足'
        if weekly_ohlcv and len(weekly_ohlcv) >= 60:
            w_dates = [d['date'] for d in weekly_ohlcv]
            w_highs = [d['high'] for d in weekly_ohlcv]
            w_lows = [d['low'] for d in weekly_ohlcv]
            w_closes = [d['close'] for d in weekly_ohlcv]
            w_volumes = [d['volume'] for d in weekly_ohlcv]

            w_ma = detect_ma_signals(w_closes, w_dates)
            w_macd = detect_macd_signals(w_closes, w_dates)
            w_vol = detect_volume_signals(w_volumes, w_closes)
            w_pattern = detect_pattern_signals(w_highs, w_lows, w_closes, w_volumes)
            w_rsi_kdj = detect_rsi_kdj_signals(w_closes, w_highs, w_lows)

            weekly_score = w_ma['score'] + w_macd['score'] + w_vol['score'] + w_pattern['score'] + w_rsi_kdj['score']
            weekly_result = {
                'ma': {'score': w_ma['score'], 'max': 25, 'signals': w_ma['signals'], 'detail': w_ma['detail']},
                'macd': {'score': w_macd['score'], 'max': 20, 'signals': w_macd['signals'], 'detail': w_macd['detail']},
                'volume': {'score': w_vol['score'], 'max': 20, 'signals': w_vol['signals'], 'detail': w_vol['detail']},
                'pattern': {'score': w_pattern['score'], 'max': 30, 'signals': w_pattern['signals'], 'detail': w_pattern['detail']},
                'rsi_kdj': {'score': w_rsi_kdj['score'], 'max': 15, 'signals': w_rsi_kdj['signals'], 'detail': w_rsi_kdj['detail']},
            }

            # 周线判定
            if weekly_score >= 75:
                weekly_verdict = '右侧确认'
            elif weekly_score >= 55:
                weekly_verdict = '疑似右侧'
            elif weekly_score >= 35:
                weekly_verdict = '非右侧'
            else:
                weekly_verdict = '左侧下跌'

        # 7. 多时间框架对齐
        current_verdict = '右侧确认' if total_score >= 75 else ('疑似右侧' if total_score >= 55 else ('非右侧' if total_score >= 35 else '左侧下跌'))
        tf_alignment = compute_timeframe_alignment(current_verdict, int(total_score), weekly_verdict, weekly_score)
        total_score += tf_alignment['alignment_score']
        total_score = min(100, total_score)

        # 8. 风险管理
        atr_val = compute_atr(highs, lows, closes)
        risk_mgmt = compute_risk_management(closes, highs, lows, atr_val)

        # 9. 假右侧检测
        rsi_vals = compute_rsi(closes)
        cur_rsi = rsi_vals[-1] if rsi_vals and rsi_vals[-1] is not None else None
        macd_raw = macd_result.get('macd_data', {})
        anti_fake = anti_fake_checks(ma_result, macd_result, vol_result, closes, cur_rsi, highs, lows, volumes, macd_raw)

        # 新增假右侧检查
        if regime_info['regime'] == 'ranging':
            anti_fake.append({
                'type': 'ranging_market',
                'severity': 'medium',
                'message': f"ADX={regime_info['adx_value']:.1f}<20，市场处于震荡状态，右侧信号可靠性较低",
            })

        if tf_alignment['conflict']:
            anti_fake.append({
                'type': 'timeframe_conflict',
                'severity': 'high',
                'message': '日线与周线趋势不一致，建议等待共振确认',
            })

        for sig in risk_mgmt.get('signals', []):
            anti_fake.append({
                'type': 'volatility_warning',
                'severity': 'medium',
                'message': sig,
            })

        # 10. 最终判定
        high_warnings = [w for w in anti_fake if w['severity'] == 'high']
        if total_score >= 75 and len(high_warnings) == 0:
            verdict = '右侧确认'
        elif total_score >= 55 and len(high_warnings) <= 1:
            verdict = '疑似右侧'
        elif total_score >= 35:
            verdict = '非右侧'
        else:
            verdict = '左侧下跌'

        # Weinstein Stage 4强制降级
        if weinstein['stage'] == 4 and verdict == '右侧确认':
            verdict = '疑似右侧'
            anti_fake.append({
                'type': 'weinstein_stage4',
                'severity': 'high',
                'message': f"Weinstein阶段分析: {weinstein['stage_name']}，已降级判定",
            })

        # 11. 构建图表数据
        cur = len(dates) - 1
        ma_data = ma_result.get('ma_data', {})
        macd_data = macd_result.get('macd_data', {})
        display_n = min(250, len(dates))
        start_idx = len(dates) - display_n

        kline = []
        for i in range(start_idx, len(dates)):
            kline.append([dates[i], opens[i], closes[i], lows[i], highs[i]])

        vol_display = []
        for i in range(start_idx, len(dates)):
            color = '#ef5350' if closes[i] >= (opens[i] if i == 0 else closes[i - 1]) else '#26a69a'
            vol_display.append({'date': dates[i], 'volume': volumes[i], 'color': color})

        # 新指标图表数据
        bb_data = compute_bollinger_bands(closes)
        obv_data = compute_obv(closes, volumes)
        cci_vals = compute_cci(highs, lows, closes)
        sar_data = compute_parabolic_sar(highs, lows)

        result = {
            'code': stock_code,
            'verdict': verdict,
            'score': round(total_score, 1),
            'dimensions': {
                'ma': {'score': ma_result['score'], 'max': 25, 'signals': ma_result['signals'], 'detail': ma_result['detail']},
                'macd': {'score': macd_result['score'], 'max': 20, 'signals': macd_result['signals'], 'detail': macd_result['detail']},
                'volume': {'score': vol_result['score'], 'max': 20, 'signals': vol_result['signals'], 'detail': vol_result['detail']},
                'pattern': {'score': pattern_result['score'], 'max': 30, 'signals': pattern_result['signals'], 'detail': pattern_result['detail']},
                'rsi_kdj': {'score': rsi_kdj_result['score'], 'max': 15, 'signals': rsi_kdj_result['signals'], 'detail': rsi_kdj_result['detail']},
                'new_indicators': {'score': new_ind_result['score'], 'max': new_ind_result['max'], 'signals': new_ind_result['signals'], 'detail': new_ind_result['detail']},
            },
            'anti_fake_checks': anti_fake,
            'market_regime': regime_info,
            'weinstein_stage': weinstein,
            'risk_management': risk_mgmt,
            'timeframe_alignment': tf_alignment,
            'weekly_dimensions': weekly_result,
            'weekly_score': weekly_score,
            'weekly_verdict': weekly_verdict,
            'dynamic_weights': weights,
            'chart_data': {
                'dates': dates[start_idx:],
                'kline': kline,
                'ma': {
                    'ma5': ma_data.get('ma5', [])[start_idx:],
                    'ma10': ma_data.get('ma10', [])[start_idx:],
                    'ma20': ma_data.get('ma20', [])[start_idx:],
                    'ma60': ma_data.get('ma60', [])[start_idx:],
                    'ma120': ma_data.get('ma120', [])[start_idx:],
                },
                'macd': {
                    'dif': macd_data.get('dif', [])[start_idx:],
                    'dea': macd_data.get('dea', [])[start_idx:],
                    'histogram': macd_data.get('histogram', [])[start_idx:],
                },
                'volume': vol_display,
                'bollinger': {
                    'upper': bb_data['upper'][start_idx:],
                    'middle': bb_data['middle'][start_idx:],
                    'lower': bb_data['lower'][start_idx:],
                },
                'adx': {
                    'adx': adx_data['adx'][start_idx:],
                    'plus_di': adx_data['plus_di'][start_idx:],
                    'minus_di': adx_data['minus_di'][start_idx:],
                },
                'cci': cci_vals[start_idx:],
                'obv': {
                    'obv': obv_data['obv'][start_idx:],
                    'obv_ma20': obv_data['obv_ma20'][start_idx:],
                },
                'sar': {
                    'sar': sar_data['sar'][start_idx:],
                    'is_long': sar_data['is_long'][start_idx:],
                },
            },
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        return result

    except Exception as e:
        logger.error(f"analyze_right_side failed for {stock_code}: {e}")
        return {'error': f'分析失败: {str(e)}', 'code': stock_code}


# ============================================================
# 6. 历史回测引擎
# ============================================================

@cached(ttl_seconds=600, key_prefix="right_side_backtest")
def backtest_right_side(stock_code: str) -> dict:
    """历史信号回测：统计过去'右侧确认'信号的后续收益"""
    try:
        ohlcv = fetch_ohlcv(stock_code, 500)
        if not ohlcv or len(ohlcv) < 250:
            return {'error': '数据不足，需要至少250个交易日', 'code': stock_code}

        dates = [d['date'] for d in ohlcv]
        highs = [d['high'] for d in ohlcv]
        lows = [d['low'] for d in ohlcv]
        closes = [d['close'] for d in ohlcv]
        volumes = [d['volume'] for d in ohlcv]
        n = len(closes)

        # 预计算所有指标数组
        ma5 = compute_ma(closes, 5)
        ma10 = compute_ma(closes, 10)
        ma20 = compute_ma(closes, 20)
        ma60 = compute_ma(closes, 60)
        ma120 = compute_ma(closes, 120)
        macd_data = compute_macd(closes)
        rsi_vals = compute_rsi(closes)
        kdj_vals = compute_kdj(highs, lows, closes)

        signals = []
        hold_days = [5, 10, 20, 60]

        # 每5天采样一次，从第200天到第N-60天
        for idx in range(200, n - 60, 5):
            # 简化评分：只计算核心指标
            score = 0

            # 均线评分（简化）
            if ma5[idx] and ma10[idx] and ma5[idx] > ma10[idx]:
                score += 3
            if ma10[idx] and ma20[idx] and ma10[idx] > ma20[idx]:
                score += 3
            if ma20[idx] and ma60[idx] and ma20[idx] > ma60[idx]:
                score += 3
            if ma60[idx] and closes[idx] > ma60[idx]:
                score += 3
            if ma120[idx] and closes[idx] > ma120[idx]:
                score += 3

            # MACD评分（简化）
            dif = macd_data['dif'][idx]
            dea = macd_data['dea'][idx]
            hist = macd_data['histogram'][idx]
            if dif is not None and dea is not None:
                if dif > dea:
                    score += 4
                    if dif > 0:
                        score += 3  # 零轴上方金叉额外加分
                if hist is not None and idx >= 1 and hist > 0 and macd_data['histogram'][idx - 1] <= 0:
                    score += 3

            # RSI评分
            if rsi_vals[idx] is not None:
                if 40 < rsi_vals[idx] < 70:
                    score += 3
                elif rsi_vals[idx] > 70:
                    score -= 2

            # 成交量评分
            if idx >= 20:
                vol_ma = sum(volumes[idx - 19:idx + 1]) / 20
                if vol_ma > 0 and volumes[idx] / vol_ma > 1.5:
                    score += 3

            # 判定
            if score >= 30:
                verdict = '右侧确认'
            elif score >= 20:
                verdict = '疑似右侧'
            else:
                continue  # 只记录有意义的信号

            # 计算后续收益
            price_at_signal = closes[idx]
            returns = {}
            for d in hold_days:
                if idx + d < n:
                    future_price = closes[idx + d]
                    returns[f'{d}d'] = round((future_price - price_at_signal) / price_at_signal * 100, 2)
                else:
                    returns[f'{d}d'] = None

            signals.append({
                'date': dates[idx],
                'score': score,
                'verdict': verdict,
                'price_at_signal': round(price_at_signal, 2),
                'returns': returns,
            })

        # 统计
        if not signals:
            return {
                'signals': [],
                'stats': {'total_signals': 0, 'win_rate_20d': 0, 'avg_return_20d': 0,
                          'max_return_20d': 0, 'min_return_20d': 0, 'sharpe_like': 0},
                'code': stock_code,
            }

        returns_20d = [s['returns']['20d'] for s in signals if s['returns']['20d'] is not None]
        if returns_20d:
            win_count = sum(1 for r in returns_20d if r > 0)
            avg_ret = sum(returns_20d) / len(returns_20d)
            std_ret = (sum((r - avg_ret) ** 2 for r in returns_20d) / len(returns_20d)) ** 0.5
            sharpe = round(avg_ret / std_ret, 2) if std_ret > 0 else 0
        else:
            win_count = 0
            avg_ret = 0
            sharpe = 0

        stats = {
            'total_signals': len(signals),
            'win_rate_20d': round(win_count / len(returns_20d) * 100, 1) if returns_20d else 0,
            'avg_return_20d': round(avg_ret, 2),
            'max_return_20d': round(max(returns_20d), 2) if returns_20d else 0,
            'min_return_20d': round(min(returns_20d), 2) if returns_20d else 0,
            'sharpe_like': sharpe,
        }

        return {
            'signals': signals[-20:],  # 最近20个信号
            'stats': stats,
            'code': stock_code,
        }

    except Exception as e:
        logger.error(f"backtest_right_side failed for {stock_code}: {e}")
        return {'error': f'回测失败: {str(e)}', 'code': stock_code}
