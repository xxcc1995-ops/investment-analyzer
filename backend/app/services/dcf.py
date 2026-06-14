"""DCF估值计算服务 - 机构级标准

支持:
1. 单阶段DCF（恒定增长率）
2. 两阶段DCF（高增长期 + 永续增长期）
3. 格雷厄姆公式（Graham Number）
4. WACC估算（基于CAPM）
5. 净负债调整（企业价值 -> 股权价值）
6. 敏感性分析矩阵
7. PS（市销率）/ PEG 估值
8. 多模型综合估值评分
9. 估值预警引擎
"""

import math
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class DCFConfig:
    """DCF配置参数"""
    discount_rate: float = 0.10       # 折现率（WACC）
    terminal_growth_rate: float = 0.03 # 永续增长率
    safety_margin: float = 0.30       # 安全边际
    projection_years: int = 10        # 预测年数
    # 两阶段模型参数
    high_growth_years: int = 5        # 高增长阶段年数
    stable_growth_rate: float = 0.05  # 稳定增长阶段增长率


class DCFService:
    """DCF估值计算服务"""

    def __init__(
        self,
        discount_rate: float = 0.10,
        terminal_growth_rate: float = 0.03,
        safety_margin: float = 0.30,
        projection_years: int = 10,
    ):
        # 参数校验
        if discount_rate <= terminal_growth_rate:
            raise ValueError(
                f"折现率({discount_rate:.1%})必须大于永续增长率({terminal_growth_rate:.1%})，"
                "否则终值公式发散。建议折现率至少高于永续增长率3个百分点。"
            )
        if terminal_growth_rate < 0 or terminal_growth_rate > 0.05:
            raise ValueError(
                f"永续增长率({terminal_growth_rate:.1%})不合理。"
                "通常应在0%-5%之间（长期通胀+GDP增速上限）。"
            )
        if safety_margin < 0 or safety_margin >= 1:
            raise ValueError("安全边际必须在0%-100%之间。")

        self.discount_rate = discount_rate
        self.terminal_growth_rate = terminal_growth_rate
        self.safety_margin = safety_margin
        self.projection_years = projection_years

    def calculate_intrinsic_value(
        self,
        current_fcf: float,
        growth_rate: float,
        shares: float,
        net_debt: float = 0.0,
        current_price: float = 0.0,
    ) -> dict:
        """
        计算DCF内在价值（单阶段模型）

        Args:
            current_fcf: 当前自由现金流（亿元）
            growth_rate: 增长率
            shares: 总股本（亿股）
            net_debt: 净负债（有息负债 - 现金及等价物，亿元），默认0
            current_price: 当前市场价格（元），用于计算安全边际

        Returns:
            完整估值结果
        """
        # 1. 预测未来N年FCF
        fcf_projections = []
        for year in range(1, self.projection_years + 1):
            projected_fcf = current_fcf * (1 + growth_rate) ** year
            fcf_projections.append(round(projected_fcf, 2))

        # 2. 计算N年FCF现值
        pv_fcf = 0
        for t, fcf in enumerate(fcf_projections, 1):
            pv_fcf += fcf / (1 + self.discount_rate) ** t

        # 3. 计算终值（Gordon Growth Model）
        terminal_fcf = fcf_projections[-1] * (1 + self.terminal_growth_rate)
        terminal_value = terminal_fcf / (self.discount_rate - self.terminal_growth_rate)

        # 4. 终值现值
        pv_terminal = terminal_value / (1 + self.discount_rate) ** self.projection_years

        # 5. 企业价值 = FCF现值 + 终值现值
        enterprise_value = pv_fcf + pv_terminal

        # 6. 股权价值 = 企业价值 - 净负债
        equity_value = enterprise_value - net_debt

        # 7. 每股内在价值
        if shares <= 0:
            raise ValueError("总股本必须大于0")
        intrinsic_per_share = equity_value / shares

        # 8. 买点（含安全边际）
        buy_price = intrinsic_per_share * (1 - self.safety_margin)

        # 9. 终值占比（越高说明估值越依赖远期假设，风险越大）
        terminal_pct = pv_terminal / enterprise_value * 100 if enterprise_value > 0 else 0

        # 10. 安全边际分析
        result = {
            "intrinsic_value": round(intrinsic_per_share, 2),
            "buy_price": round(buy_price, 2),
            "enterprise_value": round(enterprise_value, 2),
            "equity_value": round(equity_value, 2),
            "net_debt": round(net_debt, 2),
            "fcf_projections": fcf_projections,
            "terminal_value": round(terminal_value, 2),
            "pv_fcf": round(pv_fcf, 2),
            "pv_terminal": round(pv_terminal, 2),
            "terminal_pct": round(terminal_pct, 1),
            "discount_rate": self.discount_rate,
            "growth_rate": growth_rate,
            "terminal_growth_rate": self.terminal_growth_rate,
            "safety_margin": self.safety_margin,
            "projection_years": self.projection_years,
        }

        # 如果提供了当前价格，计算上行空间
        if current_price > 0:
            upside = (intrinsic_per_share / current_price - 1) * 100
            buy_upside = (buy_price / current_price - 1) * 100
            result["current_price"] = current_price
            result["upside_pct"] = round(upside, 1)
            result["buy_upside_pct"] = round(buy_upside, 1)
            result["is_undervalued"] = current_price < intrinsic_per_share
            result["is_buy_zone"] = current_price < buy_price

        return result

    def calculate_two_stage_dcf(
        self,
        current_fcf: float,
        high_growth_rate: float,
        stable_growth_rate: float,
        shares: float,
        high_growth_years: int = 5,
        net_debt: float = 0.0,
        current_price: float = 0.0,
    ) -> dict:
        """
        两阶段DCF模型

        阶段1（高增长期）: 前N年以较高增长率增长
        阶段2（永续期）: 之后以稳定增长率永续增长

        更贴近实际：企业不可能永远高速增长。
        """
        # 参数校验
        if high_growth_years < 1 or high_growth_years > self.projection_years:
            raise ValueError(f"高增长年数须在1-{self.projection_years}之间")

        # 阶段1: 高增长期FCF预测
        fcf_projections = []
        for year in range(1, high_growth_years + 1):
            projected_fcf = current_fcf * (1 + high_growth_rate) ** year
            fcf_projections.append(round(projected_fcf, 2))

        # 阶段2: 稳定增长期FCF预测（剩余年数）
        stable_start_fcf = fcf_projections[-1]
        for year in range(1, self.projection_years - high_growth_years + 1):
            projected_fcf = stable_start_fcf * (1 + stable_growth_rate) ** year
            fcf_projections.append(round(projected_fcf, 2))

        # 计算FCF现值
        pv_fcf = 0
        for t, fcf in enumerate(fcf_projections, 1):
            pv_fcf += fcf / (1 + self.discount_rate) ** t

        # 终值
        terminal_fcf = fcf_projections[-1] * (1 + self.terminal_growth_rate)
        terminal_value = terminal_fcf / (self.discount_rate - self.terminal_growth_rate)
        pv_terminal = terminal_value / (1 + self.discount_rate) ** self.projection_years

        enterprise_value = pv_fcf + pv_terminal
        equity_value = enterprise_value - net_debt
        intrinsic_per_share = equity_value / shares
        buy_price = intrinsic_per_share * (1 - self.safety_margin)
        terminal_pct = pv_terminal / enterprise_value * 100 if enterprise_value > 0 else 0

        result = {
            "intrinsic_value": round(intrinsic_per_share, 2),
            "buy_price": round(buy_price, 2),
            "enterprise_value": round(enterprise_value, 2),
            "equity_value": round(equity_value, 2),
            "net_debt": round(net_debt, 2),
            "fcf_projections": fcf_projections,
            "terminal_value": round(terminal_value, 2),
            "pv_fcf": round(pv_fcf, 2),
            "pv_terminal": round(pv_terminal, 2),
            "terminal_pct": round(terminal_pct, 1),
            "discount_rate": self.discount_rate,
            "high_growth_rate": high_growth_rate,
            "stable_growth_rate": stable_growth_rate,
            "high_growth_years": high_growth_years,
            "terminal_growth_rate": self.terminal_growth_rate,
            "safety_margin": self.safety_margin,
            "model": "two_stage",
        }

        if current_price > 0:
            upside = (intrinsic_per_share / current_price - 1) * 100
            result["current_price"] = current_price
            result["upside_pct"] = round(upside, 1)
            result["buy_upside_pct"] = round((buy_price / current_price - 1) * 100, 1)
            result["is_undervalued"] = current_price < intrinsic_per_share
            result["is_buy_zone"] = current_price < buy_price

        return result

    def estimate_growth_rate(
        self,
        historical_fcf: List[float]
    ) -> float:
        """估算FCF增长率（基于历史数据的保守估计）"""
        if len(historical_fcf) < 2:
            return 0.05

        # 过滤正值
        positive_fcf = [f for f in historical_fcf if f > 0]
        if len(positive_fcf) < 2:
            return 0.03

        start = positive_fcf[0]
        end = positive_fcf[-1]
        years = len(positive_fcf) - 1

        if start <= 0:
            return 0.03

        cagr = (end / start) ** (1 / years) - 1

        # 保守处理：取历史增长率的80%，且限制在合理范围
        conservative = cagr * 0.8
        return max(min(conservative, 0.25), 0.02)  # 2%-25%


def calculate_graham_number(eps: float, bvps: float) -> dict:
    """
    格雷厄姆公式（Graham Number）

    公式: sqrt(22.5 * EPS * BVPS)
    含义: EPS代表盈利能力，BVPS代表资产价值
    22.5 = PE上限15 * PB上限1.5（格雷厄姆认为合理估值的上限）

    适用条件:
    - EPS必须为正（亏损企业不适用）
    - BVPS必须为正（资不抵债不适用）
    - 适用于稳定盈利的成熟企业

    Returns:
        包含格雷厄姆内在价值和适用性判断
    """
    result = {
        "eps": eps,
        "bvps": bvps,
        "applicable": True,
        "warnings": [],
    }

    if eps <= 0:
        result["applicable"] = False
        result["warnings"].append(f"EPS={eps:.2f}<=0，格雷厄姆公式不适用于亏损企业")
        result["graham_value"] = None
        return result

    if bvps <= 0:
        result["applicable"] = False
        result["warnings"].append(f"BVPS={bvps:.2f}<=0，格雷厄姆公式不适用于资不抵债企业")
        result["graham_value"] = None
        return result

    # 核心公式
    graham_value = (22.5 * eps * bvps) ** 0.5
    result["graham_value"] = round(graham_value, 2)

    # 隐含PE和PB
    if graham_value > 0:
        result["implied_pe"] = round(graham_value / eps, 1)
        result["implied_pb"] = round(graham_value / bvps, 1)

    return result


def estimate_wacc(
    risk_free_rate: float = 0.025,
    market_risk_premium: float = 0.06,
    beta: float = 1.0,
    debt_ratio: float = 0.0,
    cost_of_debt: float = 0.05,
    tax_rate: float = 0.25,
) -> float:
    """
    基于CAPM估算WACC（加权平均资本成本）

    WACC = E/(E+D) * Re + D/(E+D) * Rd * (1-T)
    Re = Rf + Beta * (Rm - Rf)

    Args:
        risk_free_rate: 无风险利率（中国10年期国债约2.5%）
        market_risk_premium: 市场风险溢价（中国A股约6%）
        beta: 贝塔系数（市场波动敏感度）
        debt_ratio: 资产负债率 (%)
        cost_of_debt: 债务成本（贷款利率）
        tax_rate: 企业所得税率

    Returns:
        WACC (折现率)
    """
    # CAPM: 股权成本
    cost_of_equity = risk_free_rate + beta * market_risk_premium

    # 权重
    debt_weight = debt_ratio / 100
    equity_weight = 1 - debt_weight

    # WACC
    wacc = equity_weight * cost_of_equity + debt_weight * cost_of_debt * (1 - tax_rate)

    # 最低不低于8%（保守）
    return max(round(wacc, 4), 0.08)


# ============================================================
# PS / PEG / 综合估值评分
# ============================================================

def calc_ps_ratio(price: float, revenue_per_share: float) -> Optional[float]:
    """
    计算市销率（PS = Price / Revenue Per Share）

    适用场景:
    - 亏损企业（PE失效时的替代指标）
    - 早期高增长企业
    - 周期性行业（利润波动大，但营收相对稳定）

    Args:
        price: 当前股价
        revenue_per_share: 每股营收

    Returns:
        PS比率，数据不可用时返回None
    """
    if not revenue_per_share or revenue_per_share <= 0 or not price or price <= 0:
        return None
    return round(price / revenue_per_share, 2)


def calc_peg(pe: float, earnings_growth_rate: float) -> Optional[float]:
    """
    计算PEG比率（PE / 盈利增长率%）

    PEG = PE / (盈利增长率 * 100)
    彼得·林奇标准:
    - PEG < 1: 低估
    - PEG = 1: 合理
    - PEG > 1: 高估
    - PEG > 2: 严重高估

    注意:
    - 增长率必须为正（亏损增长不适用）
    - 适用于成长股，不适用于成熟/衰退企业
    - 周期股PEG可能失真

    Args:
        pe: 市盈率（TTM）
        earnings_growth_rate: 盈利增长率（小数形式，如0.20表示20%）

    Returns:
        PEG比率，数据不可用时返回None
    """
    if pe is None or pe <= 0:
        return None
    if earnings_growth_rate is None or earnings_growth_rate <= 0:
        return None
    growth_pct = earnings_growth_rate * 100
    if growth_pct < 1:  # 增长率过低，PEG无意义
        return None
    return round(pe / growth_pct, 2)


def get_ps_level(ps: float, industry: str = "default") -> str:
    """
    PS估值水平判断（行业差异化阈值）

    不同行业的PS合理区间差异巨大：
    - 软件/互联网：PS 5-15 可接受
    - 消费品：PS 1-5 合理
    - 制造业：PS 0.5-2 合理
    - 银行/保险：PS 不适用（用PB）
    """
    industry_thresholds = {
        "tech": {"low": 3, "fair": 8, "high": 15},
        "consumer": {"low": 1, "fair": 3, "high": 6},
        "manufacturing": {"low": 0.5, "fair": 1.5, "high": 3},
        "pharma": {"low": 2, "fair": 5, "high": 10},
        "energy": {"low": 0.3, "fair": 1, "high": 2},
        "finance": {"low": 0.5, "fair": 2, "high": 5},
        "default": {"low": 1, "fair": 3, "high": 8},
    }
    t = industry_thresholds.get(industry, industry_thresholds["default"])
    if ps < t["low"]:
        return "低估"
    elif ps < t["fair"]:
        return "合理"
    elif ps < t["high"]:
        return "偏高"
    else:
        return "高估"


def get_peg_level(peg: float) -> str:
    """
    PEG估值水平判断（彼得·林奇标准）
    """
    if peg < 0.5:
        return "显著低估"
    elif peg < 1.0:
        return "低估"
    elif peg < 1.5:
        return "合理"
    elif peg < 2.0:
        return "偏高"
    else:
        return "高估"


def get_pe_level(pe: float) -> str:
    """PE估值水平判断（通用标准，A股经验）"""
    if pe is None or pe <= 0:
        return "N/A"
    if pe < 10:
        return "低估"
    elif pe < 20:
        return "合理"
    elif pe < 40:
        return "偏高"
    else:
        return "高估"


def get_pb_level(pb: float) -> str:
    """PB估值水平判断（通用标准）"""
    if pb is None or pb <= 0:
        return "N/A"
    if pb < 1:
        return "低估"
    elif pb < 2:
        return "合理"
    elif pb < 5:
        return "偏高"
    else:
        return "高估"


def get_ev_ebitda_level(ev_ebitda: float) -> str:
    """EV/EBITDA估值水平判断"""
    if ev_ebitda is None or ev_ebitda <= 0:
        return "N/A"
    if ev_ebitda < 8:
        return "低估"
    elif ev_ebitda < 15:
        return "合理"
    elif ev_ebitda < 25:
        return "偏高"
    else:
        return "高估"


# ============================================================
# 历史分位数计算
# ============================================================

def calc_percentile(current: float, history: List[float]) -> Optional[Dict[str, Any]]:
    """
    计算当前值在历史序列中的分位数

    Args:
        current: 当前值
        history: 历史值列表（按时间正序）

    Returns:
        {
            "current": 当前值,
            "min": 历史最低,
            "max": 历史最高,
            "median": 中位数,
            "p10": 10%分位（极低估）,
            "p25": 25%分位（低估）,
            "p75": 75%分位（偏高）,
            "p90": 90%分位（极高估）,
            "percentile": 百分位排名（0-100，越低越便宜）,
            "count": 样本数,
            "z_score": 标准分（偏离均值几个标准差）,
        }
    """
    if not history or current is None:
        return None

    import numpy as np
    arr = np.array([v for v in history if v is not None and v > 0])
    if len(arr) < 10:  # 样本太少，统计意义不大
        return None

    # 过滤极端异常值（超过3倍标准差的）
    mean = np.mean(arr)
    std = np.std(arr)
    if std > 0:
        arr = arr[np.abs(arr - mean) <= 3 * std]
    if len(arr) < 10:
        return None

    count_below = int(np.sum(arr <= current))
    percentile = round(count_below / len(arr) * 100, 1)
    z_score = round((current - mean) / std, 2) if std > 0 else 0.0

    return {
        "current": round(current, 2),
        "min": round(float(np.min(arr)), 2),
        "max": round(float(np.max(arr)), 2),
        "mean": round(float(np.mean(arr)), 2),
        "median": round(float(np.median(arr)), 2),
        "p10": round(float(np.percentile(arr, 10)), 2),
        "p25": round(float(np.percentile(arr, 25)), 2),
        "p75": round(float(np.percentile(arr, 75)), 2),
        "p90": round(float(np.percentile(arr, 90)), 2),
        "percentile": percentile,
        "count": len(arr),
        "z_score": z_score,
    }


def get_percentile_signal(percentile: float) -> str:
    """
    根据历史分位数生成估值信号

    信号含义:
    - 极低估 (<10%): 强烈买入信号
    - 低估 (10-25%): 买入区间
    - 合理 (25-50%): 合理偏低
    - 中性 (50-75%): 合理偏高
    - 偏高 (75-90%): 卖出区间
    - 极高估 (>90%): 强烈卖出信号
    """
    if percentile is None:
        return "N/A"
    if percentile < 10:
        return "极低估"
    elif percentile < 25:
        return "低估"
    elif percentile < 50:
        return "合理偏低"
    elif percentile < 75:
        return "合理偏高"
    elif percentile < 90:
        return "偏高"
    else:
        return "极高估"


# ============================================================
# 多模型综合估值评分
# ============================================================

def calculate_composite_score(
    pe: Optional[float] = None,
    pb: Optional[float] = None,
    ps: Optional[float] = None,
    ev_ebitda: Optional[float] = None,
    peg: Optional[float] = None,
    fcf_yield: Optional[float] = None,
    dividend_yield: Optional[float] = None,
    pe_percentile: Optional[float] = None,
    pb_percentile: Optional[float] = None,
) -> Dict[str, Any]:
    """
    多模型综合估值评分（0-100分，越高越便宜）

    权重分配:
    - PE分位数: 25%（最常用的估值指标）
    - PB分位数: 15%（资产定价）
    - PEG: 15%（成长股核心指标）
    - EV/EBITDA: 15%（剔除资本结构影响）
    - PS: 10%（亏损企业备用）
    - FCF Yield: 10%（现金回报）
    - 股息率: 10%（实际回报）

    Returns:
        {
            "score": 0-100综合评分,
            "level": "严重低估"/"低估"/"合理"/"偏高"/"高估",
            "details": 各指标评分明细,
            "applicable_count": 有效指标数量,
        }
    """
    scores = []
    weights = []
    details = {}

    # 1. PE分位数评分（分位数越低越便宜，取反）
    if pe_percentile is not None:
        pe_score = max(0, min(100, 100 - pe_percentile))
        scores.append(pe_score)
        weights.append(25)
        details["pe_percentile"] = {
            "value": pe_percentile,
            "score": round(pe_score, 1),
            "weight": 25,
            "signal": get_percentile_signal(pe_percentile),
        }
    elif pe is not None and pe > 0:
        # 无历史数据时用绝对PE评分
        if pe < 10:
            pe_score = 90
        elif pe < 15:
            pe_score = 75
        elif pe < 20:
            pe_score = 60
        elif pe < 30:
            pe_score = 40
        elif pe < 50:
            pe_score = 20
        else:
            pe_score = 5
        scores.append(pe_score)
        weights.append(25)
        details["pe"] = {
            "value": pe,
            "score": round(pe_score, 1),
            "weight": 25,
            "level": get_pe_level(pe),
        }

    # 2. PB分位数评分
    if pb_percentile is not None:
        pb_score = max(0, min(100, 100 - pb_percentile))
        scores.append(pb_score)
        weights.append(15)
        details["pb_percentile"] = {
            "value": pb_percentile,
            "score": round(pb_score, 1),
            "weight": 15,
            "signal": get_percentile_signal(pb_percentile),
        }
    elif pb is not None and pb > 0:
        if pb < 1:
            pb_score = 90
        elif pb < 1.5:
            pb_score = 75
        elif pb < 3:
            pb_score = 50
        elif pb < 5:
            pb_score = 25
        else:
            pb_score = 10
        scores.append(pb_score)
        weights.append(15)
        details["pb"] = {
            "value": pb,
            "score": round(pb_score, 1),
            "weight": 15,
            "level": get_pb_level(pb),
        }

    # 3. PEG评分
    if peg is not None and peg > 0:
        if peg < 0.5:
            peg_score = 95
        elif peg < 0.8:
            peg_score = 80
        elif peg < 1.0:
            peg_score = 70
        elif peg < 1.5:
            peg_score = 50
        elif peg < 2.0:
            peg_score = 30
        else:
            peg_score = 10
        scores.append(peg_score)
        weights.append(15)
        details["peg"] = {
            "value": peg,
            "score": round(peg_score, 1),
            "weight": 15,
            "level": get_peg_level(peg),
        }

    # 4. EV/EBITDA评分
    if ev_ebitda is not None and ev_ebitda > 0:
        if ev_ebitda < 6:
            ebitda_score = 90
        elif ev_ebitda < 10:
            ebitda_score = 75
        elif ev_ebitda < 15:
            ebitda_score = 55
        elif ev_ebitda < 20:
            ebitda_score = 35
        elif ev_ebitda < 30:
            ebitda_score = 15
        else:
            ebitda_score = 5
        scores.append(ebitda_score)
        weights.append(15)
        details["ev_ebitda"] = {
            "value": ev_ebitda,
            "score": round(ebitda_score, 1),
            "weight": 15,
            "level": get_ev_ebitda_level(ev_ebitda),
        }

    # 5. PS评分
    if ps is not None and ps > 0:
        if ps < 1:
            ps_score = 90
        elif ps < 2:
            ps_score = 70
        elif ps < 5:
            ps_score = 50
        elif ps < 10:
            ps_score = 30
        else:
            ps_score = 10
        scores.append(ps_score)
        weights.append(10)
        details["ps"] = {
            "value": ps,
            "score": round(ps_score, 1),
            "weight": 10,
            "level": get_ps_level(ps),
        }

    # 6. FCF Yield评分
    if fcf_yield is not None and fcf_yield > 0:
        if fcf_yield > 10:
            fcf_score = 95
        elif fcf_yield > 8:
            fcf_score = 80
        elif fcf_yield > 5:
            fcf_score = 65
        elif fcf_yield > 3:
            fcf_score = 45
        else:
            fcf_score = 20
        scores.append(fcf_score)
        weights.append(10)
        details["fcf_yield"] = {
            "value": fcf_yield,
            "score": round(fcf_score, 1),
            "weight": 10,
        }

    # 7. 股息率评分
    if dividend_yield is not None and dividend_yield > 0:
        if dividend_yield > 5:
            div_score = 90
        elif dividend_yield > 3:
            div_score = 75
        elif dividend_yield > 2:
            div_score = 60
        elif dividend_yield > 1:
            div_score = 40
        else:
            div_score = 20
        scores.append(div_score)
        weights.append(10)
        details["dividend_yield"] = {
            "value": dividend_yield,
            "score": round(div_score, 1),
            "weight": 10,
        }

    # 加权平均
    if not scores:
        return {
            "score": None,
            "level": "N/A",
            "details": {},
            "applicable_count": 0,
        }

    total_weight = sum(weights)
    composite = sum(s * w for s, w in zip(scores, weights)) / total_weight

    # 评级
    if composite >= 80:
        level = "严重低估"
    elif composite >= 65:
        level = "低估"
    elif composite >= 45:
        level = "合理"
    elif composite >= 30:
        level = "偏高"
    else:
        level = "高估"

    return {
        "score": round(composite, 1),
        "level": level,
        "details": details,
        "applicable_count": len(scores),
        "total_weight": total_weight,
    }


# ============================================================
# 估值预警引擎
# ============================================================

def generate_valuation_alerts(
    pe: Optional[float] = None,
    pb: Optional[float] = None,
    ps: Optional[float] = None,
    peg: Optional[float] = None,
    ev_ebitda: Optional[float] = None,
    fcf_yield: Optional[float] = None,
    dividend_yield: Optional[float] = None,
    pe_percentile: Optional[float] = None,
    pb_percentile: Optional[float] = None,
    composite_score: Optional[float] = None,
    current_price: Optional[float] = None,
    intrinsic_value: Optional[float] = None,
) -> List[Dict[str, str]]:
    """
    估值预警引擎 - 生成多维度估值预警信号

    Returns:
        [{"level": "warning"/"danger"/"safe"/"info",
          "type": "pe"/"pb"/"peg"/...,
          "message": "预警描述"}]
    """
    alerts = []

    # 1. PE预警
    if pe is not None and pe > 0:
        if pe > 100:
            alerts.append({"level": "danger", "type": "pe", "message": f"PE(TTM)={pe:.1f}，极高估值，可能存在泡沫"})
        elif pe > 60:
            alerts.append({"level": "warning", "type": "pe", "message": f"PE(TTM)={pe:.1f}，估值偏高，需关注盈利持续性"})
        elif pe < 10:
            alerts.append({"level": "safe", "type": "pe", "message": f"PE(TTM)={pe:.1f}，估值偏低，可能是价值陷阱或真正低估"})

    # 2. PB预警
    if pb is not None and pb > 0:
        if pb > 10:
            alerts.append({"level": "danger", "type": "pb", "message": f"PB={pb:.1f}，账面价值溢价过高"})
        elif pb < 1:
            alerts.append({"level": "info", "type": "pb", "message": f"PB={pb:.2f}，低于净资产，可能破净机会"})

    # 3. PEG预警
    if peg is not None and peg > 0:
        if peg > 2:
            alerts.append({"level": "danger", "type": "peg", "message": f"PEG={peg:.2f}，增速远不匹配估值，高估风险大"})
        elif peg > 1.5:
            alerts.append({"level": "warning", "type": "peg", "message": f"PEG={peg:.2f}，估值略高于增速"})
        elif peg < 0.8:
            alerts.append({"level": "safe", "type": "peg", "message": f"PEG={peg:.2f}，增速显著高于估值，成长性价比好"})

    # 4. EV/EBITDA预警
    if ev_ebitda is not None and ev_ebitda > 0:
        if ev_ebitda > 30:
            alerts.append({"level": "danger", "type": "ev_ebitda", "message": f"EV/EBITDA={ev_ebitda:.1f}，企业价值远超盈利"})
        elif ev_ebitda < 6:
            alerts.append({"level": "safe", "type": "ev_ebitda", "message": f"EV/EBITDA={ev_ebitda:.1f}，企业价值相对盈利偏低"})

    # 5. FCF Yield预警
    if fcf_yield is not None:
        if fcf_yield > 10:
            alerts.append({"level": "safe", "type": "fcf_yield", "message": f"FCF Yield={fcf_yield:.1f}%，现金回报极高"})
        elif fcf_yield < 2:
            alerts.append({"level": "warning", "type": "fcf_yield", "message": f"FCF Yield={fcf_yield:.1f}%，现金创造能力弱"})

    # 6. 历史分位数预警
    if pe_percentile is not None:
        if pe_percentile > 90:
            alerts.append({"level": "danger", "type": "pe_percentile",
                          "message": f"PE处于历史{pe_percentile:.0f}%分位，近历史最高水平"})
        elif pe_percentile < 10:
            alerts.append({"level": "safe", "type": "pe_percentile",
                          "message": f"PE处于历史{pe_percentile:.0f}%分位，近历史最低水平"})

    if pb_percentile is not None:
        if pb_percentile > 90:
            alerts.append({"level": "danger", "type": "pb_percentile",
                          "message": f"PB处于历史{pb_percentile:.0f}%分位，近历史最高水平"})
        elif pb_percentile < 10:
            alerts.append({"level": "safe", "type": "pb_percentile",
                          "message": f"PB处于历史{pb_percentile:.0f}%分位，近历史最低水平"})

    # 7. DCF vs 市价预警
    if intrinsic_value is not None and current_price is not None and current_price > 0:
        margin = (intrinsic_value / current_price - 1) * 100
        if margin > 50:
            alerts.append({"level": "safe", "type": "dcf",
                          "message": f"DCF内在价值({intrinsic_value:.2f})高于市价{margin:.0f}%，安全边际充足"})
        elif margin < -30:
            alerts.append({"level": "danger", "type": "dcf",
                          "message": f"DCF内在价值({intrinsic_value:.2f})低于市价{abs(margin):.0f}%，高估风险"})

    # 8. 综合评分预警
    if composite_score is not None:
        if composite_score >= 80:
            alerts.append({"level": "safe", "type": "composite",
                          "message": f"综合估值评分{composite_score:.0f}分，多项指标显示严重低估"})
        elif composite_score <= 25:
            alerts.append({"level": "danger", "type": "composite",
                          "message": f"综合估值评分{composite_score:.0f}分，多项指标显示高估"})

    # 按严重程度排序：danger > warning > info > safe
    level_order = {"danger": 0, "warning": 1, "info": 2, "safe": 3}
    alerts.sort(key=lambda a: level_order.get(a["level"], 99))

    return alerts


def build_sensitivity_matrix(
    current_fcf: float,
    growth_rate: float,
    shares: float,
    discount_rate: float = 0.10,
    terminal_growth_rate: float = 0.03,
    safety_margin: float = 0.30,
    net_debt: float = 0.0,
) -> dict:
    """
    构建DCF敏感性分析矩阵（增长率 x 折现率）

    Returns:
        {
            "growth_rates": ["2%", "5%", ...],
            "discount_rates": ["8%", "10%", ...],
            "matrix": [[val, val, ...], ...],
        }
    """
    growth_rates = [0.02, 0.05, 0.08, 0.10, 0.12, 0.15, 0.20]
    discount_rates = [0.08, 0.10, 0.12, 0.15]
    matrix = []

    for gr in growth_rates:
        row = []
        for dr in discount_rates:
            if dr <= terminal_growth_rate:
                row.append(None)
                continue
            try:
                s_dcf = DCFService(
                    discount_rate=dr,
                    terminal_growth_rate=terminal_growth_rate,
                    safety_margin=safety_margin,
                )
                s_result = s_dcf.calculate_intrinsic_value(
                    current_fcf=current_fcf,
                    growth_rate=gr,
                    shares=shares,
                    net_debt=net_debt,
                )
                row.append(s_result["intrinsic_value"])
            except (ValueError, ZeroDivisionError):
                row.append(None)
        matrix.append(row)

    return {
        "growth_rates": [f"{g*100:.0f}%" for g in growth_rates],
        "discount_rates": [f"{d*100:.0f}%" for d in discount_rates],
        "matrix": matrix,
    }
