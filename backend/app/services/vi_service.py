"""价值投资筛选服务 - 巴菲特、芒格、李录、段永平投资体系"""

import requests
import time
from typing import Optional
from datetime import datetime
from app.services.data_service import DataService, _safe_float, _get_annual_report
from app.core.stock_lists import A_STOCKS_LIST, HK_STOCKS_LIST, US_STOCKS_LIST

# ============================================================
# HK/US Stock Data from Tencent Finance
# ============================================================

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}


def _fetch_tencent_quote(prefix: str, code: str) -> Optional[dict]:
    """Fetch quote from Tencent Finance. prefix: 'r_hk' for HK, 'us' for US."""
    try:
        url = f'https://qt.gtimg.cn/q={prefix}{code}'
        headers = {**HEADERS, 'Referer': 'https://stockapp.finance.qq.com/'}
        r = requests.get(url, headers=headers, timeout=10)
        r.encoding = 'gbk'

        text = r.text
        if '="' not in text:
            return None

        data = text.split('"')[1].split('~')
        if len(data) < 50:
            return None

        return data
    except Exception:
        return None


def _get_hk_stock_data(code: str) -> Optional[dict]:
    """Fetch HK stock data from Tencent Finance."""
    data = _fetch_tencent_quote('r_hk', code)
    if not data:
        return None

    try:
        name = data[1]
        price = float(data[3]) if data[3] else 0
        pre_close = float(data[4]) if data[4] else 0
        change_pct = float(data[32]) if data[32] else 0
        pe = float(data[39]) if data[39] else 0
        market_cap = float(data[44]) if data[44] else 0
        dividend_yield = float(data[43]) if data[43] else 0
        pb = float(data[51]) if len(data) > 51 and data[51] else None

        if price <= 0:
            return None

        # Calculate ROE from PB/PE if both available
        roe = None
        if pb and pe and pe > 0:
            roe = round(pb / pe * 100, 2)

        return {
            'code': code, 'name': name, 'market': 'HK',
            'price': price, 'change_pct': round(change_pct, 2),
            'pe': round(pe, 2) if pe > 0 else None,
            'pb': round(pb, 2) if pb and pb > 0 else None,
            'market_cap': round(market_cap, 2),
            'dividend_yield': round(dividend_yield, 2) if dividend_yield > 0 else None,
            'roe': roe,
            'gross_margin': None, 'net_margin': None,
            'debt_ratio': None,
            'revenue_growth': None, 'profit_growth': None,
            'report_period': '',
        }
    except Exception:
        return None


def _get_us_stock_data(symbol: str) -> Optional[dict]:
    """Fetch US stock data from Tencent Finance."""
    data = _fetch_tencent_quote('us', symbol)
    if not data:
        return None

    try:
        # Tencent US fields: [3]=price [4]=pre_close [32]=change% [39]=PE
        # [43]=div_yield [44]=mcap(亿美元) [46]=name_en [47]=EPS
        # [48]=52w_high [49]=52w_low [51]=PB
        name = data[46] if len(data) > 46 and data[46] else symbol
        price = float(data[3]) if data[3] else 0
        pre_close = float(data[4]) if data[4] else 0
        change_pct = round((price - pre_close) / pre_close * 100, 2) if pre_close else 0
        pe = float(data[39]) if data[39] else 0
        pb = float(data[51]) if len(data) > 51 and data[51] else 0
        market_cap = float(data[44]) if data[44] else 0
        dividend_yield = float(data[43]) if data[43] else 0

        if price <= 0:
            return None

        # ROE = PB/PE * 100
        roe = None
        if pb and pe and pe > 0:
            roe = round(pb / pe * 100, 2)

        return {
            'code': symbol, 'name': name, 'market': 'US',
            'price': round(price, 2), 'change_pct': change_pct,
            'pe': round(pe, 2) if pe > 0 else None,
            'pb': round(pb, 2) if pb > 0 else None,
            'market_cap': round(market_cap, 2),
            'dividend_yield': round(dividend_yield, 2) if dividend_yield > 0 else None,
            'roe': roe,
            'gross_margin': None, 'net_margin': None,
            'debt_ratio': None,
            'revenue_growth': None, 'profit_growth': None,
            'report_period': '',
        }
    except Exception:
        return None


def _get_a_stock_data(code: str) -> Optional[dict]:
    """Fetch A-share data from EastMoney."""
    try:
        basic = DataService.get_stock_basic(code)
        if "error" in basic:
            return None

        financials = DataService.get_financial_indicators(code)
        reports = financials.get("reports", [])
        latest = _get_annual_report(reports) if reports else {}

        # Get dividend data
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
# 投资大师评分体系 - 每位大师有独立的评估逻辑
# ============================================================

def _score_buffett(stock: dict) -> tuple:
    """
    巴菲特评分体系 (满分100)
    核心框架: 护城河 + 管理层 + 合理价格 + 长期持有

    巴菲特的投资逻辑:
    1. 买股票就是买企业的一部分 - 关注企业本身而非股价波动
    2. 经济护城河是最重要的 - 持久的竞争优势决定长期回报
    3. ROE是衡量管理层效率的核心指标 - 持续高ROE说明资本配置能力强
    4. 安全边际 - 即使是最好的公司也要在合理价格买入
    5. 长期持有 - "我最喜欢的持有期是永远"
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

    # 1. ROE (25分) - 巴菲特最看重的指标
    # "如果只能用一个指标选股，那就是ROE"
    # 他要求长期ROE > 15%，优秀企业 > 20%
    if roe is not None:
        if roe >= 25:
            score += 25
            details.append(f"ROE={roe:.1f}% 卓越")
        elif roe >= 20:
            score += 22
            details.append(f"ROE={roe:.1f}% 优秀")
        elif roe >= 15:
            score += 18
            details.append(f"ROE={roe:.1f}% 良好")
        elif roe >= 10:
            score += 12
            details.append(f"ROE={roe:.1f}% 一般")
        else:
            score += 5
            details.append(f"ROE={roe:.1f}% 偏低")
    else:
        score += 10
        details.append("ROE无数据")

    # 2. 护城河 - 毛利率 (20分)
    # 高毛利率说明产品有定价权，这是护城河的直接体现
    # 可口可乐毛利率60%+，茅台90%+
    if gross_margin is not None:
        if gross_margin >= 60:
            score += 20
            details.append(f"毛利率{gross_margin:.1f}% 宽护城河")
        elif gross_margin >= 40:
            score += 16
            details.append(f"毛利率{gross_margin:.1f}% 中等护城河")
        elif gross_margin >= 25:
            score += 10
            details.append(f"毛利率{gross_margin:.1f}% 窄护城河")
        else:
            score += 4
            details.append(f"毛利率{gross_margin:.1f}% 无明显护城河")
    else:
        score += 8
        details.append("毛利率无数据")

    # 3. 净利率 (15分) - 体现定价权和成本控制
    if net_margin is not None:
        if net_margin >= 25:
            score += 15
            details.append(f"净利率{net_margin:.1f}% 极强盈利能力")
        elif net_margin >= 15:
            score += 12
            details.append(f"净利率{net_margin:.1f}% 强盈利能力")
        elif net_margin >= 8:
            score += 8
            details.append(f"净利率{net_margin:.1f}% 中等")
        else:
            score += 3
            details.append(f"净利率{net_margin:.1f}% 偏低")
    else:
        score += 6
        details.append("净利率无数据")

    # 4. 估值合理性 (20分) - 安全边际
    # 巴菲特: "用合理的价格买入优秀公司，远胜于用便宜的价格买入平庸公司"
    # 但他也不会为优秀公司支付无限溢价
    val_score = 0
    if pe is not None and pe > 0:
        if pe < 15:
            val_score += 10
        elif pe < 20:
            val_score += 8
        elif pe < 25:
            val_score += 5
        elif pe < 35:
            val_score += 3
    if pb is not None and pb > 0:
        if pb < 2:
            val_score += 5
        elif pb < 4:
            val_score += 4
        elif pb < 6:
            val_score += 2
    if div_yield and div_yield > 2:
        val_score += 5
    elif div_yield and div_yield > 0:
        val_score += 2
    score += min(val_score, 20)
    details.append(f"估值得分{min(val_score,20)}/20")

    # 5. 财务健康 (10分) - 低负债
    # 巴菲特偏好低负债企业，认为高负债是管理层贪婪的表现
    if debt is not None:
        if debt < 30:
            score += 10
            details.append(f"负债率{debt:.1f}% 财务稳健")
        elif debt < 50:
            score += 7
            details.append(f"负债率{debt:.1f}% 可接受")
        elif debt < 65:
            score += 4
            details.append(f"负债率{debt:.1f}% 偏高")
        else:
            score += 1
            details.append(f"负债率{debt:.1f}% 高风险")
    else:
        score += 5
        details.append("负债率无数据")

    # 6. 成长性 (10分) - 巴菲特更看重稳定性而非高增长
    # 他愿意为稳定增长支付溢价，但不喜欢依赖高增长的故事
    if rev_growth is not None and profit_growth is not None:
        if profit_growth > 10 and rev_growth > 5:
            score += 10
            details.append(f"利润+{profit_growth:.1f}% 稳健增长")
        elif profit_growth > 0:
            score += 7
            details.append(f"利润+{profit_growth:.1f}%")
        else:
            score += 3
            details.append(f"利润{profit_growth:+.1f}% 承压")
    else:
        score += 5

    return min(score, 100), " | ".join(details)


def _score_munger(stock: dict) -> tuple:
    """
    芒格评分体系 (满分100)
    核心框架: 多元思维模型 + 逆向思考 + 理性决策

    芒格的投资逻辑:
    1. "反过来想，总是反过来想" - 先考虑如何失败，再考虑如何成功
    2. 多元思维模型 - 用多学科视角分析企业，避免"锤子综合症"
    3. 检查清单法 - 系统性排除风险因素
    4. 质量优于价格 - "以合理价格买入优秀企业"
    5. 避免愚蠢 - "与其追求聪明，不如避免做蠢事"
    6. 耐心等待 - 好机会不常有，要像猎豹一样等待
    """
    score = 0
    details = []

    roe = stock.get('roe')
    gross_margin = stock.get('gross_margin')
    net_margin = stock.get('net_margin')
    pe = stock.get('pe')
    pb = stock.get('pb')
    debt = stock.get('debt_ratio')
    rev_growth = stock.get('revenue_growth')
    profit_growth = stock.get('profit_growth')

    # 1. 企业质量 (25分) - 芒格最看重企业质量
    # 他愿意为好企业付出合理溢价，绝不买烂企业
    # ROE + 毛利率 综合判断
    quality_score = 0
    if roe is not None:
        if roe >= 20:
            quality_score += 13
        elif roe >= 15:
            quality_score += 10
        elif roe >= 10:
            quality_score += 6
        else:
            quality_score += 2
    if gross_margin is not None:
        if gross_margin >= 50:
            quality_score += 12
        elif gross_margin >= 30:
            quality_score += 8
        elif gross_margin >= 15:
            quality_score += 4
    score += min(quality_score, 25)
    details.append(f"企业质量{min(quality_score,25)}/25")

    # 2. 管理层理性 (20分) - 芒格极其看重管理层的理性
    # "好的管理层应该理性配置资本，而不是盲目扩张"
    # 用利润增长 vs 营收增长来判断资本效率
    mgmt_score = 0
    if profit_growth is not None and rev_growth is not None:
        if profit_growth > rev_growth and profit_growth > 0:
            mgmt_score += 12
            details.append(f"利润增速>营收增速 管理层高效")
        elif profit_growth > 0:
            mgmt_score += 8
        else:
            mgmt_score += 3
    else:
        mgmt_score += 6

    if debt is not None:
        if debt < 35:
            mgmt_score += 8
            details.append(f"负债率{debt:.1f}% 理性保守")
        elif debt < 55:
            mgmt_score += 5
        else:
            mgmt_score += 2
    else:
        mgmt_score += 4
    score += min(mgmt_score, 20)

    # 3. 逆向思维 - 风险排除 (20分)
    # 芒格: "告诉我我会死在哪里，我就不去那里"
    # 重点排除: 高负债、低利润、负增长
    risk_score = 20
    if debt is not None and debt > 70:
        risk_score -= 8
        details.append(f"负债率{debt:.1f}% 高风险(-8)")
    if profit_growth is not None and profit_growth < -10:
        risk_score -= 6
        details.append(f"利润下滑{profit_growth:.1f}%(-6)")
    if roe is not None and roe < 5:
        risk_score -= 6
        details.append(f"ROE过低(-6)")
    score += max(risk_score, 0)

    # 4. 估值合理性 (15分) - 芒格对估值更宽容
    # "以合理价格买入优秀企业" - 不追求极致便宜
    if pe is not None and pe > 0:
        if pe < 12:
            score += 15
            details.append(f"PE={pe:.1f} 低估")
        elif pe < 18:
            score += 12
            details.append(f"PE={pe:.1f} 合理")
        elif pe < 25:
            score += 8
            details.append(f"PE={pe:.1f} 偏高但可接受")
        elif pe < 35:
            score += 4
        else:
            score += 1
    else:
        score += 6

    # 5. 净利率 (10分) - 盈利能力验证
    if net_margin is not None:
        if net_margin >= 20:
            score += 10
        elif net_margin >= 12:
            score += 7
        elif net_margin >= 6:
            score += 4
        else:
            score += 1
    else:
        score += 4

    # 6. 成长性 (10分) - 芒格看重可持续增长
    if rev_growth is not None and profit_growth is not None:
        if rev_growth > 8 and profit_growth > 8:
            score += 10
            details.append(f"营收+{rev_growth:.1f}% 利润+{profit_growth:.1f}%")
        elif rev_growth > 0 and profit_growth > 0:
            score += 6
        else:
            score += 2
    else:
        score += 4

    return min(score, 100), " | ".join(details)


def _score_li_lu(stock: dict) -> tuple:
    """
    李录评分体系 (满分100)
    核心框架: 知识优势 + 中国实践 + 长期视角

    李录的投资逻辑:
    1. 知识优势 - 只投资自己真正理解的企业，比市场有更深的认知
    2. 中国市场的特殊性 - 中国有独特的制度红利和消费升级机会
    3. 长期视角 - 以5-10年为投资周期，不被短期波动干扰
    4. 管理层品质 - 在中国市场尤其重要，因为公司治理参差不齐
    5. 行业选择 - 选择结构性增长行业，而非周期性行业
    6. 合理估值 - 不为增长支付过高价格，保持安全边际
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

    # 1. ROE质量 (25分) - 李录: ROE是衡量企业效率的核心指标
    # 他投资的比亚迪、邮储银行等都有持续的ROE表现
    if roe is not None:
        if roe >= 20:
            score += 25
            details.append(f"ROE={roe:.1f}% 优秀")
        elif roe >= 15:
            score += 20
            details.append(f"ROE={roe:.1f}% 良好")
        elif roe >= 10:
            score += 14
            details.append(f"ROE={roe:.1f}% 可接受")
        elif roe >= 5:
            score += 8
        else:
            score += 3
    else:
        score += 10

    # 2. 护城河 (20分) - 知识优势的量化体现
    # 李录: 护城河体现在定价权(毛利率)和盈利能力(净利率)
    moat_score = 0
    if gross_margin is not None:
        if gross_margin >= 50:
            moat_score += 10
        elif gross_margin >= 30:
            moat_score += 7
        elif gross_margin >= 15:
            moat_score += 4
    if net_margin is not None:
        if net_margin >= 20:
            moat_score += 10
        elif net_margin >= 12:
            moat_score += 7
        elif net_margin >= 5:
            moat_score += 4
    score += min(moat_score, 20)
    details.append(f"护城河{min(moat_score,20)}/20")

    # 3. 成长性 (20分) - 李录重视结构性增长
    # 他选择的行业(新能源、消费、金融)都有长期增长逻辑
    if rev_growth is not None and profit_growth is not None:
        if rev_growth > 15 and profit_growth > 15:
            score += 20
            details.append(f"高增长 营收+{rev_growth:.1f}% 利润+{profit_growth:.1f}%")
        elif rev_growth > 8 and profit_growth > 8:
            score += 15
            details.append(f"稳健增长 营收+{rev_growth:.1f}% 利润+{profit_growth:.1f}%")
        elif rev_growth > 0 and profit_growth > 0:
            score += 10
            details.append(f"温和增长")
        else:
            score += 4
            details.append(f"增长承压")
    else:
        score += 8

    # 4. 估值 (15分) - 安全边际
    # 李录: "不为增长支付过高价格"
    if pe is not None and pe > 0:
        if pe < 12:
            score += 15
            details.append(f"PE={pe:.1f} 低估")
        elif pe < 18:
            score += 12
            details.append(f"PE={pe:.1f} 合理")
        elif pe < 25:
            score += 8
        elif pe < 35:
            score += 4
        else:
            score += 1
    else:
        score += 6

    # 5. 财务健康 (10分) - 在中国市场尤为重要
    if debt is not None:
        if debt < 30:
            score += 10
            details.append(f"负债率{debt:.1f}% 健康")
        elif debt < 50:
            score += 7
        elif debt < 65:
            score += 4
        else:
            score += 1
    else:
        score += 5

    # 6. 股息回报 (10分) - 李录重视股东回报
    if div_yield is not None and div_yield > 0:
        if div_yield >= 4:
            score += 10
            details.append(f"股息率{div_yield:.1f}% 高回报")
        elif div_yield >= 2:
            score += 7
        elif div_yield >= 1:
            score += 4
        else:
            score += 2
    else:
        score += 4

    return min(score, 100), " | ".join(details)


def _score_duan_yongping(stock: dict) -> tuple:
    """
    段永平评分体系 (满分100)
    核心框架: 商业模式 + 差异化 + 本分 + 长期

    段永平的投资逻辑:
    1. "买股票就是买公司，买公司就是买未来现金流的折现"
    2. 好商业模式 > 好管理 > 好价格 (优先级排序)
    3. "差异化"是核心概念 - 产品要有真实的差异化，不是同质化竞争
    4. "本分" - 做正确的事，不走捷径，管理层要诚信
    5. "Stop doing list" - 知道什么不该做比知道该做什么更重要
    6. 消费者导向 - 以消费者需求为中心，而非以竞争对手为中心
    7. 不做空、不借钱炒股、不懂不做 - 三条铁律
    8. 集中投资 - 重仓少数几家真正理解的好公司
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

    # 1. 商业模式 (30分) - 段永平最看重的维度
    # "好商业模式就是能持续赚取高利润且不需要大量资本投入"
    # 用ROE + 毛利率 + 净利率综合判断
    biz_score = 0
    if roe is not None:
        if roe >= 25:
            biz_score += 12
        elif roe >= 18:
            biz_score += 9
        elif roe >= 12:
            biz_score += 6
        else:
            biz_score += 2
    if gross_margin is not None:
        if gross_margin >= 50:
            biz_score += 10
            details.append(f"毛利率{gross_margin:.1f}% 差异化明显")
        elif gross_margin >= 30:
            biz_score += 7
        elif gross_margin >= 15:
            biz_score += 4
    if net_margin is not None:
        if net_margin >= 20:
            biz_score += 8
        elif net_margin >= 12:
            biz_score += 5
        elif net_margin >= 5:
            biz_score += 3
    score += min(biz_score, 30)
    details.append(f"商业模式{min(biz_score,30)}/30")

    # 2. 成长性 (25分) - 段永平: "好的生意会自然增长"
    # 他投资的苹果、腾讯、茅台都有持续增长
    if rev_growth is not None and profit_growth is not None:
        if rev_growth > 15 and profit_growth > 15:
            score += 25
            details.append(f"高增长 营收+{rev_growth:.1f}% 利润+{profit_growth:.1f}%")
        elif rev_growth > 8 and profit_growth > 8:
            score += 18
            details.append(f"稳健增长")
        elif rev_growth > 0 and profit_growth > 0:
            score += 12
        else:
            score += 4
            details.append(f"增长承压")
    else:
        score += 10

    # 3. 财务健康 (15分) - "不懂不做"的延伸: 不做高负债的事
    if debt is not None:
        if debt < 25:
            score += 15
            details.append(f"负债率{debt:.1f}% 非常健康")
        elif debt < 40:
            score += 12
        elif debt < 55:
            score += 7
        else:
            score += 2
    else:
        score += 7

    # 4. 估值 (15分) - 段永平: "好价格是锦上添花，不是必要条件"
    # 他愿意为好公司支付合理价格，不像格雷厄姆那样追求极致便宜
    if pe is not None and pe > 0:
        if pe < 15:
            score += 15
            details.append(f"PE={pe:.1f} 好价格")
        elif pe < 22:
            score += 12
            details.append(f"PE={pe:.1f} 合理")
        elif pe < 30:
            score += 8
        elif pe < 40:
            score += 4
        else:
            score += 1
    else:
        score += 6

    # 5. 股东回报 (10分) - 分红体现管理层对股东的态度
    if div_yield is not None and div_yield > 0:
        if div_yield >= 3:
            score += 10
            details.append(f"股息率{div_yield:.1f}% 股东友好")
        elif div_yield >= 1.5:
            score += 7
        elif div_yield > 0:
            score += 4
    else:
        score += 4

    # 6. 低负债安全性 (5分)
    if debt is not None and debt < 30:
        score += 5

    return min(score, 100), " | ".join(details)


# Master scoring dispatch
MASTER_SCORERS = {
    'buffett': _score_buffett,
    'munger': _score_munger,
    'li_lu': _score_li_lu,
    'duan_yongping': _score_duan_yongping,
}


def calculate_master_score(stock: dict, master: str) -> int:
    """Calculate score for a specific master."""
    scorer = MASTER_SCORERS.get(master, _score_buffett)
    score, _ = scorer(stock)
    return score


def calculate_all_scores(stock: dict) -> dict:
    """Calculate all master scores and details."""
    results = {}
    for master, scorer in MASTER_SCORERS.items():
        score, detail = scorer(stock)
        results[master] = {'score': score, 'detail': detail}

    buffett_s = results['buffett']['score']
    munger_s = results['munger']['score']
    li_lu_s = results['li_lu']['score']
    duan_s = results['duan_yongping']['score']
    combined = int((buffett_s + munger_s + li_lu_s + duan_s) / 4)

    return {
        'buffett_score': buffett_s,
        'munger_score': munger_s,
        'li_lu_score': li_lu_s,
        'duan_score': duan_s,
        'score': combined,
        'score_details': {
            'buffett': results['buffett'],
            'munger': results['munger'],
            'li_lu': results['li_lu'],
            'duan_yongping': results['duan_yongping'],
        }
    }


# ============================================================
# Cache
# ============================================================

from app.core.cache import get_cache as _base_get_cache, set_cache as _set_cached
_CACHE_TTL = 600

def _get_cached(key: str):
    return _base_get_cache(key, ttl_seconds=_CACHE_TTL)


# ============================================================
# Main Screener
# ============================================================

def screen_stocks(
    market: str = "all",
    master: str = "combined",
    min_score: int = 50,
    max_pe: float = 30,
    max_pb: float = 5,
    top_n: int = 50,
) -> dict:
    """Screen stocks across A/HK/US markets."""
    cache_key = f"vi_{market}_{master}_{min_score}_{max_pe}_{max_pb}_{top_n}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    stock_lists = []
    if market in ("all", "a"):
        for code in A_STOCKS_LIST:
            stock_lists.append(("a", code))
    if market in ("all", "hk"):
        for code in HK_STOCKS_LIST:
            stock_lists.append(("hk", code))
    if market in ("all", "us"):
        for code in US_STOCKS_LIST:
            stock_lists.append(("us", code))

    results = []
    batch_size = 10

    for i in range(0, len(stock_lists), batch_size):
        batch = stock_lists[i:i + batch_size]
        for mkt, code in batch:
            try:
                if mkt == "a":
                    stock = _get_a_stock_data(code)
                elif mkt == "hk":
                    stock = _get_hk_stock_data(code)
                else:
                    stock = _get_us_stock_data(code)

                if not stock or stock.get('price', 0) <= 0:
                    continue

                # Basic filters
                pe = stock.get('pe')
                pb = stock.get('pb')
                if pe is not None and (pe <= 0 or pe > max_pe):
                    continue
                if pb is not None and (pb <= 0 or pb > max_pb):
                    continue

                # Calculate all scores
                scores = calculate_all_scores(stock)
                stock.update(scores)

                # Select final score based on master
                if master != 'combined':
                    stock['score'] = scores.get(f'{master}_score', scores['score'])

                if stock['score'] < min_score:
                    continue

                if stock['score'] >= 80:
                    stock['match_level'] = 'excellent'
                elif stock['score'] >= 65:
                    stock['match_level'] = 'good'
                elif stock['score'] >= 50:
                    stock['match_level'] = 'fair'
                else:
                    stock['match_level'] = 'poor'

                results.append(stock)
            except Exception:
                continue

        if i + batch_size < len(stock_lists):
            time.sleep(0.1)

    results.sort(key=lambda x: x['score'], reverse=True)
    results = results[:top_n]

    output = {
        'stocks': results,
        'total': len(results),
        'master': master,
        'market': market,
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'criteria': {
            'min_score': min_score,
            'max_pe': max_pe,
            'max_pb': max_pb,
        }
    }

    _set_cached(cache_key, output)
    return output
