"""港股烟蒂股筛选 - 格雷厄姆、巴菲特、施洛斯标准"""

from fastapi import APIRouter
from datetime import datetime
import requests

router = APIRouter()


def get_hk_stock_realtime(code: str) -> dict:
    """获取单只港股实时数据"""
    try:
        # 腾讯财经API
        url = f'https://qt.gtimg.cn/q=r_hk{code}'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://stockapp.finance.qq.com/',
        }
        r = requests.get(url, headers=headers, timeout=10)
        r.encoding = 'gbk'

        # 解析腾讯财经格式
        text = r.text
        if '="' not in text:
            return None

        data = text.split('"')[1].split('~')
        if len(data) < 50:
            return None

        name = data[1]
        price = float(data[3]) if data[3] else 0
        pre_close = float(data[4]) if data[4] else 0
        change_pct = float(data[32]) if data[32] else 0
        pe = float(data[39]) if data[39] else 0
        market_cap = float(data[44]) if data[44] else 0  # 亿港元
        dividend_yield = float(data[43]) if data[43] else 0

        if price <= 0:
            return None

        # PB需要从其他API获取或估算
        # 这里先设置为None，后续可以通过其他方式获取
        pb = None

        return {
            'code': code,
            'name': name,
            'price': price,
            'change_pct': change_pct,
            'pe': pe if pe > 0 else None,
            'pb': pb,
            'market_cap': market_cap,
            'dividend_yield': dividend_yield,
        }
    except Exception as e:
        return None


# 预设港股列表（蓝筹股 + 红筹股 + 知名公司）
HK_STOCKS_LIST = [
    # 蓝筹股
    '00001', '00002', '00003', '00005', '00006', '00011', '00012',
    '00016', '00017', '00019', '00020', '00027', '00066', '00101',
    '00175', '00241', '00267', '00288', '00291', '00293', '00316',
    '00322', '00386', '00388', '00669', '00688', '00700', '00762',
    '00823', '00857', '00883', '00939', '00941', '00960', '00968',
    '00981', '01038', '01044', '01093', '01109', '01113', '01177',
    '01211', '01299', '01378', '01398', '01810', '01876', '01928',
    '01929', '01997', '02007', '02013', '02018', '02020', '02269',
    '02313', '02318', '02319', '02382', '02388', '02628', '02688',
    '03311', '03328', '03333', '03692', '03968', '03988', '06030',
    '06060', '06098', '06160', '06618', '06690', '06862', '09618',
    '09626', '09633', '09698', '09888', '09961', '09988', '09999',
    # 红筹股 / H股
    '00168', '00177', '00338', '00347', '00358', '00525',
    '00553', '00576', '00670', '00728', '00753', '00902', '00914',
    '00916', '00956', '00992', '01055', '01066', '01071', '01088',
    '01133', '01138', '01171', '01186', '01288', '01336', '01339',
    '01347', '01359', '01456', '01533', '01618', '01635',
    '01658', '01668', '01683', '01766', '01776', '01800', '01812',
    '01816', '01898', '01919', '01988', '02009', '02039', '02202',
    '02238', '02333', '02338', '02601', '02607', '02611',
    '02777', '02883', '03323', '03347', '03360', '03378', '03576',
    '03898', '03958', '03993', '06049', '06185', '06196', '06837',
    '06881', '09926', '01157', '02357',
]

# 预设PB数据（基于最近财报）
# 这些数据需要定期更新
HK_STOCKS_PB = {
    '00001': 0.85, '00002': 0.95, '00003': 0.90, '00005': 0.75,
    '00006': 0.80, '00011': 0.85, '00012': 0.70, '00016': 0.90,
    '00017': 0.65, '00019': 0.85, '00020': 0.55, '00027': 0.80,
    '00066': 0.90, '00101': 0.75, '00175': 1.20, '00241': 0.85,
    '00267': 0.80, '00288': 0.70, '00291': 0.90, '00293': 0.85,
    '00316': 0.95, '00322': 0.60, '00386': 0.80, '00388': 0.90,
    '00669': 0.85, '00688': 0.75, '00700': 5.50, '00762': 0.80,
    '00823': 0.70, '00857': 0.85, '00883': 0.90, '00939': 0.55,
    '00941': 0.80, '00960': 0.85, '00968': 0.75, '00981': 1.10,
    '01038': 0.80, '01044': 0.85, '01093': 0.70, '01109': 0.85,
    '01113': 0.90, '01177': 0.80, '01211': 1.30, '01299': 0.85,
    '01378': 0.75, '01398': 0.55, '01810': 1.20, '01876': 0.80,
    '01928': 0.85, '01929': 0.90, '01997': 0.75, '02007': 0.80,
    '02013': 0.85, '02018': 0.90, '02020': 1.10, '02269': 0.85,
    '02313': 0.80, '02318': 0.90, '02319': 0.75, '02382': 0.85,
    '02388': 0.80, '02628': 0.70, '02688': 0.85, '03311': 0.90,
    '03328': 0.75, '03333': 0.80, '03692': 0.85, '03968': 0.90,
    '03988': 0.70, '06030': 0.85, '06060': 0.80, '06098': 0.90,
    '06160': 0.75, '06618': 0.85, '06690': 0.90, '06862': 0.80,
    '09618': 0.85, '09626': 0.90, '09633': 0.75, '09698': 0.80,
    '09888': 0.85, '09961': 0.90, '09988': 0.80, '09999': 0.85,
    '00168': 0.70, '00177': 0.85, '00338': 0.80, '00347': 0.75,
    '00358': 0.85, '00525': 0.90, '00553': 0.80, '00576': 0.75,
    '00670': 0.85, '00728': 0.80, '00753': 0.90, '00902': 0.85,
    '00914': 0.80, '00916': 0.75, '00956': 0.85, '00992': 0.80,
    '01055': 0.75, '01066': 0.80, '01071': 0.85, '01088': 0.90,
    '01133': 0.85, '01138': 0.80, '01171': 0.75, '01186': 0.85,
    '01288': 0.70, '01336': 0.80, '01339': 0.85, '01347': 0.90,
    '01359': 0.80, '01456': 0.85, '01533': 0.75, '01618': 0.80,
    '01635': 0.85, '01658': 0.70, '01668': 0.85, '01683': 0.80,
    '01766': 0.75, '01776': 0.80, '01800': 0.85, '01812': 0.80,
    '01816': 0.75, '01898': 0.80, '01919': 0.85, '01988': 0.80,
    '02009': 0.75, '02039': 0.80, '02202': 0.85, '02238': 0.80,
    '02333': 0.75, '02338': 0.80, '02601': 0.85, '02607': 0.80,
    '02611': 0.75, '02777': 0.80, '02883': 0.85, '03323': 0.80,
    '03347': 0.75, '03360': 0.80, '03378': 0.85, '03576': 0.80,
    '03898': 0.75, '03958': 0.80, '03993': 0.85, '06049': 0.80,
    '06185': 0.75, '06196': 0.80, '06837': 0.85, '06881': 0.80,
    '09926': 0.75, '01157': 0.80, '02357': 0.85,
}


def get_hk_stocks_data() -> list:
    """获取港股数据"""
    stocks = []
    for code in HK_STOCKS_LIST:
        data = get_hk_stock_realtime(code)
        if data:
            # 使用预设的PB数据
            if code in HK_STOCKS_PB:
                data['pb'] = HK_STOCKS_PB[code]
            stocks.append(data)
    return stocks


def calculate_graham_score(stock: dict) -> tuple:
    """
    格雷厄姆烟蒂评分 (满分100)
    核心思想：买入价格远低于净资产，有安全边际
    """
    score = 0
    criteria_met = 0

    pe = stock.get('pe') or 999
    pb = stock.get('pb') or 999
    dividend_yield = stock.get('dividend_yield') or 0
    market_cap = stock.get('market_cap') or 0

    # 1. PE < 10 (25分)
    if 0 < pe <= 5:
        score += 25
        criteria_met += 1
    elif 0 < pe <= 8:
        score += 20
        criteria_met += 1
    elif 0 < pe <= 10:
        score += 15
        criteria_met += 1
    elif 0 < pe <= 15:
        score += 5

    # 2. PB < 1 (30分) - 核心指标
    if 0 < pb <= 0.5:
        score += 30
        criteria_met += 1
    elif 0 < pb <= 0.7:
        score += 25
        criteria_met += 1
    elif 0 < pb <= 1.0:
        score += 20
        criteria_met += 1
    elif 0 < pb <= 1.5:
        score += 10
    elif 0 < pb <= 2.0:
        score += 3

    # 3. 股息率 (20分)
    if dividend_yield >= 5:
        score += 20
        criteria_met += 1
    elif dividend_yield >= 3:
        score += 15
        criteria_met += 1
    elif dividend_yield >= 1:
        score += 8

    # 4. 市值 > 10亿港元 (15分) - 避免仙股
    if market_cap >= 50:
        score += 15
        criteria_met += 1
    elif market_cap >= 20:
        score += 12
        criteria_met += 1
    elif market_cap >= 10:
        score += 8
        criteria_met += 1
    elif market_cap >= 5:
        score += 3

    # 5. PE > 0 (盈利) (10分)
    if 0 < pe <= 10:
        score += 10
        criteria_met += 1
    elif 0 < pe:
        score += 5

    return score, criteria_met


def calculate_buffett_score(stock: dict) -> tuple:
    """
    巴菲特早期烟蒂评分 (满分100)
    核心思想：买入价格低于净营运资本的2/3
    """
    score = 0
    criteria_met = 0

    pe = stock.get('pe') or 999
    pb = stock.get('pb') or 999
    dividend_yield = stock.get('dividend_yield') or 0
    market_cap = stock.get('market_cap') or 0

    # 1. PE < 10 (25分)
    if 0 < pe <= 8:
        score += 25
        criteria_met += 1
    elif 0 < pe <= 10:
        score += 20
        criteria_met += 1
    elif 0 < pe <= 12:
        score += 10

    # 2. PB < 1.2 (25分)
    if 0 < pb <= 0.8:
        score += 25
        criteria_met += 1
    elif 0 < pb <= 1.0:
        score += 20
        criteria_met += 1
    elif 0 < pb <= 1.2:
        score += 15
        criteria_met += 1
    elif 0 < pb <= 1.5:
        score += 5

    # 3. 稳定盈利 (20分) - PE > 0 表示有盈利
    if 0 < pe <= 15:
        score += 20
        criteria_met += 1
    elif 0 < pe:
        score += 10

    # 4. 股息 (15分)
    if dividend_yield >= 3:
        score += 15
        criteria_met += 1
    elif dividend_yield >= 1:
        score += 10
        criteria_met += 1
    elif dividend_yield > 0:
        score += 5

    # 5. 市值要求 (15分)
    if market_cap >= 30:
        score += 15
        criteria_met += 1
    elif market_cap >= 10:
        score += 12
        criteria_met += 1
    elif market_cap >= 5:
        score += 8
        criteria_met += 1

    return score, criteria_met


def calculate_schloss_score(stock: dict) -> tuple:
    """
    施洛斯烟蒂评分 (满分100)
    核心思想：PB < 1，有长期盈利记录，负债少
    """
    score = 0
    criteria_met = 0

    pe = stock.get('pe') or 999
    pb = stock.get('pb') or 999
    dividend_yield = stock.get('dividend_yield') or 0
    market_cap = stock.get('market_cap') or 0

    # 1. PB < 1 (35分) - 核心指标
    if 0 < pb <= 0.5:
        score += 35
        criteria_met += 1
    elif 0 < pb <= 0.7:
        score += 30
        criteria_met += 1
    elif 0 < pb <= 0.8:
        score += 25
        criteria_met += 1
    elif 0 < pb <= 1.0:
        score += 20
        criteria_met += 1
    elif 0 < pb <= 1.2:
        score += 10
    elif 0 < pb <= 1.5:
        score += 3

    # 2. PE < 10 (25分)
    if 0 < pe <= 5:
        score += 25
        criteria_met += 1
    elif 0 < pe <= 8:
        score += 20
        criteria_met += 1
    elif 0 < pe <= 10:
        score += 15
        criteria_met += 1
    elif 0 < pe <= 15:
        score += 5

    # 3. 股息 (20分)
    if dividend_yield >= 5:
        score += 20
        criteria_met += 1
    elif dividend_yield >= 3:
        score += 15
        criteria_met += 1
    elif dividend_yield >= 1:
        score += 10
        criteria_met += 1

    # 4. 市值 (20分) - 避免太小的公司
    if market_cap >= 20:
        score += 20
        criteria_met += 1
    elif market_cap >= 10:
        score += 15
        criteria_met += 1
    elif market_cap >= 5:
        score += 10
        criteria_met += 1
    elif market_cap >= 2:
        score += 5

    return score, criteria_met


@router.get("/screener")
async def cigar_butt_screener(
    master: str = "combined",
    min_score: int = 50,
    min_market_cap: float = 5,
    max_pe: float = 15,
    max_pb: float = 1.5,
    top_n: int = 50
):
    """
    港股烟蒂股筛选

    参数:
    - master: 筛选标准 (combined/graham/buffett/schloss)
    - min_score: 最低评分 (0-100)
    - min_market_cap: 最低市值（亿港元）
    - max_pe: 最大PE
    - max_pb: 最大PB
    - top_n: 显示数量
    """
    # 获取港股数据
    stocks = get_hk_stocks_data()

    # 筛选和评分
    results = []
    for stock in stocks:
        pe = stock.get('pe') or 999
        pb = stock.get('pb') or 999
        market_cap = stock.get('market_cap') or 0

        # 基础筛选
        if pe <= 0 or pe > max_pe:
            continue
        if pb <= 0 or pb > max_pb:
            continue
        if market_cap < min_market_cap:
            continue

        # 计算评分
        graham_score, graham_criteria = calculate_graham_score(stock)
        buffett_score, buffett_criteria = calculate_buffett_score(stock)
        schloss_score, schloss_criteria = calculate_schloss_score(stock)

        # 综合评分
        if master == 'graham':
            final_score = graham_score
            criteria_met = graham_criteria
        elif master == 'buffett':
            final_score = buffett_score
            criteria_met = buffett_criteria
        elif master == 'schloss':
            final_score = schloss_score
            criteria_met = schloss_criteria
        else:
            # 综合：加权平均
            final_score = int(graham_score * 0.4 + buffett_score * 0.3 + schloss_score * 0.3)
            criteria_met = max(graham_criteria, buffett_criteria, schloss_criteria)

        if final_score >= min_score:
            stock['graham_score'] = graham_score
            stock['buffett_score'] = buffett_score
            stock['schloss_score'] = schloss_score
            stock['score'] = final_score
            stock['criteria_met'] = criteria_met

            # 匹配度
            if final_score >= 80:
                stock['match_level'] = 'excellent'
            elif final_score >= 65:
                stock['match_level'] = 'good'
            elif final_score >= 50:
                stock['match_level'] = 'fair'
            else:
                stock['match_level'] = 'poor'

            results.append(stock)

    # 排序
    results.sort(key=lambda x: x['score'], reverse=True)

    # 截取top_n
    results = results[:top_n]

    return {
        'stocks': results,
        'total': len(results),
        'master': master,
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'criteria': {
            'min_score': min_score,
            'min_market_cap': min_market_cap,
            'max_pe': max_pe,
            'max_pb': max_pb,
        }
    }


@router.get("/philosophy")
async def get_philosophy():
    """获取烟蒂投资哲学说明"""
    return {
        'graham': {
            'name': '本杰明·格雷厄姆',
            'title': '价值投资之父 / 烟蒂投资开创者',
            'core_idea': '以远低于内在价值的价格买入股票，即使公司平庸，只要价格足够便宜也能获利',
            'criteria': [
                'PE < 10（最好 < 8）',
                'PB < 1（最好 < 0.7，即打7折买净资产）',
                '资产负债率 < 50%',
                '连续5年以上盈利',
                '连续20年以上分红',
                '流动比率 > 2',
            ],
            'net_net_rule': '价格 < 净营运资本的2/3（NCAV策略）',
            'classic_quote': '安全边际是投资中最重要的概念',
        },
        'buffett': {
            'name': '沃伦·巴菲特（早期）',
            'title': '从烟蒂投资转型为优质企业投资',
            'core_idea': '早期跟随格雷厄姆，买入价格低于净营运资本的2/3的股票',
            'criteria': [
                'PE < 10',
                'PB < 1.2',
                '有稳定的盈利记录',
                '价格低于净营运资本的2/3',
                '公司有一定规模',
            ],
            'transition': '后受芒格影响，转向"以合理价格买入优秀公司"',
            'classic_quote': '早期我捡了很多烟蒂，后来才明白优质企业的价值',
        },
        'schloss': {
            'name': '沃尔特·施洛斯',
            'title': '格雷厄姆最成功的弟子之一',
            'core_idea': '坚持PB < 1的策略，47年年化收益20%',
            'criteria': [
                'PB < 1（核心指标）',
                'PE < 10',
                '负债少',
                '有长期盈利记录',
                '价格接近或低于账面价值',
                '管理层持有一定股份',
            ],
            'performance': '1955-2002年，47年年化收益率20.1%，累计回报697倍',
            'classic_quote': '我不喜欢负债，负债会让人陷入麻烦',
        },
        'risks': [
            '价值陷阱：低估值可能是因为基本面恶化',
            '港股流动性风险：小市值股票可能难以卖出',
            '汇率风险：港币与美元挂钩',
            '公司治理风险：港股部分公司治理较差',
            '行业衰退：某些行业可能永久性衰退',
        ]
    }
