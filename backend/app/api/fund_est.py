"""LOF基金EST净值估算 - 基于Palmmicro的技术方案"""

from fastapi import APIRouter, HTTPException
from datetime import datetime
from typing import Optional
import requests
import re
import json
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


def get_sina_realtime(symbols: list) -> dict:
    """批量获取新浪财经实时数据"""
    try:
        url = f"https://hq.sinajs.cn/list={','.join(symbols)}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://finance.sina.com.cn/',
        }
        r = requests.get(url, headers=headers, timeout=10)
        r.encoding = 'gbk'

        result = {}
        for line in r.text.strip().split('\n'):
            if '="' not in line:
                continue
            # 解析 var hq_str_sz161130="..."
            match = re.match(r'var hq_str_(\w+)="(.*)";', line)
            if match:
                symbol = match.group(1)
                data = match.group(2)
                if data:
                    result[symbol] = data.split(',')

        return result
    except Exception as e:
        logger.warning(f"获取新浪数据失败: {e}")
        return {}


def get_fund_nav_from_eastmoney(fund_code: str) -> dict:
    """从东方财富获取基金净值，优先使用最新日期的数据"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://fund.eastmoney.com/',
    }

    result1 = {}
    result2 = {}

    # 方法1：东方财富基金估值API
    try:
        url = f"https://fundgz.1234567.com.cn/js/{fund_code}.js"
        r = requests.get(url, headers=headers, timeout=10)
        match = re.search(r'jsonpgz\((.*)\)', r.text)
        if match:
            data = json.loads(match.group(1))
            nav = float(data.get('dwjz', 0))
            if nav > 0:
                result1 = {
                    'fund_code': data.get('fundcode'),
                    'name': data.get('name'),
                    'nav_date': data.get('jzrq'),
                    'nav': nav,
                    'est_nav': float(data.get('gsz', 0)),
                    'est_change': data.get('gszzl', '0'),
                    'est_time': data.get('gztime', ''),
                }
    except Exception as e:
        logger.debug(f"获取基金估值API数据失败 {fund_code}: {e}")

    # 方法2：东方财富历史净值API（数据更新更及时）
    try:
        url2 = f"https://fund.eastmoney.com/pingzhongdata/{fund_code}.js"
        r2 = requests.get(url2, headers=headers, timeout=10)
        m = re.search(r'Data_netWorthTrend\s*=\s*(\[.*?\]);', r2.text)
        if m:
            from datetime import datetime
            data = json.loads(m.group(1))
            if data:
                last = data[-1]
                nav_date = datetime.fromtimestamp(last['x'] / 1000).strftime('%Y-%m-%d')
                result2 = {
                    'fund_code': fund_code,
                    'name': result1.get('name', ''),
                    'nav_date': nav_date,
                    'nav': last['y'],
                    'est_nav': result1.get('est_nav', 0),
                    'est_change': result1.get('est_change', '0'),
                    'est_time': result1.get('est_time', ''),
                }
    except Exception as e:
        logger.warning(f"获取基金净值失败 {fund_code}: {e}")

    # 比较两个数据源的日期，返回更新的那个
    if result1 and result2:
        if result2['nav_date'] > result1['nav_date']:
            return result2
        return result1
    return result1 or result2 or {}


def get_usdcny_rate() -> float:
    """获取美元人民币中间价"""
    try:
        # 中国外汇交易中心接口
        url = "https://www.chinamoney.com.cn/r/cms/www/chinamoney/data/fx/ccpr.json"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()

        # 查找USD/CNY中间价
        for record in data.get('records', []):
            if record.get('ccyPair') == 'USD/CNY':
                return float(record.get('values', [{}])[0].get('midPrice', 0))

        # 备用：从新浪获取
        sina_data = get_sina_realtime(['fx_susdcny'])
        if 'fx_susdcny' in sina_data:
            return float(sina_data['fx_susdcny'][1])

        return 7.25  # 默认值
    except Exception as e:
        logger.warning(f"获取美元人民币汇率失败，使用默认值: {e}")
        return 7.25


# LOF基金配置：基金代码 -> 底层资产代码、仓位比例、校准值
# 校准值 = 基金官方净值 / (底层资产价格 × 汇率 × 仓位比例)
# 港股基金：校准值 = 基金官方净值 / (指数价格 × 港币汇率 × 仓位比例)
# 校准值基于2026-06-04/05的官方净值计算
# 底层资产说明：gb_xxx = 美股ETF（美元），hf_xxx = 期货（点数），rt_hkxxx = 港股指数（点数）
LOF_FUND_CONFIG = {
    # === 美股QDII LOF ===
    'SZ161130': {'name': '纳斯达克100LOF', 'underlying': 'gb_qqq', 'position': 0.95, 'calibration': 0.001012},
    'SZ161125': {'name': '标普500LOF', 'underlying': 'gb_spy', 'position': 0.95, 'calibration': 0.000660},
    'SZ162415': {'name': '美国消费LOF', 'underlying': 'gb_xly', 'position': 0.95, 'calibration': 0.003913},
    'SZ161126': {'name': '标普医疗保健LOF', 'underlying': 'gb_xlv', 'position': 0.95, 'calibration': 0.001888},
    'SZ161128': {'name': '标普信息科技LOF', 'underlying': 'gb_xlk', 'position': 0.95, 'calibration': 0.005944},
    'SZ161127': {'name': '标普生物科技LOF', 'underlying': 'gb_xbi', 'position': 0.95, 'calibration': 0.002163},
    'SZ162411': {'name': '华宝油气LOF', 'underlying': 'gb_xop', 'position': 0.95, 'calibration': 0.000846},
    'SZ160416': {'name': '石油基金LOF', 'underlying': 'gb_uso', 'position': 0.95, 'calibration': 0.002474},
    'SZ162719': {'name': '石油LOF', 'underlying': 'gb_uso', 'position': 0.95, 'calibration': 0.003201},
    'SZ164906': {'name': '中概互联网LOF', 'underlying': 'gb_kweb', 'position': 0.95, 'calibration': 0.005742},
    'SH501300': {'name': '美元债LOF', 'underlying': 'gb_agg', 'position': 0.95, 'calibration': 0.001492},
    'SZ160140': {'name': '美国REIT精选LOF', 'underlying': 'gb_vnq', 'position': 0.95, 'calibration': 0.002249},
    'SZ164824': {'name': '印度基金LOF', 'underlying': 'gb_inda', 'position': 0.95, 'calibration': 0.004203},
    'SZ163208': {'name': '全球油气能源LOF', 'underlying': 'gb_xle', 'position': 0.95, 'calibration': 0.003575},
    'SH501018': {'name': '南方原油LOF', 'underlying': 'gb_uso', 'position': 0.95, 'calibration': 0.002159},
    'SZ160723': {'name': '嘉实原油LOF', 'underlying': 'gb_uso', 'position': 0.95, 'calibration': 0.002458},
    'SZ161129': {'name': '原油LOF易方达', 'underlying': 'gb_uso', 'position': 0.95, 'calibration': 0.002060},
    'SZ160216': {'name': '国泰商品LOF', 'underlying': 'gb_gsg', 'position': 0.95, 'calibration': 0.003553},
    'SZ161815': {'name': '抗通胀LOF', 'underlying': 'gb_tip', 'position': 0.95, 'calibration': 0.001585},
    'SZ160719': {'name': '嘉实黄金LOF', 'underlying': 'gb_gld', 'position': 0.95, 'calibration': 0.000787},
    'SZ161116': {'name': '黄金主题LOF', 'underlying': 'gb_gld', 'position': 0.95, 'calibration': 0.000654},
    'SZ164701': {'name': '黄金LOF', 'underlying': 'gb_gld', 'position': 0.95, 'calibration': 0.000690},
    'SZ165513': {'name': '中信保诚商品LOF', 'underlying': 'gb_djp', 'position': 0.95, 'calibration': 0.003499},
    'SH501225': {'name': '全球芯片LOF', 'underlying': 'gb_soxx', 'position': 0.95, 'calibration': 0.000969},
    'SH501312': {'name': '海外科技LOF', 'underlying': 'gb_arkk', 'position': 0.95, 'calibration': 0.005036},
    'SZ160644': {'name': '港美互联网LOF', 'underlying': 'gb_kweb', 'position': 0.95, 'calibration': 0.012235},
    'SZ161226': {'name': '国投白银LOF', 'underlying': 'gb_slv', 'position': 0.95, 'calibration': 0.005081},
    # === 港股QDII LOF ===
    'SH501025': {'name': '香港银行LOF', 'underlying': 'rt_hkHSCEI', 'position': 0.95, 'calibration': 0.000245},
    'SZ161124': {'name': '港股小盘LOF', 'underlying': 'rt_hkHSCCI', 'position': 0.95, 'calibration': 0.000265},
    'SZ160717': {'name': 'H股LOF', 'underlying': 'rt_hkHSCEI', 'position': 0.95, 'calibration': 0.000101},
    'SZ161831': {'name': '恒生国企LOF', 'underlying': 'rt_hkHSCEI', 'position': 0.95, 'calibration': 0.000102},
    'SH501302': {'name': '恒生指数基金LOF', 'underlying': 'rt_hkHSI', 'position': 0.95, 'calibration': 0.000054},
    'SZ160924': {'name': '恒生指数LOF', 'underlying': 'rt_hkHSI', 'position': 0.95, 'calibration': 0.000047},
    'SZ164705': {'name': '恒生LOF', 'underlying': 'rt_hkHSI', 'position': 0.95, 'calibration': 0.000053},
}


# ========== 持仓组合跟踪 ==========

# 支持持仓跟踪的基金列表
SUPPORTED_HOLDINGS_FUNDS = {
    'SH501312': {'name': '海外科技LOF', 'currency': 'USD', 'fallback': True},
}

# 备用持仓数据（当东方财富API数据不足时使用）
# 数据来源：基金季报PDF（efinance + PyMuPDF自动解析）
# 最新数据：2026年一季报（截至2026-03-31）
# 总覆盖：89.86%净值资产
FUND_HOLDINGS_FALLBACK = {
    'SH501312': {
        'report_date': '2026-Q1 (截至2026-03-31)',
        'source': '基金季报PDF - 前十大基金投资明细',
        'holdings': [
            {'code': 'gb_arkk', 'name': 'ARK Innovation ETF', 'ticker': 'ARKK', 'weight': 0.1874},
            {'code': 'gb_arkg', 'name': 'ARK Genomic Revolution ETF', 'ticker': 'ARKG', 'weight': 0.1535},
            {'code': 'gb_arkq', 'name': 'ARK Autonomous Tech & Robotics ETF', 'ticker': 'ARKQ', 'weight': 0.1159},
            {'code': 'gb_soxx', 'name': 'iShares Semiconductor ETF', 'ticker': 'SOXX', 'weight': 0.0951},
            {'code': 'gb_aiq', 'name': 'Global X AI & Technology ETF', 'ticker': 'AIQ', 'weight': 0.0785},
            {'code': 'gb_qqq', 'name': 'Invesco QQQ Trust (纳斯达克100)', 'ticker': 'QQQ', 'weight': 0.0745},
            {'code': 'gb_botz', 'name': 'Global X Robotics & AI ETF', 'ticker': 'BOTZ', 'weight': 0.0744},
            {'code': 'gb_xlk', 'name': 'Technology Select Sector SPDR ETF', 'ticker': 'XLK', 'weight': 0.0644},
            {'code': 'gb_smh', 'name': 'VanEck Semiconductor ETF', 'ticker': 'SMH', 'weight': 0.0429},
            {'code': 'gb_fint', 'name': 'Global X FinTech ETF', 'ticker': 'FINX', 'weight': 0.0120},
        ]
    }
}


def _eastmoney_market_to_sina(code: str, name: str) -> Optional[str]:
    """将东方财富的股票代码转换为Sina API的symbol"""
    if not code:
        return None
    code = code.strip()

    # 美股: 105.NVDA -> gb_nvda
    if code.startswith('105.'):
        ticker = code.split('.')[1].lower()
        return f'gb_{ticker}'

    # 港股: 116.00700 -> rt_hk00700
    if code.startswith('116.'):
        ticker = code.split('.')[1]
        return f'rt_hk{ticker}'

    # A股上海: 1.600519 -> sh600519
    if code.startswith('1.'):
        return f'sh{code.split(".")[1]}'

    # A股深圳: 0.000001 -> sz000001
    if code.startswith('0.'):
        return f'sz{code.split(".")[1]}'

    # 纯美股ticker（无前缀）
    if re.match(r'^[A-Z]+$', code):
        return f'gb_{code.lower()}'

    return None


def fetch_fund_holdings_from_eastmoney(fund_code: str) -> list:
    """从东方财富获取基金十大重仓股"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://fund.eastmoney.com/',
    }

    try:
        url = f"https://fundf10.eastmoney.com/FundArchivesDatas.aspx?type=jjcc&code={fund_code}&topline=10&year=&month=&rt=0.{int(datetime.now().timestamp())}"
        r = requests.get(url, headers=headers, timeout=10)
        r.encoding = 'utf-8'
        text = r.text

        # 解析JSONP: var apidata={ content:"...",arryear:[...],curyear:... };
        match = re.search(r'content:"(.*?)"(?:,|})', text, re.DOTALL)
        if not match:
            return []

        html = match.group(1)
        if not html or len(html) < 50:
            return []

        # 提取报告日期
        date_match = re.search(r'截止至：<font[^>]*>([^<]+)</font>', html)
        report_date = date_match.group(1) if date_match else ''

        # 从表格中提取持仓数据
        holdings = []
        # 匹配每一行: <td>序号</td><td class='toc'><a href='...' >CODE</a></td><td class='toc'...>NAME</td>...<td class='toc'>占比%</td>
        rows = re.findall(
            r"<tr><td>(\d+)</td>"
            r"<td class='toc'><a[^>]*>([^<]+)</a></td>"
            r"<td class='toc'[^>]*><a[^>]*>([^<]+)</a></td>"
            r".*?"
            r"<td class='toc'>([\d.]+)%</td>",
            html, re.DOTALL
        )

        for row in rows:
            seq, raw_code, name, pct = row
            sina_code = _eastmoney_market_to_sina(raw_code, name)
            if sina_code:
                holdings.append({
                    'code': sina_code,
                    'name': name.strip(),
                    'ticker': raw_code.strip(),
                    'weight': float(pct) / 100,
                    'source': 'eastmoney',
                })

        return holdings

    except Exception as e:
        logger.warning(f"从东方财富获取基金持仓失败 {fund_code}: {e}")
        return []


def fetch_fund_holdings(fund_code: str) -> dict:
    """获取基金持仓数据（东方财富优先，不足时用备用数据）"""
    fund_code = fund_code.upper()
    if not fund_code.startswith('SH') and not fund_code.startswith('SZ'):
        if fund_code.startswith('5'):
            fund_code = f'SH{fund_code}'
        else:
            fund_code = f'SZ{fund_code}'

    if fund_code not in SUPPORTED_HOLDINGS_FUNDS:
        return {'error': f'不支持持仓跟踪的基金: {fund_code}'}

    fund_info = SUPPORTED_HOLDINGS_FUNDS[fund_code]

    # 尝试从东方财富获取
    eastmoney_holdings = fetch_fund_holdings_from_eastmoney(fund_code[2:])  # 去掉SH/SZ前缀

    # 如果东方财富数据足够（>=5只），直接使用
    if len(eastmoney_holdings) >= 5:
        # 计算总权重
        total_weight = sum(h['weight'] for h in eastmoney_holdings)
        return {
            'fund_code': fund_code,
            'fund_name': fund_info['name'],
            'currency': fund_info['currency'],
            'report_date': eastmoney_holdings[0].get('report_date', ''),
            'source': 'eastmoney',
            'total_weight': round(total_weight, 4),
            'holdings': eastmoney_holdings,
        }

    # 否则使用备用数据
    fallback = FUND_HOLDINGS_FALLBACK.get(fund_code)
    if fallback:
        return {
            'fund_code': fund_code,
            'fund_name': fund_info['name'],
            'currency': fund_info['currency'],
            'report_date': fallback['report_date'],
            'source': fallback['source'],
            'total_weight': round(sum(h['weight'] for h in fallback['holdings']), 4),
            'holdings': fallback['holdings'],
        }

    # 两者都没有
    return {
        'fund_code': fund_code,
        'fund_name': fund_info['name'],
        'currency': fund_info['currency'],
        'report_date': '',
        'source': 'none',
        'total_weight': 0,
        'holdings': eastmoney_holdings,  # 可能为空或很少
    }


@router.get("/holdings-list")
def get_holdings_list():
    """返回支持持仓跟踪的基金列表"""
    funds = []
    for code, info in SUPPORTED_HOLDINGS_FUNDS.items():
        funds.append({
            'fund_code': code,
            'fund_name': info['name'],
            'currency': info['currency'],
        })
    return {'funds': funds, 'total': len(funds)}


@router.get("/holdings/{fund_code}")
def get_fund_holdings(fund_code: str):
    """获取基金持仓组合的实时跟踪数据"""

    holdings_data = fetch_fund_holdings(fund_code)
    if 'error' in holdings_data:
        raise HTTPException(status_code=404, detail=holdings_data['error'])

    holdings = holdings_data.get('holdings', [])
    if not holdings:
        return {
            **holdings_data,
            'weighted_change': 0,
            'fund_price': 0,
            'fund_change_pct': 0,
            'premium_est': 0,
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'usdcny_rate': 0,
        }

    # 批量获取所有持仓的实时价格
    all_symbols = list(set(h['code'] for h in holdings))
    realtime_data = get_sina_realtime(all_symbols)

    # 获取基金自身价格
    fund_code_upper = holdings_data['fund_code']
    fund_symbol = fund_code_upper.lower()
    fund_data = get_sina_realtime([fund_symbol])
    fund_info = fund_data.get(fund_symbol, [])

    fund_price = 0
    fund_change_pct = 0
    if len(fund_info) >= 33:
        fund_price = float(fund_info[3]) if fund_info[3] else 0
        fund_change_pct = float(fund_info[32]) if fund_info[32] else 0

    # 获取汇率
    usdcny_rate = get_usdcny_rate()

    # 计算每只持仓的实时数据
    weighted_change = 0
    holdings_result = []

    for h in holdings:
        code = h['code']
        info = realtime_data.get(code, [])
        price = 0
        change_pct = 0
        prev_close = 0

        if code.startswith('gb_'):
            # 美股ETF/股票: fields[1]=当前价, fields[2]=涨跌幅(%)
            if len(info) >= 3:
                price = float(info[1]) if info[1] else 0
                change_pct = float(info[2]) if info[2] else 0
                prev_close = float(info[26]) if len(info) > 26 and info[26] else 0
        elif code.startswith('hf_'):
            # 期货
            if len(info) >= 8:
                price = float(info[0]) if info[0] else 0
                prev_close = float(info[7]) if info[7] else 0
                if prev_close > 0:
                    change_pct = (price - prev_close) / prev_close * 100
        elif code.startswith('rt_hk'):
            # 港股指数
            if len(info) >= 7:
                price = float(info[6]) if info[6] else 0
        elif code.startswith('sh') or code.startswith('sz'):
            # A股
            if len(info) >= 4:
                price = float(info[3]) if info[3] else 0
                prev_close = float(info[2]) if info[2] else 0
                if prev_close > 0:
                    change_pct = (price - prev_close) / prev_close * 100

        weighted_contribution = change_pct * h['weight']
        weighted_change += weighted_contribution

        holdings_result.append({
            'code': code,
            'name': h['name'],
            'ticker': h.get('ticker', ''),
            'weight': h['weight'],
            'price': round(price, 2),
            'prev_close': round(prev_close, 2),
            'change_pct': round(change_pct, 2),
            'weighted_contribution': round(weighted_contribution, 4),
        })

    # 按权重降序排列
    holdings_result.sort(key=lambda x: x['weight'], reverse=True)

    # 获取基金官方净值（T-1日）
    fund_nav_code = fund_code_upper[2:]  # 去掉SH/SZ前缀
    nav_info = get_fund_nav_from_eastmoney(fund_nav_code)
    official_nav = nav_info.get('nav', 0)
    official_nav_date = nav_info.get('nav_date', '')
    est_nav_from_api = nav_info.get('est_nav', 0)
    est_change = nav_info.get('est_change', '0')

    # EST净值 = 官方净值 × (1 + 组合加权涨跌幅 / 100)
    # 逻辑：官方净值是上一个交易日的准确值，加上今天底层持仓的涨跌变化，得到实时估算净值
    est_nav = 0
    premium = 0
    if official_nav > 0:
        est_nav = official_nav * (1 + weighted_change / 100)
        if fund_price > 0:
            premium = (fund_price - est_nav) / est_nav * 100

    return {
        **holdings_data,
        'holdings': holdings_result,
        'weighted_change': round(weighted_change, 2),
        'fund_price': fund_price,
        'fund_change_pct': fund_change_pct,
        'est_nav': round(est_nav, 4),
        'est_nav_from_api': round(est_nav_from_api, 4),
        'est_change': est_change,
        'official_nav': round(official_nav, 4),
        'official_nav_date': official_nav_date,
        'premium': round(premium, 2),
        'usdcny_rate': usdcny_rate,
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }


@router.get("/est-list")
def get_fund_est_list():
    """获取所有LOF基金的EST净值估算列表（并行优化版）"""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import time as _time

    start_time = _time.time()

    # 获取所有底层资产的实时价格
    underlying_symbols = set()
    for config in LOF_FUND_CONFIG.values():
        underlying_symbols.add(config['underlying'])
        if 'underlying_alt' in config:
            underlying_symbols.add(config['underlying_alt'])

    # 获取基金实时价格
    fund_symbols = [s.lower() for s in LOF_FUND_CONFIG.keys()]
    fund_data = get_sina_realtime(fund_symbols)

    # 获取底层资产价格
    underlying_data = get_sina_realtime(list(underlying_symbols))

    # 获取美元人民币中间价
    usdcny_rate = get_usdcny_rate()

    sina_time = _time.time() - start_time

    # === 并行获取所有基金净值（核心优化：70个串行请求 -> 并行） ===
    nav_fetch_start = _time.time()
    nav_cache = {}  # fund_code -> nav_info

    # 收集需要获取净值的基金代码
    fund_nav_codes = {}
    for fund_code in LOF_FUND_CONFIG.keys():
        fund_nav_code = fund_code[2:]  # 去掉SH/SZ前缀
        fund_nav_codes[fund_code] = fund_nav_code

    def _fetch_nav(fund_code_and_nav_code):
        fund_code, nav_code = fund_code_and_nav_code
        try:
            return fund_code, get_fund_nav_from_eastmoney(nav_code)
        except Exception as e:
            logger.warning(f"获取基金净值失败 {fund_code}: {e}")
            return fund_code, {}

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(_fetch_nav, (fc, nc)): fc
            for fc, nc in fund_nav_codes.items()
        }
        for future in as_completed(futures):
            try:
                fund_code, nav_info = future.result()
                nav_cache[fund_code] = nav_info
            except Exception as e:
                fc = futures[future]
                logger.error(f"获取基金净值异常 {fc}: {e}")
                nav_cache[fc] = {}

    nav_time = _time.time() - nav_fetch_start
    logger.info(f"并行获取{len(fund_nav_codes)}只基金净值耗时: {nav_time:.1f}s (新浪行情: {sina_time:.1f}s)")

    # === 计算所有基金的EST净值 ===
    results = []

    for fund_code, config in LOF_FUND_CONFIG.items():
        try:
            # 获取基金实时价格
            fund_info = fund_data.get(fund_code.lower(), [])
            if len(fund_info) < 10:
                continue

            fund_price = float(fund_info[3]) if fund_info[3] else 0
            fund_change_pct = float(fund_info[32]) if fund_info[32] else 0

            if fund_price <= 0:
                continue

            # 获取底层资产价格
            underlying_code = config['underlying']
            underlying_info = underlying_data.get(underlying_code, [])

            if not underlying_info:
                # 尝试备用底层资产
                if 'underlying_alt' in config:
                    underlying_code = config['underlying_alt']
                    underlying_info = underlying_data.get(underlying_code, [])

            if not underlying_info:
                continue

            # 解析底层资产价格
            if underlying_code.startswith('gb_'):
                underlying_price = float(underlying_info[1]) if underlying_info[1] else 0
            elif underlying_code.startswith('hf_'):
                underlying_price = float(underlying_info[0]) if underlying_info[0] else 0
            elif underlying_code.startswith('rt_hk'):
                underlying_price = float(underlying_info[6]) if underlying_info[6] else 0
            else:
                underlying_price = 0

            if underlying_price <= 0:
                continue

            # 从缓存获取基金净值（已并行预取）
            nav_info = nav_cache.get(fund_code, {})

            # 计算EST净值
            position = config['position']
            calibration = config['calibration']

            if underlying_code.startswith('gb_') or underlying_code.startswith('hf_'):
                est_nav = underlying_price * usdcny_rate * position * calibration
            else:
                hkd_to_cny = 0.9
                est_nav = underlying_price * hkd_to_cny * position * calibration

            premium = (fund_price - est_nav) / est_nav * 100 if est_nav > 0 else 0

            results.append({
                'fund_code': fund_code,
                'fund_name': config['name'],
                'fund_price': fund_price,
                'fund_change_pct': fund_change_pct,
                'underlying_code': underlying_code,
                'underlying_price': underlying_price,
                'est_nav': round(est_nav, 4),
                'premium': round(premium, 2),
                'official_nav': nav_info.get('nav', 0),
                'official_nav_date': nav_info.get('nav_date', ''),
                'position': position,
                'usdcny_rate': usdcny_rate,
                'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            })

        except Exception as e:
            logger.error(f"处理基金 {fund_code} 失败: {e}")
            continue

    results.sort(key=lambda x: x['premium'], reverse=True)

    total_time = _time.time() - start_time
    logger.info(f"EST列表总耗时: {total_time:.1f}s (新浪{sina_time:.1f}s + 净值{nav_time:.1f}s)")

    return {
        'funds': results,
        'total': len(results),
        'usdcny_rate': usdcny_rate,
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }


@router.get("/est/{fund_code}")
def get_fund_est(fund_code: str):
    """获取单只基金的EST净值估算"""

    # 输入校验：基金代码应为6位数字（可能带SH/SZ前缀）
    clean_code = fund_code.upper().replace('SH', '').replace('SZ', '')
    if not re.match(r'^\d{6}$', clean_code):
        raise HTTPException(status_code=400, detail=f"无效的基金代码格式: {fund_code}，应为6位数字")

    # 标准化基金代码
    fund_code = fund_code.upper()
    if not fund_code.startswith('SH') and not fund_code.startswith('SZ'):
        # 尝试自动判断
        if fund_code.startswith('5'):
            fund_code = f'SH{fund_code}'
        else:
            fund_code = f'SZ{fund_code}'

    if fund_code not in LOF_FUND_CONFIG:
        raise HTTPException(status_code=404, detail=f"不支持的基金代码: {fund_code}，请检查是否为LOF基金")

    config = LOF_FUND_CONFIG[fund_code]

    # 获取基金实时价格
    fund_data = get_sina_realtime([fund_code.lower()])
    fund_info = fund_data.get(fund_code.lower(), [])

    if len(fund_info) < 10:
        raise HTTPException(status_code=503, detail="获取基金实时价格失败，请稍后重试")

    fund_price = float(fund_info[3]) if fund_info[3] else 0
    fund_change_pct = float(fund_info[32]) if fund_info[32] else 0

    # 获取底层资产价格
    underlying_code = config['underlying']
    underlying_data = get_sina_realtime([underlying_code])
    underlying_info = underlying_data.get(underlying_code, [])

    if not underlying_info and 'underlying_alt' in config:
        underlying_code = config['underlying_alt']
        underlying_data = get_sina_realtime([underlying_code])
        underlying_info = underlying_data.get(underlying_code, [])

    # 解析底层资产价格
    if underlying_code.startswith('gb_'):
        underlying_price = float(underlying_info[1]) if underlying_info[1] else 0
    elif underlying_code.startswith('hf_'):
        underlying_price = float(underlying_info[0]) if underlying_info[0] else 0
    elif underlying_code.startswith('rt_hk'):
        underlying_price = float(underlying_info[6]) if underlying_info[6] else 0
    else:
        underlying_price = 0

    # 获取美元人民币中间价
    usdcny_rate = get_usdcny_rate()

    # 计算EST净值
    position = config['position']
    calibration = config['calibration']

    if underlying_code.startswith('gb_') or underlying_code.startswith('hf_'):
        est_nav = underlying_price * usdcny_rate * position * calibration
    else:
        # 港股资产（港币兑人民币汇率约为0.9）
        hkd_to_cny = 0.9
        est_nav = underlying_price * hkd_to_cny * position * calibration

    # 计算溢价率
    premium = (fund_price - est_nav) / est_nav * 100 if est_nav > 0 else 0

    # 获取基金净值（T-1日）
    fund_nav_code = fund_code[2:]
    nav_info = get_fund_nav_from_eastmoney(fund_nav_code)

    return {
        'fund_code': fund_code,
        'fund_name': config['name'],
        'fund_price': fund_price,
        'fund_change_pct': fund_change_pct,
        'underlying_code': underlying_code,
        'underlying_price': underlying_price,
        'est_nav': round(est_nav, 4),
        'premium': round(premium, 2),
        'official_nav': nav_info.get('nav', 0),
        'official_nav_date': nav_info.get('nav_date', ''),
        'position': position,
        'usdcny_rate': usdcny_rate,
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
