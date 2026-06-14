"""LOF基金套利评估引擎 (V2 - 机构级)

系统化检查所有套利条件，输出纪律检查清单。

套利纪律清单：
  1. 溢价率绝对值 >= 2% (critical) - 低于此值无法覆盖交易成本
  2. 成交额 >= 1000万 (critical) - 流动性不足会导致滑点
  3. 申购状态正常 (critical) - 暂停申购或限购会影响套利
  4. EST可信度高 (warning) - 两种EST方法偏差>1%时需谨慎
  5. 赎回费率 (info) - 持有<7天赎回费1.5%吞噬利润
  6. 净收益 > 0 (critical) - 扣除所有费用后仍为正
  7. 滑点估算 (warning) - 大单相对于日均成交额的冲击成本
  8. T+2结算风险 (warning) - 结算期间底层资产波动风险
  9. 仓位上限 (info) - 基于成交额的建议最大仓位

费用结构：
  - 申购费: 按基金实际费率（集思录数据），默认0.12%
  - 赎回费: 按持有时间阶梯
    < 7天: 1.5% (惩罚性)
    7~30天: 0.5%
    30~365天: 0.25%
    365~730天: 0.10%
    >= 730天: 0%
  - 交易佣金: 0.03% (场内买卖)
  - 转托管费: 0.01% (估算)
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ==================== 费用常量 ====================
DEFAULT_APPLY_FEE = 0.12  # 默认申购费率 %（当集思录数据不可用时）
TRADE_COMMISSION = 0.03  # 交易佣金 %
TRANSFER_CUSTODY_FEE = 0.01  # 转托管费 %（估算）
REDEEM_FEE_TABLE = [
    (7, 1.50),      # < 7天: 1.5%
    (30, 0.50),     # 7~30天: 0.5%
    (365, 0.25),    # 30~365天: 0.25%
    (730, 0.10),    # 365~730天: 0.10%
    (999999, 0.00), # >= 730天: 0%
]

# 套利阈值
MIN_PREMIUM_ABS = 2.0  # 最低溢价率绝对值 %
MIN_VOLUME = 1000  # 最低成交额 (万元)
MIN_NET_PROFIT = 0.0  # 最低净收益 %

# T+2结算风险参数
# QDII基金底层资产日波动率估算（基于历史数据）
UNDERLYING_DAILY_VOLATILITY = {
    "us_etf": 1.5,      # 美股ETF日均波动 ~1.5%
    "hk_index": 1.2,    # 港股指数日均波动 ~1.2%
    "futures": 2.0,     # 期货日均波动 ~2.0%
    "a_index": 1.0,     # A股指数日均波动 ~1.0%
    "multi": 1.3,       # 混合型日均波动 ~1.3%
    "active": 1.0,      # 主动型日均波动 ~1.0%
    "unknown": 1.5,     # 未知默认
}
SETTLEMENT_DAYS = 2  # T+N结算天数


def _parse_fee_value(fee_str) -> float:
    """解析费率字符串，支持 '0.12%', '0.12', '-' 等格式"""
    if fee_str is None:
        return None
    if isinstance(fee_str, (int, float)):
        return float(fee_str)
    fee_str = str(fee_str).strip()
    if not fee_str or fee_str == '-':
        return None
    try:
        return float(fee_str.replace('%', ''))
    except (ValueError, TypeError):
        return None


def get_redeem_fee(holding_days: int) -> float:
    """根据持有天数获取赎回费率

    Args:
        holding_days: 持有天数

    Returns:
        赎回费率 %
    """
    for threshold, fee in REDEEM_FEE_TABLE:
        if holding_days < threshold:
            return fee
    return 0.0


def calc_slippage(turnover_wan: float, order_amount_wan: float) -> float:
    """估算滑点成本

    基于经验公式：滑点 ≈ 0.1 * sqrt(order / turnover)
    当订单金额超过日均成交额5%时开始产生显著滑点

    Args:
        turnover_wan: 日均成交额（万元）
        order_amount_wan: 订单金额（万元）

    Returns:
        估算滑点 %
    """
    if turnover_wan <= 0 or order_amount_wan <= 0:
        return 0.0
    ratio = order_amount_wan / turnover_wan
    # 经验公式：滑点 ≈ 0.1 * sqrt(ratio) * 100
    # 当ratio=5%时滑点约0.022%，ratio=10%时约0.032%
    slippage = 0.1 * (ratio ** 0.5)
    return round(min(slippage, 1.0), 4)  # 上限1%


def calc_settlement_risk(underlying_type: str, position: float = 0.95) -> float:
    """估算T+2结算期间的风险敞口

    结算期间底层资产可能朝不利方向波动，用1.5倍标准差估算最大不利波动。

    Args:
        underlying_type: 底层资产类型
        position: 仓位比例

    Returns:
        T+2期间最大不利波动 %（正值表示潜在损失）
    """
    daily_vol = UNDERLYING_DAILY_VOLATILITY.get(underlying_type, 1.5)
    # T+2期间波动 = 日波动率 * sqrt(结算天数) * 1.5(90%置信区间)
    settlement_vol = daily_vol * (SETTLEMENT_DAYS ** 0.5) * 1.5
    return round(settlement_vol * position, 2)


def calc_max_position(turnover_wan: float, max_volume_pct: float = 0.05) -> float:
    """计算建议最大仓位

    基于流动性约束：单笔不超过日均成交额的5%（默认）

    Args:
        turnover_wan: 日均成交额（万元）
        max_volume_pct: 最大占比，默认5%

    Returns:
        建议最大仓位（万元）
    """
    if turnover_wan <= 0:
        return 0.0
    return round(turnover_wan * max_volume_pct, 2)


def calc_net_profit(
    premium_pct: float,
    direction: str,
    apply_fee: Optional[float] = None,
    redeem_fee_override: Optional[float] = None,
    holding_days: int = 2,
    underlying_type: str = "unknown",
    position: float = 0.95,
) -> dict:
    """计算套利净收益（含完整费用分解）

    Args:
        premium_pct: 溢价率% (正=溢价，负=折价)
        direction: "premium" (溢价套利) 或 "discount" (折价套利)
        apply_fee: 实际申购费率%（None则用默认值）
        redeem_fee_override: 实际赎回费率%（None则按持有天数计算）
        holding_days: 持有天数（用于计算赎回费）
        underlying_type: 底层资产类型（用于T+2风险估算）
        position: 仓位比例

    Returns:
        {
            "net_profit": float,  # 净收益%
            "gross_profit": float,  # 毛收益%
            "fee_breakdown": {
                "apply_fee": float,
                "redeem_fee": float,
                "trade_commission": float,
                "transfer_fee": float,
                "total_fee": float,
            },
            "settlement_risk": float,  # T+2风险%
            "risk_adjusted_profit": float,  # 风险调整后收益%
        }
    """
    actual_apply_fee = apply_fee if apply_fee is not None else DEFAULT_APPLY_FEE
    actual_redeem_fee = redeem_fee_override if redeem_fee_override is not None else get_redeem_fee(holding_days)

    if direction == "premium":
        # 溢价套利: 场外申购 -> T+2到账 -> 转托管 -> 场内卖出
        # 费用: 申购费 + 转托管费 + 交易佣金
        total_fee = actual_apply_fee + TRANSFER_CUSTODY_FEE + TRADE_COMMISSION
        fee_breakdown = {
            "apply_fee": round(actual_apply_fee, 4),
            "redeem_fee": 0.0,
            "trade_commission": TRADE_COMMISSION,
            "transfer_fee": TRANSFER_CUSTODY_FEE,
            "total_fee": round(total_fee, 4),
        }
        net_profit = premium_pct - total_fee
    else:
        # 折价套利: 场内买入 -> 转托管 -> 场外赎回
        # 费用: 交易佣金 + 转托管费 + 赎回费
        total_fee = actual_redeem_fee + TRANSFER_CUSTODY_FEE + TRADE_COMMISSION
        fee_breakdown = {
            "apply_fee": 0.0,
            "redeem_fee": round(actual_redeem_fee, 4),
            "trade_commission": TRADE_COMMISSION,
            "transfer_fee": TRANSFER_CUSTODY_FEE,
            "total_fee": round(total_fee, 4),
        }
        net_profit = abs(premium_pct) - total_fee

    # T+2结算风险
    settlement_risk = calc_settlement_risk(underlying_type, position)

    return {
        "net_profit": round(net_profit, 2),
        "gross_profit": round(abs(premium_pct), 2),
        "fee_breakdown": fee_breakdown,
        "settlement_risk": settlement_risk,
        "risk_adjusted_profit": round(net_profit - settlement_risk, 2),
    }


def evaluate_arbitrage(
    est_result: dict,
    turnover: float = 0,
    apply_status: str = "",
    holding_days: int = 2,
    apply_fee: Optional[float] = None,
    redeem_fee: Optional[float] = None,
    underlying_type: str = "unknown",
    position: float = 0.95,
) -> dict:
    """套利可行性评估 (V2)

    Args:
        est_result: EST计算结果 (from fund_est_engine.calc_fund_est)
        turnover: 成交额 (万元)
        apply_status: 申购状态
        holding_days: 持有天数（溢价套利默认2天T+2结算）
        apply_fee: 实际申购费率%（None则用默认值）
        redeem_fee: 实际赎回费率%（None则按持有天数计算）
        underlying_type: 底层资产类型
        position: 仓位比例

    Returns:
        {
            "verdict": "可以套利" / "谨慎套利" / "不建议套利",
            "direction": "premium" / "discount" / "none",
            "checks": [{"name", "value", "pass", "severity", "note"}, ...],
            "net_profit": float,
            "gross_profit": float,
            "fee_breakdown": dict,
            "settlement_risk": float,
            "risk_adjusted_profit": float,
            "slippage_est": float,
            "max_position_wan": float,
        }
    """
    premium_pct = float(est_result.get("premium_pct", 0) or 0)
    confidence = est_result.get("est_confidence", "low")
    abs_premium = abs(premium_pct)

    # 判断套利方向
    if premium_pct > 0:
        direction = "premium"
    elif premium_pct < 0:
        direction = "discount"
    else:
        direction = "none"

    checks = []

    # 纪律1: 溢价率阈值
    checks.append({
        "name": "溢价率",
        "value": f"{premium_pct:+.2f}%",
        "pass": abs_premium >= MIN_PREMIUM_ABS,
        "severity": "critical",
        "note": f"绝对值需>={MIN_PREMIUM_ABS}%才能覆盖交易成本" if abs_premium < MIN_PREMIUM_ABS else
                f"{'溢价' if direction == 'premium' else '折价'}{abs_premium:.2f}%，满足阈值"
    })

    # 纪律2: 成交额门槛
    checks.append({
        "name": "成交额",
        "value": f"{turnover:.0f}万",
        "pass": turnover >= MIN_VOLUME,
        "severity": "critical",
        "note": f"建议>={MIN_VOLUME}万，避免流动性风险" if turnover < MIN_VOLUME else "流动性充足"
    })

    # 纪律3: 申购状态
    is_open = "限" not in apply_status and "停" not in apply_status
    checks.append({
        "name": "申购状态",
        "value": apply_status if apply_status else "正常",
        "pass": is_open,
        "severity": "critical",
        "note": "暂停申购或限购会影响套利" if not is_open else "申购正常"
    })

    # 纪律4: EST可信度
    checks.append({
        "name": "EST可信度",
        "value": {"high": "高", "medium": "中", "low": "低"}.get(confidence, confidence),
        "pass": confidence in ("high", "medium"),
        "severity": "warning",
        "note": "两种EST方法偏差>1%时需谨慎" if confidence == "low" else "EST估算可信"
    })

    # 纪律5: 赎回费率（仅折价套利时关键）
    actual_redeem = redeem_fee if redeem_fee is not None else get_redeem_fee(holding_days)
    checks.append({
        "name": "赎回费率",
        "value": f"{actual_redeem:.2f}%（持有{holding_days}天）",
        "pass": direction != "discount" or actual_redeem < 1.0,
        "severity": "warning" if direction == "discount" and actual_redeem >= 1.0 else "info",
        "note": "赎回费>=1%会严重侵蚀折价套利利润" if direction == "discount" and actual_redeem >= 1.0
                else f"赎回费率{actual_redeem:.2f}%"
    })

    # 纪律6: 滑点估算
    # 假设单笔建议不超过成交额5%
    max_position_wan = calc_max_position(turnover)
    slippage_est = calc_slippage(turnover, max_position_wan) if turnover > 0 else 0
    checks.append({
        "name": "滑点估算",
        "value": f"{slippage_est:.3f}%（5%仓位）",
        "pass": slippage_est < 0.1,
        "severity": "warning",
        "note": f"建议单笔<={max_position_wan:.0f}万（日均成交额5%）" if turnover > 0 else "成交额未知，无法估算"
    })

    # 纪律7: T+2结算风险
    settlement_risk = calc_settlement_risk(underlying_type, position)
    checks.append({
        "name": "T+2结算风险",
        "value": f"±{settlement_risk:.2f}%",
        "pass": settlement_risk < abs_premium * 0.5,
        "severity": "warning",
        "note": f"结算期间底层资产({underlying_type})可能波动±{settlement_risk:.2f}%"
    })

    # 纪律8: 净收益
    if direction != "none":
        profit_result = calc_net_profit(
            premium_pct, direction,
            apply_fee=apply_fee,
            redeem_fee_override=redeem_fee,
            holding_days=holding_days,
            underlying_type=underlying_type,
            position=position,
        )
        net_profit = profit_result["net_profit"]
        fee_breakdown = profit_result["fee_breakdown"]
        risk_adjusted_profit = profit_result["risk_adjusted_profit"]
    else:
        net_profit = 0
        fee_breakdown = {
            "apply_fee": 0, "redeem_fee": 0,
            "trade_commission": 0, "transfer_fee": 0, "total_fee": 0,
        }
        settlement_risk = 0
        risk_adjusted_profit = 0

    checks.append({
        "name": "预估净收益",
        "value": f"{net_profit:+.2f}%",
        "pass": net_profit > MIN_NET_PROFIT,
        "severity": "critical",
        "note": "扣除所有费用后仍为正" if net_profit > MIN_NET_PROFIT else "净收益为负，不值得套利"
    })

    # 纪律9: 风险调整后收益
    checks.append({
        "name": "风险调整收益",
        "value": f"{risk_adjusted_profit:+.2f}%",
        "pass": risk_adjusted_profit > 0,
        "severity": "warning",
        "note": f"扣除T+2结算风险({settlement_risk:.2f}%)后的收益" if risk_adjusted_profit > 0
                else "考虑结算风险后收益为负，风险较大"
    })

    # 综合评估
    critical_pass = all(c["pass"] for c in checks if c["severity"] == "critical")
    warning_pass = all(c["pass"] for c in checks if c["severity"] == "warning")

    if critical_pass and warning_pass:
        verdict = "可以套利"
    elif critical_pass:
        verdict = "谨慎套利"
    else:
        verdict = "不建议套利"

    return {
        "verdict": verdict,
        "direction": direction,
        "checks": checks,
        "net_profit": round(net_profit, 2),
        "gross_profit": round(abs_premium, 2),
        "fee_breakdown": fee_breakdown,
        "settlement_risk": settlement_risk,
        "risk_adjusted_profit": round(risk_adjusted_profit, 2),
        "slippage_est": round(slippage_est, 4),
        "max_position_wan": max_position_wan,
    }
