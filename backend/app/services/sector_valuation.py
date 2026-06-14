"""
行业特异性估值模型

银行估值：P/TBV、NIM、不良率、拨备覆盖率
保险估值：PEV、综合成本率
REIT估值：FFO/AFFO、NAV折价

这些行业的现金流特征与普通企业不同，标准DCF不适用。
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def analyze_bank_valuation(
    # 价格数据
    current_price: float,
    total_shares: float,
    # 资产负债表
    total_equity: float,
    goodwill: float = 0,
    intangible_assets: float = 0,
    total_assets: float = 0,
    # 利润表
    net_interest_income: float = 0,
    operating_income: float = 0,
    net_profit: float = 0,
    operating_expense: float = 0,
    # 资产质量
    non_performing_loans: float = 0,
    total_loans: float = 0,
    loan_provisions: float = 0,
    # 其他
    deposit_cost: float = 0,
    loan_yield: float = 0,
) -> Dict[str, Any]:
    """
    银行估值分析

    银行的核心估值指标：
    1. P/TBV - 最核心的银行估值指标（比PB更准确，排除了商誉和无形资产）
    2. NIM - 净息差（银行的"毛利率"）
    3. 不良率 - 资产质量的核心指标
    4. 拨备覆盖率 - 风险抵御能力
    5. 成本收入比 - 经营效率
    """
    result = {
        "sector": "银行",
        "metrics": {},
        "valuation": {},
        "warnings": [],
        "strengths": [],
    }

    # market_cap单位取决于输入（元或亿元），保持一致性
    market_cap = current_price * total_shares

    # 1. TBV和P/TBV
    tbv = total_equity - goodwill - intangible_assets
    if tbv > 0 and market_cap > 0:
        p_tbv = market_cap / tbv  # 同单位相除
        result["metrics"]["tbv"] = round(tbv, 2)
        result["metrics"]["p_tbv"] = round(p_tbv, 2)

        if p_tbv < 0.6:
            result["valuation"]["p_tbv_level"] = "深度低估"
            result["strengths"].append(f"P/TBV={p_tbv:.2f}，估值处于历史低位")
        elif p_tbv < 1.0:
            result["valuation"]["p_tbv_level"] = "低估"
        elif p_tbv < 1.5:
            result["valuation"]["p_tbv_level"] = "合理"
        else:
            result["valuation"]["p_tbv_level"] = "偏高"
            result["warnings"].append(f"P/TBV={p_tbv:.2f}，估值偏高")

    # 2. NIM净息差
    if total_assets > 0 and net_interest_income > 0:
        nim = net_interest_income / total_assets * 100
        result["metrics"]["nim"] = round(nim, 2)

        if nim > 2.5:
            result["strengths"].append(f"NIM={nim:.2f}%，息差优秀")
        elif nim < 1.5:
            result["warnings"].append(f"NIM={nim:.2f}%，息差收窄压力大")

    # 3. 不良率
    if total_loans > 0 and non_performing_loans >= 0:
        npl_ratio = non_performing_loans / total_loans * 100
        result["metrics"]["npl_ratio"] = round(npl_ratio, 2)

        if npl_ratio < 1.0:
            result["strengths"].append(f"不良率{npl_ratio:.2f}%，资产质量优秀")
        elif npl_ratio < 1.5:
            pass  # 正常水平
        elif npl_ratio < 2.0:
            result["warnings"].append(f"不良率{npl_ratio:.2f}%，需关注资产质量")
        else:
            result["warnings"].append(f"不良率{npl_ratio:.2f}%，资产质量恶化")

    # 4. 拨备覆盖率
    if non_performing_loans > 0 and loan_provisions > 0:
        provision_coverage = loan_provisions / non_performing_loans * 100
        result["metrics"]["provision_coverage"] = round(provision_coverage, 2)

        if provision_coverage > 300:
            result["strengths"].append(f"拨备覆盖率{provision_coverage:.0f}%，风险抵御能力强")
        elif provision_coverage < 150:
            result["warnings"].append(f"拨备覆盖率仅{provision_coverage:.0f}%，低于监管红线")

    # 5. 成本收入比
    if operating_income > 0 and operating_expense > 0:
        cost_income_ratio = operating_expense / operating_income * 100
        result["metrics"]["cost_income_ratio"] = round(cost_income_ratio, 2)

        if cost_income_ratio < 30:
            result["strengths"].append(f"成本收入比{cost_income_ratio:.0f}%，经营效率极高")
        elif cost_income_ratio > 45:
            result["warnings"].append(f"成本收入比{cost_income_ratio:.0f}%，效率偏低")

    # 6. ROE
    if total_equity > 0 and net_profit > 0:
        roe = net_profit / total_equity * 100
        result["metrics"]["roe"] = round(roe, 2)

        if roe > 15:
            result["strengths"].append(f"ROE={roe:.1f}%，盈利能力优秀")
        elif roe < 8:
            result["warnings"].append(f"ROE={roe:.1f}%，盈利能力偏弱")

    # 综合估值评分（0-100）
    score = 50
    p_tbv = result["metrics"].get("p_tbv")
    if p_tbv:
        if p_tbv < 0.5:
            score += 25
        elif p_tbv < 0.8:
            score += 15
        elif p_tbv < 1.0:
            score += 5
        elif p_tbv > 1.5:
            score -= 15

    npl = result["metrics"].get("npl_ratio")
    if npl is not None:
        if npl < 1.0:
            score += 10
        elif npl > 2.0:
            score -= 15

    roe = result["metrics"].get("roe")
    if roe:
        if roe > 15:
            score += 10
        elif roe < 8:
            score -= 10

    result["valuation"]["score"] = max(0, min(100, score))
    if score >= 75:
        result["valuation"]["grade"] = "低估"
    elif score >= 55:
        result["valuation"]["grade"] = "合理"
    elif score >= 35:
        result["valuation"]["grade"] = "偏高"
    else:
        result["valuation"]["grade"] = "高估"

    return result


def analyze_insurance_valuation(
    current_price: float,
    total_shares: float,
    embedded_value: float = 0,
    new_business_value: float = 0,
    net_profit: float = 0,
    earned_premium: float = 0,
    underwriting_expense: float = 0,
    claims_expense: float = 0,
    total_equity: float = 0,
) -> Dict[str, Any]:
    """
    保险估值分析

    保险公司的核心估值指标：
    1. PEV - 最核心（P/EV = 市值/内含价值）
    2. 综合成本率 - 承保盈利能力
    3. 新业务价值增速 - 成长性
    """
    result = {
        "sector": "保险",
        "metrics": {},
        "valuation": {},
        "warnings": [],
        "strengths": [],
    }

    market_cap = current_price * total_shares

    # 1. PEV
    if embedded_value > 0 and market_cap > 0:
        pev = market_cap / embedded_value  # 同单位相除
        result["metrics"]["pev"] = round(pev, 2)

        if pev < 0.6:
            result["valuation"]["pev_level"] = "深度低估"
            result["strengths"].append(f"PEV={pev:.2f}，估值极低")
        elif pev < 1.0:
            result["valuation"]["pev_level"] = "低估"
        elif pev < 1.5:
            result["valuation"]["pev_level"] = "合理"
        else:
            result["valuation"]["pev_level"] = "偏高"

    # 2. 新业务价值倍数
    if new_business_value > 0 and market_cap > 0:
        p_nbv = market_cap / new_business_value  # 同单位相除
        result["metrics"]["p_nbv"] = round(p_nbv, 2)

    # 3. 综合成本率
    if earned_premium > 0:
        combined_ratio = (underwriting_expense + claims_expense) / earned_premium * 100
        result["metrics"]["combined_ratio"] = round(combined_ratio, 2)

        if combined_ratio < 95:
            result["strengths"].append(f"综合成本率{combined_ratio:.0f}%，承保盈利")
        elif combined_ratio > 105:
            result["warnings"].append(f"综合成本率{combined_ratio:.0f}%，承保亏损")

    # 4. ROE
    if total_equity > 0 and net_profit > 0:
        roe = net_profit / total_equity * 100
        result["metrics"]["roe"] = round(roe, 2)

    # 综合评分
    score = 50
    pev = result["metrics"].get("pev")
    if pev:
        if pev < 0.5:
            score += 25
        elif pev < 0.8:
            score += 15
        elif pev > 1.5:
            score -= 15

    cr = result["metrics"].get("combined_ratio")
    if cr:
        if cr < 95:
            score += 10
        elif cr > 105:
            score -= 15

    result["valuation"]["score"] = max(0, min(100, score))
    if score >= 75:
        result["valuation"]["grade"] = "低估"
    elif score >= 55:
        result["valuation"]["grade"] = "合理"
    elif score >= 35:
        result["valuation"]["grade"] = "偏高"
    else:
        result["valuation"]["grade"] = "高估"

    return result
