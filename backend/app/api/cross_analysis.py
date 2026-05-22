"""横纵分析法 - 公司快速扫盲工具"""

from fastapi import APIRouter, HTTPException
from app.services.data_service import DataService, _get_annual_report
from datetime import datetime

router = APIRouter()
data_service = DataService()


# 行业竞品映射表
INDUSTRY_PEERS = {
    # 白酒
    '600519': ['600519', '000858', '000568', '600809', '002304', '000596'],
    '000858': ['600519', '000858', '000568', '600809', '002304', '000596'],
    '000568': ['600519', '000858', '000568', '600809', '002304', '000596'],
    '600809': ['600519', '000858', '000568', '600809', '002304', '000596'],
    '002304': ['600519', '000858', '000568', '600809', '002304', '000596'],
    '000596': ['600519', '000858', '000568', '600809', '002304', '000596'],

    # 银行
    '601398': ['601398', '601288', '601939', '601988', '600036', '601166'],
    '601288': ['601398', '601288', '601939', '601988', '600036', '601166'],
    '601939': ['601398', '601288', '601939', '601988', '600036', '601166'],
    '601988': ['601398', '601288', '601939', '601988', '600036', '601166'],
    '600036': ['601398', '601288', '601939', '601988', '600036', '601166'],
    '601166': ['601398', '601288', '601939', '601988', '600036', '601166'],

    # 家电
    '000333': ['000333', '000651', '600690', '002032'],
    '000651': ['000333', '000651', '600690', '002032'],
    '600690': ['000333', '000651', '600690', '002032'],

    # 新能源
    '300750': ['300750', '002594', '600438', '601012'],
    '002594': ['300750', '002594', '600438', '601012'],

    # 医药
    '600276': ['600276', '000538', '002001', '600196', '300015'],
    '000538': ['600276', '000538', '002001', '600196', '300015'],

    # 互联网/科技
    '00700': ['00700', '09988', '03690', '09618', '09888'],
    '09988': ['00700', '09988', '03690', '09618', '09888'],

    # 能源
    '601088': ['601088', '600188', '601857', '600028'],
    '601857': ['601088', '600188', '601857', '600028'],

    # 电力
    '600900': ['600900', '600886', '600795', '600023', '601985'],
    '600886': ['600900', '600886', '600795', '600023', '601985'],

    # 保险
    '601318': ['601318', '601628', '601601', '02628'],
    '601628': ['601318', '601628', '601601', '02628'],

    # 地产
    '001979': ['001979', '600048', '000002', '601155'],
    '600048': ['001979', '600048', '000002', '601155'],
}

# 行业名称映射
INDUSTRY_NAMES = {
    '600519': '白酒', '000858': '白酒', '000568': '白酒', '600809': '白酒',
    '601398': '银行', '601288': '银行', '601939': '银行', '601988': '银行', '600036': '银行',
    '000333': '家电', '000651': '家电', '600690': '家电',
    '300750': '新能源', '002594': '新能源',
    '600276': '医药', '000538': '医药',
    '601088': '能源', '601857': '能源',
    '600900': '电力', '600886': '电力',
    '601318': '保险', '601628': '保险',
}


def get_peer_codes(stock_code: str) -> list:
    """获取同行业竞品代码"""
    return INDUSTRY_PEERS.get(stock_code, [stock_code])


def get_industry_name(stock_code: str) -> str:
    """获取行业名称"""
    return INDUSTRY_NAMES.get(stock_code, '未知行业')


def calculate_growth_rate(data_list: list, field: str) -> list:
    """计算增长率趋势"""
    values = []
    for item in data_list:
        val = item.get(field)
        if val is not None:
            values.append(val)
    return values


def analyze_lifecycle_stage(reports: list) -> str:
    """分析公司所处生命周期阶段"""
    if not reports or len(reports) < 3:
        return '数据不足'

    # 取最近3年的数据
    recent = reports[:3]

    # 计算平均增长率
    revenue_growth = [r.get('revenue_growth', 0) or 0 for r in recent]
    profit_growth = [r.get('profit_growth', 0) or 0 for r in recent]
    avg_revenue_growth = sum(revenue_growth) / len(revenue_growth)
    avg_profit_growth = sum(profit_growth) / len(profit_growth)

    # 判断阶段
    if avg_revenue_growth > 20 and avg_profit_growth > 20:
        return '高速成长期'
    elif avg_revenue_growth > 10 and avg_profit_growth > 10:
        return '稳定成长期'
    elif avg_revenue_growth > 0 and avg_profit_growth > 0:
        return '成熟期'
    elif avg_revenue_growth < 0 and avg_profit_growth < 0:
        return '衰退期'
    elif avg_revenue_growth < 0 and avg_profit_growth > 0:
        return '收缩期（利润优化）'
    else:
        return '转型期'


def generate_timeline(reports: list) -> list:
    """生成财务指标时间线"""
    timeline = []
    for r in reversed(reports):
        timeline.append({
            'date': r.get('date', ''),
            'report_name': r.get('report_name', ''),
            'roe': r.get('roe'),
            'gross_margin': r.get('gross_margin'),
            'net_margin': r.get('net_margin'),
            'revenue_growth': r.get('revenue_growth'),
            'profit_growth': r.get('profit_growth'),
            'debt_ratio': r.get('debt_ratio'),
        })
    return timeline


@router.get("/analyze/{stock_code}")
async def cross_analysis(stock_code: str):
    """
    横纵分析法 - 公司快速扫盲

    返回：
    1. 纵向分析：公司历史财务指标趋势
    2. 横向分析：与同行业竞品对比
    3. 交叉洞察：投资判断
    """
    try:
        # 1. 获取目标公司数据
        basic = data_service.get_stock_basic(stock_code)
        if 'error' in basic:
            raise HTTPException(status_code=400, detail=basic['error'])

        financials = data_service.get_financial_indicators(stock_code)
        if 'error' in financials:
            raise HTTPException(status_code=400, detail=financials['error'])

        reports = financials.get('reports', [])
        if not reports:
            raise HTTPException(status_code=400, detail='未找到财务数据')

        latest = _get_annual_report(reports)

        # 2. 纵向分析
        timeline = generate_timeline(reports)
        lifecycle_stage = analyze_lifecycle_stage(reports)

        # 计算关键指标趋势
        roe_trend = [r.get('roe') for r in reports if r.get('roe') is not None]
        gross_margin_trend = [r.get('gross_margin') for r in reports if r.get('gross_margin') is not None]
        revenue_growth_trend = [r.get('revenue_growth') for r in reports if r.get('revenue_growth') is not None]

        # 3. 横向分析
        peer_codes = get_peer_codes(stock_code)
        industry_name = get_industry_name(stock_code)

        peers_data = []
        for code in peer_codes:
            if code == stock_code:
                continue
            try:
                peer_basic = data_service.get_stock_basic(code)
                peer_financials = data_service.get_financial_indicators(code)
                if 'error' not in peer_basic and 'error' not in peer_financials:
                    peer_reports = peer_financials.get('reports', [])
                    if peer_reports:
                        peer_latest = _get_annual_report(peer_reports)
                        peers_data.append({
                            'code': code,
                            'name': peer_basic.get('name', ''),
                            'price': peer_basic.get('price', 0),
                            'pe': peer_basic.get('pe'),
                            'pb': peer_basic.get('pb'),
                            'roe': peer_latest.get('roe'),
                            'gross_margin': peer_latest.get('gross_margin'),
                            'net_margin': peer_latest.get('net_margin'),
                            'revenue_growth': peer_latest.get('revenue_growth'),
                            'profit_growth': peer_latest.get('profit_growth'),
                            'debt_ratio': peer_latest.get('debt_ratio'),
                        })
            except Exception:
                continue

        # 计算行业平均值
        industry_avg = {}
        if peers_data:
            for field in ['roe', 'gross_margin', 'net_margin', 'revenue_growth', 'profit_growth', 'debt_ratio']:
                values = [p.get(field) for p in peers_data if p.get(field) is not None]
                if values:
                    industry_avg[field] = round(sum(values) / len(values), 2)

        # 4. 生成投资洞察
        insights = generate_insights(basic, latest, peers_data, industry_avg, lifecycle_stage)

        # 5. 评级
        rating = calculate_rating(latest, industry_avg)

        return {
            'stock': {
                'code': stock_code,
                'name': basic.get('name', ''),
                'price': basic.get('price', 0),
                'pe': basic.get('pe'),
                'pb': basic.get('pb'),
                'market_cap': basic.get('market_cap'),
            },
            'vertical_analysis': {
                'lifecycle_stage': lifecycle_stage,
                'timeline': timeline,
                'roe_trend': roe_trend,
                'gross_margin_trend': gross_margin_trend,
                'revenue_growth_trend': revenue_growth_trend,
                'latest_metrics': {
                    'roe': latest.get('roe'),
                    'gross_margin': latest.get('gross_margin'),
                    'net_margin': latest.get('net_margin'),
                    'revenue_growth': latest.get('revenue_growth'),
                    'profit_growth': latest.get('profit_growth'),
                    'debt_ratio': latest.get('debt_ratio'),
                },
            },
            'horizontal_analysis': {
                'industry': industry_name,
                'peers': peers_data,
                'industry_avg': industry_avg,
            },
            'insights': insights,
            'rating': rating,
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def generate_insights(basic: dict, latest: dict, peers: list, industry_avg: dict, lifecycle: str) -> dict:
    """生成投资洞察"""
    insights = {
        'summary': '',
        'strengths': [],
        'weaknesses': [],
        'opportunities': [],
        'threats': [],
        'conclusion': '',
    }

    name = basic.get('name', '该公司')
    roe = latest.get('roe', 0) or 0
    gross_margin = latest.get('gross_margin', 0) or 0
    revenue_growth = latest.get('revenue_growth', 0) or 0
    debt_ratio = latest.get('debt_ratio', 0) or 0

    # 一句话结论
    if roe > 15 and gross_margin > 40:
        insights['summary'] = f'{name}是一家盈利能力突出的优质企业，ROE和毛利率均处于行业领先水平。'
    elif roe > 10:
        insights['summary'] = f'{name}盈利能力良好，处于{lifecycle}阶段。'
    else:
        insights['summary'] = f'{name}盈利能力一般，需要关注基本面变化。'

    # 优势
    if roe > 15:
        insights['strengths'].append(f'ROE={roe:.1f}%，盈利能力优秀')
    if gross_margin > 40:
        insights['strengths'].append(f'毛利率={gross_margin:.1f}%，护城河宽')
    if revenue_growth > 10:
        insights['strengths'].append(f'营收增长={revenue_growth:.1f}%，成长性好')
    if debt_ratio < 40:
        insights['strengths'].append(f'资产负债率={debt_ratio:.1f}%，财务稳健')

    # 劣势
    if roe < 10:
        insights['weaknesses'].append(f'ROE={roe:.1f}%，盈利能力偏弱')
    if gross_margin < 30:
        insights['weaknesses'].append(f'毛利率={gross_margin:.1f}%，护城河窄')
    if revenue_growth < 0:
        insights['weaknesses'].append(f'营收增长={revenue_growth:.1f}%，业务收缩')
    if debt_ratio > 60:
        insights['weaknesses'].append(f'资产负债率={debt_ratio:.1f}%，负债偏高')

    # 机会
    if '成长' in lifecycle:
        insights['opportunities'].append('公司处于成长期，未来增长空间大')
    if industry_avg.get('roe', 0) > 0 and roe > industry_avg['roe']:
        insights['opportunities'].append('ROE高于行业平均，竞争优势明显')

    # 威胁
    if '衰退' in lifecycle:
        insights['threats'].append('公司处于衰退期，需要关注转型')
    if revenue_growth < 0:
        insights['threats'].append('营收下滑，需要关注市场变化')

    # 总结
    if len(insights['strengths']) > len(insights['weaknesses']):
        insights['conclusion'] = f'{name}整体表现优秀，建议关注。'
    elif len(insights['strengths']) == len(insights['weaknesses']):
        insights['conclusion'] = f'{name}表现中性，需要进一步研究。'
    else:
        insights['conclusion'] = f'{name}存在较多风险因素，建议谨慎。'

    return insights


def calculate_rating(latest: dict, industry_avg: dict) -> dict:
    """计算投资评级"""
    score = 0
    details = []

    roe = latest.get('roe', 0) or 0
    gross_margin = latest.get('gross_margin', 0) or 0
    revenue_growth = latest.get('revenue_growth', 0) or 0
    debt_ratio = latest.get('debt_ratio', 0) or 0

    # ROE评分 (30分)
    if roe > 20:
        score += 30
        details.append({'item': 'ROE', 'score': 30, 'comment': '优秀'})
    elif roe > 15:
        score += 25
        details.append({'item': 'ROE', 'score': 25, 'comment': '良好'})
    elif roe > 10:
        score += 15
        details.append({'item': 'ROE', 'score': 15, 'comment': '一般'})
    else:
        score += 5
        details.append({'item': 'ROE', 'score': 5, 'comment': '偏弱'})

    # 毛利率评分 (25分)
    if gross_margin > 50:
        score += 25
        details.append({'item': '毛利率', 'score': 25, 'comment': '优秀'})
    elif gross_margin > 40:
        score += 20
        details.append({'item': '毛利率', 'score': 20, 'comment': '良好'})
    elif gross_margin > 30:
        score += 12
        details.append({'item': '毛利率', 'score': 12, 'comment': '一般'})
    else:
        score += 5
        details.append({'item': '毛利率', 'score': 5, 'comment': '偏弱'})

    # 成长性评分 (25分)
    if revenue_growth > 20:
        score += 25
        details.append({'item': '成长性', 'score': 25, 'comment': '高增长'})
    elif revenue_growth > 10:
        score += 20
        details.append({'item': '成长性', 'score': 20, 'comment': '稳定增长'})
    elif revenue_growth > 0:
        score += 12
        details.append({'item': '成长性', 'score': 12, 'comment': '低增长'})
    else:
        score += 5
        details.append({'item': '成长性', 'score': 5, 'comment': '负增长'})

    # 财务健康评分 (20分)
    if debt_ratio < 30:
        score += 20
        details.append({'item': '财务健康', 'score': 20, 'comment': '优秀'})
    elif debt_ratio < 50:
        score += 15
        details.append({'item': '财务健康', 'score': 15, 'comment': '良好'})
    elif debt_ratio < 60:
        score += 10
        details.append({'item': '财务健康', 'score': 10, 'comment': '一般'})
    else:
        score += 3
        details.append({'item': '财务健康', 'score': 3, 'comment': '风险'})

    # 评级
    if score >= 85:
        grade = 'A+'
        recommendation = '强烈推荐'
    elif score >= 75:
        grade = 'A'
        recommendation = '推荐'
    elif score >= 65:
        grade = 'B+'
        recommendation = '谨慎推荐'
    elif score >= 55:
        grade = 'B'
        recommendation = '中性'
    elif score >= 45:
        grade = 'C'
        recommendation = '观望'
    else:
        grade = 'D'
        recommendation = '不推荐'

    return {
        'score': score,
        'grade': grade,
        'recommendation': recommendation,
        'details': details,
    }
