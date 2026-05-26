from fastapi import APIRouter
from app.services.data_service import DataService
from datetime import datetime

router = APIRouter()
data_service = DataService()


@router.get("/screener")
def dividend_screener(master: str = "combined"):
    """
    基于王文和散户乙投资思想的股票筛选

    参数:
    - master: 筛选标准 (combined/wangwen/sanhuyi)
    """
    # 获取A股主要高股息股票数据
    stocks = data_service.get_dividend_stocks()

    # 根据不同大师的标准筛选
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
            total_criteria += 7

        # 散户乙标准
        if master in ["sanhuyi", "combined"]:
            sanhuyi_score, sanhuyi_match = calculate_sanhuyi_score(stock)
            score += sanhuyi_score * (0.4 if master == "combined" else 1.0)
            match_count += sanhuyi_match
            total_criteria += 5

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


def calculate_wangwen_score(stock: dict) -> tuple:
    """计算王文标准评分 (满分100)"""
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

    return score, match_count


def calculate_sanhuyi_score(stock: dict) -> tuple:
    """计算散户乙标准评分 (满分100)"""
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

    return score, match_count
