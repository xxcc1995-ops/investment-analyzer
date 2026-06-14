"""攒股收息筛选服务 - 基于王文和散户乙投资思想的股票筛选

机构级增强：
- 股息率计算：基于TTM实际分红（中期+年终），排除特别股息干扰
- 连续分红年数：按财政年度分组统计，正确处理中期分红
- 股息增长率：3年/5年CAGR计算
- 派息率可持续性：>100%标记为不可持续，>80%为偏高
- 特别股息检测：显著偏离历史中位数的异常分红
"""

import logging
from datetime import datetime
from typing import Dict, List, Tuple

from app.services.data_service import DataService

logger = logging.getLogger(__name__)


def calculate_wangwen_score(stock: dict) -> Tuple[int, int]:
    """计算王文标准评分 (满分100)

    Args:
        stock: 股票数据字典

    Returns:
        (score, match_count) 元组
    """
    score = 0
    match_count = 0

    # 股息率 (30分)
    dividend_yield = stock.get("dividend_yield") or 0
    if dividend_yield >= 5:
        score += 30
        match_count += 1
    elif dividend_yield >= 4:
        score += 25
        match_count += 1
    elif dividend_yield >= 3:
        score += 15
    elif dividend_yield >= 2:
        score += 5

    # PE (20分)
    pe = stock.get("pe") or 999
    if pe <= 10:
        score += 20
        match_count += 1
    elif pe <= 15:
        score += 15
        match_count += 1
    elif pe <= 20:
        score += 8
    elif pe <= 25:
        score += 3

    # PB (10分)
    pb = stock.get("pb") or 999
    if pb <= 1:
        score += 10
        match_count += 1
    elif pb <= 2:
        score += 7
        match_count += 1
    elif pb <= 3:
        score += 3

    # 连续分红年数 (15分)
    years = stock.get("consecutive_years") or 0
    if years >= 10:
        score += 15
        match_count += 1
    elif years >= 5:
        score += 12
        match_count += 1
    elif years >= 3:
        score += 6

    # 分红比例 (10分)
    ratio = stock.get("dividend_ratio") or 0
    if 30 <= ratio <= 70:
        score += 10
        match_count += 1
    elif 20 <= ratio <= 80:
        score += 5

    # 资产负债率 (10分)
    debt = stock.get("debt_ratio") or 100
    if debt <= 40:
        score += 10
        match_count += 1
    elif debt <= 60:
        score += 7
        match_count += 1
    elif debt <= 70:
        score += 3

    # 经营现金流为正 (5分)
    if stock.get("operating_cashflow") and stock["operating_cashflow"] > 0:
        score += 5
        match_count += 1

    # 股息增长率 CAGR (10分) - 王文重视分红的持续增长
    cagr_3y = stock.get("dividend_cagr_3y")
    cagr_5y = stock.get("dividend_cagr_5y")
    best_cagr = max(c for c in [cagr_3y, cagr_5y] if c is not None) if (cagr_3y is not None or cagr_5y is not None) else None
    if best_cagr is not None:
        if best_cagr >= 10:
            score += 10
            match_count += 1
        elif best_cagr >= 5:
            score += 8
            match_count += 1
        elif best_cagr >= 0:
            score += 4
        # 负增长不加分

    # 派息率可持续性 (5分) - 排除不可持续的高派息
    payout_sus = stock.get("payout_sustainability", "unknown")
    if payout_sus == "sustainable":
        score += 5
        match_count += 1
    elif payout_sus == "high":
        score += 2

    return score, match_count


def calculate_sanhuyi_score(stock: dict) -> Tuple[int, int]:
    """计算散户乙标准评分 (满分100)

    Args:
        stock: 股票数据字典

    Returns:
        (score, match_count) 元组
    """
    score = 0
    match_count = 0

    # ROE (30分)
    roe = stock.get("roe") or 0
    if roe >= 20:
        score += 30
        match_count += 1
    elif roe >= 15:
        score += 25
        match_count += 1
    elif roe >= 10:
        score += 12
    elif roe >= 8:
        score += 5

    # 股息率 (25分)
    dividend_yield = stock.get("dividend_yield") or 0
    if dividend_yield >= 5:
        score += 25
        match_count += 1
    elif dividend_yield >= 3:
        score += 20
        match_count += 1
    elif dividend_yield >= 2:
        score += 10

    # 毛利率 (20分)
    gross_margin = stock.get("gross_margin") or 0
    if gross_margin >= 50:
        score += 20
        match_count += 1
    elif gross_margin >= 30:
        score += 15
        match_count += 1
    elif gross_margin >= 20:
        score += 8

    # 净利率 (15分)
    net_margin = stock.get("net_margin") or 0
    if net_margin >= 20:
        score += 15
        match_count += 1
    elif net_margin >= 15:
        score += 12
        match_count += 1
    elif net_margin >= 10:
        score += 6

    # 资产负债率 (10分)
    debt = stock.get("debt_ratio") or 100
    if debt <= 40:
        score += 10
        match_count += 1
    elif debt <= 60:
        score += 7
        match_count += 1
    elif debt <= 70:
        score += 3

    # 股息增长率 CAGR (10分) - 散户乙重视复利增长
    cagr_3y = stock.get("dividend_cagr_3y")
    cagr_5y = stock.get("dividend_cagr_5y")
    best_cagr = max(c for c in [cagr_3y, cagr_5y] if c is not None) if (cagr_3y is not None or cagr_5y is not None) else None
    if best_cagr is not None:
        if best_cagr >= 10:
            score += 10
            match_count += 1
        elif best_cagr >= 5:
            score += 8
            match_count += 1
        elif best_cagr >= 0:
            score += 4
        # 负增长不加分

    # 派息率可持续性 (5分) - 高ROE+合理派息才是可持续的
    payout_sus = stock.get("payout_sustainability", "unknown")
    if payout_sus == "sustainable":
        score += 5
        match_count += 1
    elif payout_sus == "high":
        score += 2

    return score, match_count


def get_dividend_screener(master: str = "combined") -> Dict:
    """基于王文和散户乙投资思想的股票筛选

    Args:
        master: 筛选标准 (combined/wangwen/sanhuyi)

    Returns:
        {
            "stocks": [...],
            "update_time": str,
            "master": str,
            "total": int
        }
    """
    data_service = DataService()
    stocks = data_service.get_dividend_stocks()

    filtered = []
    for stock in stocks:
        score = 0
        match_count = 0
        total_criteria = 0

        # 王文标准
        if master in ["wangwen", "combined"]:
            wangwen_score, wangwen_match = calculate_wangwen_score(stock)
            score += wangwen_score * (0.6 if master == "combined" else 1.0)
            match_count += wangwen_match
            total_criteria += 9

        # 散户乙标准
        if master in ["sanhuyi", "combined"]:
            sanhuyi_score, sanhuyi_match = calculate_sanhuyi_score(stock)
            score += sanhuyi_score * (0.4 if master == "combined" else 1.0)
            match_count += sanhuyi_match
            total_criteria += 7

        # 计算综合评分
        final_score = int(score)

        # 确定匹配度
        if final_score >= 80:
            match_level = "excellent"
        elif final_score >= 60:
            match_level = "good"
        elif final_score >= 40:
            match_level = "fair"
        else:
            match_level = "poor"

        # 只保留评分40分以上的
        if final_score >= 40:
            stock["score"] = final_score
            stock["match_level"] = match_level
            filtered.append(stock)

    # 按评分排序
    filtered.sort(key=lambda x: x["score"], reverse=True)

    return {
        "stocks": filtered,
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "master": master,
        "total": len(filtered)
    }
