"""金渐成（机哥）投资体系筛选服务 - 第一兼唯一选股法"""

import requests
import time
from typing import Optional
from datetime import datetime
from app.services.data_service import DataService, _safe_float, _get_annual_report
from app.services.vi_service import _get_hk_stock_data, _get_us_stock_data

# ============================================================
# 金渐成核心投资理念
# ============================================================
# 1. "第一兼唯一" - 只投行业第一且具有垄断地位的公司
# 2. 两大类别：改变未来的科技龙头 + 不被未来改变的消费/避险股
# 3. 三大赛道：科技、消费、医疗保健
# 4. 管理层至上：诚实可靠、踏实进取、眼光长远
# 5. 下跌20%开始试探，25%加仓；金字塔加仓，倒金字塔卖出
# 6. 永不满仓，7成底仓+3成做T
# 7. 进取:稳健:防守 = 4:1.5:4.5

# ============================================================
# 股票池 - 基于金渐成实际持仓和关注标的
# ============================================================

# 行业地位标签：用于"第一兼唯一"评分
INDUSTRY_POSITION = {
    # A股 - 行业龙头
    "000651": ("家电龙头", 20), "600519": ("白酒龙头", 20), "000333": ("家电龙头", 18),
    "601318": ("保险龙头", 18), "600036": ("零售银行龙头", 18), "600900": ("水电龙头", 20),
    "600941": ("运营商龙头", 18), "601088": ("煤炭龙头", 16), "603288": ("调味品龙头", 20),
    "600887": ("乳业龙头", 18), "600276": ("创新药龙头", 18), "601012": ("光伏龙头", 16),
    "300750": ("动力电池龙头", 20), "002594": ("新能源车龙头", 18), "600030": ("券商龙头", 14),
    # 港股
    "00700": ("互联网龙头", 20), "09988": ("电商龙头", 18), "03690": ("本地生活龙头", 18),
    "01810": ("IoT龙头", 16), "01211": ("新能源车龙头", 18), "09992": ("潮玩龙头", 16),
    # 美股 - Mag7 + 半导体 + 消费 + 医疗
    "NVDA": ("AI芯片龙头", 20), "MSFT": ("云计算+AI龙头", 20), "AAPL": ("消费电子龙头", 20),
    "GOOG": ("搜索+AI龙头", 20), "AMZN": ("电商+云龙头", 20), "META": ("社交+AI龙头", 18),
    "TSLA": ("电动车+机器人龙头", 16), "TSM": ("芯片代工龙头", 20), "AVGO": ("芯片设计龙头", 18),
    "AMD": ("CPU/GPU龙头", 16), "COST": ("会员零售龙头", 20), "WMT": ("零售龙头", 18),
    "MCD": ("快餐龙头", 18), "PG": ("日化龙头", 18), "KO": ("饮料龙头", 20),
    "LLY": ("创新药龙头", 18), "UNH": ("医疗保险龙头", 18), "JNJ": ("医疗龙头", 16),
    "BRK-B": ("投资龙头", 20), "V": ("支付龙头", 20), "MO": ("烟草龙头", 16),
}

A_STOCKS_LIST = [
    "000651", "600519", "000333", "601318", "600036", "600900",
    "600941", "601088", "603288", "600887", "600276", "601012",
    "300750", "002594", "600030",
]

HK_STOCKS_LIST = [
    "00700", "09988", "03690", "01810", "01211", "09992",
]

US_STOCKS_LIST = [
    "NVDA", "MSFT", "AAPL", "GOOG", "AMZN", "META", "TSLA",
    "TSM", "AVGO", "AMD",
    "COST", "WMT", "MCD", "PG", "KO",
    "LLY", "UNH", "JNJ",
    "BRK-B", "V", "MO",
]

# ============================================================
# Data Fetching (reuse existing functions)
# ============================================================

def _get_a_stock_data(code: str) -> Optional[dict]:
    """Fetch A-share data from EastMoney."""
    try:
        basic = DataService.get_stock_basic(code)
        if "error" in basic:
            return None

        financials = DataService.get_financial_indicators(code)
        reports = financials.get("reports", [])
        latest = _get_annual_report(reports) if reports else {}

        div_per_share, _, _ = DataService._get_actual_dividend(code)
        dividend_yield = None
        if div_per_share > 0 and basic.get('price', 0) > 0:
            dividend_yield = round(div_per_share / basic['price'] * 100, 2)

        return {
            'code': code, 'name': basic.get('name', ''), 'market': 'A',
            'price': basic.get('price', 0),
            'change_pct': basic.get('change_pct', 0),
            'pe': basic.get('pe'),
            'pb': basic.get('pb'),
            'market_cap': basic.get('market_cap'),
            'dividend_yield': dividend_yield,
            'roe': latest.get('roe'),
            'gross_margin': latest.get('gross_margin'),
            'net_margin': latest.get('net_margin'),
            'debt_ratio': latest.get('debt_ratio'),
            'revenue_growth': latest.get('revenue_growth'),
            'profit_growth': latest.get('profit_growth'),
            'report_period': latest.get('report_period', ''),
        }
    except Exception:
        return None


# ============================================================
# 金渐成评分体系 (满分100)
# ============================================================

def _score_jc(stock: dict) -> tuple:
    """
    金渐成评分体系 (满分100)
    核心框架: "第一兼唯一" + 管理层 + 安全边际

    金渐成的投资逻辑:
    1. "第一兼唯一" - 只投行业第一且具有垄断/唯一地位的公司
    2. 科技、消费、医疗三大赛道
    3. 管理层品质：诚实可靠、踏实进取、眼光长远
    4. 下跌20%开始试探，金字塔加仓
    5. 永不满仓，控制安全边际
    6. "止赚比止损重要，活着比暴利重要"
    """
    score = 0
    details = []

    roe = stock.get('roe')
    gross_margin = stock.get('gross_margin')
    net_margin = stock.get('net_margin')
    pe = stock.get('pe')
    pb = stock.get('pb')
    debt = stock.get('debt_ratio')
    div_yield = stock.get('dividend_yield')
    rev_growth = stock.get('revenue_growth')
    profit_growth = stock.get('profit_growth')
    code = stock.get('code', '')

    # 1. 行业地位 - "第一兼唯一" (20分)
    # 金渐成最看重的维度：必须是行业第一且有垄断地位
    pos_info = INDUSTRY_POSITION.get(code)
    if pos_info:
        pos_score = pos_info[1]
        score += pos_score
        details.append(f"行业地位:{pos_info[0]} +{pos_score}")
    else:
        score += 8
        details.append("行业地位:未标注 +8")

    # 2. ROE - 衡量股东回报效率 (20分)
    # 金渐成: 高ROE说明公司赚钱能力强，资本运用效率高
    if roe is not None:
        if roe >= 25:
            score += 20
            details.append(f"ROE={roe:.1f}% 卓越 +20")
        elif roe >= 20:
            score += 16
            details.append(f"ROE={roe:.1f}% 优秀 +16")
        elif roe >= 15:
            score += 12
            details.append(f"ROE={roe:.1f}% 良好 +12")
        elif roe >= 10:
            score += 8
            details.append(f"ROE={roe:.1f}% 一般 +8")
        else:
            score += 4
            details.append(f"ROE={roe:.1f}% 偏低 +4")
    else:
        score += 8
        details.append("ROE无数据 +8")

    # 3. 毛利率 - 护城河体现 (15分)
    # 金渐成: 高毛利率=定价权=护城河（茅台90%+, Costco低毛利但模式独特）
    if gross_margin is not None:
        if gross_margin >= 60:
            score += 15
            details.append(f"毛利率{gross_margin:.1f}% 宽护城河 +15")
        elif gross_margin >= 40:
            score += 12
            details.append(f"毛利率{gross_margin:.1f}% 中等护城河 +12")
        elif gross_margin >= 25:
            score += 9
            details.append(f"毛利率{gross_margin:.1f}% 窄护城河 +9")
        else:
            score += 5
            details.append(f"毛利率{gross_margin:.1f}% 低护城河 +5")
    else:
        score += 7
        details.append("毛利率无数据 +7")

    # 4. 估值合理性 (15分)
    # 金渐成: 不追高，逢低买入；PE太高要警惕，但科技股可以容忍较高PE
    val_score = 0
    if pe is not None and pe > 0:
        if pe < 15:
            val_score += 8
            details.append(f"PE={pe:.1f} 低估 +8")
        elif pe < 25:
            val_score += 6
            details.append(f"PE={pe:.1f} 合理 +6")
        elif pe < 40:
            val_score += 4
            details.append(f"PE={pe:.1f} 偏高 +4")
        else:
            val_score += 2
            details.append(f"PE={pe:.1f} 高估 +2")
    if pb is not None and pb > 0:
        if pb < 3:
            val_score += 4
        elif pb < 6:
            val_score += 3
        elif pb < 10:
            val_score += 1
    if div_yield and div_yield > 2:
        val_score += 3
        details.append(f"股息率{div_yield:.1f}% +3")
    elif div_yield and div_yield > 0:
        val_score += 1
    score += min(val_score, 15)

    # 5. 成长性 (10分)
    # 金渐成: 看重"改变未来的科技龙头"，但也看重稳定增长
    if rev_growth is not None and profit_growth is not None:
        if profit_growth > 15 and rev_growth > 10:
            score += 10
            details.append(f"利润+{profit_growth:.1f}% 高成长 +10")
        elif profit_growth > 5 and rev_growth > 0:
            score += 7
            details.append(f"利润+{profit_growth:.1f}% 稳健 +7")
        elif profit_growth > 0:
            score += 5
            details.append(f"利润+{profit_growth:.1f}% +5")
        else:
            score += 2
            details.append(f"利润{profit_growth:+.1f}% 承压 +2")
    else:
        score += 5
        details.append("成长数据无 +5")

    # 6. 负债率 - 财务健康 (10分)
    # 金渐成: "控制好安全边际"，低负债是安全的基础
    if debt is not None:
        if debt < 30:
            score += 10
            details.append(f"负债率{debt:.1f}% 稳健 +10")
        elif debt < 50:
            score += 7
            details.append(f"负债率{debt:.1f}% 可接受 +7")
        elif debt < 70:
            score += 4
            details.append(f"负债率{debt:.1f}% 偏高 +4")
        else:
            score += 1
            details.append(f"负债率{debt:.1f}% 高风险 +1")
    else:
        score += 5
        details.append("负债率无数据 +5")

    # 7. 股息率 - 现金流回报 (10分)
    # 金渐成: 防守型资产看重股息，进取型可容忍低股息
    if div_yield is not None:
        if div_yield >= 4:
            score += 10
            details.append(f"股息率{div_yield:.1f}% 高股息 +10")
        elif div_yield >= 2.5:
            score += 8
            details.append(f"股息率{div_yield:.1f}% 中等 +8")
        elif div_yield >= 1:
            score += 5
            details.append(f"股息率{div_yield:.1f}% +5")
        else:
            score += 2
            details.append(f"股息率{div_yield:.1f}% 低 +2")
    else:
        score += 3
        details.append("股息率无数据 +3")

    return min(score, 100), " | ".join(details)


# ============================================================
# 缓存
# ============================================================

from app.core.cache import get_cache as _base_get_cache, set_cache as _set_cached
_CACHE_TTL = 600

def _get_cached(key: str):
    return _base_get_cache(key, ttl_seconds=_CACHE_TTL)


# ============================================================
# 主筛选函数
# ============================================================

def screen_stocks(market: str = 'all', min_score: int = 0,
                  max_pe: float = None, top_n: int = 50) -> dict:
    """
    金渐成体系筛选股票

    Args:
        market: 'A', 'HK', 'US', 'all'
        min_score: 最低分数
        max_pe: 最大PE
        top_n: 返回前N只
    """
    cache_key = f"jc_{market}_{min_score}_{max_pe}_{top_n}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    stocks = []

    # Fetch A-share stocks
    if market in ('A', 'all'):
        for code in A_STOCKS_LIST:
            stock = _get_a_stock_data(code)
            if stock:
                stocks.append(stock)

    # Fetch HK stocks
    if market in ('HK', 'all'):
        for code in HK_STOCKS_LIST:
            stock = _get_hk_stock_data(code)
            if stock:
                stocks.append(stock)

    # Fetch US stocks
    if market in ('US', 'all'):
        for symbol in US_STOCKS_LIST:
            stock = _get_us_stock_data(symbol)
            if stock:
                stocks.append(stock)

    # Score each stock
    results = []
    for stock in stocks:
        # Apply PE filter
        if max_pe and stock.get('pe') and stock['pe'] > max_pe:
            continue

        score, detail = _score_jc(stock)

        if score >= min_score:
            # Get industry position label
            pos_info = INDUSTRY_POSITION.get(stock.get('code', ''))
            industry_label = pos_info[0] if pos_info else ""

            results.append({
                **stock,
                'jc_score': score,
                'jc_detail': detail,
                'industry_position': industry_label,
                'match_level': (
                    'excellent' if score >= 80 else
                    'good' if score >= 65 else
                    'fair' if score >= 50 else
                    'poor'
                ),
            })

    # Sort by score descending
    results.sort(key=lambda x: x['jc_score'], reverse=True)
    results = results[:top_n]

    result = {
        'stocks': results,
        'total': len(results),
        'master': '金渐成',
        'market': market,
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'criteria': {
            'min_score': min_score,
            'max_pe': max_pe,
            'top_n': top_n,
        },
    }

    _set_cached(cache_key, result)
    return result


def get_buy_signals(market: str = 'all') -> dict:
    """
    基于金渐成"下跌20%开始捞"逻辑，返回当前接近买入区间的标的

    金渐成买入规则:
    - 下跌20%左右开始小仓试探
    - 下跌25%后开始逐步加仓
    - 金字塔加仓法：越跌买越多
    """
    cache_key = f"jc_signals_{market}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    stocks = []
    if market in ('A', 'all'):
        for code in A_STOCKS_LIST:
            stock = _get_a_stock_data(code)
            if stock:
                stocks.append(stock)
    if market in ('HK', 'all'):
        for code in HK_STOCKS_LIST:
            stock = _get_hk_stock_data(code)
            if stock:
                stocks.append(stock)
    if market in ('US', 'all'):
        for symbol in US_STOCKS_LIST:
            stock = _get_us_stock_data(symbol)
            if stock:
                stocks.append(stock)

    # Score and filter for buy signals
    signals = []
    for stock in stocks:
        score, detail = _score_jc(stock)
        pos_info = INDUSTRY_POSITION.get(stock.get('code', ''))

        signals.append({
            **stock,
            'jc_score': score,
            'industry_position': pos_info[0] if pos_info else "",
            'match_level': (
                'excellent' if score >= 80 else
                'good' if score >= 65 else
                'fair' if score >= 50 else
                'poor'
            ),
        })

    # Sort by score
    signals.sort(key=lambda x: x['jc_score'], reverse=True)

    result = {
        'stocks': signals,
        'total': len(signals),
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'buy_rules': {
            'rule_1': '下跌20%左右开始小仓试探',
            'rule_2': '下跌25%后开始逐步加仓',
            'rule_3': '金字塔加仓法：越跌买越多',
            'rule_4': '分批买入，不追高，不满仓',
            'rule_5': '7成底仓做长线，3成做T',
        },
    }

    _set_cached(cache_key, result)
    return result


def get_philosophy() -> dict:
    """返回金渐成完整投资哲学体系"""
    return {
        'name': '金渐成（机哥/天玑）',
        'title': '投资人 | 公众号:天机奇谈/金渐成/生玑伯伯',
        'era': '2016年至今 | 美股为主 | 年化收益优异',
        'core_philosophy': '第一兼唯一选股，永不满仓，金字塔加仓，做负成本持股。止赚比止损重要，活着比暴利重要。',
        'investment_framework': [
            {
                'dimension': '选股原则 - "第一兼唯一"',
                'description': '只投行业第一且具有唯一/垄断地位的公司',
                'criteria': [
                    '改变未来的科技龙头：NVDA、MSFT、GOOG、AAPL、AMZN、META、TSLA、TSM、AVGO、AMD',
                    '不被未来改变的消费/避险股：COST、WMT、MCD、PG、KO、BRK-B',
                    '医疗保健矛与盾：LLY（进攻矛）、UNH、JNJ（防守盾）',
                    '科技、消费、医疗三大赛道最凶猛',
                    '远离能源/大宗商品（不具备唯一性，全球竞争大）',
                    '远离中概股和垃圾股',
                ],
                'key_insight': '资本开支的增量在哪里，意味着总需求的增量就在哪里，赚钱的机会也就在哪里。',
            },
            {
                'dimension': '管理层品质',
                'description': '最看重管理层：诚实可靠、踏实进取、眼光长远',
                'criteria': [
                    '纳德拉上任微软：砍掉Windows主战略→大举投入云计算→Azure成为增长引擎',
                    'Costco管理层从低做起，对每个部门岗位都非常了解',
                    '企业是管理者人格的映射',
                    '好的管理层能让平庸公司变伟大，糟糕管理层会毁掉好公司',
                ],
                'key_insight': '中长线持仓，除了看基本面、商业模式、价格，最重要的是看大势、看人。',
            },
            {
                'dimension': '买入规则',
                'description': '金字塔加仓法，逢低分批买入',
                'criteria': [
                    '下跌20%左右开始小仓试探',
                    '下跌25%后开始逐步加仓',
                    '金字塔加仓法：越跌买越多，摊低成本',
                    '分批买入，不追高，不满仓',
                    '价格档差要拉开，才能有效拉低成本',
                    '聪明定投：低点多买，高点少买',
                ],
                'key_insight': '不要错过任何一次基本面没有恶化、而是由恐慌情绪主导的下跌。这就是赚钱的秘诀。',
            },
            {
                'dimension': '卖出与仓位管理',
                'description': '倒金字塔卖出，做负成本持股',
                'criteria': [
                    '倒金字塔卖出法：涨得越多卖得越多',
                    '做低成本/负成本：卖出部分回收本金，剩余零成本长期持有',
                    '7成底仓做长线，3成做短线做T',
                    '永不满仓，保持现金储备作为"备用牌"',
                    '进取:稳健:防守 = 4:1.5:4.5',
                    '防守型资产目标40%+',
                ],
                'key_insight': '逢高适当减仓做低成本，就可以没有心理负担长期持有了。',
            },
            {
                'dimension': '风险控制',
                'description': '止赚比止损重要，活着比暴利重要',
                'criteria': [
                    '控制安全边际：仓位、资金、成本',
                    '创富是运气，守富是能力',
                    '不预测，只应对（来自《反脆弱》）',
                    '看空不做空',
                    '永远留一些仓位，方便市场出机会时加仓',
                    '正常不超过8.5成仓位',
                ],
                'key_insight': '赚钱是一场意外，守住钱才是一项能力。',
            },
            {
                'dimension': '资产配置',
                'description': '三账户体系，分散化配置',
                'criteria': [
                    '进取型账户：纯科技股 - Mag7 + TSM + AVGO + AMD',
                    '稳健型账户：宽基指数ETF(50%+) + 消费股(20%+) + 医药(29%)',
                    '防守型账户：美债(65%) + BRK-B(13.5%) + KO/JNJ/V/SCHD(21.3%)',
                    '现金储备与持仓比约1:2',
                    '全球分散：美股95% + 日本/英国/印度/港股',
                ],
                'key_insight': '在有鱼的地方钓鱼。选择比努力重要。',
            },
        ],
        'classic_quotes': [
            '第一兼唯一 - 只投行业第一且有垄断地位的公司',
            '不要错过任何一次基本面没有恶化、而是由恐慌情绪主导的下跌',
            '止赚比止损重要，活着比暴利重要',
            '创富是运气，守富是能力',
            '不预测，只应对',
            '在有鱼的地方钓鱼',
            '选择比努力重要',
            '资本开支的增量在哪里，赚钱的机会就在哪里',
            '看懂了钱的流向，赚钱其实挺简单的',
            '永不满仓，永远留一些备用牌',
        ],
        'performance': {
            '2025_return': '~73% (全部账户)',
            'top_holders': 'NVDA(31.5%), MSFT(11%), AMZN(9%), AAPL(8%+), GOOG(7.5%+), TSM(7.5%+)',
            'target_2026': '6-8% (保守预期)',
            'note': '高收益得益于：现金储备多 + 遇上下跌行情 + 高位减仓增配防守型安全垫',
        },
    }
