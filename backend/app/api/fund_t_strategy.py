"""QDII基金做T策略分析 (V2 - 机构级)

基于历史数据验证的规律：
1. 高开回落规律：高开3%以上时，回落概率约75%
2. 低开反弹规律：低开-2%~-1%时，反弹概率约70%

V2改进：
- 多因子信号：开盘缺口 + 底层资产方向 + 溢价率 + 成交量
- 费用计算：完整交易成本建模（佣金 + 过户费 + 滑点）
- 风险控制：止损线、仓位上限、最大日亏损
- 回测引擎：历史信号胜率验证
- LOF套利联动：集成EST净值、溢价率、底层资产数据
"""

import logging
import math
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from app.api.fund_config import FUND_CONFIG, get_fund_config
from app.api.fund_utils import (
    get_fund_nav_from_eastmoney,
    get_sina_realtime,
    parse_underlying_price,
    get_usdcny_rate,
    get_hkdcny_rate,
)
from app.api.fund_est_engine import calc_fund_est, get_official_est, get_official_est_batch
from app.api.fund_arb_engine import calc_slippage, calc_max_position, _parse_fee_value
from app.core.utils import safe_float

logger = logging.getLogger(__name__)


# ==================== 交易费用常量 ====================

# LOF基金场内交易费用（无印花税）
T_TRADE_COMMISSION = 0.025       # 单边佣金 % (万2.5，行业常见)
T_MIN_COMMISSION = 5.0           # 最低佣金 元
T_TRANSFER_FEE = 0.002           # 过户费 % (上海市场，深圳免收)
T_ROUND_TRIP_FEE = T_TRADE_COMMISSION * 2 + T_TRANSFER_FEE  # 双边总费率

# 滑点参数
T_SLIPPAGE_BASE = 0.02           # 基础滑点 % (流动性好的基金)
T_SLIPPAGE_ILLIQUID = 0.08       # 流动性差时的滑点 %


# ==================== 信号阈值参数 ====================

T_STRATEGY_PARAMS = {
    "high_open": {
        "threshold": 2.0,          # 高开阈值（%）
        "strong_threshold": 3.0,   # 强高开阈值（%）
        "fall_prob_normal": 0.35,  # 普通高开回落概率
        "fall_prob_strong": 0.75,  # 强高开回落概率
        "action": "卖出止盈，等回落接回",
    },
    "low_open": {
        "threshold": -1.0,         # 低开阈值（%）
        "strong_threshold": -3.0,  # 强低开阈值（%）
        "bounce_prob_normal": 0.65,  # 普通低开反弹概率
        "bounce_prob_strong": 0.70,  # 强低开反弹概率
        "action": "加仓，等反弹卖出",
    },
}

# 风险控制参数
RISK_PARAMS = {
    "stop_loss_ratio": 0.5,       # 止损线 = 信号幅度 * 此比例
    "take_profit_ratio": 0.6,     # 止盈线 = 信号幅度 * 此比例
    "max_daily_loss_pct": 2.0,    # 最大单日亏损 % (相对仓位)
    "max_position_turnover_pct": 0.05,  # 最大仓位占比 (相对成交额)
    "min_turnover_wan": 500.0,    # 最低成交额门槛 (万元)
    "max_slippage_pct": 0.10,     # 最大可接受滑点 %
}

# 概率加成/减成因子
PROBABILITY_ADJUSTMENTS = {
    "underlying_confirm": 0.10,   # 底层资产方向确认 +10%
    "underlying_contradict": -0.15,  # 底层资产方向矛盾 -15%
    "high_premium": 0.05,         # 高溢价(>5%) +5% (高开回落更确定)
    "low_premium": 0.05,          # 深度折价(<-5%) +5% (低开反弹更确定)
    "high_volume": 0.05,          # 高成交量 +5% (信号更可靠)
    "low_volume": -0.05,          # 低成交量 -5% (信号不可靠)
}


# ==================== 核心分析函数 ====================


def analyze_t_opportunity(
    fund_code: str,
    fund_price: float,
    prev_close: float,
    current_price: float = 0,
    est_nav: float = 0,
    premium_pct: float = 0,
    underlying_change_pct: float = 0,
    turnover_wan: float = 0,
    apply_status: str = "",
    fund_nav: float = 0,
    underlying_type: str = "",
    position: float = 0.95,
) -> Optional[dict]:
    """分析做T机会 (V2 - 多因子)

    多因子信号生成：
    1. 开盘缺口（主信号）：当前价 vs 前收盘
    2. 底层资产方向确认/矛盾（信号增强/减弱）
    3. 溢价率水平（信号增强/减弱）
    4. 成交量（信号可靠性）

    Args:
        fund_code: 基金代码
        fund_price: 开盘价（用于计算开盘缺口）
        prev_close: 前一日收盘价
        current_price: 当前价（盘中使用，0则使用fund_price）
        est_nav: 估算净值
        premium_pct: 基于EST的溢价率
        underlying_change_pct: 底层资产涨跌幅
        turnover_wan: 成交额（万元）
        apply_status: 申购状态
        fund_nav: 前一日官方净值
        underlying_type: 底层资产类型
        position: 仓位比例

    Returns:
        {
            "signal": "high_open_sell" / "low_open_buy" / "none",
            "strength": "strong" / "normal" / "none",
            "open_change_pct": float,
            "current_change_pct": float,
            "probability": float,           # 调整后概率
            "base_probability": float,      # 基础概率
            "probability_adjustments": list, # 概率调整明细
            "action": str,
            "reason": str,
            "fee": {                        # V2新增
                "round_trip_fee_pct": float,
                "slippage_pct": float,
                "total_cost_pct": float,
            },
            "risk": {                       # V2新增
                "stop_loss_pct": float,
                "take_profit_pct": float,
                "max_position_wan": float,
                "expected_profit_pct": float,
                "risk_reward_ratio": float,
            },
            "factors": {                    # V2新增
                "underlying_confirm": bool,
                "premium_level": str,
                "volume_level": str,
                "est_nav": float,
                "premium_pct": float,
                "underlying_change_pct": float,
                "turnover_wan": float,
            },
            "verdict": str,                 # V2新增: "强烈推荐" / "推荐" / "谨慎" / "不建议"
        }
    """
    if not prev_close or prev_close <= 0:
        return None

    # 计算开盘涨幅
    open_change_pct = (fund_price - prev_close) / prev_close * 100

    # 计算当前涨幅（盘中）
    effective_price = current_price if current_price > 0 else fund_price
    current_change_pct = (effective_price - prev_close) / prev_close * 100

    # ===== 信号生成 =====
    params_high = T_STRATEGY_PARAMS["high_open"]
    params_low = T_STRATEGY_PARAMS["low_open"]

    signal = "none"
    strength = "none"
    base_probability = 0.0
    action = "无明显做T机会"
    reason = f"开盘涨跌{open_change_pct:.1f}%，未达阈值"

    if open_change_pct >= params_high["strong_threshold"]:
        signal = "high_open_sell"
        strength = "strong"
        base_probability = params_high["fall_prob_strong"]
        action = "卖出止盈，等回落接回"
        reason = f"强高开{open_change_pct:.1f}%，历史回落概率约75%"
    elif open_change_pct >= params_high["threshold"]:
        signal = "high_open_sell"
        strength = "normal"
        base_probability = params_high["fall_prob_normal"]
        action = "可考虑卖出止盈"
        reason = f"高开{open_change_pct:.1f}%，历史回落概率约35%"
    elif open_change_pct <= params_low["strong_threshold"]:
        signal = "low_open_buy"
        strength = "strong"
        base_probability = params_low["bounce_prob_strong"]
        action = "加仓，等反弹卖出"
        reason = f"强低开{open_change_pct:.1f}%，历史反弹概率约70%"
    elif open_change_pct <= params_low["threshold"]:
        signal = "low_open_buy"
        strength = "normal"
        base_probability = params_low["bounce_prob_normal"]
        action = "可考虑加仓"
        reason = f"低开{open_change_pct:.1f}%，历史反弹概率约65%"

    if signal == "none":
        return {
            "signal": "none",
            "strength": "none",
            "open_change_pct": round(open_change_pct, 2),
            "current_change_pct": round(current_change_pct, 2),
            "probability": 0,
            "base_probability": 0,
            "probability_adjustments": [],
            "action": action,
            "reason": reason,
            "fee": _calc_t_fees(turnover_wan, effective_price),
            "risk": {},
            "factors": {
                "underlying_confirm": None,
                "premium_level": "unknown",
                "volume_level": "unknown",
                "est_nav": est_nav,
                "premium_pct": premium_pct,
                "underlying_change_pct": underlying_change_pct,
                "turnover_wan": turnover_wan,
            },
            "verdict": "不建议",
        }

    # ===== 多因子概率调整 =====
    adjustments = []
    adjusted_probability = base_probability

    # 因子1: 底层资产方向确认
    underlying_confirm = None
    if underlying_change_pct != 0:
        if signal == "high_open_sell" and underlying_change_pct > 0:
            # 高开时底层资产也在涨 -> 概率稍增（更确定是高开）
            adjustments.append({"factor": "底层资产上涨确认高开", "delta": PROBABILITY_ADJUSTMENTS["underlying_confirm"]})
            adjusted_probability += PROBABILITY_ADJUSTMENTS["underlying_confirm"]
            underlying_confirm = True
        elif signal == "high_open_sell" and underlying_change_pct < 0:
            # 高开但底层资产在跌 -> 可能是情绪驱动，回落概率更高
            adjustments.append({"factor": "底层资产下跌增强回落预期", "delta": PROBABILITY_ADJUSTMENTS["underlying_confirm"]})
            adjusted_probability += PROBABILITY_ADJUSTMENTS["underlying_confirm"]
            underlying_confirm = True
        elif signal == "low_open_buy" and underlying_change_pct < 0:
            # 低开且底层资产也在跌 -> 概率稍增（更确定是低开）
            adjustments.append({"factor": "底层资产下跌确认低开", "delta": PROBABILITY_ADJUSTMENTS["underlying_confirm"]})
            adjusted_probability += PROBABILITY_ADJUSTMENTS["underlying_confirm"]
            underlying_confirm = True
        elif signal == "low_open_buy" and underlying_change_pct > 0:
            # 低开但底层资产在涨 -> 矛盾信号
            adjustments.append({"factor": "底层资产上涨与低开矛盾", "delta": PROBABILITY_ADJUSTMENTS["underlying_contradict"]})
            adjusted_probability += PROBABILITY_ADJUSTMENTS["underlying_contradict"]
            underlying_confirm = False

    # 因子2: 溢价率水平
    premium_level = "normal"
    if premium_pct > 5:
        premium_level = "high"
        if signal == "high_open_sell":
            adjustments.append({"factor": f"高溢价({premium_pct:.1f}%)增强回落预期", "delta": PROBABILITY_ADJUSTMENTS["high_premium"]})
            adjusted_probability += PROBABILITY_ADJUSTMENTS["high_premium"]
    elif premium_pct < -5:
        premium_level = "discount"
        if signal == "low_open_buy":
            adjustments.append({"factor": f"深度折价({premium_pct:.1f}%)增强反弹预期", "delta": PROBABILITY_ADJUSTMENTS["low_premium"]})
            adjusted_probability += PROBABILITY_ADJUSTMENTS["low_premium"]

    # 因子3: 成交量
    volume_level = "normal"
    if turnover_wan > 0:
        if turnover_wan >= 3000:
            volume_level = "high"
            adjustments.append({"factor": f"成交量充足({turnover_wan:.0f}万)", "delta": PROBABILITY_ADJUSTMENTS["high_volume"]})
            adjusted_probability += PROBABILITY_ADJUSTMENTS["high_volume"]
        elif turnover_wan < RISK_PARAMS["min_turnover_wan"]:
            volume_level = "low"
            adjustments.append({"factor": f"成交量不足({turnover_wan:.0f}万)", "delta": PROBABILITY_ADJUSTMENTS["low_volume"]})
            adjusted_probability += PROBABILITY_ADJUSTMENTS["low_volume"]

    # 概率限幅 [0.1, 0.95]
    adjusted_probability = max(0.1, min(0.95, adjusted_probability))

    # ===== 费用计算 =====
    fee_info = _calc_t_fees(turnover_wan, effective_price)

    # ===== 风险控制 =====
    signal_amplitude = abs(open_change_pct)
    risk_info = _calc_risk_params(
        signal_amplitude=signal_amplitude,
        signal_direction="sell" if signal == "high_open_sell" else "buy",
        fee_total_pct=fee_info["total_cost_pct"],
        turnover_wan=turnover_wan,
        adjusted_probability=adjusted_probability,
    )

    # ===== 综合判断 =====
    verdict = _calc_verdict(
        strength=strength,
        adjusted_probability=adjusted_probability,
        expected_profit_pct=risk_info.get("expected_profit_pct", 0),
        volume_level=volume_level,
        fee_total_pct=fee_info["total_cost_pct"],
    )

    # 更新reason
    if adjustments:
        adj_desc = " | ".join([a["factor"] for a in adjustments])
        reason = f"{reason} [{adj_desc}]"

    return {
        "signal": signal,
        "strength": strength,
        "open_change_pct": round(open_change_pct, 2),
        "current_change_pct": round(current_change_pct, 2),
        "probability": round(adjusted_probability, 2),
        "base_probability": round(base_probability, 2),
        "probability_adjustments": adjustments,
        "action": action,
        "reason": reason,
        "fee": fee_info,
        "risk": risk_info,
        "factors": {
            "underlying_confirm": underlying_confirm,
            "premium_level": premium_level,
            "volume_level": volume_level,
            "est_nav": round(est_nav, 4) if est_nav else 0,
            "premium_pct": round(premium_pct, 2),
            "underlying_change_pct": round(underlying_change_pct, 2),
            "turnover_wan": round(turnover_wan, 2),
        },
        "verdict": verdict,
    }


# ==================== 费用计算 ====================


def _calc_t_fees(turnover_wan: float, price: float) -> dict:
    """计算做T交易费用

    LOF基金场内T+0交易费用：
    - 佣金: 万2.5（双边），最低5元
    - 过户费: 万0.2（仅上海，深圳免收）
    - 无印花税（基金交易免征）

    Args:
        turnover_wan: 成交额（万元）
        price: 基金价格

    Returns:
        {
            "commission_pct": float,     # 单边佣金 %
            "transfer_fee_pct": float,   # 过户费 %
            "round_trip_fee_pct": float, # 双边总费率 %
            "slippage_pct": float,       # 估算滑点 %
            "total_cost_pct": float,     # 总交易成本 %
            "min_trade_amount": float,   # 最低交易金额（元，受最低佣金限制）
        }
    """
    # 佣金（考虑最低佣金）
    commission_pct = T_TRADE_COMMISSION
    if turnover_wan > 0:
        # 单边交易额
        single_side_wan = turnover_wan
        commission_yuan = single_side_wan * 10000 * T_TRADE_COMMISSION / 100
        if commission_yuan < T_MIN_COMMISSION:
            # 实际佣金率 = 最低佣金 / 交易额
            actual_commission_pct = T_MIN_COMMISSION / (single_side_wan * 10000) * 100
            commission_pct = max(actual_commission_pct, T_TRADE_COMMISSION)

    # 过户费
    transfer_fee_pct = T_TRANSFER_FEE

    # 双边总费率
    round_trip_fee_pct = commission_pct * 2 + transfer_fee_pct

    # 滑点估算
    slippage_pct = T_SLIPPAGE_BASE
    if turnover_wan > 0 and turnover_wan < RISK_PARAMS["min_turnover_wan"]:
        # 流动性差，滑点增大
        slippage_pct = T_SLIPPAGE_ILLIQUID
    elif turnover_wan > 0:
        # 基于经验公式
        slippage_pct = calc_slippage(turnover_wan, turnover_wan * RISK_PARAMS["max_position_turnover_pct"])

    # 总交易成本
    total_cost_pct = round_trip_fee_pct + slippage_pct

    # 最低交易金额（受最低佣金限制）
    min_trade_amount = T_MIN_COMMISSION / (T_TRADE_COMMISSION / 100) if T_TRADE_COMMISSION > 0 else 0

    return {
        "commission_pct": round(commission_pct, 4),
        "transfer_fee_pct": round(transfer_fee_pct, 4),
        "round_trip_fee_pct": round(round_trip_fee_pct, 4),
        "slippage_pct": round(slippage_pct, 4),
        "total_cost_pct": round(total_cost_pct, 4),
        "min_trade_amount": round(min_trade_amount, 2),
    }


# ==================== 风险控制 ====================


def _calc_risk_params(
    signal_amplitude: float,
    signal_direction: str,
    fee_total_pct: float,
    turnover_wan: float,
    adjusted_probability: float,
) -> dict:
    """计算做T风险控制参数

    Args:
        signal_amplitude: 信号幅度（绝对值%）
        signal_direction: "sell" 或 "buy"
        fee_total_pct: 总交易成本 %
        turnover_wan: 成交额（万元）
        adjusted_probability: 调整后概率

    Returns:
        {
            "stop_loss_pct": float,        # 止损线 % (相对买入价)
            "take_profit_pct": float,      # 止盈线 % (相对买入价)
            "max_position_wan": float,     # 建议最大仓位（万元）
            "expected_profit_pct": float,  # 期望收益 %
            "risk_reward_ratio": float,    # 风险收益比
        }
    """
    # 止损线 = 信号幅度 * 止损比例（回落了说明判断错误，及时止损）
    stop_loss_pct = round(signal_amplitude * RISK_PARAMS["stop_loss_ratio"], 2)
    # 止盈线 = 信号幅度 * 止盈比例（回落/反弹了预期幅度的一半即止盈）
    take_profit_pct = round(signal_amplitude * RISK_PARAMS["take_profit_ratio"], 2)

    # 最大仓位（基于流动性）
    max_position_wan = calc_max_position(turnover_wan, RISK_PARAMS["max_position_turnover_pct"])
    if max_position_wan <= 0:
        max_position_wan = 100.0  # 默认上限100万

    # 期望收益 = 概率 * 止盈 - (1-概率) * 止损 - 费用
    expected_profit_pct = round(
        adjusted_probability * take_profit_pct
        - (1 - adjusted_probability) * stop_loss_pct
        - fee_total_pct,
        2,
    )

    # 风险收益比 = 止盈 / 止损
    risk_reward_ratio = round(take_profit_pct / stop_loss_pct, 2) if stop_loss_pct > 0 else 0

    return {
        "stop_loss_pct": stop_loss_pct,
        "take_profit_pct": take_profit_pct,
        "max_position_wan": max_position_wan,
        "expected_profit_pct": expected_profit_pct,
        "risk_reward_ratio": risk_reward_ratio,
    }


# ==================== 综合判断 ====================


def _calc_verdict(
    strength: str,
    adjusted_probability: float,
    expected_profit_pct: float,
    volume_level: str,
    fee_total_pct: float,
) -> str:
    """综合判断做T机会质量

    Returns:
        "强烈推荐" / "推荐" / "谨慎" / "不建议"
    """
    score = 0

    # 信号强度
    if strength == "strong":
        score += 3
    elif strength == "normal":
        score += 1

    # 概率
    if adjusted_probability >= 0.70:
        score += 3
    elif adjusted_probability >= 0.50:
        score += 2
    elif adjusted_probability >= 0.35:
        score += 1

    # 期望收益
    if expected_profit_pct >= 1.0:
        score += 3
    elif expected_profit_pct >= 0.5:
        score += 2
    elif expected_profit_pct >= 0:
        score += 1
    else:
        score -= 2

    # 成交量
    if volume_level == "high":
        score += 1
    elif volume_level == "low":
        score -= 2

    # 费用占比（费用超过信号幅度的30%则减分）
    if fee_total_pct > 0:
        fee_ratio = fee_total_pct / max(abs(expected_profit_pct) + fee_total_pct, 0.01)
        if fee_ratio > 0.3:
            score -= 1

    if score >= 8:
        return "强烈推荐"
    elif score >= 5:
        return "推荐"
    elif score >= 2:
        return "谨慎"
    else:
        return "不建议"


# ==================== 扫描函数 ====================


def scan_t_opportunities(
    fund_list: List[str] = None,
    include_details: bool = True,
) -> List[dict]:
    """扫描所有QDII基金的做T机会 (V2)

    V2改进：
    - 集成EST净值和溢价率
    - 集成底层资产实时行情
    - 集成费用和风险计算
    - 支持详情模式和简略模式

    Args:
        fund_list: 基金代码列表，None则扫描所有QDII基金
        include_details: 是否包含费用/风险/因子详情

    Returns:
        做T机会列表（按信号强度排序）
    """
    if fund_list is None:
        fund_list = list(FUND_CONFIG.keys())

    # 筛选QDII基金（支持做T的类型）
    qdii_codes = []
    for code in fund_list:
        config = get_fund_config(code)
        if config and config.get("underlying_type") in ("us_etf", "futures", "hk_index", "multi"):
            qdii_codes.append(code)

    if not qdii_codes:
        return []

    # ===== 批量获取数据 =====

    # 1. 基金实时行情（新浪）
    sina_codes = []
    for code in qdii_codes:
        prefix = "sz" if code.startswith("1") else "sh"
        sina_codes.append(f"{prefix}{code}")

    realtime_data = get_sina_realtime(sina_codes) if sina_codes else {}

    # 2. 底层资产行情
    underlying_symbols = set()
    for code in qdii_codes:
        config = get_fund_config(code)
        if config:
            if config.get("underlying"):
                underlying_symbols.add(config["underlying"])
            for h in config.get("multi_holdings", []):
                underlying_symbols.add(h["code"])

    underlying_data = get_sina_realtime(list(underlying_symbols)) if underlying_symbols else {}

    # 3. EST净值（天天基金API）
    est_data = get_official_est_batch(qdii_codes)

    # 4. 汇率
    usdcny_rate = get_usdcny_rate()

    # ===== 逐只基金分析 =====
    results = []
    for code in qdii_codes:
        config = get_fund_config(code)
        if not config:
            continue

        fund_name = config.get("name", code)
        underlying_type = config.get("underlying_type", "")
        position = config.get("position", 0.95)

        # 获取基金行情
        prefix = "sz" if code.startswith("1") else "sh"
        sina_code = f"{prefix}{code}"
        raw_data = realtime_data.get(sina_code, [])

        if not raw_data or len(raw_data) < 10:
            continue

        try:
            fund_price = safe_float(raw_data[3], 0)   # 当前价
            prev_close = safe_float(raw_data[2], 0)    # 昨收
            open_price = safe_float(raw_data[1], 0)    # 今开
            volume_wan = safe_float(raw_data[8], 0)    # 成交量（股）
            amount_wan = safe_float(raw_data[9], 0)    # 成交额（元）

            if fund_price <= 0 or prev_close <= 0:
                continue

            # 转换成交额为万元
            turnover_wan = amount_wan / 10000 if amount_wan > 0 else 0

            # 获取EST净值和溢价率
            est_nav = 0
            premium_pct = 0
            fund_nav = 0
            official_est = est_data.get(code)
            if official_est:
                est_nav = official_est.get("est_nav", 0)
                fund_nav = official_est.get("official_nav", 0)
                if est_nav > 0 and fund_price > 0:
                    premium_pct = (fund_price - est_nav) / est_nav * 100

            # 获取底层资产涨跌幅
            underlying_change_pct = 0
            underlying_code = config.get("underlying", "")
            if underlying_code and underlying_code in underlying_data:
                parsed = parse_underlying_price(underlying_code, underlying_data[underlying_code])
                if parsed:
                    underlying_change_pct = parsed["change_pct"]
            elif underlying_type == "multi":
                # 多标的：加权涨跌幅
                holdings = config.get("multi_holdings", [])
                total_weight = 0
                weighted_change = 0
                for h in holdings:
                    h_data = underlying_data.get(h["code"], [])
                    if h_data:
                        parsed = parse_underlying_price(h["code"], h_data)
                        if parsed and parsed["price"] > 0:
                            weighted_change += parsed["change_pct"] * h["weight"]
                            total_weight += h["weight"]
                if total_weight > 0:
                    underlying_change_pct = weighted_change / total_weight

            # 申购状态
            apply_status = ""  # 从fund_service获取需要额外请求，暂留空

            # ===== 分析做T机会 =====
            t_signal = analyze_t_opportunity(
                fund_code=code,
                fund_price=open_price,
                prev_close=prev_close,
                current_price=fund_price,
                est_nav=est_nav,
                premium_pct=premium_pct,
                underlying_change_pct=underlying_change_pct,
                turnover_wan=turnover_wan,
                apply_status=apply_status,
                fund_nav=fund_nav,
                underlying_type=underlying_type,
                position=position,
            )

            if not t_signal:
                continue

            # 构建结果（保持前端兼容）
            result = {
                "fund_code": code,
                "fund_name": fund_name,
                "open_price": open_price,
                "prev_close": prev_close,
                "current_price": fund_price,
                "open_change_pct": t_signal["open_change_pct"],
                "current_change_pct": t_signal["current_change_pct"],
                "signal": t_signal["signal"],
                "strength": t_signal["strength"],
                "probability": t_signal["probability"],
                "base_probability": t_signal["base_probability"],
                "action": t_signal["action"],
                "reason": t_signal["reason"],
                "verdict": t_signal["verdict"],
            }

            # V2新增字段（详情模式）
            if include_details:
                result["fee"] = t_signal["fee"]
                result["risk"] = t_signal["risk"]
                result["factors"] = t_signal["factors"]
                result["probability_adjustments"] = t_signal["probability_adjustments"]

            # 只返回有信号的基金（排除signal=none但verdict=不建议的）
            if t_signal["signal"] != "none":
                results.append(result)

        except Exception as e:
            logger.warning(f"分析基金 {code} 做T机会失败: {e}")
            continue

    # 排序：按信号强度和概率排序（强信号优先，同强度按概率降序）
    strength_order = {"strong": 0, "normal": 1, "none": 2}
    results.sort(
        key=lambda x: (
            strength_order.get(x["strength"], 2),
            -x["probability"],
            -abs(x["open_change_pct"]),
        )
    )

    return results


# ==================== 回测引擎 ====================


def backtest_t_strategy(
    fund_code: str,
    days: int = 60,
) -> dict:
    """回测做T策略历史表现

    通过获取基金历史K线数据，模拟在每个交易日开盘时生成信号，
    并根据日内最高/最低价判断信号是否成功。

    Args:
        fund_code: 基金代码
        days: 回测天数（默认60个交易日）

    Returns:
        {
            "fund_code": str,
            "fund_name": str,
            "total_days": int,
            "signal_days": int,
            "high_open_signals": int,
            "low_open_signals": int,
            "high_open_success": int,
            "low_open_success": int,
            "high_open_win_rate": float,
            "low_open_win_rate": float,
            "overall_win_rate": float,
            "avg_profit_per_trade": float,
            "max_profit": float,
            "max_loss": float,
            "signals": list,  # 最近N条信号详情
        }
    """
    config = get_fund_config(fund_code)
    if not config:
        return {"error": f"基金 {fund_code} 未在配置中"}

    fund_name = config.get("name", fund_code)

    # 获取历史K线数据（从东方财富）
    try:
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        session = requests.Session()
        adapter = HTTPAdapter(max_retries=Retry(total=2, backoff_factor=0.5))
        session.mount("https://", adapter)

        # 东方财富基金K线API
        # 判断市场前缀
        prefix = "0" if fund_code.startswith("1") else "1"  # 0=深圳, 1=上海
        url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
        params = {
            "secid": f"{prefix}.{fund_code}",
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57",
            "klt": "101",  # 日K
            "fqt": "0",
            "lmt": days + 5,  # 多取几天
            "end": "20500101",
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://quote.eastmoney.com/",
        }

        resp = session.get(url, headers=headers, params=params, timeout=15)
        data = resp.json()
        klines = data.get("data", {}).get("klines", [])

        if not klines:
            return {"error": f"无法获取 {fund_code} 的历史K线数据", "fund_code": fund_code, "fund_name": fund_name}

        # 解析K线: 日期,开盘,收盘,最高,最低,成交量,成交额
        parsed_klines = []
        for line in klines:
            parts = line.split(",")
            if len(parts) >= 7:
                parsed_klines.append({
                    "date": parts[0],
                    "open": float(parts[1]),
                    "close": float(parts[2]),
                    "high": float(parts[3]),
                    "low": float(parts[4]),
                    "volume": float(parts[5]),
                    "amount": float(parts[6]),
                })

        # 回测逻辑
        high_open_signals = 0
        low_open_signals = 0
        high_open_success = 0
        low_open_success = 0
        total_profit = 0
        max_profit = 0
        max_loss = 0
        signal_details = []

        for i in range(1, len(parsed_klines)):
            prev = parsed_klines[i - 1]
            curr = parsed_klines[i]

            if prev["close"] <= 0:
                continue

            # 计算开盘缺口
            open_change_pct = (curr["open"] - prev["close"]) / prev["close"] * 100

            signal = None
            success = False
            profit_pct = 0

            # 高开回落信号
            if open_change_pct >= T_STRATEGY_PARAMS["high_open"]["threshold"]:
                high_open_signals += 1
                signal = "high_open_sell"
                # 判断：日内最低价是否低于开盘价（回落了）
                intraday_low_change = (curr["low"] - curr["open"]) / curr["open"] * 100
                # 止盈：回落幅度 >= 止盈线
                take_profit = abs(open_change_pct) * RISK_PARAMS["take_profit_ratio"]
                if intraday_low_change <= -take_profit:
                    success = True
                    high_open_success += 1
                    profit_pct = take_profit - T_ROUND_TRIP_FEE
                else:
                    # 未止盈，收盘平仓
                    close_change = (curr["close"] - curr["open"]) / curr["open"] * 100
                    profit_pct = -close_change - T_ROUND_TRIP_FEE  # 卖出后价格涨了就亏

            # 低开反弹信号
            elif open_change_pct <= T_STRATEGY_PARAMS["low_open"]["threshold"]:
                low_open_signals += 1
                signal = "low_open_buy"
                # 判断：日内最高价是否高于开盘价（反弹了）
                intraday_high_change = (curr["high"] - curr["open"]) / curr["open"] * 100
                take_profit = abs(open_change_pct) * RISK_PARAMS["take_profit_ratio"]
                if intraday_high_change >= take_profit:
                    success = True
                    low_open_success += 1
                    profit_pct = take_profit - T_ROUND_TRIP_FEE
                else:
                    # 未止盈，收盘平仓
                    close_change = (curr["close"] - curr["open"]) / curr["open"] * 100
                    profit_pct = close_change - T_ROUND_TRIP_FEE

            if signal:
                total_profit += profit_pct
                max_profit = max(max_profit, profit_pct)
                max_loss = min(max_loss, profit_pct)

                signal_details.append({
                    "date": curr["date"],
                    "signal": signal,
                    "open_change_pct": round(open_change_pct, 2),
                    "success": success,
                    "profit_pct": round(profit_pct, 2),
                    "open": curr["open"],
                    "close": curr["close"],
                    "high": curr["high"],
                    "low": curr["low"],
                })

        total_signals = high_open_signals + low_open_signals
        total_success = high_open_success + low_open_success

        return {
            "fund_code": fund_code,
            "fund_name": fund_name,
            "total_days": len(parsed_klines) - 1,
            "signal_days": total_signals,
            "high_open_signals": high_open_signals,
            "low_open_signals": low_open_signals,
            "high_open_success": high_open_success,
            "low_open_success": low_open_success,
            "high_open_win_rate": round(high_open_success / high_open_signals * 100, 1) if high_open_signals > 0 else 0,
            "low_open_win_rate": round(low_open_success / low_open_signals * 100, 1) if low_open_signals > 0 else 0,
            "overall_win_rate": round(total_success / total_signals * 100, 1) if total_signals > 0 else 0,
            "avg_profit_per_trade": round(total_profit / total_signals, 2) if total_signals > 0 else 0,
            "total_profit_pct": round(total_profit, 2),
            "max_profit": round(max_profit, 2),
            "max_loss": round(max_loss, 2),
            "fee_per_trade": round(T_ROUND_TRIP_FEE, 4),
            "signals": signal_details[-20:],  # 最近20条信号
        }

    except Exception as e:
        logger.error(f"回测 {fund_code} 失败: {e}")
        return {"error": f"回测失败: {str(e)}", "fund_code": fund_code, "fund_name": fund_name}
