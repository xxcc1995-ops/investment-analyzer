"""商业模式脆弱性/反脆弱性分析服务

基于Nassim Taleb的脆弱性/反脆弱性框架，结合财务数据量化评估公司商业模式的韧性。
"""

import logging
from app.services.data_service import DataService
from app.core.cache import get_cache, set_cache

logger = logging.getLogger(__name__)


def analyze_fragility(stock_code: str) -> dict:
    """分析公司商业模式的脆弱性/反脆弱性"""
    cache_key = f"fragility_{stock_code}"
    cached = get_cache(cache_key, ttl_seconds=600)
    if cached:
        return cached

    try:
        # 获取基本面数据（PE/PB）
        basic = DataService.get_stock_basic(stock_code)
        if "error" in basic:
            return {"error": basic["error"]}

        # 获取财务指标
        financials = DataService.get_financial_indicators(stock_code)
        if "error" in financials:
            return {"error": financials["error"]}

        # 取最新年报数据
        reports = financials.get("reports", [])
        if not reports:
            return {"error": "无财务数据"}

        latest = reports[0]
        pe = basic.get("pe")
        pb = basic.get("pb")
        roe = latest.get("roe")
        gross_margin = latest.get("gross_margin")
        net_margin = latest.get("net_margin")
        debt_ratio = latest.get("debt_ratio")
        revenue_growth = latest.get("revenue_growth")
        profit_growth = latest.get("profit_growth")

        # 六维度评分
        dimensions = []

        # 1. 债务脆弱性 (20分)
        debt_score, debt_label, debt_signal = _score_debt(debt_ratio)
        dimensions.append({
            "name": "债务韧性",
            "score": debt_score,
            "max": 20,
            "label": debt_label,
            "signal": debt_signal,
            "value": f"{debt_ratio:.1f}%" if debt_ratio is not None else "N/A",
        })

        # 2. 利润护城河 (20分)
        margin_score, margin_label, margin_signal = _score_gross_margin(gross_margin)
        dimensions.append({
            "name": "利润护城河",
            "score": margin_score,
            "max": 20,
            "label": margin_label,
            "signal": margin_signal,
            "value": f"{gross_margin:.1f}%" if gross_margin is not None else "N/A",
        })

        # 3. 盈利质量 (15分)
        net_score, net_label, net_signal = _score_net_margin(net_margin)
        dimensions.append({
            "name": "盈利质量",
            "score": net_score,
            "max": 15,
            "label": net_label,
            "signal": net_signal,
            "value": f"{net_margin:.1f}%" if net_margin is not None else "N/A",
        })

        # 4. 成长稳定性 (15分)
        growth_score, growth_label, growth_signal = _score_growth(revenue_growth, profit_growth)
        dimensions.append({
            "name": "成长稳定性",
            "score": growth_score,
            "max": 15,
            "label": growth_label,
            "signal": growth_signal,
            "value": f"营{'↑' if revenue_growth and revenue_growth > 0 else '↓'} 利{'↑' if profit_growth and profit_growth > 0 else '↓'}",
        })

        # 5. ROE资本效率 (15分)
        roe_score, roe_label, roe_signal = _score_roe(roe)
        dimensions.append({
            "name": "资本效率",
            "score": roe_score,
            "max": 15,
            "label": roe_label,
            "signal": roe_signal,
            "value": f"{roe:.1f}%" if roe is not None else "N/A",
        })

        # 6. 估值韧性 (15分)
        val_score, val_label, val_signal = _score_valuation(pe, pb)
        dimensions.append({
            "name": "估值韧性",
            "score": val_score,
            "max": 15,
            "label": val_label,
            "signal": val_signal,
            "value": f"PE={pe:.1f} PB={pb:.2f}" if pe and pb else "N/A",
        })

        total_score = sum(d["score"] for d in dimensions)
        total_max = sum(d["max"] for d in dimensions)

        # 最终判定
        if total_score >= 75:
            verdict = "反脆弱型"
            verdict_desc = "商业模式坚韧，抗风险能力强，能在不确定性中受益"
            color = "#16a34a"
        elif total_score >= 60:
            verdict = "稳健型"
            verdict_desc = "有一定护城河，需关注薄弱环节"
            color = "#ca8a04"
        elif total_score >= 40:
            verdict = "脆弱型"
            verdict_desc = "存在明显弱点，抗风险能力不足"
            color = "#ea580c"
        else:
            verdict = "高度脆弱"
            verdict_desc = "商业模式风险大，建议排除"
            color = "#dc2626"

        # 薄弱环节
        warnings = [d for d in dimensions if d["score"] / d["max"] < 0.4]

        result = {
            "code": stock_code,
            "name": basic.get("name", ""),
            "total_score": total_score,
            "max_score": total_max,
            "verdict": verdict,
            "verdict_desc": verdict_desc,
            "color": color,
            "dimensions": dimensions,
            "warnings": [{"name": w["name"], "label": w["label"], "signal": w["signal"]} for w in warnings],
            "report_period": latest.get("report_name", latest.get("date", "")),
        }

        set_cache(cache_key, result)
        return result

    except Exception as e:
        logger.error(f"analyze_fragility failed for {stock_code}: {e}")
        return {"error": f"分析失败: {str(e)}"}


def _score_debt(debt_ratio):
    """债务脆弱性评分 (20分)"""
    if debt_ratio is None:
        return 10, "未知", "缺少负债率数据"
    if debt_ratio < 30:
        return 20, "反脆弱", "极低负债，财务安全"
    elif debt_ratio < 50:
        return 15, "稳健", "负债适中，风险可控"
    elif debt_ratio < 70:
        return 8, "脆弱", "负债偏高，需关注偿债能力"
    else:
        return 2, "极脆弱", "高负债经营，财务风险大"


def _score_gross_margin(gross_margin):
    """利润护城河评分 (20分)"""
    if gross_margin is None:
        return 10, "未知", "缺少毛利率数据"
    if gross_margin > 50:
        return 20, "强护城河", "高毛利率，定价权强"
    elif gross_margin > 30:
        return 14, "中等护城河", "毛利率尚可，有一定竞争力"
    elif gross_margin > 15:
        return 8, "弱护城河", "毛利率偏低，竞争激烈"
    else:
        return 2, "无护城河", "极低毛利率，同质化严重"


def _score_net_margin(net_margin):
    """盈利质量评分 (15分)"""
    if net_margin is None:
        return 7, "未知", "缺少净利率数据"
    if net_margin > 20:
        return 15, "优质", "高净利，盈利能力突出"
    elif net_margin > 10:
        return 10, "良好", "净利合理"
    elif net_margin > 5:
        return 6, "一般", "净利偏低"
    else:
        return 2, "脆弱", "微利或亏损"


def _score_growth(revenue_growth, profit_growth):
    """成长稳定性评分 (15分)"""
    rg = revenue_growth
    pg = profit_growth
    if rg is None and pg is None:
        return 7, "未知", "缺少增长率数据"
    if rg is not None and pg is not None:
        if rg > 15 and pg > 15:
            return 15, "强劲", "营收利润双高增长"
        elif rg > 5 and pg > 5:
            return 10, "稳健", "双增长，成长性良好"
        elif (rg > 0 and pg < 0) or (rg < 0 and pg > 0):
            return 6, "波动", "增长不一致，稳定性存疑"
        elif rg < 0 and pg < 0:
            return 2, "衰退", "营收利润双降，基本面恶化"
        else:
            return 8, "平稳", "低速增长"
    # 只有一个数据
    val = rg if rg is not None else pg
    if val > 15:
        return 12, "良好", "高增长"
    elif val > 0:
        return 8, "平稳", "正增长"
    else:
        return 4, "下滑", "负增长"


def _score_roe(roe):
    """ROE资本效率评分 (15分)"""
    if roe is None:
        return 7, "未知", "缺少ROE数据"
    if roe > 20:
        return 15, "高效", "资本回报卓越"
    elif roe > 15:
        return 11, "良好", "资本回报优秀"
    elif roe > 10:
        return 7, "一般", "资本回报尚可"
    else:
        return 3, "低效", "资本回报偏低"


def _score_valuation(pe, pb):
    """估值韧性评分 (15分)"""
    if pe is None or pb is None:
        return 7, "未知", "缺少估值数据"
    if pe <= 0:
        return 4, "亏损", "市盈率为负，公司亏损"
    elif pe < 15 and pb < 2:
        return 15, "低估韧性", "低估值提供安全边际"
    elif pe < 25 and pb < 4:
        return 10, "合理", "估值适中"
    elif pe < 40 and pb < 8:
        return 6, "偏高", "估值偏贵，下行风险较大"
    else:
        return 4, "高估脆弱", "高估值高风险"
