"""金渐成（机哥）做T点位算法引擎

三重确认机制：
1. 方向判断 — 加权多指标共振（RSI/KDJ/MACD/布林带/VWAP）+ 趋势过滤器
2. 点位确定 — ATR自适应网格（含滑点和手续费）
3. 入场确认 — 最低利润门槛（覆盖2倍交易成本）

机构级增强：
- 加权信号评分：★★★=3, ★★=2, ★=1，取代简单计数
- 趋势过滤器：MA20/MA60方向判断，避免逆势做T
- 最低利润门槛：预期利润必须覆盖2倍交易成本
- 滑点模型：A股0.05%，港股0.1%，美股0.05%
- 回测引擎：历史模拟验证策略有效性

核心理念：
- 7成底仓不动，3成做T
- 金字塔加仓：越跌买越多
- 负成本持股：做T回收的资金 > 初始投入
"""

import math
import requests
from typing import Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from app.services.grid_service import calculate_atr, _fetch_hk_historical
from app.services.jc_service import INDUSTRY_POSITION, A_STOCKS_LIST, HK_STOCKS_LIST, US_STOCKS_LIST
from app.core.cache import get_cache as _base_get_cache, set_cache as _set_cached

# ============================================================
# 常量 & 缓存
# ============================================================

_CACHE_TTL = 60  # 做T信号缓存60秒（需要较实时）

# 交易成本参数（机构级）
TRADE_COST = {
    "A": {"commission": 0.00025, "stamp_tax": 0.0005, "slippage": 0.0005, "min_commission": 5.0},
    "HK": {"commission": 0.0003, "stamp_tax": 0.0013, "slippage": 0.001, "min_commission": 5.0},
    "US": {"commission": 0.0001, "stamp_tax": 0.0, "slippage": 0.0005, "min_commission": 0.0},
}

# 信号权重（机构级：★★★=3, ★★=2, ★=1）
SIGNAL_WEIGHTS = {"★": 1, "★★": 2, "★★★": 3}

def _get_cached(key: str):
    return _base_get_cache(key, ttl_seconds=_CACHE_TTL)


# ============================================================
# 历史K线数据获取
# ============================================================

def _fetch_a_historical(code: str, days: int = 252) -> list[dict]:
    """获取A股日K线数据（腾讯财经API，与港股共用同一数据源）"""
    try:
        # 腾讯财经前缀：深圳sz，上海sh
        prefix = "sz" if code.startswith(("0", "3")) else "sh"
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days + 30)).strftime("%Y-%m-%d")

        url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
        params = {"param": f"{prefix}{code},day,{start_date},{end_date},{days + 30},qfq"}
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r = requests.get(url, params=params, headers=headers, timeout=10)
        data = r.json()

        if "data" in data and f"{prefix}{code}" in data["data"]:
            klines = data["data"][f"{prefix}{code}"]
            rows = klines.get("qfqday") or klines.get("day") or []
            records = []
            for row in rows:
                if len(row) >= 6:
                    records.append({
                        "date": str(row[0]),
                        "open": float(row[1]),
                        "close": float(row[2]),
                        "high": float(row[3]),
                        "low": float(row[4]),
                        "volume": float(row[5]),
                        "amount": 0,
                    })
            return records[-days:] if len(records) > days else records
    except Exception:
        pass

    # Fallback: 新浪财经K线API
    try:
        prefix = "sz" if code.startswith(("0", "3")) else "sh"
        url = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
        params = {
            "symbol": f"{prefix}{code}",
            "scale": "240",
            "ma": "no",
            "datalen": days,
        }
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r = requests.get(url, params=params, headers=headers, timeout=10)
        rows = r.json()
        records = []
        for row in rows:
            records.append({
                "date": row["day"],
                "open": float(row["open"]),
                "close": float(row["close"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "volume": float(row["volume"]),
                "amount": 0,
            })
        return records[-days:]
    except Exception:
        return []


def _fetch_us_historical(symbol: str, days: int = 252) -> list[dict]:
    """获取美股日K线数据（新浪财经API）"""
    try:
        import json as _json
        url = "https://stock.finance.sina.com.cn/usstock/api/jsonp.php/data/US_MinKService.getDailyK"
        params = {"symbol": symbol, "type": "daily"}
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r = requests.get(url, params=params, headers=headers, timeout=10)
        # 新浪返回JSONP格式，需要提取JSON部分
        text = r.text
        start_idx = text.find("(")
        end_idx = text.rfind(")")
        if start_idx >= 0 and end_idx > start_idx:
            json_str = text[start_idx + 1:end_idx]
            rows = _json.loads(json_str)
            records = []
            for row in rows:
                records.append({
                    "date": row.get("d", ""),
                    "open": float(row.get("o", 0)),
                    "close": float(row.get("c", 0)),
                    "high": float(row.get("h", 0)),
                    "low": float(row.get("l", 0)),
                    "volume": float(row.get("v", 0)),
                    "amount": 0,
                })
            return records[-days:]
    except Exception:
        pass

    return []


def fetch_historical_klines(code: str, market: str, days: int = 252) -> list[dict]:
    """统一入口：获取各市场日K线数据"""
    if market == "A":
        return _fetch_a_historical(code, days)
    elif market == "HK":
        return _fetch_hk_historical(code, days)
    elif market == "US":
        return _fetch_us_historical(code, days)
    return []


# ============================================================
# 技术指标计算
# ============================================================

def calc_rsi(closes: list[float], period: int = 14) -> float:
    """RSI相对强弱指标（Wilder平滑法，机构标准）"""
    if len(closes) < period + 1:
        return 50.0

    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]

    # Wilder平滑法（指数移动平均），与TradingView一致
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - 100 / (1 + rs), 2)


def calc_kdj(highs: list[float], lows: list[float], closes: list[float],
             n: int = 9, m1: int = 3, m2: int = 3) -> dict:
    """KDJ随机指标"""
    if len(closes) < n:
        return {"k": 50, "d": 50, "j": 50, "signal": "neutral"}

    # 计算RSV
    rsv_list = []
    for i in range(n - 1, len(closes)):
        period_high = max(highs[i - n + 1:i + 1])
        period_low = min(lows[i - n + 1:i + 1])
        if period_high == period_low:
            rsv_list.append(50)
        else:
            rsv_list.append((closes[i] - period_low) / (period_high - period_low) * 100)

    # K、D、J
    k_values = [rsv_list[0]]
    d_values = [rsv_list[0]]

    for i in range(1, len(rsv_list)):
        k = (2 / m1) * k_values[-1] + (1 / m1) * rsv_list[i]
        d = (2 / m2) * d_values[-1] + (1 / m2) * k
        k_values.append(k)
        d_values.append(d)

    k = round(k_values[-1], 2)
    d = round(d_values[-1], 2)
    j = round(3 * k - 2 * d, 2)

    # 信号判定
    signal = "neutral"
    if len(k_values) >= 2 and len(d_values) >= 2:
        prev_k, prev_d = k_values[-2], d_values[-2]
        if prev_k <= prev_d and k > d and j < 20:
            signal = "golden_cross"  # 金叉（超卖区）
        elif prev_k >= prev_d and k < d and j > 80:
            signal = "dead_cross"    # 死叉（超买区）
        elif k < 20 and d < 20:
            signal = "oversold"
        elif k > 80 and d > 80:
            signal = "overbought"

    return {"k": k, "d": d, "j": j, "signal": signal}


def calc_macd(closes: list[float], fast: int = 12, slow: int = 26,
              signal_period: int = 9) -> dict:
    """MACD指标（含背离检测）"""
    if len(closes) < slow + signal_period:
        return {"dif": 0, "dea": 0, "hist": 0, "signal": "neutral", "divergence": "none"}

    # EMA计算
    def ema(data, period):
        result = [data[0]]
        multiplier = 2 / (period + 1)
        for i in range(1, len(data)):
            result.append(data[i] * multiplier + result[-1] * (1 - multiplier))
        return result

    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    dif = [ema_fast[i] - ema_slow[i] for i in range(len(closes))]
    dea = ema(dif, signal_period)
    hist = [(dif[i] - dea[i]) * 2 for i in range(len(closes))]

    current_dif = round(dif[-1], 4)
    current_dea = round(dea[-1], 4)
    current_hist = round(hist[-1], 4)

    # 基本信号
    signal = "neutral"
    if len(dif) >= 2 and len(dea) >= 2:
        if dif[-2] <= dea[-2] and dif[-1] > dea[-1]:
            signal = "golden_cross"
        elif dif[-2] >= dea[-2] and dif[-1] < dea[-1]:
            signal = "dead_cross"

    # 背离检测（最近30个交易日）
    divergence = "none"
    lookback = min(30, len(closes) - 1)
    if lookback >= 10:
        recent_closes = closes[-lookback:]
        recent_hist = hist[-lookback:]

        # 底背离：价格创新低但MACD柱不创新低
        price_min_idx = recent_closes.index(min(recent_closes))
        hist_at_price_min = recent_hist[price_min_idx]
        hist_min = min(recent_hist)

        if price_min_idx > lookback * 0.6 and hist_at_price_min > hist_min:
            divergence = "bottom"  # 底背离（买入信号）

        # 顶背离：价格创新高但MACD柱不创新高
        price_max_idx = recent_closes.index(max(recent_closes))
        hist_at_price_max = recent_hist[price_max_idx]
        hist_max = max(recent_hist)

        if price_max_idx > lookback * 0.6 and hist_at_price_max < hist_max:
            divergence = "top"  # 顶背离（卖出信号）

    return {
        "dif": current_dif,
        "dea": current_dea,
        "hist": current_hist,
        "signal": signal,
        "divergence": divergence,
    }


def calc_bollinger(closes: list[float], period: int = 20,
                   std_dev: float = 2.0) -> dict:
    """布林带指标"""
    if len(closes) < period:
        mid = closes[-1] if closes else 0
        return {"upper": mid * 1.02, "middle": mid, "lower": mid * 0.98, "signal": "neutral",
                "position_pct": 50}

    recent = closes[-period:]
    middle = sum(recent) / period
    variance = sum((x - middle) ** 2 for x in recent) / period
    std = math.sqrt(variance)

    upper = round(middle + std_dev * std, 2)
    lower = round(middle - std_dev * std, 2)
    middle = round(middle, 2)

    current = closes[-1]
    band_width = upper - lower
    position_pct = round((current - lower) / band_width * 100, 1) if band_width > 0 else 50

    # 信号
    signal = "neutral"
    if current <= lower:
        signal = "below_lower"  # 触及下轨（买入信号）
    elif current >= upper:
        signal = "above_upper"  # 触及上轨（卖出信号）
    elif position_pct < 20:
        signal = "near_lower"
    elif position_pct > 80:
        signal = "near_upper"

    return {
        "upper": upper,
        "middle": middle,
        "lower": lower,
        "signal": signal,
        "position_pct": position_pct,
        "bandwidth_pct": round(band_width / middle * 100, 2) if middle > 0 else 0,
    }


def calc_vwap_deviation(closes: list[float], volumes: list[float]) -> float:
    """VWAP偏离度（%）— 当前价偏离成交量加权均价的程度"""
    if not closes or not volumes or len(closes) != len(volumes):
        return 0.0

    # 用最近20个交易日计算
    lookback = min(20, len(closes))
    recent_closes = closes[-lookback:]
    recent_volumes = volumes[-lookback:]

    total_amount = sum(c * v for c, v in zip(recent_closes, recent_volumes))
    total_volume = sum(recent_volumes)

    if total_volume == 0:
        return 0.0

    vwap = total_amount / total_volume
    current = recent_closes[-1]
    deviation = round((current - vwap) / vwap * 100, 2)
    return deviation


def calc_volume_ratio(volumes: list[float], period: int = 5) -> float:
    """量比 — 当前成交量 vs 近期平均成交量"""
    if len(volumes) < period + 1:
        return 1.0
    avg_vol = sum(volumes[-period - 1:-1]) / period
    if avg_vol == 0:
        return 1.0
    return round(volumes[-1] / avg_vol, 2)


def calc_trend_filter(closes: list[float]) -> dict:
    """
    趋势过滤器（机构级增强）

    使用MA20/MA60判断中期趋势，避免逆势做T：
    - uptrend: MA20 > MA60 且 MA20向上 → 只允许做多T
    - downtrend: MA20 < MA60 且 MA20向下 → 只允许做空T（或观望）
    - sideways: 其他情况 → 双向可做

    额外检查：价格相对MA20的偏离度，偏离过大时降低信号强度
    """
    if len(closes) < 60:
        return {"trend": "unknown", "ma20": 0, "ma60": 0, "deviation_pct": 0, "filter_pass": True}

    ma20 = sum(closes[-20:]) / 20
    ma60 = sum(closes[-60:]) / 60
    ma20_prev = sum(closes[-21:-1]) / 20  # 前一日MA20

    current = closes[-1]
    deviation_pct = round((current - ma20) / ma20 * 100, 2) if ma20 > 0 else 0

    # 趋势判断
    if ma20 > ma60 and ma20 > ma20_prev:
        trend = "uptrend"
    elif ma20 < ma60 and ma20 < ma20_prev:
        trend = "downtrend"
    else:
        trend = "sideways"

    # 过滤规则：价格偏离MA20超过8%时，降低信号可信度
    filter_pass = abs(deviation_pct) < 8

    return {
        "trend": trend,
        "ma20": round(ma20, 2),
        "ma60": round(ma60, 2),
        "deviation_pct": deviation_pct,
        "filter_pass": filter_pass,
    }


def calc_round_trip_cost(market: str) -> float:
    """
    计算一次完整买卖（round-trip）的总交易成本率

    包含：佣金（双向）+ 印花税（卖出） + 滑点（双向）
    """
    cost = TRADE_COST.get(market, TRADE_COST["A"])
    # 买入成本：佣金 + 滑点
    buy_cost = cost["commission"] + cost["slippage"]
    # 卖出成本：佣金 + 印花税 + 滑点
    sell_cost = cost["commission"] + cost["stamp_tax"] + cost["slippage"]
    return round(buy_cost + sell_cost, 6)


def backtest_t_strategy(code: str, market: str, klines: list[dict],
                         t_capital: float = 300000) -> dict:
    """
    历史回测引擎

    使用最近60个交易日数据模拟做T策略表现：
    1. 遍历每个交易日，计算信号
    2. 模拟执行买卖操作
    3. 统计胜率、盈亏比、最大回撤
    """
    if len(klines) < 60:
        return {"error": "回测需要至少60个交易日数据", "valid": False}

    round_trip_cost = calc_round_trip_cost(market)
    base_lot = 100 if market == "A" else 1

    # 模拟参数
    trades = []
    position = 0  # 当前T仓持仓（股数）
    entry_price = 0.0
    total_pnl = 0.0
    max_pnl = 0.0
    max_drawdown = 0.0
    peak_pnl = 0.0

    # 遍历最近30个交易日（前30天用于计算指标）
    for i in range(30, len(klines)):
        window = klines[:i + 1]
        closes = [k["close"] for k in window]
        highs = [k["high"] for k in window]
        lows = [k["low"] for k in window]
        volumes = [k["volume"] for k in window]

        current_price = closes[-1]
        atr = calculate_atr(highs, lows, closes, 14)

        # 计算简化的信号
        rsi = calc_rsi(closes)
        kdj = calc_kdj(highs, lows, closes)
        bollinger = calc_bollinger(closes)
        trend = calc_trend_filter(closes)

        buy_score = 0
        sell_score = 0

        if rsi < 30:
            buy_score += 2
        elif rsi > 70:
            sell_score += 2

        if kdj["signal"] == "golden_cross":
            buy_score += 2
        elif kdj["signal"] == "dead_cross":
            sell_score += 2
        elif kdj["signal"] == "oversold":
            buy_score += 1
        elif kdj["signal"] == "overbought":
            sell_score += 1

        if bollinger["signal"] in ("below_lower", "near_lower"):
            buy_score += 2 if bollinger["signal"] == "below_lower" else 1
        elif bollinger["signal"] in ("above_upper", "near_upper"):
            sell_score += 2 if bollinger["signal"] == "above_upper" else 1

        # 趋势过滤
        if trend["trend"] == "downtrend":
            buy_score = max(0, buy_score - 2)  # 下降趋势降低买入信号
        elif trend["trend"] == "uptrend":
            sell_score = max(0, sell_score - 1)  # 上升趋势降低卖出信号

        # 模拟交易
        min_profit_threshold = current_price * round_trip_cost * 2  # 至少覆盖2倍成本

        if buy_score >= 3 and position == 0:
            # 开多仓
            t_shares = int(t_capital / 3 / current_price / base_lot) * base_lot
            t_shares = max(t_shares, base_lot)
            entry_price = current_price * (1 + TRADE_COST[market]["slippage"])
            position = t_shares
            trades.append({
                "date": klines[i]["date"],
                "action": "buy",
                "price": entry_price,
                "shares": t_shares,
                "reason": f"buy_score={buy_score}",
            })

        elif sell_score >= 3 and position > 0:
            # 平仓
            exit_price = current_price * (1 - TRADE_COST[market]["slippage"])
            gross_pnl = (exit_price - entry_price) * position
            cost = position * entry_price * round_trip_cost
            net_pnl = gross_pnl - cost
            total_pnl += net_pnl
            peak_pnl = max(peak_pnl, total_pnl)
            max_drawdown = min(max_drawdown, total_pnl - peak_pnl)

            trades.append({
                "date": klines[i]["date"],
                "action": "sell",
                "price": exit_price,
                "shares": position,
                "pnl": round(net_pnl, 2),
                "reason": f"sell_score={sell_score}",
            })
            position = 0
            entry_price = 0.0

    # 统计
    closed_trades = [t for t in trades if t["action"] == "sell"]
    winning_trades = [t for t in closed_trades if t.get("pnl", 0) > 0]
    losing_trades = [t for t in closed_trades if t.get("pnl", 0) <= 0]

    win_rate = len(winning_trades) / len(closed_trades) * 100 if closed_trades else 0
    avg_win = sum(t["pnl"] for t in winning_trades) / len(winning_trades) if winning_trades else 0
    avg_loss = sum(t["pnl"] for t in losing_trades) / len(losing_trades) if losing_trades else 0
    profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else float("inf")

    return {
        "valid": True,
        "total_trades": len(closed_trades),
        "winning_trades": len(winning_trades),
        "losing_trades": len(losing_trades),
        "win_rate": round(win_rate, 1),
        "total_pnl": round(total_pnl, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else "N/A",
        "max_drawdown": round(max_drawdown, 2),
        "round_trip_cost_pct": round(round_trip_cost * 100, 4),
        "trade_log": trades[-10:],  # 最近10笔
        "backtest_period": f"{klines[30]['date']} ~ {klines[-1]['date']}",
    }


# ============================================================
# T点信号判定引擎
# ============================================================

@dataclass
class TSignal:
    """做T信号"""
    code: str
    name: str
    market: str
    current_price: float
    signal_type: str          # "buy" / "sell" / "hold"
    signal_strength: str      # "strong" / "medium" / "weak"
    buy_point: float          # 建议买入T点价格
    sell_point: float         # 建议卖出T点价格
    suggested_t_shares: int   # 建议做T股数
    expected_profit_pct: float  # 预期单次做T收益率
    atr: float
    atr_pct: float
    indicators: dict          # 各指标详情
    reasoning: list[str]      # 信号理由


def _get_current_price_and_info(code: str, market: str) -> Optional[dict]:
    """获取当前价格和基本信息"""
    if market == "A":
        from app.services.data_service import DataService
        return DataService.get_stock_basic(code)
    elif market == "HK":
        from app.services.vi_service import _get_hk_stock_data
        return _get_hk_stock_data(code)
    elif market == "US":
        from app.services.vi_service import _get_us_stock_data
        return _get_us_stock_data(code)
    return None


def calc_support_resistance(highs: list, lows: list, closes: list, lookback: int = 60) -> dict:
    """
    计算支撑位和阻力位 — 基于枢轴点和价格聚集区

    专家级实现：
    1. 枢轴点（Pivot Points）— 基于前一日高低收
    2. 价格聚集区 — 成交密集的价格区间
    3. 近期高低点 — 最近N日的关键转折点

    返回：
    - pivot: 枢轴点
    - support_1/support_2: 支撑位
    - resistance_1/resistance_2: 阻力位
    - key_levels: 所有关键价位（排序后）
    """
    if len(closes) < 5:
        return {"pivot": 0, "support_1": 0, "support_2": 0, "resistance_1": 0, "resistance_2": 0, "key_levels": []}

    # --- 1. 经典枢轴点 ---
    h = highs[-1]
    l = lows[-1]
    c = closes[-1]
    pivot = round((h + l + c) / 3, 2)
    s1 = round(2 * pivot - h, 2)
    s2 = round(pivot - (h - l), 2)
    r1 = round(2 * pivot - l, 2)
    r2 = round(pivot + (h - l), 2)

    # --- 2. 近期关键高低点（swing points）---
    recent_n = min(lookback, len(highs))
    recent_highs = highs[-recent_n:]
    recent_lows = lows[-recent_n:]
    recent_closes = closes[-recent_n:]

    # 找局部高点（比左右2根K线都高的点）
    swing_highs = []
    swing_lows = []
    for i in range(2, len(recent_highs) - 2):
        if recent_highs[i] > max(recent_highs[i-2:i]) and recent_highs[i] > max(recent_highs[i+1:i+3]):
            swing_highs.append(recent_highs[i])
        if recent_lows[i] < min(recent_lows[i-2:i]) and recent_lows[i] < min(recent_lows[i+1:i+3]):
            swing_lows.append(recent_lows[i])

    # --- 3. 价格聚集区（用分位数找到成交密集区间）---
    sorted_closes = sorted(recent_closes)
    n = len(sorted_closes)
    q25 = sorted_closes[n // 4]
    q50 = sorted_closes[n // 2]
    q75 = sorted_closes[3 * n // 4]

    # 合并所有关键价位
    all_levels = [pivot, s1, s2, r1, r2]
    all_levels.extend(swing_highs[-3:] if swing_highs else [])
    all_levels.extend(swing_lows[-3:] if swing_lows else [])
    all_levels.extend([q25, q50, q75])

    # 去重并排序
    all_levels = sorted(set(round(lv, 2) for lv in all_levels if lv > 0))

    # 找当前价格最近的支撑和阻力
    current = closes[-1]
    supports = [lv for lv in all_levels if lv < current]
    resistances = [lv for lv in all_levels if lv > current]

    nearest_support = supports[-1] if supports else s1
    nearest_resistance = resistances[0] if resistances else r1

    return {
        "pivot": pivot,
        "support_1": round(nearest_support, 2),
        "support_2": round(s2, 2),
        "resistance_1": round(nearest_resistance, 2),
        "resistance_2": round(r2, 2),
        "key_levels": all_levels[-10:],  # 最多返回10个关键价位
        "swing_highs": [round(h, 2) for h in swing_highs[-3:]],
        "swing_lows": [round(l, 2) for l in swing_lows[-3:]],
    }


def detect_macd_divergence_v2(closes: list, macd_hist: list, lookback: int = 60) -> str:
    """
    改进的MACD背离检测 — 使用真正的swing high/low

    原版问题：只用30根K线的简单索引比较
    改进版：
    1. 找真正的swing high和swing low（局部极值点）
    2. 比较价格极值和MACD柱状图极值的方向
    3. 要求至少间隔10根K线
    4. 使用更长的lookback窗口(60)

    返回: "bottom" (底背离) / "top" (顶背离) / "none"
    """
    if len(closes) < lookback or len(macd_hist) < lookback:
        return "none"

    recent_closes = closes[-lookback:]
    recent_macd = macd_hist[-lookback:]
    n = len(recent_closes)

    # 找价格的swing low（局部最低点）
    price_lows = []
    for i in range(3, n - 3):
        if recent_closes[i] <= min(recent_closes[i-3:i]) and recent_closes[i] <= min(recent_closes[i+1:i+4]):
            price_lows.append((i, recent_closes[i], recent_macd[i]))

    # 找价格的swing high（局部最高点）
    price_highs = []
    for i in range(3, n - 3):
        if recent_closes[i] >= max(recent_closes[i-3:i]) and recent_closes[i] >= max(recent_closes[i+1:i+4]):
            price_highs.append((i, recent_closes[i], recent_macd[i]))

    # 检查底背离：价格新低但MACD不新低
    if len(price_lows) >= 2:
        for i in range(len(price_lows) - 1, 0, -1):
            curr = price_lows[i]
            prev = price_lows[i - 1]
            # 间隔至少10根K线
            if curr[0] - prev[0] < 10:
                continue
            # 价格新低，MACD不新低 = 底背离
            if curr[1] < prev[1] and curr[2] > prev[2]:
                return "bottom"

    # 检查顶背离：价格新高但MACD不新高
    if len(price_highs) >= 2:
        for i in range(len(price_highs) - 1, 0, -1):
            curr = price_highs[i]
            prev = price_highs[i - 1]
            if curr[0] - prev[0] < 10:
                continue
            # 价格新高，MACD不新高 = 顶背离
            if curr[1] > prev[1] and curr[2] < prev[2]:
                return "top"

    return "none"


def analyze_t_signal(code: str, market: str, t_capital: float = 300000) -> Optional[TSignal]:
    """
    分析单只股票的做T信号（机构级）

    三重确认：
    1. 加权多指标共振 → 确定方向（★=1, ★★=2, ★★★=3）
    2. ATR自适应 + 滑点 → 确定点位
    3. 最低利润门槛 → 过滤无效信号

    额外保护：
    - 趋势过滤器：下降趋势中降低买入信号，上升趋势中降低卖出信号
    - 利润门槛：预期利润必须覆盖2倍round-trip交易成本
    - 偏离度保护：价格偏离MA20超过8%时降低信号强度

    Args:
        code: 股票代码
        market: 市场 A/HK/US
        t_capital: 做T资金（默认30万，对应金渐成3成做T仓）
    """
    cache_key = f"t_signal_{market}_{code}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    # 获取历史K线
    klines = fetch_historical_klines(code, market, 252)
    if not klines or len(klines) < 60:
        return None

    closes = [k["close"] for k in klines]
    highs = [k["high"] for k in klines]
    lows = [k["low"] for k in klines]
    volumes = [k["volume"] for k in klines]

    current_price = closes[-1]

    # 获取股票名称
    stock_info = _get_current_price_and_info(code, market)
    stock_name = stock_info.get("name", code) if stock_info else code

    # 计算所有技术指标
    rsi = calc_rsi(closes)
    kdj = calc_kdj(highs, lows, closes)
    macd = calc_macd(closes)
    bollinger = calc_bollinger(closes)
    vwap_dev = calc_vwap_deviation(closes, volumes)
    vol_ratio = calc_volume_ratio(volumes)
    trend = calc_trend_filter(closes)
    atr = calculate_atr(highs, lows, closes, 14)
    sr = calc_support_resistance(highs, lows, closes, 60)
    atr_pct = round(atr / current_price * 100, 2) if current_price > 0 else 0

    # === 加权多指标共振：方向判断 ===
    # 每个信号格式: (名称, 详情, 权重星级)
    buy_signals = []
    sell_signals = []

    # RSI
    if rsi < 30:
        buy_signals.append(("RSI超卖", f"RSI={rsi}", "★★"))
    elif rsi < 40:
        buy_signals.append(("RSI偏低", f"RSI={rsi}", "★"))
    elif rsi > 70:
        sell_signals.append(("RSI超买", f"RSI={rsi}", "★★"))
    elif rsi > 60:
        sell_signals.append(("RSI偏高", f"RSI={rsi}", "★"))

    # KDJ
    if kdj["signal"] == "golden_cross":
        buy_signals.append(("KDJ金叉", f"K={kdj['k']},D={kdj['d']},J={kdj['j']}", "★★"))
    elif kdj["signal"] == "dead_cross":
        sell_signals.append(("KDJ死叉", f"K={kdj['k']},D={kdj['d']},J={kdj['j']}", "★★"))
    elif kdj["signal"] == "oversold":
        buy_signals.append(("KDJ超卖", f"J={kdj['j']}", "★"))
    elif kdj["signal"] == "overbought":
        sell_signals.append(("KDJ超买", f"J={kdj['j']}", "★"))

    # MACD
    if macd["signal"] == "golden_cross":
        buy_signals.append(("MACD金叉", f"DIF={macd['dif']}", "★★"))
    elif macd["signal"] == "dead_cross":
        sell_signals.append(("MACD死叉", f"DIF={macd['dif']}", "★★"))

    # 使用改进的背离检测（v2: 基于真正的swing high/low）
    divergence_v2 = detect_macd_divergence_v2(closes, macd["histogram"], 60)
    if divergence_v2 == "bottom":
        buy_signals.append(("MACD底背离", "价格新低但MACD不新低（Swing验证）", "★★★"))
    elif divergence_v2 == "top":
        sell_signals.append(("MACD顶背离", "价格新高但MACD不新高（Swing验证）", "★★★"))

    # 布林带
    if bollinger["signal"] in ("below_lower", "near_lower"):
        weight = "★★" if bollinger["signal"] == "below_lower" else "★"
        buy_signals.append((f"布林带{'触及下轨' if bollinger['signal'] == 'below_lower' else '接近下轨'}",
                           f"位置{bollinger['position_pct']}%", weight))
    elif bollinger["signal"] in ("above_upper", "near_upper"):
        weight = "★★" if bollinger["signal"] == "above_upper" else "★"
        sell_signals.append((f"布林带{'触及上轨' if bollinger['signal'] == 'above_upper' else '接近上轨'}",
                            f"位置{bollinger['position_pct']}%", weight))

    # VWAP偏离
    if vwap_dev < -2:
        buy_signals.append(("分时偏离低", f"低于VWAP {abs(vwap_dev)}%", "★"))
    elif vwap_dev > 2:
        sell_signals.append(("分时偏离高", f"高于VWAP {vwap_dev}%", "★"))

    # 量比（缩量后放量）
    if vol_ratio > 1.5 and len(volumes) >= 6 and volumes[-2] < sum(volumes[-6:-1]) / 5 * 0.5:
        buy_signals.append(("缩量后放量", f"量比={vol_ratio}", "★"))

    # === 加权评分（机构级：使用权重而非简单计数）===
    buy_weight = sum(SIGNAL_WEIGHTS.get(s[2], 1) for s in buy_signals)
    sell_weight = sum(SIGNAL_WEIGHTS.get(s[2], 1) for s in sell_signals)

    # === 趋势过滤器（机构级增强）===
    trend_adjusted_buy = buy_weight
    trend_adjusted_sell = sell_weight
    trend_warning = ""

    if trend["trend"] == "downtrend":
        trend_adjusted_buy = max(0, buy_weight - 2)
        if buy_weight > 0:
            trend_warning = f"下降趋势（MA20={trend['ma20']}<MA60={trend['ma60']}），买入信号降权"
    elif trend["trend"] == "uptrend":
        trend_adjusted_sell = max(0, sell_weight - 1)
        if sell_weight > 0:
            trend_warning = f"上升趋势（MA20={trend['ma20']}>MA60={trend['ma60']}），卖出信号降权"

    # 偏离度保护
    if not trend["filter_pass"]:
        if trend["deviation_pct"] > 8:
            trend_adjusted_sell = max(0, trend_adjusted_sell - 1)
            trend_warning = f"价格偏离MA20达{trend['deviation_pct']}%，注意回调风险"
        elif trend["deviation_pct"] < -8:
            trend_adjusted_buy = max(0, trend_adjusted_buy - 1)
            trend_warning = f"价格偏离MA20达{trend['deviation_pct']}%，注意反弹力度"

    # === 综合判断 ===
    if trend_adjusted_buy >= 6:
        signal_type = "buy"
        signal_strength = "strong"
    elif trend_adjusted_buy >= 4:
        signal_type = "buy"
        signal_strength = "medium"
    elif trend_adjusted_buy >= 2 and trend_adjusted_sell == 0:
        signal_type = "buy"
        signal_strength = "weak"
    elif trend_adjusted_sell >= 6:
        signal_type = "sell"
        signal_strength = "strong"
    elif trend_adjusted_sell >= 4:
        signal_type = "sell"
        signal_strength = "medium"
    elif trend_adjusted_sell >= 2 and trend_adjusted_buy == 0:
        signal_type = "sell"
        signal_strength = "weak"
    else:
        signal_type = "hold"
        signal_strength = "neutral"

    # === ATR自适应：确定精确点位（含滑点）===
    atr_multiplier = {"strong": 1.5, "medium": 1.0, "weak": 0.5}.get(signal_strength, 0.5)
    slippage = TRADE_COST.get(market, TRADE_COST["A"])["slippage"]

    if signal_type == "buy":
        raw_buy = current_price * (1 - slippage) - atr * atr_multiplier
        raw_sell = current_price + atr * 0.5
        # 支撑位优化：如果最近支撑位在合理范围内，用支撑位作为买入点
        if sr["support_1"] > 0 and abs(sr["support_1"] - raw_buy) / raw_buy < 0.02:
            buy_point = sr["support_1"]
        else:
            buy_point = round(raw_buy, 2)
        # 阻力位优化：用最近阻力位作为卖出点
        if sr["resistance_1"] > 0 and sr["resistance_1"] > current_price:
            sell_point = sr["resistance_1"]
        else:
            sell_point = round(raw_sell, 2)
    elif signal_type == "sell":
        raw_buy = current_price - atr * 0.5
        raw_sell = current_price * (1 + slippage) + atr * atr_multiplier
        if sr["support_1"] > 0 and sr["support_1"] < current_price:
            buy_point = sr["support_1"]
        else:
            buy_point = round(raw_buy, 2)
        if sr["resistance_1"] > 0 and abs(sr["resistance_1"] - raw_sell) / raw_sell < 0.02:
            sell_point = sr["resistance_1"]
        else:
            sell_point = round(raw_sell, 2)
    else:
        buy_point = sr["support_1"] if sr["support_1"] > 0 else round(current_price - atr * 0.5, 2)
        sell_point = sr["resistance_1"] if sr["resistance_1"] > 0 else round(current_price + atr * 0.5, 2)

    # === 最低利润门槛（机构级：必须覆盖2倍交易成本）===
    round_trip_cost = calc_round_trip_cost(market)
    min_profit_threshold = current_price * round_trip_cost * 2
    price_spread = abs(sell_point - buy_point)

    if signal_type != "hold" and price_spread < min_profit_threshold:
        # 利润不足以覆盖交易成本，降级为hold
        signal_type = "hold"
        signal_strength = "neutral"
        if not trend_warning:
            trend_warning = f"预期利润不足以覆盖2倍交易成本（{round(round_trip_cost*100, 3)}%），建议观望"

    # === 做T仓位计算 ===
    t_shares_raw = t_capital / current_price if current_price > 0 else 0

    # A股100股整数倍，港股/美股1股
    if market == "A":
        base_lot = 100
    else:
        base_lot = 1

    if signal_strength == "strong":
        suggested_t = int(t_shares_raw / base_lot) * base_lot
    elif signal_strength == "medium":
        suggested_t = int(t_shares_raw / 2 / base_lot) * base_lot
    else:
        suggested_t = int(t_shares_raw / 3 / base_lot) * base_lot

    suggested_t = max(suggested_t, base_lot)

    # 预期收益率（扣费后）
    gross_profit_pct = round(price_spread / current_price * 100, 2) if current_price > 0 else 0
    net_profit_pct = round(gross_profit_pct - round_trip_cost * 100, 2)

    # 信号理由
    reasoning = []
    if buy_signals:
        reasoning.extend([f"[买入] {name}: {detail} {weight}" for name, detail, weight in buy_signals])
    if sell_signals:
        reasoning.extend([f"[卖出] {name}: {detail} {weight}" for name, detail, weight in sell_signals])
    if trend_warning:
        reasoning.append(f"[趋势] {trend_warning}")
    if sr["support_1"] > 0:
        reasoning.append(f"[支撑] 近支撑位 ¥{sr['support_1']}")
    if sr["resistance_1"] > 0:
        reasoning.append(f"[阻力] 近阻力位 ¥{sr['resistance_1']}")
    if not reasoning:
        reasoning.append("无明确信号，建议观望")

    result = TSignal(
        code=code,
        name=stock_name,
        market=market,
        current_price=current_price,
        signal_type=signal_type,
        signal_strength=signal_strength,
        buy_point=buy_point,
        sell_point=sell_point,
        suggested_t_shares=suggested_t,
        expected_profit_pct=net_profit_pct,
        atr=round(atr, 2),
        atr_pct=atr_pct,
        indicators={
            "rsi": rsi,
            "kdj": kdj,
            "macd": macd,
            "bollinger": bollinger,
            "vwap_deviation": vwap_dev,
            "volume_ratio": vol_ratio,
            "trend": trend,
            "buy_weight": buy_weight,
            "sell_weight": sell_weight,
            "round_trip_cost_pct": round(round_trip_cost * 100, 4),
            "min_profit_threshold": round(min_profit_threshold, 2),
            "support_resistance": sr,
        },
        reasoning=reasoning,
    )

    _set_cached(cache_key, result)
    return result


# ============================================================
# 全市场扫描
# ============================================================

def scan_all_signals(market: str = "all", t_capital: float = 300000) -> dict:
    """扫描全部金渐成股票池的做T信号"""
    cache_key = f"t_scan_{market}_{t_capital}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    stocks_to_scan = []
    if market in ("A", "all"):
        stocks_to_scan.extend([(c, "A") for c in A_STOCKS_LIST])
    if market in ("HK", "all"):
        stocks_to_scan.extend([(c, "HK") for c in HK_STOCKS_LIST])
    if market in ("US", "all"):
        stocks_to_scan.extend([(c, "US") for c in US_STOCKS_LIST])

    signals = []
    for code, mkt in stocks_to_scan:
        try:
            sig = analyze_t_signal(code, mkt, t_capital)
            if sig:
                signals.append(sig)
        except Exception:
            continue

    # 统计
    buy_signals = [s for s in signals if s.signal_type == "buy"]
    sell_signals = [s for s in signals if s.signal_type == "sell"]
    hold_signals = [s for s in signals if s.signal_type == "hold"]

    # 按信号强度排序
    strength_order = {"strong": 0, "medium": 1, "weak": 2, "neutral": 3}
    signals.sort(key=lambda s: (strength_order.get(s.signal_strength, 3),
                                 0 if s.signal_type == "buy" else 1))

    result = {
        "signals": [_signal_to_dict(s) for s in signals],
        "summary": {
            "total": len(signals),
            "buy_signals": len(buy_signals),
            "sell_signals": len(sell_signals),
            "hold": len(hold_signals),
            "strong_signals": len([s for s in signals if s.signal_strength == "strong"]),
        },
        "t_capital": t_capital,
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    _set_cached(cache_key, result)
    return result


def get_detailed_analysis(code: str, market: str, t_capital: float = 300000) -> dict:
    """获取单只股票的详细T点分析（含回测验证）"""
    sig = analyze_t_signal(code, market, t_capital)
    if not sig:
        return {"error": f"无法分析 {code}", "update_time": datetime.now().isoformat()}

    # 获取历史数据
    klines = fetch_historical_klines(code, market, 252)
    price_history = [{"date": k["date"], "close": k["close"]} for k in klines[-30:]]

    # 历史回测验证
    backtest = backtest_t_strategy(code, market, klines, t_capital)

    # 交易成本分析
    round_trip_cost = calc_round_trip_cost(market)

    return {
        **_signal_to_dict(sig),
        "price_history": price_history,
        "backtest": backtest,
        "cost_analysis": {
            "round_trip_cost_pct": round(round_trip_cost * 100, 4),
            "commission": TRADE_COST.get(market, TRADE_COST["A"])["commission"],
            "stamp_tax": TRADE_COST.get(market, TRADE_COST["A"])["stamp_tax"],
            "slippage": TRADE_COST.get(market, TRADE_COST["A"])["slippage"],
            "min_profit_needed": round(sig.current_price * round_trip_cost * 2, 4),
        },
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _signal_to_dict(sig: TSignal) -> dict:
    """TSignal转字典"""
    return {
        "code": sig.code,
        "name": sig.name,
        "market": sig.market,
        "current_price": sig.current_price,
        "signal_type": sig.signal_type,
        "signal_strength": sig.signal_strength,
        "buy_point": sig.buy_point,
        "sell_point": sig.sell_point,
        "suggested_t_shares": sig.suggested_t_shares,
        "expected_profit_pct": sig.expected_profit_pct,
        "atr": sig.atr,
        "atr_pct": sig.atr_pct,
        "indicators": sig.indicators,
        "reasoning": sig.reasoning,
        "trend": sig.indicators.get("trend", {}),
        "buy_weight": sig.indicators.get("buy_weight", 0),
        "sell_weight": sig.indicators.get("sell_weight", 0),
    }


# ============================================================
# 金字塔加仓方案
# ============================================================

def calc_pyramid_orders(current_price: float, atr: float,
                        total_t_capital: float, market: str = "A") -> dict:
    """
    金渐成金字塔加仓法：越跌买越多

    规则：
    - 下跌10%: 买1份（总做T资金的10%）
    - 下跌15%: 买2份（总做T资金的20%）
    - 下跌20%: 买3份（总做T资金的30%）
    - 下跌25%: 买4份（总做T资金的40%）
    """
    levels = [
        {"drop_pct": 10, "capital_pct": 10, "label": "小仓试探"},
        {"drop_pct": 15, "capital_pct": 20, "label": "逐步加仓"},
        {"drop_pct": 20, "capital_pct": 30, "label": "重点加仓"},
        {"drop_pct": 25, "capital_pct": 40, "label": "重仓抄底"},
    ]

    orders = []
    for lv in levels:
        target_price = round(current_price * (1 - lv["drop_pct"] / 100), 2)
        capital = total_t_capital * lv["capital_pct"] / 100

        if market == "A":
            shares = int(capital / target_price / 100) * 100
            shares = max(shares, 100)
        else:
            shares = int(capital / target_price)
            shares = max(shares, 1)

        actual_capital = round(shares * target_price, 2)
        cost_after = round(
            (total_t_capital * 0.7 + actual_capital) /  # 假设已有7成底仓
            (total_t_capital * 0.7 / current_price + shares), 2
        )

        orders.append({
            "level": lv["drop_pct"],
            "drop_pct": lv["drop_pct"],
            "target_price": target_price,
            "shares": shares,
            "capital": actual_capital,
            "label": lv["label"],
            "new_avg_cost": cost_after,
        })

    return {
        "current_price": current_price,
        "atr": round(atr, 2),
        "total_t_capital": total_t_capital,
        "orders": orders,
        "max_drawdown_budget": round(total_t_capital, 2),
    }


# ============================================================
# 做T方法论
# ============================================================

def get_t_philosophy() -> dict:
    """做T方法论说明（机构级增强版）"""
    return {
        "title": "金渐成做T体系 — 确定做T点位、做低持股成本（机构级）",
        "core_principle": "7成底仓做长线，3成做T降低成本，最终实现负成本持股",
        "methodology": [
            {
                "dimension": "T点确定 — 加权多指标共振 + 趋势过滤",
                "description": "加权评分确定方向（★★★=3,★★=2,★=1）+ 趋势过滤器避免逆势",
                "rules": [
                    "RSI < 30 超卖（★★），40-60 中性，> 70 超买（★★）",
                    "KDJ金叉/死叉（★★）为入场时机信号",
                    "MACD底背离/顶背离（★★★）为最强确认信号",
                    "布林带触及上下轨（★★），接近上下轨（★）",
                    "VWAP偏离度 > 2% 为日内偏离信号（★）",
                    "加权总分 >= 6 为强信号，>= 4 为中信号，>= 2 为弱信号",
                    "趋势过滤器：下降趋势买入信号降权2分，上升趋势卖出信号降权1分",
                ],
                "key_insight": "加权评分比简单计数更准确。MACD背离权重最高，因为它是趋势反转的领先指标。趋势过滤器避免在单边行情中逆势做T。",
            },
            {
                "dimension": "点位确定 — ATR自适应 + 滑点 + 利润门槛",
                "description": "基于ATR动态计算买卖点位，含滑点模型和最低利润门槛",
                "rules": [
                    "买入T点 = 当前价 × (1 - 滑点) - N × ATR",
                    "卖出T点 = 当前价 × (1 + 滑点) + N × ATR",
                    "N根据信号强度：强信号1.5，中信号1.0，弱信号0.5",
                    "最低利润门槛：预期利润必须 > 2倍round-trip交易成本",
                    "滑点假设：A股0.05%, 港股0.1%, 美股0.05%",
                ],
                "key_insight": "ATR自动适应波动率。滑点和利润门槛确保每次操作都有正期望值，避免频繁小额操作被手续费侵蚀。",
            },
            {
                "dimension": "仓位管理 — 底仓与做T仓分离",
                "description": "严格区分底仓（不参与做T）和做T仓（用于高抛低吸）",
                "rules": [
                    "底仓7成：长期持有，不做T",
                    "做T仓3成：用于日内/短线高抛低吸",
                    "强信号：用全部做T仓",
                    "中信号：用一半做T仓",
                    "弱信号：用1/3做T仓或观望",
                ],
                "key_insight": "底仓是你的核心资产，做T仓是你的降成本工具。绝不动摇底仓。",
            },
            {
                "dimension": "成本降低 — 金字塔加仓 + 倒金字塔卖出",
                "description": "越跌买越多摊低成本，越涨卖越多回收本金",
                "rules": [
                    "金字塔加仓：下跌10%买1份，15%买2份，20%买3份，25%买4份",
                    "倒金字塔卖出：上涨10%卖1份，15%卖2份，20%卖3份",
                    "每次做T盈利都降低持仓成本",
                    "目标：累计做T回收 > 初始投入 = 负成本",
                ],
                "key_insight": "不要错过任何一次基本面没有恶化、而是由恐慌情绪主导的下跌。",
            },
            {
                "dimension": "负成本持股 — 终极目标",
                "description": "通过反复做T，使持仓成本降为负数",
                "rules": [
                    "负成本公式：每股成本 = (累计买入 - 累计卖出) / 持股数",
                    "当累计卖出 > 累计买入时，成本为负",
                    "负成本后：股票相当于免费持有，只赚不赔",
                    "需要时间积累：通常需要数月到数年",
                ],
                "key_insight": "逢高适当减仓做低成本，就可以没有心理负担长期持有了。",
            },
        ],
        "risk_warnings": [
            "做T需要严格纪律，判断失误可能扩大亏损",
            "单边下跌行情中做T容易越做越套（趋势过滤器会降权但不完全阻止）",
            "频繁做T的手续费会侵蚀利润（利润门槛机制已自动过滤低利润信号）",
            "做T仓比例不宜超过总仓位的40%",
            "基本面恶化的股票不适合做T",
            "偏离MA20超过8%时信号可信度下降，需谨慎操作",
            "回测结果仅供参考，历史表现不代表未来收益",
        ],
    }
