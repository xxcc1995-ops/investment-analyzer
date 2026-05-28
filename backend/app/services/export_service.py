"""出口冠军筛选服务 - 筛选具备全球竞争力、分红稳健、且满足价值投资标准的企业"""

import time
from typing import Optional
from datetime import datetime
from app.services.data_service import DataService, _safe_float, _get_annual_report
from app.services.vi_service import (
    _get_hk_stock_data,
    _score_buffett,
    _score_munger,
    _score_li_lu,
    _score_duan_yongping,
)

# ============================================================
# 出口冠军股票池 - 精选具备全球竞争力的A股和港股
# ============================================================

EXPORT_STOCKS = {
    # === 家电出口 ===
    "000333": {"name": "美的集团", "industry": "家电出口", "export_intensity": "high", "est_overseas_pct": 40},
    "000651": {"name": "格力电器", "industry": "家电出口", "export_intensity": "medium", "est_overseas_pct": 15},
    "002032": {"name": "苏泊尔", "industry": "家电出口", "export_intensity": "high", "est_overseas_pct": 50},
    "600690": {"name": "海尔智家", "industry": "家电出口", "export_intensity": "high", "est_overseas_pct": 50},
    "600060": {"name": "海信视像", "industry": "家电出口", "export_intensity": "high", "est_overseas_pct": 40},

    # === 动力电池 / 新能源车 ===
    "300750": {"name": "宁德时代", "industry": "动力电池", "export_intensity": "high", "est_overseas_pct": 35},
    "002594": {"name": "比亚迪", "industry": "新能源车", "export_intensity": "high", "est_overseas_pct": 25},
    "002460": {"name": "赣锋锂业", "industry": "锂矿", "export_intensity": "high", "est_overseas_pct": 45},
    "601633": {"name": "长城汽车", "industry": "汽车出口", "export_intensity": "high", "est_overseas_pct": 30},

    # === 光伏 / 太阳能 ===
    "601012": {"name": "隆基绿能", "industry": "光伏", "export_intensity": "high", "est_overseas_pct": 35},
    "600438": {"name": "通威股份", "industry": "光伏", "export_intensity": "high", "est_overseas_pct": 30},
    "002459": {"name": "晶澳科技", "industry": "光伏", "export_intensity": "high", "est_overseas_pct": 60},

    # === 船舶制造 / 重工 ===
    "600150": {"name": "中国船舶", "industry": "船舶制造", "export_intensity": "high", "est_overseas_pct": 70},
    "601989": {"name": "中国重工", "industry": "船舶制造", "export_intensity": "high", "est_overseas_pct": 50},

    # === 工程机械 ===
    "600031": {"name": "三一重工", "industry": "工程机械", "export_intensity": "high", "est_overseas_pct": 45},
    "000157": {"name": "中联重科", "industry": "工程机械", "export_intensity": "high", "est_overseas_pct": 35},

    # === 电子 / 消费电子 ===
    "002415": {"name": "海康威视", "industry": "安防设备", "export_intensity": "high", "est_overseas_pct": 35},
    "000725": {"name": "京东方A", "industry": "面板", "export_intensity": "high", "est_overseas_pct": 50},
    "002241": {"name": "歌尔股份", "industry": "消费电子", "export_intensity": "high", "est_overseas_pct": 75},
    "002475": {"name": "立讯精密", "industry": "消费电子", "export_intensity": "high", "est_overseas_pct": 80},
    "601138": {"name": "工业富联", "industry": "电子制造", "export_intensity": "high", "est_overseas_pct": 70},

    # === 化工 / 材料 ===
    "600309": {"name": "万华化学", "industry": "化工", "export_intensity": "high", "est_overseas_pct": 45},
    "002353": {"name": "杰瑞股份", "industry": "油服设备", "export_intensity": "high", "est_overseas_pct": 50},

    # === 通信设备 ===
    "000063": {"name": "中兴通讯", "industry": "通信设备", "export_intensity": "high", "est_overseas_pct": 30},

    # === 半导体 ===
    "603501": {"name": "韦尔股份", "industry": "半导体", "export_intensity": "high", "est_overseas_pct": 60},

    # === 发动机 / 工业 ===
    "000338": {"name": "潍柴动力", "industry": "发动机", "export_intensity": "high", "est_overseas_pct": 40},

    # === 港股 ===
    "01810": {"name": "小米集团", "industry": "消费电子", "export_intensity": "high", "est_overseas_pct": 40},
    "01211": {"name": "比亚迪股份", "industry": "新能源车", "export_intensity": "high", "est_overseas_pct": 25},
    "02333": {"name": "长城汽车", "industry": "汽车出口", "export_intensity": "high", "est_overseas_pct": 30},
    "00175": {"name": "吉利汽车", "industry": "汽车出口", "export_intensity": "high", "est_overseas_pct": 20},
    "02269": {"name": "药明生物", "industry": "CXO", "export_intensity": "high", "est_overseas_pct": 70},
    "06690": {"name": "海尔智家H", "industry": "家电出口", "export_intensity": "high", "est_overseas_pct": 50},
    "09992": {"name": "泡泡玛特", "industry": "潮玩", "export_intensity": "high", "est_overseas_pct": 30},
    "01929": {"name": "周大福", "industry": "珠宝", "export_intensity": "medium", "est_overseas_pct": 15},
}

# A股和港股代码列表
A_EXPORT_STOCKS = [c for c in EXPORT_STOCKS if not c.startswith("0") or len(c) == 6 and c[0] in "603"]
HK_EXPORT_STOCKS = [c for c in EXPORT_STOCKS if len(c) == 5]

# ============================================================
# Data Fetching
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

        div_per_share, consecutive_years, dividend_ratio = DataService._get_actual_dividend(code)
        dividend_yield = None
        if div_per_share > 0 and basic.get('price', 0) > 0:
            dividend_yield = round(div_per_share / basic['price'] * 100, 2)

        export_info = EXPORT_STOCKS.get(code, {})

        return {
            'code': code, 'name': basic.get('name', ''), 'market': 'A',
            'price': basic.get('price', 0),
            'change_pct': basic.get('change_pct', 0),
            'pe': basic.get('pe'),
            'pb': basic.get('pb'),
            'market_cap': basic.get('market_cap'),
            'dividend_yield': dividend_yield,
            'consecutive_years': consecutive_years,
            'dividend_ratio': dividend_ratio,
            'roe': latest.get('roe'),
            'gross_margin': latest.get('gross_margin'),
            'net_margin': latest.get('net_margin'),
            'debt_ratio': latest.get('debt_ratio'),
            'revenue_growth': latest.get('revenue_growth'),
            'profit_growth': latest.get('profit_growth'),
            'report_period': latest.get('report_period', ''),
            'industry': export_info.get('industry', ''),
            'export_intensity': export_info.get('export_intensity', 'low'),
            'est_overseas_pct': export_info.get('est_overseas_pct', 0),
        }
    except Exception:
        return None


def _get_hk_data(code: str) -> Optional[dict]:
    """Fetch HK stock data and enrich with export info."""
    stock = _get_hk_stock_data(code)
    if not stock:
        return None

    # Fix data quality: Tencent API returns negative PB for HK stocks with
    # negative net assets (or data issues), which causes ROE to be garbage.
    # When PB is None or non-positive, ROE is unreliable — clear it.
    pb = stock.get('pb')
    if pb is None or pb <= 0:
        stock['pb'] = None
        stock['roe'] = None

    export_info = EXPORT_STOCKS.get(code, {})
    stock['industry'] = export_info.get('industry', '')
    stock['export_intensity'] = export_info.get('export_intensity', 'low')
    stock['est_overseas_pct'] = export_info.get('est_overseas_pct', 0)
    stock['consecutive_years'] = None
    stock['dividend_ratio'] = None
    return stock


# ============================================================
# 出口冠军评分体系 (满分100)
# ============================================================

def _score_export_champion(stock: dict) -> tuple:
    """
    出口冠军评分体系 (满分100)
    核心框架: 出口竞争力 + 分红稳健 + 盈利能力 + 财务健康
    """
    score = 0
    details = []
    code = stock.get('code', '')

    # 1. 出口强度 (25分)
    export_info = EXPORT_STOCKS.get(code, {})
    intensity = export_info.get('export_intensity', 'low')
    est_pct = export_info.get('est_overseas_pct', 0)
    if intensity == 'high':
        pts = min(25, 15 + est_pct // 10)
        score += pts
        details.append(f"出口强度:高(海外~{est_pct}%) +{pts}")
    elif intensity == 'medium':
        score += 10
        details.append(f"出口强度:中(海外~{est_pct}%) +10")
    else:
        score += 5
        details.append(f"出口强度:低 +5")

    # 2. 股息率 (20分)
    div_yield = stock.get('dividend_yield') or 0
    if div_yield >= 5:
        score += 20
        details.append(f"股息率{div_yield:.1f}% 高股息 +20")
    elif div_yield >= 3:
        score += 15
        details.append(f"股息率{div_yield:.1f}% 中等 +15")
    elif div_yield >= 2:
        score += 10
        details.append(f"股息率{div_yield:.1f}% +10")
    elif div_yield >= 1.5:
        score += 5
        details.append(f"股息率{div_yield:.1f}% +5")

    # 3. 连续分红年数 (10分)
    years = stock.get('consecutive_years')
    if years is not None:
        if years >= 10:
            score += 10
            details.append(f"连续分红{years}年 +10")
        elif years >= 5:
            score += 7
            details.append(f"连续分红{years}年 +7")
        elif years >= 3:
            score += 4
            details.append(f"连续分红{years}年 +4")
    else:
        # 港股无此数据，给默认分
        score += 5
        details.append("连续分红:港股无数据 +5")

    # 4. ROE (15分)
    roe = stock.get('roe')
    if roe is not None:
        if roe >= 20:
            score += 15
            details.append(f"ROE={roe:.1f}% 卓越 +15")
        elif roe >= 15:
            score += 12
            details.append(f"ROE={roe:.1f}% 优秀 +12")
        elif roe >= 10:
            score += 8
            details.append(f"ROE={roe:.1f}% 良好 +8")
        elif roe >= 5:
            score += 4
            details.append(f"ROE={roe:.1f}% +4")
    else:
        score += 5
        details.append("ROE无数据 +5")

    # 5. 毛利率 - 护城河 (10分)
    gm = stock.get('gross_margin')
    if gm is not None:
        if gm >= 40:
            score += 10
            details.append(f"毛利率{gm:.1f}% 宽护城河 +10")
        elif gm >= 25:
            score += 7
            details.append(f"毛利率{gm:.1f}% 中护城河 +7")
        elif gm >= 15:
            score += 4
            details.append(f"毛利率{gm:.1f}% +4")
    else:
        score += 4
        details.append("毛利率无数据 +4")

    # 6. 估值合理性 (10分)
    pe = stock.get('pe') or 999
    pb = stock.get('pb') or 999
    val_pts = 0
    if pe > 0 and pe < 15:
        val_pts += 5
    elif pe < 25:
        val_pts += 3
    if pb > 0 and pb < 2:
        val_pts += 3
    elif pb < 4:
        val_pts += 2
    if div_yield and div_yield > 2:
        val_pts += 2
    score += min(val_pts, 10)
    if val_pts > 0:
        details.append(f"估值 PE={pe:.1f} PB={pb:.1f} +{min(val_pts, 10)}")

    # 7. 财务健康 - 负债率 (10分)
    debt = stock.get('debt_ratio')
    if debt is not None:
        if debt < 40:
            score += 10
            details.append(f"负债率{debt:.1f}% 稳健 +10")
        elif debt < 60:
            score += 7
            details.append(f"负债率{debt:.1f}% 可接受 +7")
        elif debt < 70:
            score += 4
            details.append(f"负债率{debt:.1f}% 偏高 +4")
    else:
        score += 4
        details.append("负债率无数据 +4")

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

def screen_export_champions(market: str = 'all', min_score: int = 0,
                            min_dividend_yield: float = 1.5,
                            top_n: int = 50) -> dict:
    """
    出口冠军筛选

    Args:
        market: 'A', 'HK', 'all'
        min_score: 最低分数
        min_dividend_yield: 最低股息率(%)
        top_n: 返回前N只
    """
    cache_key = f"export_{market}_{min_score}_{min_dividend_yield}_{top_n}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    stocks = []

    # Fetch A-share stocks
    if market in ('A', 'all'):
        for code in EXPORT_STOCKS:
            if code in HK_EXPORT_STOCKS:
                continue
            stock = _get_a_stock_data(code)
            if stock:
                stocks.append(stock)

    # Fetch HK stocks
    if market in ('HK', 'all'):
        for code in HK_EXPORT_STOCKS:
            stock = _get_hk_data(code)
            if stock:
                stocks.append(stock)

    # Score and filter
    results = []
    for stock in stocks:
        # Hard filter: dividend yield
        dy = stock.get('dividend_yield') or 0
        if dy < min_dividend_yield:
            continue

        # Hard filter: consecutive years (A-shares only)
        cy = stock.get('consecutive_years')
        if cy is not None and cy < 3:
            continue

        # Value investing hard filters
        pe = stock.get('pe')
        pb = stock.get('pb')
        roe = stock.get('roe')

        # PE must be positive and <= 50 (exclude negative earnings and extreme overvaluation)
        if pe is not None and (pe <= 0 or pe > 50):
            continue

        # PB must be <= 5 if available (exclude extreme overvaluation)
        # Skip HK stocks with PB=None/0 (data quality issue from Tencent API)
        if pb is not None and pb > 5:
            continue

        # ROE must be positive if available (exclude loss-making companies)
        # Skip HK stocks with ROE=None (data quality issue)
        if roe is not None and roe < 0:
            continue

        # Export champion score
        export_score, export_detail = _score_export_champion(stock)

        # Value investing master scores
        buffett_score, buffett_detail = _score_buffett(stock)
        munger_score, munger_detail = _score_munger(stock)
        li_lu_score, li_lu_detail = _score_li_lu(stock)
        duan_score, duan_detail = _score_duan_yongping(stock)
        vi_avg = round((buffett_score + munger_score + li_lu_score + duan_score) / 4)

        # Combined score: export 40% + value investing avg 60%
        combined_score = round(export_score * 0.4 + vi_avg * 0.6)

        if combined_score >= min_score:
            results.append({
                **stock,
                'export_score': export_score,
                'export_detail': export_detail,
                'buffett_score': buffett_score,
                'buffett_detail': buffett_detail,
                'munger_score': munger_score,
                'munger_detail': munger_detail,
                'li_lu_score': li_lu_score,
                'li_lu_detail': li_lu_detail,
                'duan_score': duan_score,
                'duan_detail': duan_detail,
                'vi_avg_score': vi_avg,
                'combined_score': combined_score,
                'match_level': (
                    'excellent' if combined_score >= 80 else
                    'good' if combined_score >= 65 else
                    'fair' if combined_score >= 50 else
                    'poor'
                ),
            })

    # Sort by combined score descending
    results.sort(key=lambda x: x['combined_score'], reverse=True)
    results = results[:top_n]

    result = {
        'stocks': results,
        'total': len(results),
        'market': market,
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'criteria': {
            'min_score': min_score,
            'min_dividend_yield': min_dividend_yield,
            'top_n': top_n,
        },
    }

    _set_cached(cache_key, result)
    return result


# ============================================================
# 筛选理念
# ============================================================

def get_philosophy() -> dict:
    """返回出口冠军筛选理念 — 出口竞争力 + 价值投资双轮驱动"""
    return {
        'name': '出口冠军筛选',
        'title': '出口竞争力 × 价值投资：在日本化时代寻找全球化赢家',
        'core_thesis': '中国正在经历类似日本1990年后的估值中枢下移。日本30年的教训只有一个结论：全球化是估值修复的唯一确定性路径。纯内需消费股的PE从60-70倍永久性下移到12-15倍，而成功全球化的公司（尤妮佳海外营收从20%到60%、资生堂靠中国市场修复估值、优衣库PE长期维持30-40倍）成为唯一的例外者。',
        'core_idea': '在中国经济"日本化"的宏观背景下（人口下降、房地产下行、通缩压力），纯内需企业面临估值中枢永久性下移的风险。本筛选池聚焦那些已经建立全球竞争力、海外营收占比高、有持续出口能力的企业——它们是日本化时代最有可能"逃出生天"的标的。同时要求一定的分红率，在低增长时代提供确定性回报。',
        'japan_mirror': {
            'title': '日本镜鉴：谁逃过了估值下移？',
            'content': '日本消费股PE从1989年的60-70倍永久性下移到2010年代的12-15倍。逃过下移的只有三类公司：(1) 海外扩张成功者——尤妮佳(海外营收20%→60%,PE修复到25-30倍)、资生堂(中国市场爆发,PE回到30倍+)；(2) 品类结构性受益者——亚瑟士(全球跑步热潮,PE从10倍修复到20倍)、养乐多(全球化+健康概念)；(3) 极致效率者——优衣库(制造零售业+全球化,PE长期30-40倍)。它们的共同特征：增长引擎从"日本国内"切换到了"全球市场"。',
            'lesson': '只守着国内市场的消费股，无一例外经历了估值中枢的永久性下移。全球化不是加分项，而是生存条件。',
        },
        'china_context': {
            'title': '中国现状：估值中枢已下移30-50%',
            'content': '茅台PE从35-40倍跌到22-25倍，海天从55-65倍跌到30-35倍，伊利从25-30倍跌到15-18倍。机构共识：新估值中枢在15-25倍PE，回到2020-2021年水平(30-50倍)已无可能。三个剧本：温和日本化(45%概率,PE稳在15-22倍)、深度日本化(25%概率,PE跌到10-15倍)、中国特色路径(30%概率,改革激活内需,PE回到25-30倍)。',
            'implication': '无论哪个剧本，有全球竞争力的企业都处于更有利的位置——它们的增长引擎不依赖单一的国内市场。',
        },
        'why_export_why_dividend': {
            'title': '为什么是"出口+分红"？',
            'reasons': [
                '出口 = 增长引擎的多元化。当国内消费增速从8%降到3%，海外市场的增量就是估值的救命稻草。',
                '分红 = 低增长时代的确定性回报。当估值扩张不再可期，股息率2-4%就是核心回报来源。',
                '出口企业有更强的定价权。面对国内通缩压力，海外市场往往有更好的定价环境。',
                '分红证明管理层愿意与股东分享利润，而非盲目再投资——在低增长时代，这比增长更珍贵。',
            ],
        },
        'scoring_dimensions': [
            {
                'dimension': '出口强度 (25分)',
                'description': '企业海外市场收入占比和全球竞争力——这是筛选的第一权重',
                'criteria': [
                    '高出口强度(海外收入>30%): 15-25分——已建立全球竞争力',
                    '中出口强度(海外收入10-30%): 10分——正在出海',
                    '低出口强度(海外收入<10%): 5分——仍以国内为主',
                ],
                'japan_parallel': '尤妮佳海外营收从20%到60%的过程中，PE从15倍修复到25-30倍',
            },
            {
                'dimension': '股息率 (20分)',
                'description': '低增长时代的核心回报来源',
                'criteria': [
                    '股息率>=5%: 20分',
                    '股息率>=3%: 15分',
                    '股息率>=2%: 10分',
                    '股息率>=1.5%: 5分',
                ],
                'japan_parallel': '日本消费股在估值下移过程中，股息率从0.5-1%上升到2-2.5%，成为主要回报来源',
            },
            {
                'dimension': '连续分红年数 (10分)',
                'description': '分红的持续性证明管理层的股东回报意愿',
                'criteria': [
                    '连续10年以上: 10分',
                    '连续5年以上: 7分',
                    '连续3年以上: 4分',
                ],
            },
            {
                'dimension': 'ROE (15分)',
                'description': '资本回报效率——全球化企业的ROE往往更可持续',
                'criteria': [
                    'ROE>=20%: 卓越 15分',
                    'ROE>=15%: 优秀 12分',
                    'ROE>=10%: 良好 8分',
                    'ROE>=5%: 一般 4分',
                ],
            },
            {
                'dimension': '毛利率 (10分)',
                'description': '定价权和护城河——出口企业的毛利率反映全球竞争力',
                'criteria': [
                    '毛利率>=40%: 宽护城河 10分',
                    '毛利率>=25%: 中护城河 7分',
                    '毛利率>=15%: 窄护城河 4分',
                ],
            },
            {
                'dimension': '估值合理性 (10分)',
                'description': '在估值中枢下移时代，买贵了就是最大的风险',
                'criteria': [
                    'PE<15且PB<2: 估值偏低',
                    'PE<25且PB<4: 估值合理',
                    '高股息率额外加分',
                ],
            },
            {
                'dimension': '财务健康 (10分)',
                'description': '资产负债率——在去杠杆化时代，低负债就是安全边际',
                'criteria': [
                    '负债率<40%: 稳健 10分',
                    '负债率<60%: 可接受 7分',
                    '负债率<70%: 偏高 4分',
                ],
            },
        ],
        'hard_filters': [
            '股息率 >= 1.5% (出口企业reinvest较多，门槛适当降低)',
            '连续分红 >= 3年 (确保分红意愿)',
        ],
        'industry_categories': [
            {'name': '家电出口', 'examples': '美的、海尔、格力、苏泊尔、海信', 'global_note': '家电是中国最早建立全球竞争力的行业，美的海外营收占比~40%，海尔~50%'},
            {'name': '动力电池/新能源车', 'examples': '宁德时代、比亚迪、赣锋锂业、长城汽车', 'global_note': '中国在新能源领域的全球领先优势是结构性的，类似日本汽车业1980年代的崛起'},
            {'name': '光伏/太阳能', 'examples': '隆基绿能、通威股份、晶澳科技', 'global_note': '中国光伏产能占全球80%+，是真正的全球垄断级产业'},
            {'name': '船舶制造/重工', 'examples': '中国船舶、中国重工', 'global_note': '中国已超越韩国成为全球第一造船大国，订单占比50%+'},
            {'name': '工程机械', 'examples': '三一重工、中联重科', 'global_note': '三一海外营收占比~45%，正在复制卡特彼勒的全球化路径'},
            {'name': '电子/消费电子', 'examples': '海康威视、京东方、歌尔股份、立讯精密、工业富联', 'global_note': '消费电子供应链的全球化程度最高，立讯海外占比~80%'},
            {'name': '化工/材料', 'examples': '万华化学、杰瑞股份', 'global_note': '万华化学是全球MDI龙头，海外占比~45%'},
            {'name': '通信/半导体', 'examples': '中兴通讯、韦尔股份', 'global_note': '半导体设计的全球化程度高，韦尔海外占比~60%'},
            {'name': '港股出口龙头', 'examples': '小米、比亚迪H、海尔H、泡泡玛特、药明生物', 'global_note': '港股上市公司往往有更高的国际化程度和更透明的治理结构'},
        ],

        # ============================================================
        # 价值投资四位大师评分体系
        # ============================================================
        'value_investing_integration': {
            'title': '价值投资四位大师评分体系',
            'description': '出口冠军筛选不仅关注全球化竞争力，还必须通过价值投资的严格检验。每只股票同时接受四位投资大师的独立评分，确保既具备出口竞争力，又满足价值投资标准。',
            'scoring_model': '综合评分 = 出口竞争力(40%) + 价值投资均分(60%)。价值投资均分 = (巴菲特 + 芒格 + 李录 + 段永平) / 4',
            'masters': [
                {
                    'name': '巴菲特',
                    'focus': '护城河 + ROE + 安全边际',
                    'framework': 'ROE(25分) + 毛利率护城河(20分) + 净利率(15分) + 估值安全边际(20分) + 财务健康(10分) + 成长性(10分)',
                    'key_insight': '"如果只能用一个指标选股，那就是ROE" — 持续高ROE说明管理层资本配置能力强，护城河宽广',
                    'criteria': ['ROE>=20%: 优秀', '毛利率>=40%: 中等护城河', 'PE<15且PB<2: 低估', '负债率<30%: 财务稳健'],
                },
                {
                    'name': '芒格',
                    'focus': '企业质量 + 管理层理性 + 风险排除',
                    'framework': '企业质量(25分) + 管理层理性(20分) + 风险排除(20分) + 估值(15分) + 净利率(10分) + 成长性(10分)',
                    'key_insight': '"反过来想，总是反过来想" — 先排除风险，再寻找机会。检查清单法系统性排除高负债、负增长、低ROE',
                    'criteria': ['利润增速>营收增速: 管理层高效', '负债率<35%: 理性保守', '风险排除: 无高负债/负增长/低ROE'],
                },
                {
                    'name': '李录',
                    'focus': 'ROE + 护城河 + 结构性增长',
                    'framework': 'ROE质量(25分) + 护城河(20分) + 成长性(20分) + 估值(15分) + 财务健康(10分) + 股息回报(10分)',
                    'key_insight': '只投资自己真正理解的企业，以5-10年为投资周期。在中国市场，管理层品质和行业结构性增长尤为重要',
                    'criteria': ['ROE>=15%: 良好', '毛利率>=30%且净利率>=12%: 护城河', '营收和利润均>8%: 稳健增长'],
                },
                {
                    'name': '段永平',
                    'focus': '商业模式 + 成长性 + 财务健康',
                    'framework': '商业模式(30分) + 成长性(25分) + 财务健康(15分) + 估值(15分) + 股东回报(10分) + 低负债安全(5分)',
                    'key_insight': '"买股票就是买公司，买公司就是买未来现金流的折现" — 好商业模式 > 好管理 > 好价格',
                    'criteria': ['ROE>=18%且毛利率>=30%: 好商业模式', '营收利润均>8%: 好生意自然增长', '负债率<25%: 非常健康'],
                },
            ],
            'match_levels': {
                'excellent': '综合80+分 — 出口竞争力强且四位大师都认可的优秀企业',
                'good': '综合65-79分 — 全球化布局良好，多数大师会关注的优质标的',
                'fair': '综合50-64分 — 部分维度突出，出口或价值投资某一方面有待提升',
                'poor': '综合<50分 — 出口竞争力或价值投资标准不达标',
            },
            'risks': [
                '价值陷阱：低PE/PB可能反映基本面恶化，而非低估',
                '护城河侵蚀：技术变革可能摧毁看似牢固的护城河',
                '出口依赖风险：过度依赖海外市场可能受贸易政策影响',
                '估值锚定：过度依赖历史估值可能错过结构性变化',
                '中国市场特殊性：政策风险、公司治理、信息不对称',
            ],
        },
    }
