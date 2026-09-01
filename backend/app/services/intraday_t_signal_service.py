"""日内实时做T信号引擎（腾讯控股 00700.HK 专用）

与 t_trading_service（日线级别）的区别：
- 数据驱动：用当日1分钟分时 + 实时五档盘口 + 5分钟K，而非日K
- 信号频率：日内多次触发，响应秒级行情变化
- 核心指标：日内VWAP、分时前高前低、盘口买卖失衡、分钟级量比

信号触发条件（三重确认，复用金渐成体系「最低利润门槛」理念）：
1. 位置确认：价格触及日内支撑（买入）/ 阻力（卖出）
   - 支撑 = min(日内VWAP, 分时前低, 5分钟K近低点)
   - 阻力 = max(日内VWAP, 分时前高, 5分钟K近高点)
2. 盘口确认：买盘强（imbalance>0，买入）/ 卖盘强（imbalance<0，卖出）
3. 量能确认：当前分钟量比 > 阈值（放量异动）

利润门槛（复用 t_trading_service.calc_round_trip_cost）：
- 预期买卖价差必须 ≥ min_profit_multiple × round_trip_cost（港股默认2倍）
- 港股round_trip_cost ≈ 0.16%（佣金万3双向 + 印花税千1.3 + 滑点0.1%双向）
- 故最低价差阈值约 0.32%

输出信号结构：
{
  signal_type: "buy"|"sell"|"hold",
  strength: "strong"|"medium"|"weak",
  buy_price, sell_price, current_price,
  expected_profit_pct, expected_profit_hkd,
  reasons: [触发原因列表],
  indicators: {vwap, support, resistance, imbalance, volume_ratio, spread_pct, ...},
  timestamp
}

遵循 CLAUDE.md：数据不可靠（分时/盘口为空）时不编造信号，返回 hold + 明确原因。
"""

import logging
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field

from app.services.t_trading_service import calc_round_trip_cost, TRADE_COST

logger = logging.getLogger(__name__)


# ============================================================
# 默认参数（可通过 config 覆盖）
# ============================================================

DEFAULT_CONFIG = {
    # 买卖价差阈值（%）：预期买卖价差低于此值不出信号
    "spread_threshold_pct": 0.30,
    # 前高前低回看分钟数（用于分时支撑压力）
    "swing_lookback": 30,
    # 量比异动阈值（当前分钟量 / 近N分钟均量）
    "volume_ratio_threshold": 1.5,
    "volume_ratio_lookback": 10,
    # 盘口失衡阈值（%）：|imbalance_pct| 超过此值才作为确认信号
    "imbalance_threshold_pct": 20,
    # 利润门槛倍数：预期利润 ≥ N × round_trip_cost
    "min_profit_multiple": 2,
    # 信号强度阈值（确认项数）
    "strong_confirm_count": 3,
    "medium_confirm_count": 2,
    # 止损线（%）：持仓浮亏超过此值触发止损提醒
    "stop_loss_pct": 2.0,
}


@dataclass
class IntradaySignal:
    """日内做T信号"""
    code: str
    name: str
    signal_type: str           # buy / sell / hold
    strength: str              # strong / medium / weak / neutral
    current_price: float
    buy_price: float
    sell_price: float
    expected_profit_pct: float
    expected_profit_hkd: float
    reasons: list = field(default_factory=list)
    indicators: dict = field(default_factory=dict)
    timestamp: str = ""
    bias: str = "neutral"          # bullish / bearish / neutral（即便 hold 也给出倾向）
    bias_text: str = ""            # 中文倾向描述，供前端常驻"操作参考"展示

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "name": self.name,
            "signal_type": self.signal_type,
            "strength": self.strength,
            "current_price": self.current_price,
            "buy_price": self.buy_price,
            "sell_price": self.sell_price,
            "expected_profit_pct": self.expected_profit_pct,
            "expected_profit_hkd": self.expected_profit_hkd,
            "reasons": self.reasons,
            "indicators": self.indicators,
            "timestamp": self.timestamp,
            "bias": self.bias,
            "bias_text": self.bias_text,
        }


# ============================================================
# 指标计算
# ============================================================

def calc_intraday_vwap(minute_klines: list[dict]) -> float:
    """日内成交量加权均价（VWAP）

    minute_klines: [{'time','price','avg','volume'}, ...]
    返回 VWAP，无数据返回 0
    """
    total_amount = 0.0
    total_vol = 0.0
    for k in minute_klines:
        p = k.get("price", 0)
        v = k.get("volume", 0)
        if p > 0 and v > 0:
            total_amount += p * v
            total_vol += v
    if total_vol == 0:
        # 退化为简单均价（量缺失时）
        prices = [k.get("price", 0) for k in minute_klines if k.get("price", 0) > 0]
        return round(sum(prices) / len(prices), 3) if prices else 0.0
    return round(total_amount / total_vol, 3)


def calc_swing_levels(minute_klines: list[dict], lookback: int = 30) -> dict:
    """分时前高前低（支撑压力）

    取最近 lookback 根分时的最高价/最低价。
    由于1分钟分时只有价格点（无高低），用窗口内 max/min 近似。
    """
    if not minute_klines:
        return {"recent_high": 0, "recent_low": 0, "day_high": 0, "day_low": 0}

    prices = [k.get("price", 0) for k in minute_klines if k.get("price", 0) > 0]
    if not prices:
        return {"recent_high": 0, "recent_low": 0, "day_high": 0, "day_low": 0}

    day_high = max(prices)
    day_low = min(prices)

    recent = prices[-lookback:] if len(prices) > lookback else prices
    recent_high = max(recent)
    recent_low = min(recent)

    return {
        "recent_high": round(recent_high, 3),
        "recent_low": round(recent_low, 3),
        "day_high": round(day_high, 3),
        "day_low": round(day_low, 3),
    }


def calc_minute_volume_ratio(minute_klines: list[dict], lookback: int = 10) -> float:
    """分钟级量比：最近一根分时量 / 前N根均量"""
    if len(minute_klines) < lookback + 1:
        return 1.0
    vols = [k.get("volume", 0) for k in minute_klines]
    recent_avg = sum(vols[-lookback - 1:-1]) / lookback if lookback > 0 else 0
    if recent_avg == 0:
        return 1.0
    return round(vols[-1] / recent_avg, 2)


def calc_support_resistance_from_5min(kline_5min: list[dict], lookback: int = 12) -> dict:
    """从5分钟K线算支撑压力（近 lookback 根=1小时）

    用近N根5分钟K的最低价/最高价作为短期支撑压力。
    """
    if not kline_5min:
        return {"support": 0, "resistance": 0}

    recent = kline_5min[-lookback:] if len(kline_5min) > lookback else kline_5min
    lows = [k.get("low", 0) for k in recent if k.get("low", 0) > 0]
    highs = [k.get("high", 0) for k in recent if k.get("high", 0) > 0]

    return {
        "support": round(min(lows), 3) if lows else 0,
        "resistance": round(max(highs), 3) if highs else 0,
    }


# ============================================================
# 信号判定主引擎
# ============================================================

def analyze_intraday_signal(
    code: str,
    name: str,
    minute_klines: list[dict],
    kline_5min: list[dict],
    order_book: Optional[dict],
    config: Optional[dict] = None,
) -> IntradaySignal:
    """分析日内做T信号

    Args:
        code: 股票代码（如 00700）
        name: 股票名称
        minute_klines: 当日1分钟分时（来自 TencentSource.get_minute_kline）
        kline_5min: 5分钟K线（来自 TencentSource.get_5min_kline）
        order_book: 五档盘口（来自 TencentSource.get_order_book）
        config: 参数覆盖（见 DEFAULT_CONFIG）

    Returns:
        IntradaySignal 信号对象
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    market = "HK"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # --- 数据完整性检查（遵循 CLAUDE.md：宁可空着）---
    if not minute_klines or not order_book:
        return IntradaySignal(
            code=code, name=name, signal_type="hold", strength="neutral",
            current_price=order_book.get("current_price", 0) if order_book else 0,
            buy_price=0, sell_price=0,
            expected_profit_pct=0, expected_profit_hkd=0,
            reasons=["数据不完整：分时或盘口为空，无法识别信号"],
            indicators={}, timestamp=now,
        )

    current_price = order_book.get("current_price", 0)
    if current_price <= 0:
        # 兜底用分时最后一根价格
        current_price = minute_klines[-1].get("price", 0) if minute_klines else 0
    if current_price <= 0:
        return IntradaySignal(
            code=code, name=name, signal_type="hold", strength="neutral",
            current_price=0, buy_price=0, sell_price=0,
            expected_profit_pct=0, expected_profit_hkd=0,
            reasons=["当前价格异常为0"], indicators={}, timestamp=now,
        )

    # --- 计算指标 ---
    vwap = calc_intraday_vwap(minute_klines)
    swing = calc_swing_levels(minute_klines, cfg["swing_lookback"])
    vol_ratio = calc_minute_volume_ratio(minute_klines, cfg["volume_ratio_lookback"])
    sr_5min = calc_support_resistance_from_5min(kline_5min)

    # 盘口指标
    spread_pct = order_book.get("spread_pct", 0)
    imbalance = order_book.get("imbalance", 0)
    imbalance_pct = order_book.get("imbalance_pct", 0)
    mid_price = order_book.get("mid_price", current_price)

    # --- 综合支撑/阻力（取各源的最近价位）---
    # 支撑 = 下方最近的价位（VWAP / 分时前低 / 5分钟支撑）
    below_levels = [lv for lv in [vwap, swing["recent_low"], sr_5min["support"]] if lv > 0 and lv < current_price]
    above_levels = [lv for lv in [vwap, swing["recent_high"], sr_5min["resistance"]] if lv > 0 and lv > current_price]

    nearest_support = max(below_levels) if below_levels else swing["recent_low"]
    nearest_resistance = min(above_levels) if above_levels else swing["recent_high"]

    # --- 位置确认：价格相对支撑/阻力的位置 ---
    # 买入位置：当前价接近或跌破支撑（距支撑 < 0.3%）
    buy_position_score = 0
    if nearest_support > 0:
        dist_to_support_pct = (current_price - nearest_support) / current_price * 100
        if dist_to_support_pct <= 0:  # 跌破支撑
            buy_position_score = 2
        elif dist_to_support_pct < 0.3:  # 接近支撑
            buy_position_score = 1

    # 卖出位置：当前价接近或突破阻力
    sell_position_score = 0
    if nearest_resistance > 0:
        dist_to_resistance_pct = (nearest_resistance - current_price) / current_price * 100
        if dist_to_resistance_pct <= 0:  # 突破阻力
            sell_position_score = 2
        elif dist_to_resistance_pct < 0.3:  # 接近阻力
            sell_position_score = 1

    # --- 盘口确认 ---
    buy_orderbook_score = 0
    sell_orderbook_score = 0
    if imbalance_pct > cfg["imbalance_threshold_pct"]:
        buy_orderbook_score = 1  # 买盘强
    elif imbalance_pct < -cfg["imbalance_threshold_pct"]:
        sell_orderbook_score = 1  # 卖盘强

    # --- 量能确认 ---
    buy_volume_score = 0
    sell_volume_score = 0
    if vol_ratio >= cfg["volume_ratio_threshold"]:
        # 放量方向跟随位置（放量+低位=买入确认，放量+高位=卖出确认）
        if buy_position_score > 0:
            buy_volume_score = 1
        elif sell_position_score > 0:
            sell_volume_score = 1

    # --- 加权确认数 ---
    buy_confirm = buy_position_score + buy_orderbook_score + buy_volume_score
    sell_confirm = sell_position_score + sell_orderbook_score + sell_volume_score

    # --- 方向判定 ---
    if buy_confirm >= cfg["strong_confirm_count"]:
        signal_type, strength = "buy", "strong"
    elif buy_confirm >= cfg["medium_confirm_count"]:
        signal_type, strength = "buy", "medium"
    elif buy_confirm >= 1 and sell_confirm == 0:
        signal_type, strength = "buy", "weak"
    elif sell_confirm >= cfg["strong_confirm_count"]:
        signal_type, strength = "sell", "strong"
    elif sell_confirm >= cfg["medium_confirm_count"]:
        signal_type, strength = "sell", "medium"
    elif sell_confirm >= 1 and buy_confirm == 0:
        signal_type, strength = "sell", "weak"
    else:
        signal_type, strength = "hold", "neutral"

    # --- 点位确定（含滑点，复用 t_trading_service 费率模型）---
    slippage = TRADE_COST["HK"]["slippage"]
    round_trip_cost = calc_round_trip_cost("HK")

    if signal_type == "buy":
        # 买入价：支撑位（或当前价-滑点），卖出价：阻力位（或当前价+ATR近似）
        buy_price = nearest_support if nearest_support > 0 else round(current_price * (1 - slippage), 3)
        sell_price = nearest_resistance if nearest_resistance > buy_price else round(current_price * (1 + slippage) + current_price * 0.005, 3)
    elif signal_type == "sell":
        # 先卖后买：卖出价=阻力位，买回价=支撑位
        sell_price = nearest_resistance if nearest_resistance > 0 else round(current_price * (1 + slippage), 3)
        buy_price = nearest_support if nearest_support < sell_price else round(current_price * (1 - slippage) - current_price * 0.005, 3)
    else:
        buy_price = nearest_support if nearest_support > 0 else round(current_price * (1 - slippage), 3)
        sell_price = nearest_resistance if nearest_resistance > 0 else round(current_price * (1 + slippage), 3)

    # --- 利润门槛（复用金渐成体系：预期利润 ≥ N × round_trip_cost）---
    price_spread = abs(sell_price - buy_price)
    gross_profit_pct = round(price_spread / current_price * 100, 3) if current_price > 0 else 0
    net_profit_pct = round(gross_profit_pct - round_trip_cost * 100, 3)
    min_profit_pct = round(round_trip_cost * 100 * cfg["min_profit_multiple"], 3)

    if signal_type != "hold" and gross_profit_pct < min_profit_pct:
        # 利润不足以覆盖门槛，降级为 hold
        signal_type, strength = "hold", "neutral"
        reasons_warning = f"预期价差{gross_profit_pct}% < 门槛{min_profit_pct}%（{cfg['min_profit_multiple']}倍round-trip成本），观望"
    else:
        reasons_warning = ""

    # --- 信号理由 ---
    reasons = []
    if buy_position_score > 0:
        reasons.append(f"[位置] 价格接近日内支撑 HK${nearest_support:.2f}（偏离{dist_to_support_pct:.2f}%）")
    if sell_position_score > 0:
        reasons.append(f"[位置] 价格接近日内阻力 HK${nearest_resistance:.2f}（偏离{dist_to_resistance_pct:.2f}%）")
    if buy_orderbook_score > 0:
        reasons.append(f"[盘口] 买盘强，失衡{imbalance_pct:+.1f}%（买盘总量{order_book.get('total_bid_volume',0):.0f} > 卖盘{order_book.get('total_ask_volume',0):.0f}）")
    if sell_orderbook_score > 0:
        reasons.append(f"[盘口] 卖盘强，失衡{imbalance_pct:+.1f}%（卖盘总量{order_book.get('total_ask_volume',0):.0f} > 买盘{order_book.get('total_bid_volume',0):.0f}）")
    if buy_volume_score > 0 or sell_volume_score > 0:
        reasons.append(f"[量能] 分钟量比{vol_ratio:.2f}（阈值{cfg['volume_ratio_threshold']}），放量异动")
    if vwap > 0:
        vwap_dev = (current_price - vwap) / vwap * 100
        reasons.append(f"[VWAP] 日内均价HK${vwap:.2f}，当前偏离{vwap_dev:+.2f}%")
    if reasons_warning:
        reasons.append(f"[门槛] {reasons_warning}")
    if not reasons:
        reasons.append("无明确信号，价格在支撑阻力间震荡，建议观望")

    # --- 预期收益 ---
    # 港股1手=100股，做T通常按手计算。expected_profit_hkd 按100股估算
    expected_profit_hkd = round(price_spread * 100 - current_price * 100 * round_trip_cost, 2) if signal_type != "hold" else 0

    # --- 倾向判断（即便 hold 也给出偏多/偏空，供 UI 常驻"操作参考"）---
    if signal_type == "buy":
        bias, bias_text = "bullish", "偏多（触发买入信号）"
    elif signal_type == "sell":
        bias, bias_text = "bearish", "偏空（触发卖出信号）"
    elif imbalance_pct > 10:
        bias, bias_text = "bullish", "偏多（买盘占优）"
    elif imbalance_pct < -10:
        bias, bias_text = "bearish", "偏空（卖盘占优）"
    elif current_price > 0 and vwap > 0 and current_price < vwap:
        bias, bias_text = "bullish", "偏多（价低于VWAP，逢低关注）"
    elif current_price > 0 and vwap > 0 and current_price > vwap:
        bias, bias_text = "bearish", "偏空（价高于VWAP，逢高关注）"
    else:
        bias, bias_text = "neutral", "中性（震荡）"

    indicators = {
        "vwap": vwap,
        "nearest_support": nearest_support,
        "nearest_resistance": nearest_resistance,
        "swing": swing,
        "support_5min": sr_5min["support"],
        "resistance_5min": sr_5min["resistance"],
        "volume_ratio": vol_ratio,
        "imbalance_pct": imbalance_pct,
        "imbalance": imbalance,
        "spread_pct": spread_pct,
        "spread": order_book.get("spread", 0),
        "mid_price": mid_price,
        "round_trip_cost_pct": round(round_trip_cost * 100, 4),
        "min_profit_threshold_pct": min_profit_pct,
        "buy_confirm": buy_confirm,
        "sell_confirm": sell_confirm,
    }

    return IntradaySignal(
        code=code, name=name, signal_type=signal_type, strength=strength,
        current_price=round(current_price, 3),
        buy_price=round(buy_price, 3), sell_price=round(sell_price, 3),
        expected_profit_pct=net_profit_pct,
        expected_profit_hkd=expected_profit_hkd,
        reasons=reasons, indicators=indicators, timestamp=now,
        bias=bias, bias_text=bias_text,
    )
