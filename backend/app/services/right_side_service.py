"""右侧交易判断服务 - 五维度评分系统 + 假右侧排除"""

import logging
import requests
from datetime import datetime, timedelta

from app.core.cache import get_cache, set_cache, cached
from app.core.utils import fetch_tencent_names

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


def _get_stock_name(stock_code: str) -> str:
    """通过腾讯行情接口获取股票名称（用于扫描结果展示，K线接口不带名称）"""
    if _is_hk_code(stock_code):
        symbol = f'hk{stock_code}'
    elif stock_code.startswith('6'):
        symbol = f'sh{stock_code}'
    else:
        symbol = f'sz{stock_code}'
    names = fetch_tencent_names([symbol], timeout=5)
    return names.get(symbol, stock_code)


def _quick_screen(code: str) -> bool:
    """快速预筛：用少量K线过滤明显左侧股，避免全量深度分析导致超时/限流。

    仅当价格站上MA20且近期未明显缩量时才进入完整 analyze_right_side。
    """
    try:
        ohlcv = fetch_ohlcv(code, 60)
        if len(ohlcv) < 20:
            return False
        closes = [d['close'] for d in ohlcv]
        vols = [d['volume'] for d in ohlcv]
        price = closes[-1]
        ma20 = sum(closes[-20:]) / 20
        if price < ma20:
            return False
        recent_vol = sum(vols[-5:]) / 5
        base_vol = sum(vols[-20:]) / 20
        if base_vol > 0 and recent_vol < base_vol * 0.8:
            return False
        return True
    except Exception:
        return False


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

    verdict_rank = {'右侧确认': 3, '疑似右侧': 2, '观望等待': 2, '非右侧': 1, '左侧下跌': 0}
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
    n = len(values)
    if n < period:
        return [None] * n
    k = 2.0 / (period + 1)
    ema = [None] * n
    ema[period - 1] = sum(values[:period]) / period
    for i in range(period, n):
        ema[i] = values[i] * k + ema[i - 1] * (1 - k)
    return ema


def compute_macd(closes: list, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    """MACD: DIF/DEA/柱状图"""
    n = len(closes)
    ema_fast = compute_ema(closes, fast)
    ema_slow = compute_ema(closes, slow)
    # DIF: only valid from index slow-1 (where both EMAs exist)
    dif = [None] * n
    for i in range(slow - 1, n):
        dif[i] = ema_fast[i] - ema_slow[i]
    # DEA = EMA of DIF; feed 0.0 for None slots so EMA can compute, then mask invalids
    dif_for_ema = [v if v is not None else 0.0 for v in dif]
    dea_raw = compute_ema(dif_for_ema, signal)
    dea_start = slow + signal - 2  # first index where DEA is truly valid
    dea = [None if i < dea_start else dea_raw[i] for i in range(n)]
    histogram = [None] * n
    for i in range(n):
        if dif[i] is not None and dea[i] is not None:
            histogram[i] = round((dif[i] - dea[i]) * 2, 4)
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
        result.append(round(100.0 - 100.0 / (1 + avg_gain / avg_loss), 2))
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


def compute_kama(closes: list, period: int = 10, fast_period: int = 2, slow_period: int = 30) -> list:
    """Kaufman自适应均线 (Perry Kaufman)
    效率比率(ER)自动适应市场噪声：趋势市快速响应，震荡市减少假信号
    """
    n = len(closes)
    if n < period + 1:
        return [None] * n
    fast_sc = 2.0 / (fast_period + 1)
    slow_sc = 2.0 / (slow_period + 1)
    kama = [None] * n
    kama[period] = closes[period]  # 初始化为第一个可用值
    for i in range(period + 1, n):
        direction = abs(closes[i] - closes[i - period])
        volatility = sum(abs(closes[j] - closes[j - 1]) for j in range(i - period + 1, i + 1))
        er = direction / volatility if volatility > 0 else 0
        sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2
        kama[i] = kama[i - 1] + sc * (closes[i] - kama[i - 1])
    return kama


def compute_kst(closes: list) -> dict:
    """KST指标 (Martin Pring) — 多周期动量综合
    KST = RCMA1×1 + RCMA2×2 + RCMA3×3 + RCMA4×4
    RCMA1 = ROC(10)的10日SMA, RCMA2 = ROC(15)的10日SMA,
    RCMA3 = ROC(20)的10日SMA, RCMA4 = ROC(30)的15日SMA
    """
    n = len(closes)
    if n < 45:
        return {'kst': [None] * n, 'signal': [None] * n}

    def roc(values, period):
        result = [None] * len(values)
        for i in range(period, len(values)):
            if values[i - period] != 0:
                result[i] = (values[i] - values[i - period]) / values[i - period] * 100
            else:
                result[i] = 0
        return result

    def sma(values, period):
        result = [None] * len(values)
        for i in range(period - 1, len(values)):
            window = [v for v in values[i - period + 1:i + 1] if v is not None]
            if len(window) == period:
                result[i] = sum(window) / period
        return result

    roc10 = roc(closes, 10)
    roc15 = roc(closes, 15)
    roc20 = roc(closes, 20)
    roc30 = roc(closes, 30)
    rcma1 = sma(roc10, 10)
    rcma2 = sma(roc15, 10)
    rcma3 = sma(roc20, 10)
    rcma4 = sma(roc30, 15)

    kst = [None] * n
    for i in range(n):
        vals = [rcma1[i], rcma2[i], rcma3[i], rcma4[i]]
        if all(v is not None for v in vals):
            kst[i] = vals[0] * 1 + vals[1] * 2 + vals[2] * 3 + vals[3] * 4

    # KST信号线 = 9日SMA
    signal = sma(kst, 9)
    return {'kst': kst, 'signal': signal}


def compute_williams_r(highs: list, lows: list, closes: list, period: int = 14) -> list:
    """Williams %R指标 (Larry Williams)
    %R = (最高价 - 收盘价) / (最高价 - 最低价) × (-100)
    范围：-100 到 0，<-80超买，>-20超卖
    """
    n = len(closes)
    result = [None] * n
    for i in range(period - 1, n):
        hh = max(highs[i - period + 1:i + 1])
        ll = min(lows[i - period + 1:i + 1])
        if hh != ll:
            result[i] = round((hh - closes[i]) / (hh - ll) * (-100), 2)
        else:
            result[i] = -50.0
    return result


def compute_td_sequential(closes: list, highs: list, lows: list) -> dict:
    """DeMark TD序列 (Tom DeMark) — 趋势衰竭计数系统
    TD Setup: 连续9根K线收盘价高于/低于4根前的收盘价
    TD Countdown: 13根K线计数确认
    """
    n = len(closes)
    setup = [0] * n      # 正数=卖出setup计数, 负数=买入setup计数
    countdown = [0] * n  # 正数=卖出countdown, 负数=买入countdown
    tdst_support = [None] * n
    tdst_resistance = [None] * n

    # TD Setup
    sell_count = 0
    buy_count = 0
    for i in range(4, n):
        if closes[i] > closes[i - 4]:
            sell_count += 1
            buy_count = 0
        elif closes[i] < closes[i - 4]:
            buy_count += 1
            sell_count = 0
        else:
            sell_count = 0
            buy_count = 0
        setup[i] = sell_count if sell_count > 0 else -buy_count

    # TDST (Setup的极值)
    for i in range(4, n):
        if setup[i] >= 9:
            # 卖出Setup完成，记录最高价为阻力
            tdst_resistance[i] = max(highs[max(0, i - 8):i + 1])
        elif setup[i] <= -9:
            # 买入Setup完成，记录最低价为支撑
            tdst_support[i] = min(lows[max(0, i - 8):i + 1])

    # TD Countdown (简化版：在Setup完成后开始13根计数)
    sell_cd_count = 0
    buy_cd_count = 0
    sell_cd_active = False
    buy_cd_active = False
    for i in range(4, n):
        if setup[i] >= 9:
            sell_cd_active = True
            sell_cd_count = 0
        elif setup[i] <= -9:
            buy_cd_active = True
            buy_cd_count = 0

        if sell_cd_active and i >= 2:
            if closes[i] >= highs[max(0, i - 2)]:
                sell_cd_count += 1
            if sell_cd_count >= 13:
                countdown[i] = 13
                sell_cd_active = False
                sell_cd_count = 0

        if buy_cd_active and i >= 2:
            if closes[i] <= lows[max(0, i - 2)]:
                buy_cd_count += 1
            if buy_cd_count >= 13:
                countdown[i] = -13
                buy_cd_active = False
                buy_cd_count = 0

    return {'setup': setup, 'countdown': countdown,
            'tdst_support': tdst_support, 'tdst_resistance': tdst_resistance}


def compute_roc(closes: list, period: int) -> list:
    """ROC: Rate of Change 变动率"""
    n = len(closes)
    result = [None] * n
    for i in range(period, n):
        if closes[i - period] != 0:
            result[i] = round((closes[i] - closes[i - period]) / closes[i - period] * 100, 2)
        else:
            result[i] = 0
    return result


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
    """根据市场环境返回动态权重（九维度，总和100）"""
    if regime == 'trending':
        # 趋势市：均线/MACD/自适应趋势权重高
        return {'ma': 20, 'macd': 15, 'volume': 14, 'pattern': 12,
                'rsi_kdj': 5, 'new_ind': 8, 'momentum': 10, 'adaptive_trend': 10, 'td': 6}
    elif regime == 'developing':
        # 发展中：均衡分配
        return {'ma': 18, 'macd': 14, 'volume': 14, 'pattern': 14,
                'rsi_kdj': 7, 'new_ind': 8, 'momentum': 10, 'adaptive_trend': 8, 'td': 7}
    else:  # ranging
        # 震荡市：形态/RSI/动量权重高，均线/自适应趋势权重低
        return {'ma': 10, 'macd': 10, 'volume': 12, 'pattern': 18,
                'rsi_kdj': 14, 'new_ind': 14, 'momentum': 10, 'adaptive_trend': 4, 'td': 8}


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


def detect_flag_pattern(highs: list, lows: list, closes: list, volumes: list) -> dict:
    """旗形/三角旗形形态检测 (Dan Zanger)
    旗杆：快速上涨25%+，旗面：小幅回调10-40%，突破：放量突破旗面上轨
    """
    n = len(closes)
    cur = n - 1
    score = 0
    signals = []

    if cur < 60:
        return {'score': 0, 'signals': [], 'found': False, 'flag_type': 'none'}

    # 找旗杆：过去60日内连续10天以上涨幅超30%
    best_flagpole = 0
    flagpole_start = -1
    flagpole_end = -1
    for start in range(max(0, cur - 50), cur - 10):
        for end in range(start + 10, min(start + 30, cur)):
            gain = (closes[end] - closes[start]) / closes[start] * 100
            if gain > best_flagpole and gain >= 25:
                best_flagpole = gain
                flagpole_start = start
                flagpole_end = end

    if flagpole_start < 0:
        return {'score': 0, 'signals': [], 'found': False, 'flag_type': 'none'}

    # 找旗面：旗杆后的回调
    flag_high = max(highs[flagpole_end:min(flagpole_end + 20, cur + 1)])
    flag_low = min(lows[flagpole_end:min(flagpole_end + 20, cur + 1)])
    flag_range = (flag_high - flag_low) / flag_high * 100 if flag_high > 0 else 0
    flagpole_height = closes[flagpole_end] - closes[flagpole_start]
    flag_depth = (closes[flagpole_end] - flag_low) / flagpole_height * 100 if flagpole_height > 0 else 0

    # 旗形条件：回调幅度15-35%，旗面振幅合理
    if 10 < flag_depth < 40 and flag_range < 15:
        # 检查是否突破旗面上轨
        neckline = flag_high
        if closes[cur] > neckline:
            # 检查突破日成交量
            vol_ma = sum(volumes[max(0, cur - 19):cur + 1]) / min(20, cur + 1)
            vol_ratio = volumes[cur] / vol_ma if vol_ma > 0 else 1
            if vol_ratio > 1.5:
                score = 7
                signals.append(f"旗形突破确认：旗杆涨幅{best_flagpole:.0f}%，旗面回调{flag_depth:.0f}%，放量突破")
            else:
                score = 4
                signals.append(f"旗形突破但量能不足：旗杆{best_flagpole:.0f}%，旗面{flag_depth:.0f}%")
        else:
            score = 2
            signals.append(f"旗形形成中：旗杆涨幅{best_flagpole:.0f}%，待突破{neckline:.2f}")

    # 三角旗形：旗面呈收敛状
    if flagpole_end >= 0 and cur - flagpole_end >= 5:
        recent_highs = highs[flagpole_end:min(flagpole_end + 15, cur + 1)]
        recent_lows = lows[flagpole_end:min(flagpole_end + 15, cur + 1)]
        if len(recent_highs) >= 3:
            highs_decreasing = all(recent_highs[i] <= recent_highs[i - 1] * 1.01 for i in range(1, len(recent_highs)))
            lows_increasing = all(recent_lows[i] >= recent_lows[i - 1] * 0.99 for i in range(1, len(recent_lows)))
            if highs_decreasing and lows_increasing and closes[cur] > recent_highs[-1]:
                score = max(score, 6)
                signals.append("三角旗形收敛突破")

    return {
        'score': score,
        'signals': signals,
        'found': score > 0,
        'flag_type': 'triangle_flag' if '三角旗形' in ' '.join(signals) else ('flag' if score > 0 else 'none'),
    }


def detect_sepa_template(closes: list, highs: list, lows: list) -> dict:
    """Minervini SEPA趋势模板 — 8个条件全部满足才得分
    用于筛选处于Stage 2上升趋势的强势股
    """
    n = len(closes)
    cur = n - 1
    signals = []
    details = []

    if cur < 200:
        return {'score': 0, 'conditions_met': 0, 'signals': ['数据不足(需200+交易日)'], 'details': []}

    ma50 = compute_ma(closes, 50)
    ma150 = compute_ma(closes, 150)
    ma200 = compute_ma(closes, 200)

    if not all([ma50[cur], ma150[cur], ma200[cur]]):
        return {'score': 0, 'conditions_met': 0, 'signals': ['均线数据不足'], 'details': []}

    price = closes[cur]
    conditions = []

    # 1. 股价 > 150日均线 > 200日均线
    c1 = price > ma150[cur] > ma200[cur]
    conditions.append(('股价>MA150>MA200', c1))

    # 2. 150日均线 > 200日均线
    c2 = ma150[cur] > ma200[cur]
    conditions.append(('MA150>MA200', c2))

    # 3. 200日均线至少上升1个月(20个交易日)
    c3 = ma200[cur] > ma200[max(0, cur - 20)] if ma200[max(0, cur - 20)] else False
    conditions.append(('MA200上升趋势', c3))

    # 4. 50日均线 > 150日均线 > 200日均线
    c4 = ma50[cur] > ma150[cur] > ma200[cur]
    conditions.append(('MA50>MA150>MA200', c4))

    # 5. 股价 > 50日均线
    c5 = price > ma50[cur]
    conditions.append(('股价>MA50', c5))

    # 6. 股价比52周低点至少高25%
    low_52w = min(lows[max(0, cur - 250):cur + 1])
    c6 = (price - low_52w) / low_52w * 100 >= 25 if low_52w > 0 else False
    conditions.append((f'距52周低点+{(price - low_52w) / low_52w * 100:.0f}%', c6))

    # 7. 股价距离52周高点不超过25%
    high_52w = max(highs[max(0, cur - 250):cur + 1])
    dist_from_high = (high_52w - price) / high_52w * 100
    c7 = dist_from_high <= 25
    conditions.append((f'距52周高点-{dist_from_high:.0f}%', c7))

    # 8. 相对强度(简化：使用近50日涨幅 vs 近200日涨幅的加权)
    if cur >= 200:
        ret_50 = (price - closes[cur - 50]) / closes[cur - 50] * 100
        ret_200 = (price - closes[cur - 200]) / closes[cur - 200] * 100
        rs_score = ret_50 * 0.4 + ret_200 * 0.6
        c8 = rs_score >= 0  # 简化：正收益即达标
        conditions.append((f'相对强度={rs_score:.1f}', c8))
    else:
        c8 = False
        conditions.append(('相对强度:数据不足', False))

    met = sum(1 for _, ok in conditions if ok)
    for name, ok in conditions:
        details.append({'condition': name, 'met': ok})

    # 评分：满足条件越多得分越高
    score_map = {8: 10, 7: 8, 6: 6, 5: 4, 4: 2}
    score = score_map.get(met, max(0, met - 3))

    if met >= 7:
        signals.append(f"SEPA模板高度满足({met}/8)，强势趋势确认")
    elif met >= 5:
        signals.append(f"SEPA模板部分满足({met}/8)，趋势发展中")
    else:
        signals.append(f"SEPA模板仅满足{met}/8，趋势尚未形成")

    return {
        'score': score,
        'conditions_met': met,
        'signals': signals,
        'details': details,
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

    # R-multiple目标位（让利润奔跑）
    r_targets = {
        '1R': round(price + 1.0 * atr_value, 2),
        '2R': round(price + 2.0 * atr_value, 2),
        '3R': round(price + 3.0 * atr_value, 2),
        '5R': round(price + 5.0 * atr_value, 2),
    }

    # 自适应移动止损 (Trailing Stop)
    trailing_stop = {
        'tight': round(price - 1.5 * atr_value, 2),
        'normal': round(price - 2.5 * atr_value, 2),
        'breakeven_trigger': round(price + 1.0 * atr_value, 2),
    }

    # 移动止损阶梯 (基于盈利百分比)
    trailing_ladder = {
        'profit_5pct': {'action': 'move_stop_to_breakeven', 'stop': round(price, 2)},
        'profit_10pct': {'action': 'lock_5pct_profit', 'stop': round(price * 1.05, 2)},
        'profit_20pct': {'action': 'lock_10pct_profit', 'stop': round(price * 1.10, 2)},
        'profit_30pct': {'action': 'lock_15pct + tighten_1.5ATR', 'stop': round(price * 1.15, 2)},
    }

    return {
        'atr': round(atr_value, 4),
        'atr_pct': round(atr_pct, 2),
        'volatility_level': vol_level,
        'stop_loss': stop_loss,
        'position_sizing': position_sizing,
        'risk_reward': risk_reward,
        'r_targets': r_targets,
        'trailing_stop': trailing_stop,
        'trailing_ladder': trailing_ladder,
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
        if (dif[i - 1] is not None and dea[i - 1] is not None and dif[i] is not None and dea[i] is not None and
                dif[i - 1] <= dea[i - 1] and dif[i] > dea[i]):
            golden_cross_at = i
            break
    if golden_cross_at is not None:
        cross_score = 4
        # 零轴附近或以上金叉加分
        if dif[golden_cross_at] >= 0:
            cross_score += 2
            signals.append("MACD零轴上方金叉（强信号）")
        else:
            dif_60 = [v for v in dif[max(0, cur - 59):cur + 1] if v is not None]
            if dif_60 and abs(dif[golden_cross_at]) < abs(max(dif_60) - min(dif_60)) * 0.1:
                cross_score += 1
                signals.append("MACD零轴附近金叉")
            else:
                signals.append("MACD零轴下方金叉")
        score += cross_score

    # 2. 柱状图由负转正（0-4分）
    if cur >= 1 and hist[cur] is not None and hist[cur] > 0 and hist[cur - 1] is not None and hist[cur - 1] <= 0:
        score += 4
        signals.append("MACD柱状图由负转正")
    elif cur >= 2 and hist[cur] is not None and hist[cur] > 0 and hist[cur - 1] is not None and hist[cur - 1] > 0 and hist[cur - 2] is not None and hist[cur - 2] <= 0:
        score += 2
        signals.append("MACD柱状图连续为正")

    # 3. 底背离检测（0-6分）
    divergence = _detect_bottom_divergence(closes, dif)
    if divergence['confirmed']:
        score += 6
        signals.append("MACD底背离确认（强信号）")

    # 4. DIF趋势向上（0-4分）
    if cur >= 5 and dif[cur] is not None and dif[cur - 5] is not None:
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
        if recent_closes[i] == min(window) and recent_dif[i] is not None:
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

    # 3. RSI超买惩罚（-4分，>80深度超买额外-2分）
    if cur_rsi is not None and cur_rsi > 80:
        score -= 6
        signals.append(f"RSI深度超买({cur_rsi:.0f}>)，追高风险极大")
    elif cur_rsi is not None and cur_rsi > 70:
        score -= 4
        signals.append(f"RSI超买({cur_rsi:.0f})，注意短期回调风险")

    score = max(0, min(15, score))
    return {
        'score': score,
        'signals': signals,
        'detail': f"RSI/KDJ得分 {score}/15",
    }


def detect_momentum_signals(closes: list, highs: list, lows: list, volumes: list) -> dict:
    """动量综合评分（满分20）— 融合Pring KST + Williams %R + ROC多周期
    来源：Martin Pring (KST), Larry Williams (%R), 多周期动量确认
    """
    score = 0
    signals = []
    cur = len(closes) - 1

    if cur < 45:
        return {'score': 0, 'signals': ['数据不足'], 'detail': '动量数据不足', 'max': 20}

    # 1. KST上穿信号线 (0-6分)
    kst_data = compute_kst(closes)
    kst_val = kst_data['kst'][cur]
    sig_val = kst_data['signal'][cur]
    if kst_val is not None and sig_val is not None:
        if kst_val > sig_val:
            # KST在信号线上方
            if cur >= 2 and kst_data['kst'][cur - 1] is not None and kst_data['signal'][cur - 1] is not None:
                if kst_data['kst'][cur - 1] <= kst_data['signal'][cur - 1]:
                    score += 6
                    signals.append(f"KST上穿信号线（金叉），动量转强")
                else:
                    score += 4
                    signals.append(f"KST在信号线上方，动量持续")
            else:
                score += 3
        elif kst_val < sig_val * 0.8:
            signals.append("KST在信号线下方，动量偏弱")

    # 2. Williams %R从超卖回升 (0-4分)
    wr = compute_williams_r(highs, lows, closes)
    wr_val = wr[cur] if cur < len(wr) else None
    if wr_val is not None:
        min_wr_20 = min((v for v in wr[max(0, cur - 19):cur + 1] if v is not None), default=-50)
        if min_wr_20 < -80 and wr_val > -50:
            score += 4
            signals.append(f"Williams %R从超卖区({min_wr_20:.0f})回升至{wr_val:.0f}")
        elif min_wr_20 < -70 and wr_val > -40:
            score += 2
            signals.append(f"Williams %R从低位({min_wr_20:.0f})回升")
        elif wr_val > -20:
            signals.append(f"Williams %R={wr_val:.0f}进入超买区，注意回调风险")

    # 3. 多周期ROC方向一致 (0-6分)
    roc10 = compute_roc(closes, 10)
    roc20 = compute_roc(closes, 20)
    roc40 = compute_roc(closes, 40)
    r10 = roc10[cur] if cur < len(roc10) and roc10[cur] is not None else None
    r20 = roc20[cur] if cur < len(roc20) and roc20[cur] is not None else None
    r40 = roc40[cur] if cur < len(roc40) and roc40[cur] is not None else None
    if r10 is not None and r20 is not None and r40 is not None:
        if r10 > 0 and r20 > 0 and r40 > 0:
            score += 6
            signals.append(f"三周期ROC全部为正(10d:{r10:.1f}%,20d:{r20:.1f}%,40d:{r40:.1f}%)，动量共振")
        elif r10 > 0 and r20 > 0:
            score += 3
            signals.append(f"短期+中期ROC为正，动量偏多")
        elif r10 < 0 and r20 < 0 and r40 < 0:
            signals.append("三周期ROC全部为负，动量偏空")

    # 4. 动量背离检测 (0-4分)
    if cur >= 60 and kst_val is not None:
        # 价格创新高但KST未创新高 → 顶背离警告
        price_high_30 = max(closes[cur - 30:cur + 1])
        kst_30 = [kst_data['kst'][i] for i in range(max(0, cur - 30), cur + 1) if kst_data['kst'][i] is not None]
        if kst_30 and closes[cur] >= price_high_30 * 0.99:
            max_kst_30 = max(kst_30)
            if kst_val < max_kst_30 * 0.8:
                score -= 2
                signals.append("KST顶背离：价格接近高位但动量减弱")
        # 价格创新低但KST未创新低 → 底背离
        price_low_30 = min(closes[cur - 30:cur + 1])
        min_kst_30 = min(kst_30) if kst_30 else 0
        if closes[cur] <= price_low_30 * 1.01 and kst_val > min_kst_30 * 1.2:
            score += 4
            signals.append("KST底背离：价格低位但动量回升")

    score = max(0, min(20, score))
    return {
        'score': score,
        'signals': signals,
        'detail': f"动量综合得分 {score}/20",
        'max': 20,
        'kst_data': kst_data,
        'williams_r': wr,
    }


def detect_adaptive_trend_signals(closes: list, highs: list, lows: list,
                                   weekly_closes: list = None) -> dict:
    """自适应趋势评分（满分15）— 融合KAMA + Elder三重滤网
    来源：Perry Kaufman (KAMA), Alexander Elder (Triple Screen)
    """
    score = 0
    signals = []
    cur = len(closes) - 1

    if cur < 30:
        return {'score': 0, 'signals': ['数据不足'], 'detail': '自适应趋势数据不足', 'max': 15}

    # 1. KAMA趋势方向 (0-5分)
    kama = compute_kama(closes, period=10)
    kama_val = kama[cur]
    if kama_val is not None:
        price = closes[cur]
        kama_pct = (price - kama_val) / kama_val * 100
        if price > kama_val:
            # KAMA斜率
            if cur >= 5 and kama[cur - 5] is not None:
                kama_slope = (kama_val - kama[cur - 5]) / kama[cur - 5] * 100
                if kama_slope > 1:
                    score += 5
                    signals.append(f"KAMA上升趋势({kama_slope:.1f}%)，自适应均线确认")
                elif kama_slope > 0:
                    score += 3
                    signals.append(f"KAMA温和上升，价格在KAMA上方{kama_pct:.1f}%")
                else:
                    score += 1
                    signals.append("KAMA走平，价格勉强在上方")
            else:
                score += 2
        else:
            signals.append(f"价格在KAMA下方{kama_pct:.1f}%，自适应趋势偏空")

    # 2. KAMA自适应效率 (0-3分)
    if cur >= 20 and kama_val is not None:
        # 计算效率比率
        direction = abs(closes[cur] - closes[cur - 10])
        volatility = sum(abs(closes[j] - closes[j - 1]) for j in range(cur - 9, cur + 1))
        er = direction / volatility if volatility > 0 else 0
        if er > 0.5:
            score += 3
            signals.append(f"效率比率={er:.2f}，市场趋势清晰")
        elif er > 0.3:
            score += 1
            signals.append(f"效率比率={er:.2f}，趋势中等")

    # 3. 三重滤网确认 (0-7分) — Elder Triple Screen
    # 第一重：周线MACD方向（使用周线数据或近5日模拟）
    weekly_macd_ok = False
    if weekly_closes and len(weekly_closes) >= 30:
        w_macd = compute_macd(weekly_closes)
        w_cur = len(weekly_closes) - 1
        if w_macd['histogram'][w_cur] is not None:
            if w_macd['histogram'][w_cur] > 0:
                weekly_macd_ok = True
                score += 3
                signals.append("三重滤网①：周线MACD柱状图为正")
            else:
                signals.append("三重滤网①：周线MACD柱状图为负（周线趋势偏空）")
    else:
        # 使用日线MACD模拟
        macd = compute_macd(closes)
        if macd['histogram'][cur] is not None and macd['histogram'][cur] > 0:
            weekly_macd_ok = True
            score += 2
            signals.append("三重滤网①：日线MACD柱状图为正（周线数据不足）")

    # 第二重：日线振荡指标超卖回升
    rsi = compute_rsi(closes)
    rsi_val = rsi[cur] if cur < len(rsi) and rsi[cur] is not None else None
    if rsi_val is not None and weekly_macd_ok:
        min_rsi_10 = min((v for v in rsi[max(0, cur - 9):cur + 1] if v is not None), default=50)
        if min_rsi_10 < 40 and rsi_val > 45:
            score += 2
            signals.append(f"三重滤网②：RSI从{min_rsi_10:.0f}回升至{rsi_val:.0f}")
        elif 40 < rsi_val < 65:
            score += 1
            signals.append(f"三重滤网②：RSI={rsi_val:.0f}处于中性偏多")

    # 第三重：入场突破信号
    if cur >= 5:
        recent_high = max(highs[cur - 5:cur])
        if closes[cur] > recent_high:
            score += 2
            signals.append(f"三重滤网③：突破近5日高点({recent_high:.2f})")

    score = max(0, min(15, score))
    return {
        'score': score,
        'signals': signals,
        'detail': f"自适应趋势得分 {score}/15",
        'max': 15,
        'kama_data': kama,
    }


def detect_td_signals(closes: list, highs: list, lows: list) -> dict:
    """DeMark TD序列评分（满分10）
    来源：Tom DeMark — 趋势衰竭计数系统
    注意：在右侧交易中，TD卖出信号作为风险警告，TD买入信号作为趋势确认
    """
    score = 0
    signals = []
    cur = len(closes) - 1

    if cur < 20:
        return {'score': 0, 'signals': ['数据不足'], 'detail': 'TD序列数据不足', 'max': 10}

    td = compute_td_sequential(closes, highs, lows)

    setup_val = td['setup'][cur]
    countdown_val = td['countdown'][cur]

    # 买入Setup完成（连续9根收盘低于4根前）→ 底部信号
    if setup_val <= -9:
        score += 4
        signals.append(f"TD买入Setup完成({abs(setup_val)}根)，底部衰竭信号")

    # 卖出Setup完成（连续9根收盘高于4根前）→ 顶部警告
    if setup_val >= 9:
        score -= 3
        signals.append(f"TD卖出Setup完成({setup_val}根)，顶部衰竭警告")

    # 买入Countdown完成（13根计数）→ 强底部信号
    if countdown_val <= -13:
        score += 6
        signals.append("TD买入Countdown完成(13根)，强底部反转信号")

    # 卖出Countdown完成 → 强顶部警告
    if countdown_val >= 13:
        score -= 4
        signals.append("TD卖出Countdown完成(13根)，强顶部反转警告")

    # TDST支撑/阻力
    if td['tdst_support'][cur] is not None:
        dist = (closes[cur] - td['tdst_support'][cur]) / closes[cur] * 100
        if 0 < dist < 5:
            score += 2
            signals.append(f"价格接近TDST支撑位({td['tdst_support'][cur]:.2f})")

    if td['tdst_resistance'][cur] is not None:
        dist = (td['tdst_resistance'][cur] - closes[cur]) / closes[cur] * 100
        if 0 < dist < 3:
            score -= 2
            signals.append(f"价格接近TDST阻力位({td['tdst_resistance'][cur]:.2f})")

    score = max(0, min(10, score))
    return {
        'score': score,
        'signals': signals,
        'detail': f"TD序列得分 {score}/10",
        'max': 10,
        'td_data': td,
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
            dif_60_valid = [d for d in dif_list[max(0, cur - 60):cur + 1] if d is not None]
            dif_30_valid = [d for d in dif_list[max(0, cur - 30):cur + 1] if d is not None]
            dif_at_60_high = max(dif_60_valid) if dif_60_valid else None
            dif_at_30_high = max(dif_30_valid) if dif_30_valid else None
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

    # 12. RSI超买（强趋势中RSI可持续60-80，>80才触发警告）
    if rsi_val is not None and rsi_val > 80:
        warnings.append({
            'type': 'rsi_overbought',
            'severity': 'high',
            'message': f'RSI={rsi_val:.0f}已深度超买(>80)，追高风险极大',
        })
    elif rsi_val is not None and rsi_val > 70:
        warnings.append({
            'type': 'rsi_overbought',
            'severity': 'medium',
            'message': f'RSI={rsi_val:.0f}进入超买区(>70)，注意短期回调风险',
        })

    return warnings


# ============================================================
# 4b. 大师级三层过滤器 + 精确入场
# ============================================================

def fetch_index_klines(index_code: str = '000001', days: int = 120) -> list[dict]:
    """获取大盘指数K线（上证指数默认）"""
    cache_key = f"index_klines_{index_code}_{days}"
    cached_data = get_cache(cache_key, 600)
    if cached_data:
        return cached_data
    try:
        url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get'
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=int(days * 1.6))).strftime('%Y-%m-%d')
        params = {'param': f'sh{index_code},day,{start_date},{end_date},{days + 10},qfq'}
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        if 'data' in data and f'sh{index_code}' in data['data']:
            klines = data['data'][f'sh{index_code}']
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
        logger.error(f"fetch_index_klines failed for {index_code}: {e}")
    return []


def detect_market_timing() -> dict:
    """大盘择时判断（O'Neil M=Market + Weinstein Stage）
    大盘下跌时一票否决，不做多。
    """
    idx_data = fetch_index_klines('000001', 120)
    if not idx_data or len(idx_data) < 60:
        return {'status': 'unknown', 'signal': 'caution', 'reason': '大盘数据不足',
                'index_close': 0, 'index_ma60': 0, 'index_ma60_slope': 0}

    closes = [d['close'] for d in idx_data]
    cur = len(closes) - 1
    ma60 = compute_ma(closes, 60)
    ma20 = compute_ma(closes, 20)

    idx_close = closes[cur]
    idx_ma60 = ma60[cur] if ma60[cur] else idx_close
    idx_ma20 = ma20[cur] if ma20[cur] else idx_close

    # MA60斜率（过去20日）
    slope = 0
    if cur >= 20 and ma60[cur - 20] and ma60[cur - 20] > 0:
        slope = (idx_ma60 - ma60[cur - 20]) / ma60[cur - 20] * 100

    price_vs_ma60 = (idx_close - idx_ma60) / idx_ma60 * 100 if idx_ma60 > 0 else 0

    if idx_close > idx_ma60 and slope > 0:
        status = 'bull'
        signal = 'go'
        reason = f'上证指数({idx_close:.0f})站上MA60({idx_ma60:.0f})且均线向上({slope:+.1f}%)，牛市环境'
    elif idx_close > idx_ma60 and slope >= -0.5:
        status = 'neutral'
        signal = 'caution'
        reason = f'上证指数在MA60上方但均线走平({slope:+.1f}%)，趋势不明'
    elif idx_close > idx_ma20 and idx_close <= idx_ma60:
        status = 'neutral'
        signal = 'caution'
        reason = f'上证指数在MA20上方但MA60下方，反弹中需确认'
    else:
        status = 'bear'
        signal = 'no_trade'
        reason = f'上证指数({idx_close:.0f})低于MA60({idx_ma60:.0f})，熊市环境，不宜做多'

    return {
        'status': status,
        'signal': signal,
        'reason': reason,
        'index_close': round(idx_close, 2),
        'index_ma60': round(idx_ma60, 2),
        'index_ma20': round(idx_ma20, 2),
        'index_ma60_slope': round(slope, 2),
        'price_vs_ma60': round(price_vs_ma60, 2),
    }


def detect_sector_strength(stock_code: str) -> dict:
    """行业相对强度判断（Livermore: 只买领涨行业的领涨股）
    复用 akshare_service 获取行业排名
    """
    try:
        from app.services.akshare_service import AKShareService
        svc = AKShareService()
        sectors = svc.get_industry_rank()
        if not sectors:
            return {'sector_name': '未知', 'sector_rank': 99, 'sector_signal': 'neutral',
                    'reason': '行业数据获取失败', 'sector_change_pct': 0}

        # 尝试匹配股票所属行业（简化：通过股票代码推断市场，取行业前20）
        # 实际上这里返回的是行业排名列表，不是个股所属行业
        # 我们用行业整体表现来判断市场热度
        top_sectors = sectors[:5]
        bottom_sectors = sectors[-5:] if len(sectors) > 5 else []

        avg_top_change = sum(s.get('change_pct', 0) for s in top_sectors) / len(top_sectors) if top_sectors else 0
        avg_all_change = sum(s.get('change_pct', 0) for s in sectors) / len(sectors) if sectors else 0

        if avg_top_change > 1:
            signal = 'strong'
            reason = f'领涨行业平均涨幅{avg_top_change:.1f}%，市场热点活跃'
        elif avg_all_change > 0:
            signal = 'neutral'
            reason = f'行业平均涨幅{avg_all_change:.1f}%，市场温和'
        else:
            signal = 'weak'
            reason = f'行业平均涨幅{avg_all_change:.1f}%，市场偏冷'

        return {
            'sector_name': '全市场行业',
            'sector_rank': 0,
            'sector_signal': signal,
            'reason': reason,
            'sector_change_pct': round(avg_all_change, 2),
            'top_sector': top_sectors[0].get('name', '') if top_sectors else '',
            'top_sector_change': round(top_sectors[0].get('change_pct', 0), 2) if top_sectors else 0,
        }
    except Exception as e:
        logger.error(f"detect_sector_strength failed: {e}")
        return {'sector_name': '未知', 'sector_rank': 99, 'sector_signal': 'neutral',
                'reason': f'行业数据异常: {str(e)}', 'sector_change_pct': 0}


def detect_fundamental_health(stock_code: str) -> dict:
    """基本面健康度检查（O'Neil CAN SLIM: C=Current Earnings）
    复用 data_service 获取 EPS/ROE
    """
    try:
        from app.services.data_service import DataService
        svc = DataService()
        fin = svc.get_financial_indicators(stock_code)
        if not fin or not fin.get('indicators'):
            return {'eps_growth': None, 'roe': None, 'revenue_growth': None,
                    'signal': 'warning', 'reason': '财务数据不足，无法验证基本面'}

        # 取最新一期数据
        latest = fin['indicators'][0] if fin['indicators'] else {}
        eps_growth = latest.get('profit_growth')
        revenue_growth = latest.get('revenue_growth')
        roe = latest.get('roe')

        # 判断
        if eps_growth is not None and eps_growth >= 20 and roe is not None and roe >= 12:
            signal = 'pass'
            reason = f'EPS增长{eps_growth:.0f}%、ROE={roe:.0f}%，基本面健康'
        elif eps_growth is not None and eps_growth >= 10:
            signal = 'warning'
            reason = f'EPS增长{eps_growth:.0f}%，增长尚可但不够强劲'
        elif eps_growth is not None and eps_growth < 0:
            signal = 'fail'
            reason = f'EPS增长{eps_growth:.0f}%，利润下滑，基本面承压'
        elif eps_growth is None:
            signal = 'warning'
            reason = 'EPS增长数据缺失，无法判断'
        else:
            signal = 'warning'
            reason = f'EPS增长{eps_growth:.0f}%，增长偏弱'

        return {
            'eps_growth': round(eps_growth, 2) if eps_growth is not None else None,
            'roe': round(roe, 2) if roe is not None else None,
            'revenue_growth': round(revenue_growth, 2) if revenue_growth is not None else None,
            'signal': signal,
            'reason': reason,
            'report_date': latest.get('report_date', ''),
        }
    except Exception as e:
        logger.error(f"detect_fundamental_health failed for {stock_code}: {e}")
        return {'eps_growth': None, 'roe': None, 'revenue_growth': None,
                'signal': 'warning', 'reason': f'基本面查询异常: {str(e)}'}


def compute_entry_plan(closes: list, highs: list, lows: list, atr_value: float,
                       pattern_result: dict, verdict: str) -> dict:
    """精确入场建议（Minervini: 在中枢点买入，止损设在形态低点下方）
    返回精确的入场价、止损价、仓位建议
    """
    cur = len(closes) - 1
    price = closes[cur]

    if verdict != '右侧确认' or atr_value <= 0 or price <= 0:
        return {'entry_type': 'none', 'entry_price': 0, 'stop_loss_price': 0,
                'position_size_pct': 0, 'reason': '当前不满足入场条件'}

    # 寻找最近的支撑位（过去20日低点）
    recent_low = min(lows[max(0, cur - 19):cur + 1])
    recent_high = max(highs[max(0, cur - 9):cur + 1])

    # 入场策略选择
    signals_text = ' '.join(pattern_result.get('signals', []))

    if 'VCP' in signals_text or '旗形' in signals_text:
        # 形态突破入场
        entry_type = 'breakout'
        entry_price = recent_high  # 突破近期高点
        stop_loss_price = round(recent_low - 0.5 * atr_value, 2)
        reason = f'形态突破入场：突破{recent_high:.2f}，止损设在{stop_loss_price:.2f}'
    elif price > recent_high * 0.98:
        # 接近突破
        entry_type = 'breakout'
        entry_price = round(recent_high * 1.005, 2)  # 突破位+0.5%
        stop_loss_price = round(price - 2.0 * atr_value, 2)
        reason = f'接近突破位{recent_high:.2f}，突破后入场，止损{stop_loss_price:.2f}'
    else:
        # 回调买入
        entry_type = 'pullback'
        entry_price = round(price, 2)  # 当前价即可入场
        stop_loss_price = round(price - 2.0 * atr_value, 2)
        reason = f'趋势确认后入场，当前价{price:.2f}，止损{stop_loss_price:.2f}'

    # 仓位计算（1%风险法则）
    risk_per_share = entry_price - stop_loss_price
    if risk_per_share <= 0:
        risk_per_share = atr_value * 2

    # 假设10万资金，单笔风险1%
    base_capital = 100000
    risk_amount = base_capital * 0.01  # = 1000元
    shares = int(risk_amount / risk_per_share)  # 最多可买股数
    # A股100股整数倍
    lots = shares // 100
    shares = lots * 100 if lots > 0 else 0
    position_value = shares * entry_price
    position_pct = round(position_value / base_capital * 100, 1)
    position_pct = min(position_pct, 20)  # 最大20%

    # 目标位
    target_2r = round(entry_price + 2 * risk_per_share, 2)
    target_3r = round(entry_price + 3 * risk_per_share, 2)

    return {
        'entry_type': entry_type,
        'entry_price': round(entry_price, 2),
        'stop_loss_price': round(stop_loss_price, 2),
        'risk_per_share': round(risk_per_share, 2),
        'position_size_pct': position_pct,
        'position_shares': shares,
        'position_value': round(position_value, 0),
        'target_2r': target_2r,
        'target_3r': target_3r,
        'reason': reason,
    }


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

        # 2b. 大师级三层过滤器
        market_timing = detect_market_timing()
        sector_strength = detect_sector_strength(stock_code)
        fundamental_health = detect_fundamental_health(stock_code)

        # 3. Weinstein阶段分析
        weinstein = detect_weinstein_stage(highs, lows, closes, volumes)

        # 4. 九维度检测
        ma_result = detect_ma_signals(closes, dates)
        macd_result = detect_macd_signals(closes, dates)
        vol_result = detect_volume_signals(volumes, closes)
        pattern_result = detect_pattern_signals(highs, lows, closes, volumes)
        rsi_kdj_result = detect_rsi_kdj_signals(closes, highs, lows)
        new_ind_result = detect_new_indicators_signals(closes, highs, lows, volumes)

        # 新增三维度
        w_closes_for_adaptive = None
        if weekly_ohlcv and len(weekly_ohlcv) >= 30:
            w_closes_for_adaptive = [d['close'] for d in weekly_ohlcv]
        momentum_result = detect_momentum_signals(closes, highs, lows, volumes)
        adaptive_result = detect_adaptive_trend_signals(closes, highs, lows, w_closes_for_adaptive)
        td_result = detect_td_signals(closes, highs, lows)

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
            weighted_score(new_ind_result['score'], new_ind_result['max'], weights['new_ind']) +
            weighted_score(momentum_result['score'], momentum_result['max'], weights['momentum']) +
            weighted_score(adaptive_result['score'], adaptive_result['max'], weights['adaptive_trend']) +
            weighted_score(td_result['score'], td_result['max'], weights['td'])
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
            w_new_ind = detect_new_indicators_signals(w_closes, w_highs, w_lows, w_volumes)
            w_momentum = detect_momentum_signals(w_closes, w_highs, w_lows, w_volumes)
            w_adaptive = detect_adaptive_trend_signals(w_closes, w_highs, w_lows)
            w_td = detect_td_signals(w_closes, w_highs, w_lows)

            weekly_raw = (w_ma['score'] + w_macd['score'] + w_vol['score'] +
                          w_pattern['score'] + w_rsi_kdj['score'] + w_new_ind['score'] +
                          w_momentum['score'] + w_adaptive['score'] + w_td['score'])
            weekly_max = (25 + 20 + 20 + 30 + 15 + w_new_ind['max'] +
                          w_momentum['max'] + w_adaptive['max'] + w_td['max'])
            weekly_score = round(weekly_raw / weekly_max * 100, 1) if weekly_max > 0 else 0

            weekly_result = {
                'ma': {'score': w_ma['score'], 'max': 25, 'signals': w_ma['signals'], 'detail': w_ma['detail']},
                'macd': {'score': w_macd['score'], 'max': 20, 'signals': w_macd['signals'], 'detail': w_macd['detail']},
                'volume': {'score': w_vol['score'], 'max': 20, 'signals': w_vol['signals'], 'detail': w_vol['detail']},
                'pattern': {'score': w_pattern['score'], 'max': 30, 'signals': w_pattern['signals'], 'detail': w_pattern['detail']},
                'rsi_kdj': {'score': w_rsi_kdj['score'], 'max': 15, 'signals': w_rsi_kdj['signals'], 'detail': w_rsi_kdj['detail']},
                'new_indicators': {'score': w_new_ind['score'], 'max': w_new_ind['max'], 'signals': w_new_ind['signals'], 'detail': w_new_ind['detail']},
                'momentum': {'score': w_momentum['score'], 'max': w_momentum['max'], 'signals': w_momentum['signals'], 'detail': w_momentum['detail']},
                'adaptive_trend': {'score': w_adaptive['score'], 'max': w_adaptive['max'], 'signals': w_adaptive['signals'], 'detail': w_adaptive['detail']},
                'td_sequential': {'score': w_td['score'], 'max': w_td['max'], 'signals': w_td['signals'], 'detail': w_td['detail']},
            }

            # 周线判定 (百分制)
            if weekly_score >= 65:
                weekly_verdict = '右侧确认'
            elif weekly_score >= 45:
                weekly_verdict = '疑似右侧'
            elif weekly_score >= 25:
                weekly_verdict = '非右侧'
            else:
                weekly_verdict = '左侧下跌'

        # 7. 多时间框架对齐
        current_verdict = '右侧确认' if total_score >= 72 else ('疑似右侧' if total_score >= 52 else ('非右侧' if total_score >= 32 else '左侧下跌'))
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

        # TD序列警告
        for sig in td_result.get('signals', []):
            if '警告' in sig:
                anti_fake.append({
                    'type': 'td_warning',
                    'severity': 'high' if 'Countdown' in sig else 'medium',
                    'message': sig,
                })

        # 10. 最终判定（大师级逻辑：大盘一票否决 + 二元信号）
        high_warnings = [w for w in anti_fake if w['severity'] == 'high']

        # 大盘择时一票否决（O'Neil: M=Market）
        if market_timing['signal'] == 'no_trade':
            verdict = '左侧下跌'
            anti_fake.insert(0, {
                'type': 'market_veto',
                'severity': 'high',
                'message': f"大盘否决: {market_timing['reason']}，不做多",
            })
        elif total_score >= 65 and len(high_warnings) == 0:
            verdict = '右侧确认'
        elif total_score >= 45 and len(high_warnings) <= 1:
            verdict = '观望等待'
        elif total_score >= 32:
            verdict = '观望等待'
        else:
            verdict = '左侧下跌'

        # Weinstein Stage 4强制降级
        if weinstein['stage'] == 4 and verdict == '右侧确认':
            verdict = '观望等待'
            anti_fake.append({
                'type': 'weinstein_stage4',
                'severity': 'high',
                'message': f"Weinstein阶段分析: {weinstein['stage_name']}，已降级判定",
            })

        # 行业偏弱警告
        if sector_strength['sector_signal'] == 'weak':
            anti_fake.append({
                'type': 'weak_sector',
                'severity': 'medium',
                'message': f"行业偏弱: {sector_strength['reason']}",
            })

        # 基本面警告
        if fundamental_health['signal'] == 'fail':
            anti_fake.append({
                'type': 'weak_fundamental',
                'severity': 'high',
                'message': f"基本面承压: {fundamental_health['reason']}",
            })

        # 11. 精确入场建议
        entry_plan = compute_entry_plan(closes, highs, lows, atr_val, pattern_result, verdict)

        # 12. 构建图表数据
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
        kama_data = compute_kama(closes, period=10)
        kst_data = compute_kst(closes)
        wr_data = compute_williams_r(highs, lows, closes)

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
                'momentum': {'score': momentum_result['score'], 'max': momentum_result['max'], 'signals': momentum_result['signals'], 'detail': momentum_result['detail']},
                'adaptive_trend': {'score': adaptive_result['score'], 'max': adaptive_result['max'], 'signals': adaptive_result['signals'], 'detail': adaptive_result['detail']},
                'td_sequential': {'score': td_result['score'], 'max': td_result['max'], 'signals': td_result['signals'], 'detail': td_result['detail']},
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
                'kama': kama_data[start_idx:],
                'kst': {
                    'kst': kst_data['kst'][start_idx:],
                    'signal': kst_data['signal'][start_idx:],
                },
                'williams_r': wr_data[start_idx:],
                'rsi': rsi_vals[start_idx:],
            },
            # 大师级三层过滤器
            'market_timing': market_timing,
            'sector_strength': sector_strength,
            'fundamental_health': fundamental_health,
            # 精确入场建议
            'entry_plan': entry_plan,
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
    """历史信号回测 V2：九维度评分 + KAMA过滤 + Trailing Stop模拟"""
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
        kama_vals = compute_kama(closes, period=10)
        kst_data = compute_kst(closes)
        wr_vals = compute_williams_r(highs, lows, closes)
        td_data = compute_td_sequential(closes, highs, lows)
        atr_series = compute_atr_series(highs, lows, closes, 14)

        signals = []
        hold_days = [5, 10, 20, 60]

        # 每5天采样一次，从第200天到第N-60天
        for idx in range(200, n - 60, 5):
            score = 0

            # === 维度1: 均线（满分15） ===
            if ma5[idx] and ma10[idx] and ma5[idx] > ma10[idx]:
                score += 2
            if ma10[idx] and ma20[idx] and ma10[idx] > ma20[idx]:
                score += 2
            if ma20[idx] and ma60[idx] and ma20[idx] > ma60[idx]:
                score += 2
            if ma60[idx] and closes[idx] > ma60[idx]:
                score += 2
            if ma120[idx] and closes[idx] > ma120[idx]:
                score += 2
            # 多头排列加分
            if (ma5[idx] and ma10[idx] and ma20[idx] and ma60[idx] and
                    ma5[idx] > ma10[idx] > ma20[idx] > ma60[idx]):
                score += 5

            # === 维度2: MACD（满分12） ===
            dif = macd_data['dif'][idx]
            dea = macd_data['dea'][idx]
            hist = macd_data['histogram'][idx]
            if dif is not None and dea is not None:
                if dif > dea:
                    score += 4
                    if dif > 0:
                        score += 3
                if hist is not None and idx >= 1 and hist > 0 and macd_data['histogram'][idx - 1] is not None and macd_data['histogram'][idx - 1] <= 0:
                    score += 3
                # DIF趋势
                if idx >= 5 and macd_data['dif'][idx - 5] is not None and dif > macd_data['dif'][idx - 5]:
                    score += 2

            # === 维度3: 成交量（满分10） ===
            if idx >= 20:
                vol_ma = sum(volumes[idx - 19:idx + 1]) / 20
                if vol_ma > 0:
                    vol_ratio = volumes[idx] / vol_ma
                    if vol_ratio > 1.5:
                        score += 5
                    elif vol_ratio > 1.2:
                        score += 3
                    # 量价配合
                    up_vols = [volumes[j] for j in range(max(1, idx - 9), idx + 1) if closes[j] > closes[j - 1]]
                    dn_vols = [volumes[j] for j in range(max(1, idx - 9), idx + 1) if closes[j] < closes[j - 1]]
                    if up_vols and dn_vols:
                        if sum(up_vols) / len(up_vols) > sum(dn_vols) / len(dn_vols) * 1.2:
                            score += 5

            # === 维度4: RSI/KDJ（满分8） ===
            if rsi_vals[idx] is not None:
                if 40 < rsi_vals[idx] < 65:
                    score += 4
                elif rsi_vals[idx] > 70:
                    score -= 2
            k_val = kdj_vals['k'][idx]
            d_val = kdj_vals['d'][idx]
            if idx >= 1 and k_val is not None and d_val is not None:
                if kdj_vals['k'][idx - 1] <= kdj_vals['d'][idx - 1] and k_val > d_val:
                    score += 4

            # === 维度5: 动量 — KST + W%R + ROC（满分12） ===
            kst_val = kst_data['kst'][idx]
            kst_sig = kst_data['signal'][idx]
            if kst_val is not None and kst_sig is not None:
                if kst_val > kst_sig:
                    score += 4
                if idx >= 2 and kst_data['kst'][idx - 1] is not None and kst_data['signal'][idx - 1] is not None:
                    if kst_data['kst'][idx - 1] <= kst_data['signal'][idx - 1] and kst_val > kst_sig:
                        score += 2  # KST金叉

            wr_val = wr_vals[idx] if idx < len(wr_vals) else None
            if wr_val is not None:
                min_wr = min((v for v in wr_vals[max(0, idx - 19):idx + 1] if v is not None), default=-50)
                if min_wr < -80 and wr_val > -50:
                    score += 3

            # 多周期ROC
            if idx >= 40:
                roc10 = (closes[idx] - closes[idx - 10]) / closes[idx - 10] * 100
                roc20 = (closes[idx] - closes[idx - 20]) / closes[idx - 20] * 100
                if roc10 > 0 and roc20 > 0:
                    score += 3

            # === 维度6: 自适应趋势 — KAMA（满分8） ===
            kama_val = kama_vals[idx] if idx < len(kama_vals) else None
            if kama_val is not None:
                if closes[idx] > kama_val:
                    score += 4
                    if idx >= 5 and kama_vals[idx - 5] is not None and kama_val > kama_vals[idx - 5]:
                        score += 2
                # 效率比率
                if idx >= 10:
                    direction = abs(closes[idx] - closes[idx - 10])
                    volatility = sum(abs(closes[j] - closes[j - 1]) for j in range(idx - 9, idx + 1))
                    er = direction / volatility if volatility > 0 else 0
                    if er > 0.5:
                        score += 2

            # === 维度7: TD序列（满分5，用于风控） ===
            if td_data['setup'][idx] <= -9:
                score += 3  # 买入Setup → 底部信号
            if td_data['setup'][idx] >= 9:
                score -= 2  # 卖出Setup → 风险警告

            # === KAMA过滤：只在KAMA上方做多 ===
            if kama_val is not None and closes[idx] < kama_val:
                continue  # 价格在KAMA下方，跳过

            # 判定
            if score >= 40:
                verdict = '右侧确认'
            elif score >= 28:
                verdict = '疑似右侧'
            else:
                continue

            # 计算后续收益（固定止损）
            price_at_signal = closes[idx]
            returns = {}
            for d in hold_days:
                if idx + d < n:
                    future_price = closes[idx + d]
                    returns[f'{d}d'] = round((future_price - price_at_signal) / price_at_signal * 100, 2)
                else:
                    returns[f'{d}d'] = None

            # Trailing Stop模拟（20日持有期）
            trailing_return = None
            if idx + 20 < n:
                atr_val = atr_series[idx] if idx < len(atr_series) and atr_series[idx] is not None else price_at_signal * 0.02
                stop_price = price_at_signal - 2.0 * atr_val
                best_price = price_at_signal
                for j in range(idx + 1, min(idx + 21, n)):
                    best_price = max(best_price, highs[j])
                    # 移动止损：盈利超过5%时止损移至成本价
                    if best_price > price_at_signal * 1.05:
                        stop_price = max(stop_price, price_at_signal)
                    # 盈利超过10%时止损移至盈利5%
                    if best_price > price_at_signal * 1.10:
                        stop_price = max(stop_price, price_at_signal * 1.05)
                    # 检查是否触发止损
                    if lows[j] <= stop_price:
                        trailing_return = round((stop_price - price_at_signal) / price_at_signal * 100, 2)
                        break
                if trailing_return is None:
                    trailing_return = returns.get('20d')

            signals.append({
                'date': dates[idx],
                'score': score,
                'verdict': verdict,
                'price_at_signal': round(price_at_signal, 2),
                'returns': returns,
                'trailing_return': trailing_return,
            })

        # 统计
        if not signals:
            return {
                'signals': [],
                'stats': {'total_signals': 0, 'win_rate_20d': 0, 'avg_return_20d': 0,
                          'max_return_20d': 0, 'min_return_20d': 0, 'sharpe_like': 0,
                          'avg_trailing_return': 0, 'win_rate_trailing': 0,
                          'profit_loss_ratio': 0, 'avg_hold_days': 0},
                'code': stock_code,
            }

        returns_20d = [s['returns']['20d'] for s in signals if s['returns']['20d'] is not None]
        trailing_returns = [s['trailing_return'] for s in signals if s['trailing_return'] is not None]

        if returns_20d:
            win_count = sum(1 for r in returns_20d if r > 0)
            avg_ret = sum(returns_20d) / len(returns_20d)
            std_ret = (sum((r - avg_ret) ** 2 for r in returns_20d) / len(returns_20d)) ** 0.5
            sharpe = round(avg_ret / std_ret, 2) if std_ret > 0 else 0
            # 盈亏比
            wins = [r for r in returns_20d if r > 0]
            losses = [abs(r) for r in returns_20d if r < 0]
            avg_win = sum(wins) / len(wins) if wins else 0
            avg_loss = sum(losses) / len(losses) if losses else 1
            pl_ratio = round(avg_win / avg_loss, 2) if avg_loss > 0 else 0
        else:
            win_count = 0
            avg_ret = 0
            sharpe = 0
            pl_ratio = 0

        # Trailing Stop统计
        trailing_win = sum(1 for r in trailing_returns if r > 0) if trailing_returns else 0
        avg_trailing = round(sum(trailing_returns) / len(trailing_returns), 2) if trailing_returns else 0

        stats = {
            'total_signals': len(signals),
            'win_rate_20d': round(win_count / len(returns_20d) * 100, 1) if returns_20d else 0,
            'avg_return_20d': round(avg_ret, 2),
            'max_return_20d': round(max(returns_20d), 2) if returns_20d else 0,
            'min_return_20d': round(min(returns_20d), 2) if returns_20d else 0,
            'sharpe_like': sharpe,
            'profit_loss_ratio': pl_ratio,
            'avg_trailing_return': avg_trailing,
            'win_rate_trailing': round(trailing_win / len(trailing_returns) * 100, 1) if trailing_returns else 0,
        }

        return {
            'signals': signals[-20:],
            'stats': stats,
            'code': stock_code,
        }

    except Exception as e:
        logger.error(f"backtest_right_side failed for {stock_code}: {e}")
        return {'error': f'回测失败: {str(e)}', 'code': stock_code}


# ============================================================
# 专家级：批量扫描
# ============================================================

def batch_scan_right_side(
    market: str = "all",
    min_score: float = 0,
    limit: int = 50,
) -> dict:
    """
    批量扫描全市场股票的右侧信号

    返回按分数排序的列表，用于快速发现机会。
    """
    from app.services.jc_service import A_STOCKS_LIST, HK_STOCKS_LIST

    stocks = []
    if market in ("A", "all"):
        stocks.extend([(c, "A") for c in A_STOCKS_LIST])
    if market in ("HK", "all"):
        stocks.extend([(c, "HK") for c in HK_STOCKS_LIST])

    candidates = []
    for code, mkt in stocks:
        try:
            # 轻量预筛：明显左侧/缩量股先跳过，避免对全池做深度分析导致超时/限流
            if not _quick_screen(code):
                continue
            result = analyze_right_side(code)
            if "error" in result:
                continue
            score = result.get("score", 0)
            if score >= min_score:
                candidates.append((code, mkt, score, result))
        except Exception:
            continue

    # 按分数排序后取 top
    candidates.sort(key=lambda x: x[2], reverse=True)
    candidates = candidates[:limit]

    results = []
    for code, mkt, score, result in candidates:
        results.append({
            "code": code,
            "name": _get_stock_name(code),
            "market": mkt,
            "score": score,
            "verdict": result.get("verdict", ""),
            "market_regime": result.get("market_regime", {}).get("regime", ""),
            "weinstein_stage": result.get("weinstein_stage", {}).get("stage", 0),
            "risk_reward": result.get("risk_management", {}).get("risk_reward", {}),
            "entry_type": result.get("entry_plan", {}).get("entry_type", "none"),
        })

    return {
        "results": results,
        "total": len(results),
        "scanned": len(stocks),
        "market": market,
        "min_score": min_score,
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ============================================================
# 专家级：板块轮动分析
# ============================================================

def analyze_sector_rotation() -> dict:
    """
    板块轮动分析

    使用东方财富行业分类API获取板块数据，计算各板块近5/10/20日涨跌幅，
    返回板块强度排名和轮动方向。
    """
    try:
        # 东方财富行业板块API
        url = "https://push2.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": 1,
            "pz": 50,
            "po": 1,
            "np": 1,
            "fltt": 2,
            "invt": 2,
            "fid": "f3",
            "fs": "m:90+t:2",  # 行业板块
            "fields": "f2,f3,f4,f12,f14,f104,f105,f128,f136,f140",
        }
        r = requests.get(url, params=params, timeout=10)
        data = r.json()

        sectors = []
        if data.get("data") and data["data"].get("diff"):
            for item in data["data"]["diff"]:
                sectors.append({
                    "code": item.get("f12", ""),
                    "name": item.get("f14", ""),
                    "change_pct": item.get("f3", 0),
                    "up_count": item.get("f104", 0),
                    "down_count": item.get("f105", 0),
                    "lead_stock": item.get("f140", ""),
                    "lead_change": item.get("f136", 0),
                })

        # 按涨跌幅排序
        sectors.sort(key=lambda x: x.get("change_pct", 0), reverse=True)

        # 板块强度分类
        strong = [s for s in sectors if s.get("change_pct", 0) > 1]
        weak = [s for s in sectors if s.get("change_pct", 0) < -1]

        return {
            "sectors": sectors[:30],
            "total": len(sectors),
            "strong_sectors": strong[:5],
            "weak_sectors": weak[-5:] if weak else [],
            "market_mood": (
                "强势" if len(strong) > len(sectors) * 0.6
                else "偏弱" if len(weak) > len(sectors) * 0.6
                else "分化"
            ),
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    except Exception as e:
        logger.error(f"analyze_sector_rotation failed: {e}")
        return {"error": f"板块轮动分析失败: {str(e)}", "sectors": []}


# ============================================================
# 专家级：信号表现跟踪
# ============================================================

def get_signal_performance_history(stock_code: str) -> dict:
    """
    获取某只股票的历史信号及后续表现

    用于评估该股票的右侧信号是否可靠。
    """
    result = backtest_right_side(stock_code)
    if "error" in result:
        return result

    signals = result.get("signals", [])
    stats = result.get("stats", {})

    # 为每个信号添加质量标签
    for s in signals:
        ret_20d = s.get("returns", {}).get("20d")
        if ret_20d is not None:
            if ret_20d > 5:
                s["quality"] = "excellent"
                s["quality_label"] = "🏆 优秀信号"
            elif ret_20d > 0:
                s["quality"] = "good"
                s["quality_label"] = "✅ 盈利信号"
            elif ret_20d > -3:
                s["quality"] = "neutral"
                s["quality_label"] = "➖ 持平"
            else:
                s["quality"] = "bad"
                s["quality_label"] = "❌ 亏损信号"

    return {
        "stock_code": stock_code,
        "signals": signals,
        "stats": stats,
        "reliability": (
            "高可靠" if stats.get("win_rate_20d", 0) > 60
            else "中等可靠" if stats.get("win_rate_20d", 0) > 45
            else "低可靠"
        ),
        "recommendation": (
            f"该股票右侧信号胜率{stats.get('win_rate_20d', 0)}%，"
            f"平均20日收益{stats.get('avg_return_20d', 0)}%，"
            + ("信号可靠，可以参考" if stats.get("win_rate_20d", 0) > 55 else "信号不太可靠，需谨慎")
        ),
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ============================================================
# 专家级：自选股管理
# ============================================================

import json
import os

_WATCHLIST_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "right_side_watchlist.json")


def _load_watchlist() -> list:
    if os.path.exists(_WATCHLIST_FILE):
        try:
            with open(_WATCHLIST_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"自选股加载失败: {e}")
    return []


def _save_watchlist(watchlist: list):
    os.makedirs(os.path.dirname(_WATCHLIST_FILE), exist_ok=True)
    with open(_WATCHLIST_FILE, "w", encoding="utf-8") as f:
        json.dump(watchlist, f, ensure_ascii=False, indent=2)


def add_to_watchlist(code: str, name: str = "", market: str = "A", note: str = "") -> dict:
    """添加股票到右侧交易自选股"""
    watchlist = _load_watchlist()
    for w in watchlist:
        if w["code"] == code:
            return {"error": f"{code} 已在自选股中"}

    entry = {
        "code": code,
        "name": name or code,
        "market": market,
        "note": note,
        "added_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_score": None,
        "last_verdict": None,
    }
    watchlist.append(entry)
    _save_watchlist(watchlist)
    return {"message": f"已添加 {code} 到自选股", "entry": entry}


def remove_from_watchlist(code: str) -> dict:
    """从自选股中移除"""
    watchlist = _load_watchlist()
    new_list = [w for w in watchlist if w["code"] != code]
    if len(new_list) == len(watchlist):
        return {"error": f"未找到 {code}"}
    _save_watchlist(new_list)
    return {"message": f"已移除 {code}"}


def get_watchlist() -> dict:
    """获取自选股列表"""
    watchlist = _load_watchlist()
    return {
        "watchlist": watchlist,
        "total": len(watchlist),
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def scan_watchlist() -> dict:
    """
    扫描自选股的右侧信号

    只扫描自选股中的股票，比全市场扫描更快更精准。
    """
    watchlist = _load_watchlist()
    if not watchlist:
        return {"error": "自选股为空", "results": []}

    results = []
    for w in watchlist:
        try:
            result = analyze_right_side(w["code"])
            if "error" in result:
                continue

            score = result.get("score", 0)
            verdict = result.get("verdict", "")

            # 更新自选股记录
            w["last_score"] = score
            w["last_verdict"] = verdict

            results.append({
                "code": w["code"],
                "name": w.get("name", w["code"]),
                "market": w.get("market", "A"),
                "score": score,
                "verdict": verdict,
                "market_regime": result.get("market_regime", {}).get("regime", ""),
                "weinstein_stage": result.get("weinstein_stage", {}).get("stage", 0),
                "entry_type": result.get("entry_plan", {}).get("entry_type", "none"),
                "entry_price": result.get("entry_plan", {}).get("entry_price"),
                "stop_loss": result.get("risk_management", {}).get("stop_loss", {}).get("normal"),
                "note": w.get("note", ""),
            })
        except Exception:
            continue

    # 保存更新后的自选股
    _save_watchlist(watchlist)

    # 按分数排序
    results.sort(key=lambda x: x["score"], reverse=True)

    # 统计
    confirmed = [r for r in results if r["verdict"] == "右侧确认"]
    waiting = [r for r in results if r["verdict"] == "观望等待"]

    return {
        "results": results,
        "summary": {
            "total": len(results),
            "confirmed": len(confirmed),
            "waiting": len(waiting),
            "top_opportunity": results[0] if results else None,
        },
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
