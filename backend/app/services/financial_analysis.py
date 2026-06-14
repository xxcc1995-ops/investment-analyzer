"""
机构级财务分析引擎

参考框架：
- 巴菲特：护城河、管理层资本配置、安全边际
- 高瓴：产业格局、长期结构性增长
- 高盛资管：ROIC、单位经济模型、现金转换周期

分析维度（7大类）：
1. 盈利能力与质量 - ROE/ROIC/毛利率/净利率/应计利润比率
2. 成长性分析 - CAGR/增长效率/增长驱动力
3. 财务安全性 - 杠杆/流动性/债务结构
4. 经营效率 - 费用率趋势/资产周转/资本密度
5. 现金流质量 - 经营现金流/利润偏离度/自由现金流
6. 护城河量化 - 毛利率稳定性/ROE持续性/定价权
7. 管理层评估 - 资本配置/留存收益回报率
"""

import logging
import math
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class DimensionResult:
    """单维度分析结果，分数限制在0-100"""
    score: int = 50
    metrics: Dict[str, Any] = field(default_factory=dict)
    strengths: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)

    def add_score(self, delta: int):
        """调整分数，限制在[0, 100]"""
        self.score = max(0, min(100, self.score + delta))


def analyze_financials(income: list, balance: list, cashflow: list) -> Dict[str, Any]:
    """机构级财务分析主入口"""
    # 取年报数据（10年）
    annual_income = [r for r in income if r.get("report_type") == "annual"][:10]
    annual_balance = [r for r in balance if r.get("report_type") == "annual"][:10]
    annual_cashflow = [r for r in cashflow if r.get("report_type") == "annual"][:10]

    # 7大维度分析
    dimensions = {}
    dimensions["earnings"] = _analyze_earnings(annual_income, annual_balance, annual_cashflow)
    dimensions["growth"] = _analyze_growth(annual_income)
    dimensions["safety"] = _analyze_safety(annual_balance, annual_income)
    dimensions["efficiency"] = _analyze_efficiency(annual_income, annual_balance)
    dimensions["cashflow"] = _analyze_cashflow_quality(annual_income, annual_cashflow)
    dimensions["moat"] = _analyze_moat(annual_income)
    dimensions["management"] = _analyze_management(annual_income, annual_balance, annual_cashflow)

    # 加权综合评分
    weights = {
        "earnings": 0.20,
        "growth": 0.15,
        "safety": 0.15,
        "efficiency": 0.10,
        "cashflow": 0.15,
        "moat": 0.15,
        "management": 0.10,
    }
    total_score = sum(dimensions[k].score * weights[k] for k in weights)
    score = round(total_score)

    # 评级
    if score >= 85:
        grade = "A"
    elif score >= 70:
        grade = "B"
    elif score >= 55:
        grade = "C"
    elif score >= 40:
        grade = "D"
    else:
        grade = "F"

    # 汇总
    all_strengths = []
    all_risks = []
    for d in dimensions.values():
        all_strengths.extend(d.strengths)
        all_risks.extend(d.risks)

    conclusion = _generate_conclusion(grade, dimensions)

    return {
        "score": score,
        "grade": grade,
        "conclusion": conclusion,
        "strengths": all_strengths[:8],
        "risks": all_risks[:8],
        "dimensions": {
            k: {"score": v.score, "metrics": v.metrics, "strengths": v.strengths, "risks": v.risks}
            for k, v in dimensions.items()
        },
        "dimension_scores": {k: v.score for k, v in dimensions.items()},
    }


# ==================== 维度1：盈利能力与质量 ====================

def _analyze_earnings(income: list, balance: list, cashflow: list) -> DimensionResult:
    """分析盈利能力与质量"""
    r = DimensionResult()
    if not income:
        return r

    latest = income[0]

    # 毛利率
    gm = latest.get("gross_margin")
    if gm is not None:
        r.metrics["gross_margin"] = gm
        if gm > 50:
            r.add_score(15)
            r.strengths.append(f"毛利率{gm:.1f}%，具备强定价权")
        elif gm > 30:
            r.add_score(8)
        elif gm < 15:
            r.add_score(-10)
            r.risks.append(f"毛利率仅{gm:.1f}%，盈利能力弱")

    # 净利率
    nm = latest.get("net_margin")
    if nm is not None:
        r.metrics["net_margin"] = nm
        if nm > 20:
            r.add_score(12)
            r.strengths.append(f"净利率{nm:.1f}%，赚钱效率高")
        elif nm > 10:
            r.add_score(5)
        elif nm < 3:
            r.add_score(-8)
            r.risks.append(f"净利率仅{nm:.1f}%")

    # ROE
    roe = latest.get("roe")
    if roe is not None:
        r.metrics["roe"] = roe
        if roe > 20:
            r.add_score(12)
            r.strengths.append(f"ROE {roe:.1f}%，资本回报率优秀")
        elif roe > 15:
            r.add_score(8)
        elif roe < 8:
            r.add_score(-5)

    # ROIC（用已有数据估算）
    roic = _estimate_roic(income, balance)
    if roic is not None:
        r.metrics["roic"] = roic
        if roic > 15:
            r.add_score(10)
            r.strengths.append(f"ROIC约{roic:.1f}%，创造经济价值")
        elif roic > 10:
            r.add_score(5)
        elif roic < 5:
            r.add_score(-8)
            r.risks.append(f"ROIC仅{roic:.1f}%，资本回报低于成本")

    # 盈利质量：应计利润比率
    if income and cashflow:
        aq = _calc_accruals_ratio(income[0], cashflow, balance)
        if aq is not None:
            r.metrics["accruals_ratio"] = aq
            if abs(aq) < 0.05:
                r.add_score(8)
                r.strengths.append("应计利润比率低，盈利质量高")
            elif aq > 0.1:
                r.add_score(-10)
                r.risks.append(f"应计利润比率{aq:.1%}，利润含金量存疑")

    # 盈利持续性：毛利率稳定性
    margins = [i.get("gross_margin") for i in income if i.get("gross_margin") is not None]
    if len(margins) >= 3:
        avg_gm = sum(margins) / len(margins)
        std_gm = (sum((m - avg_gm) ** 2 for m in margins) / len(margins)) ** 0.5
        if avg_gm > 0:
            cv = std_gm / avg_gm  # 变异系数
            r.metrics["gross_margin_cv"] = round(cv, 3)
            if cv < 0.1:
                r.add_score(5)
                r.strengths.append("毛利率高度稳定，盈利可预测")

    return r


def _estimate_roic(income: list, balance: list) -> float:
    """估算ROIC = NOPAT / 投入资本"""
    if not income or not balance:
        return None

    inc = income[0]
    bal = balance[0]

    operate_profit = inc.get("operate_profit")
    income_tax = inc.get("income_tax")
    total_profit = inc.get("total_profit")
    total_equity = bal.get("total_equity")
    total_liabilities = bal.get("total_liabilities")
    monetary = bal.get("monetary_funds") or 0

    if not operate_profit or not total_equity:
        return None

    # 估算有效税率
    tax_rate = 0.25  # 默认25%
    if income_tax and total_profit and total_profit > 0:
        tax_rate = min(max(income_tax / total_profit, 0.1), 0.35)

    # NOPAT = 营业利润 * (1 - 税率)
    nopat = operate_profit * (1 - tax_rate)

    # 投入资本 = 股东权益 + 有息负债 - 超额现金
    short_debt = bal.get("short_term_borrowing") or 0
    long_debt = bal.get("long_term_borrowing") or 0
    invested_capital = total_equity + short_debt + long_debt - monetary

    if invested_capital <= 0:
        return None

    return round(nopat / invested_capital * 100, 1)


def _calc_accruals_ratio(income: dict, cashflow: list, balance: list) -> float:
    """计算应计利润比率 = (净利润 - 经营现金流) / 总资产"""
    net_profit = income.get("parent_net_profit")
    if not net_profit or not cashflow:
        return None

    # 找对应日期的现金流
    cf = None
    for c in cashflow:
        if c.get("report_date") == income.get("report_date"):
            cf = c
            break
    if not cf:
        return None

    ocf = cf.get("netcash_operate")
    if ocf is None:
        return None

    # 找总资产
    total_assets = None
    if balance:
        for b in balance:
            if b.get("report_date") == income.get("report_date"):
                total_assets = b.get("total_assets")
                break
        if total_assets is None and balance:
            total_assets = balance[0].get("total_assets")

    if not total_assets or total_assets <= 0:
        return None

    return round((net_profit - ocf) / total_assets, 4)


# ==================== 维度2：成长性分析 ====================

def _analyze_growth(income: list) -> DimensionResult:
    """分析成长性"""
    r = DimensionResult()
    if len(income) < 3:
        return r

    # 营收CAGR（安全计算）
    revenues = [i.get("total_revenue") for i in income if i.get("total_revenue") and i.get("total_revenue") > 0]
    if len(revenues) >= 3:
        years = len(revenues) - 1
        # 安全检查：起始值不能为0
        if revenues[-1] > 0 and revenues[0] > 0:
            try:
                cagr = (revenues[0] / revenues[-1]) ** (1 / years) - 1
            except (ValueError, ZeroDivisionError):
                cagr = 0
            r.metrics["revenue_cagr"] = round(cagr * 100, 1)
            r.metrics["revenue_cagr_years"] = years

            if cagr > 0.15:
                r.add_score(18)
                r.strengths.append(f"营收{years}年复合增长率{cagr:.1%}，高成长")
            elif cagr > 0.08:
                r.add_score(10)
                r.strengths.append(f"营收{years}年复合增长率{cagr:.1%}，稳健增长")
            elif cagr > 0:
                r.add_score(3)
            else:
                r.add_score(-12)
                r.risks.append(f"营收{years}年复合增长率{cagr:.1%}，在萎缩")

    # 利润CAGR（安全计算，仅使用正值利润避免亏损年份扭曲）
    profits = [i.get("parent_net_profit") for i in income if i.get("parent_net_profit") and i.get("parent_net_profit") > 0]
    if len(profits) >= 3:
        years = len(profits) - 1
        if profits[-1] > 0 and profits[0] > 0:
            try:
                cagr = (profits[0] / profits[-1]) ** (1 / years) - 1
            except (ValueError, ZeroDivisionError):
                cagr = 0
            r.metrics["profit_cagr"] = round(cagr * 100, 1)

            if cagr > 0.20:
                r.add_score(15)
                r.strengths.append(f"净利润{years}年复合增长率{cagr:.1%}，盈利能力快速提升")
            elif cagr > 0.08:
                r.add_score(8)
            elif cagr < 0:
                r.add_score(-10)
                r.risks.append(f"净利润{years}年复合增长率{cagr:.1%}，盈利能力下降")

    # 增长效率：利润增速 vs 营收增速
    if len(revenues) >= 2 and len(profits) >= 2:
        rev_g = (revenues[0] - revenues[1]) / revenues[1] if revenues[1] else 0
        profit_g = (profits[0] - profits[1]) / profits[1] if profits[1] and profits[1] != 0 else 0

        if rev_g > 0 and profit_g > rev_g * 1.2:
            r.add_score(8)
            r.strengths.append("利润增速超过营收增速，经营杠杆正向")
        elif rev_g > 0 and profit_g < 0:
            r.add_score(-8)
            r.risks.append("营收增长但利润下降，成本失控")

    # 增长稳定性（营收增长率的标准差）
    if len(revenues) >= 4:
        growth_rates = []
        for i in range(len(revenues) - 1):
            if revenues[i + 1] > 0:
                growth_rates.append((revenues[i] - revenues[i + 1]) / revenues[i + 1])
        if growth_rates:
            avg = sum(growth_rates) / len(growth_rates)
            std = (sum((g - avg) ** 2 for g in growth_rates) / len(growth_rates)) ** 0.5
            r.metrics["growth_stability"] = round(std * 100, 1)
            if std < 0.1:
                r.add_score(5)
                r.strengths.append("增长非常稳定，可预测性强")
            elif std > 0.3:
                r.risks.append("增长波动大，可预测性差")

    return r


# ==================== 维度3：财务安全性 ====================

def _analyze_safety(balance: list, income: list) -> DimensionResult:
    """分析财务安全性"""
    r = DimensionResult()
    if not balance:
        return r

    latest = balance[0]

    # 资产负债率
    dr = latest.get("debt_ratio")
    if dr is not None:
        r.metrics["debt_ratio"] = dr
        if dr < 30:
            r.add_score(15)
            r.strengths.append(f"资产负债率{dr:.1f}%，财务极度稳健")
        elif dr < 50:
            r.add_score(8)
        elif dr > 65:
            r.add_score(-12)
            r.risks.append(f"资产负债率{dr:.1f}%，债务负担重")

    # 流动比率
    cr = latest.get("current_ratio")
    if cr is not None:
        r.metrics["current_ratio"] = cr
        if cr > 2:
            r.add_score(10)
        elif cr > 1.2:
            r.add_score(3)
        elif cr < 1:
            r.add_score(-10)
            r.risks.append(f"流动比率{cr:.1f}，短期偿债压力大")

    # 速动比率
    qr = latest.get("quick_ratio")
    if qr is not None:
        r.metrics["quick_ratio"] = qr
        if qr > 1:
            r.add_score(5)
        elif qr < 0.5:
            r.add_score(-5)

    # 短期借款占比
    short = latest.get("short_term_borrowing") or 0
    long_borrowing = latest.get("long_term_borrowing") or 0
    total_debt = short + long_borrowing
    if total_debt > 0:
        short_ratio = short / total_debt
        r.metrics["short_debt_ratio"] = round(short_ratio * 100, 1)
        if short_ratio > 0.7:
            r.add_score(-8)
            r.risks.append(f"短期借款占总有息负债{short_ratio:.0%}，再融资风险高")

    # 利息保障倍数
    if income:
        operate_profit = income[0].get("operate_profit")
        finance_expense = income[0].get("finance_expense")
        if operate_profit and finance_expense and finance_expense > 0:
            interest_coverage = operate_profit / finance_expense
            r.metrics["interest_coverage"] = round(interest_coverage, 1)
            if interest_coverage > 10:
                r.add_score(8)
                r.strengths.append(f"利息保障倍数{interest_coverage:.0f}倍，偿债无忧")
            elif interest_coverage < 3:
                r.add_score(-8)
                r.risks.append(f"利息保障倍数仅{interest_coverage:.1f}倍，偿债压力大")

    # 负债趋势：检查最近一年负债率变化
    if len(balance) >= 2:
        prev_dr = balance[1].get("debt_ratio")
        if dr is not None and prev_dr is not None and prev_dr > 0:
            dr_change = dr - prev_dr
            r.metrics["debt_ratio_change"] = round(dr_change, 1)
            if dr_change > 5:
                r.add_score(-5)
                r.risks.append(f"资产负债率同比上升{dr_change:.1f}个百分点，杠杆扩大")
            elif dr_change < -5:
                r.add_score(3)
                r.strengths.append(f"资产负债率同比下降{abs(dr_change):.1f}个百分点，去杠杆中")

    return r


# ==================== 维度4：经营效率 ====================

def _analyze_efficiency(income: list, balance: list) -> DimensionResult:
    """分析经营效率"""
    r = DimensionResult()
    if not income:
        return r

    latest = income[0]

    # 费用率分析
    sell = latest.get("sell_expense_ratio")
    manage = latest.get("manage_expense_ratio")
    rd = latest.get("research_expense_ratio")
    finance = latest.get("finance_expense_ratio")

    if sell is not None:
        r.metrics["sell_expense_ratio"] = sell
    if manage is not None:
        r.metrics["manage_expense_ratio"] = manage
    if rd is not None:
        r.metrics["rd_expense_ratio"] = rd
    if finance is not None:
        r.metrics["finance_expense_ratio"] = finance

    # 研发投入
    if rd is not None:
        if rd > 10:
            r.add_score(10)
            r.strengths.append(f"研发费用率{rd:.1f}%，研发投入高")
        elif rd > 5:
            r.add_score(5)
        elif 0 < rd < 1:
            r.risks.append(f"研发费用率仅{rd:.1f}%，可能缺乏创新投入")

    # 财务费用
    if finance is not None:
        if finance < 0:
            r.add_score(8)
            r.strengths.append("财务费用为负，利息收入大于支出")
        elif finance > 5:
            r.add_score(-5)
            r.risks.append(f"财务费用率{finance:.1f}%，利息负担重")

    # 费用率趋势
    if len(income) >= 4:
        old_sell = income[-1].get("sell_expense_ratio") or 0
        old_manage = income[-1].get("manage_expense_ratio") or 0
        new_sell = income[0].get("sell_expense_ratio") or 0
        new_manage = income[0].get("manage_expense_ratio") or 0
        old_total = old_sell + old_manage
        new_total = new_sell + new_manage
        if old_total > 0:
            change = (new_total - old_total) / old_total
            if change < -0.1:
                r.add_score(8)
                r.strengths.append(f"期间费用率下降{abs(change):.0%}，效率提升")
            elif change > 0.2:
                r.add_score(-5)
                r.risks.append(f"期间费用率上升{change:.0%}，效率下降")

    # 资产周转率
    if balance and income:
        revenue = latest.get("total_revenue")
        total_assets = balance[0].get("total_assets")
        if revenue and total_assets and total_assets > 0:
            turnover = revenue / total_assets
            r.metrics["asset_turnover"] = round(turnover, 2)
            if turnover > 0.8:
                r.add_score(5)
            elif turnover < 0.3:
                r.risks.append(f"资产周转率{turnover:.2f}，资产效率低")

    return r


# ==================== 维度5：现金流质量 ====================

def _analyze_cashflow_quality(income: list, cashflow: list) -> DimensionResult:
    """分析现金流质量"""
    r = DimensionResult()
    if not cashflow:
        return r

    # 自由现金流
    fcf = cashflow[0].get("free_cashflow")
    if fcf is not None:
        r.metrics["free_cashflow"] = fcf
        if fcf > 0:
            r.add_score(15)
            r.strengths.append("自由现金流为正，公司能自己养活自己")
        else:
            r.add_score(-10)
            r.risks.append("自由现金流为负，需要外部融资")

    # 自由现金流趋势
    fcf_list = [c.get("free_cashflow") for c in cashflow[:5] if c.get("free_cashflow") is not None]
    if len(fcf_list) >= 2:
        positive_fcf_count = sum(1 for x in fcf_list if x > 0)
        if positive_fcf_count == len(fcf_list):
            r.add_score(5)
            r.strengths.append("连续多年自由现金流为正")
        elif positive_fcf_count == 0:
            r.risks.append("连续多年自由现金流为负")

    # 经营现金流/净利润
    if income and cashflow:
        cf_map = {c["report_date"]: c for c in cashflow}
        ratios = []
        for inc in income[:5]:
            cf = cf_map.get(inc["report_date"])
            if cf and cf.get("netcash_operate") and inc.get("parent_net_profit") and inc["parent_net_profit"] != 0:
                ratios.append(cf["netcash_operate"] / inc["parent_net_profit"])
        if ratios:
            avg_ratio = sum(ratios) / len(ratios)
            r.metrics["avg_cash_to_profit"] = round(avg_ratio * 100, 1)
            if avg_ratio > 1.2:
                r.add_score(12)
                r.strengths.append(f"平均经营现金流/净利润={avg_ratio:.0%}，利润含金量高")
            elif avg_ratio > 0.8:
                r.add_score(5)
            else:
                r.add_score(-10)
                r.risks.append(f"平均经营现金流/净利润={avg_ratio:.0%}，利润质量差")

    # 经营现金流趋势
    ocf_list = [c.get("netcash_operate") for c in cashflow[:5] if c.get("netcash_operate") is not None]
    if len(ocf_list) >= 3:
        positive_count = sum(1 for x in ocf_list if x > 0)
        if positive_count == len(ocf_list):
            r.add_score(8)
            r.strengths.append("连续多年经营现金流为正")
        elif positive_count < len(ocf_list) // 2:
            r.add_score(-8)
            r.risks.append("经营现金流时正时负")

    return r


# ==================== 维度6：护城河量化 ====================

def _analyze_moat(income: list) -> DimensionResult:
    """量化护城河"""
    r = DimensionResult()
    if len(income) < 3:
        return r

    # 毛利率稳定性（标准差越小越好）
    margins = [i.get("gross_margin") for i in income if i.get("gross_margin") is not None]
    if len(margins) >= 3:
        avg = sum(margins) / len(margins)
        std = (sum((m - avg) ** 2 for m in margins) / len(margins)) ** 0.5
        r.metrics["gross_margin_avg"] = round(avg, 1)
        r.metrics["gross_margin_std"] = round(std, 1)
        r.metrics["gross_margin_stability"] = round(1 - min(std / avg, 1), 2) if avg > 0 else 0

        if avg > 40 and std < 5:
            r.add_score(18)
            r.strengths.append(f"毛利率均值{avg:.0f}%且极稳定(σ={std:.1f})，护城河宽")
        elif avg > 30 and std < 8:
            r.add_score(10)
            r.strengths.append(f"毛利率均值{avg:.0f}%较稳定，有一定护城河")
        elif std > 15:
            r.risks.append(f"毛利率波动大(σ={std:.1f})，缺乏定价权")

    # ROE持续性
    roes = [i.get("roe") for i in income if i.get("roe") is not None]
    if len(roes) >= 3:
        high_roe_count = sum(1 for r_val in roes if r_val > 15)
        r.metrics["roe_above_15_count"] = high_roe_count
        r.metrics["roe_total_years"] = len(roes)
        if high_roe_count >= len(roes) * 0.8:
            r.add_score(15)
            r.strengths.append(f"{high_roe_count}/{len(roes)}年ROE>15%，盈利能力持续")
        elif high_roe_count < len(roes) * 0.3:
            r.risks.append(f"仅{high_roe_count}/{len(roes)}年ROE>15%")

    # 定价权指标：毛利率趋势
    if len(margins) >= 4:
        recent_avg = sum(margins[:2]) / 2
        old_avg = sum(margins[-2:]) / 2
        if old_avg > 0:
            margin_change = (recent_avg - old_avg) / old_avg
            if margin_change > 0.05:
                r.add_score(8)
                r.strengths.append("毛利率趋势向上，定价权增强")
            elif margin_change < -0.1:
                r.add_score(-8)
                r.risks.append("毛利率趋势下降，定价权减弱")

    return r


# ==================== 维度7：管理层评估 ====================

def _analyze_management(income: list, balance: list, cashflow: list) -> DimensionResult:
    """评估管理层资本配置能力"""
    r = DimensionResult()

    # 留存收益回报率 = 增量利润 / 增量留存收益
    if len(income) >= 2 and len(balance) >= 2:
        profit_delta = (income[0].get("parent_net_profit") or 0) - (income[1].get("parent_net_profit") or 0)
        equity_delta = (balance[0].get("total_equity") or 0) - (balance[1].get("total_equity") or 0)

        if equity_delta > 0 and profit_delta > 0:
            retention_return = profit_delta / equity_delta
            r.metrics["retention_return"] = round(retention_return * 100, 1)
            if retention_return > 0.15:
                r.add_score(15)
                r.strengths.append(f"留存收益回报率{retention_return:.0%}，管理层善用资本")
            elif retention_return > 0.08:
                r.add_score(8)
            elif retention_return < 0.03:
                r.risks.append(f"留存收益回报率仅{retention_return:.0%}，资本配置效率低")

    # 资本密度（资本开支/营收）
    if income and cashflow:
        revenue = income[0].get("total_revenue")
        # 使用CAPEX字段（更准确）或投资活动现金流近似
        capex = cashflow[0].get("capex")
        invest_cf = cashflow[0].get("netcash_invest") if cashflow else None
        capex_val = capex if capex else (abs(invest_cf) if invest_cf and invest_cf < 0 else None)

        if revenue and capex_val and revenue > 0:
            capex_ratio = capex_val / revenue
            r.metrics["capex_ratio"] = round(capex_ratio * 100, 1)
            if capex_ratio < 0.05:
                r.add_score(8)
                r.strengths.append(f"资本开支/营收={capex_ratio:.0%}，轻资产模式")
            elif capex_ratio > 0.2:
                r.risks.append(f"资本开支/营收={capex_ratio:.0%}，重资产模式")

    # 分红倾向：筹资活动现金流中的分红支出
    # 注：更精确的分红数据应从分红历史API获取

    return r


# ==================== 结论生成 ====================

def _generate_conclusion(grade: str, dimensions: dict) -> str:
    """生成投资结论"""
    strengths = []
    risks = []
    for d in dimensions.values():
        strengths.extend(d.strengths)
        risks.extend(d.risks)

    if grade in ("A", "B"):
        parts = []
        if any("护城河" in s or "毛利率" in s for s in strengths):
            parts.append("具备护城河")
        if any("ROE" in s or "ROIC" in s for s in strengths):
            parts.append("资本回报率优秀")
        if any("增长" in s or "成长" in s for s in strengths):
            parts.append("成长性好")
        if any("现金流" in s for s in strengths):
            parts.append("现金流健康")
        if parts:
            return f"优质标的：{'、'.join(parts)}，值得深入研究"
        return "基本面扎实，财务状况良好"
    elif grade == "C":
        if risks:
            return f"基本面中等，需关注{risks[0][:20]}..."
        return "基本面中等，无明显优势也无明显风险"
    else:
        return "基本面较弱，建议谨慎对待"


# ==================== 保留旧接口兼容 ====================

class AnalysisResult:
    """兼容旧接口"""
    pass
