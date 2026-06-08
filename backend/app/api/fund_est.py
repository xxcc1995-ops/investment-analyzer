"""LOF基金EST净值估算 - 基于Palmmicro的技术方案"""

from fastapi import APIRouter
from datetime import datetime
import requests
import re
import json

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
        print(f"获取新浪数据失败: {e}")
        return {}


def get_fund_nav_from_eastmoney(fund_code: str) -> dict:
    """从东方财富获取基金净值（T-1日）"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://fund.eastmoney.com/',
    }

    # 方法1：东方财富基金估值API
    try:
        url = f"https://fundgz.1234567.com.cn/js/{fund_code}.js"
        r = requests.get(url, headers=headers, timeout=10)
        match = re.search(r'jsonpgz\((.*)\)', r.text)
        if match:
            data = json.loads(match.group(1))
            nav = float(data.get('dwjz', 0))
            if nav > 0:
                return {
                    'fund_code': data.get('fundcode'),
                    'name': data.get('name'),
                    'nav_date': data.get('jzrq'),
                    'nav': nav,
                    'est_nav': float(data.get('gsz', 0)),
                    'est_change': data.get('gszzl', '0'),
                    'est_time': data.get('gztime', ''),
                }
    except:
        pass

    # 方法2：东方财富历史净值API（适用于所有基金，包括5开头的基金）
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
                return {
                    'fund_code': fund_code,
                    'name': '',
                    'nav_date': nav_date,
                    'nav': last['y'],
                    'est_nav': 0,
                    'est_change': '0',
                    'est_time': '',
                }
    except Exception as e:
        print(f"获取基金净值失败 {fund_code}: {e}")

    return {}


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
    except:
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


@router.get("/est-list")
def get_fund_est_list():
    """获取所有LOF基金的EST净值估算列表"""

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

    results = []

    for fund_code, config in LOF_FUND_CONFIG.items():
        try:
            # 获取基金实时价格
            fund_info = fund_data.get(fund_code.lower(), [])
            if len(fund_info) < 10:
                continue

            fund_price = float(fund_info[3]) if fund_info[3] else 0
            fund_change_pct = float(fund_info[32]) if fund_info[32] else 0
            fund_name = fund_info[1]

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
                # 美股ETF
                underlying_price = float(underlying_info[1]) if underlying_info[1] else 0
            elif underlying_code.startswith('hf_'):
                # 期货
                underlying_price = float(underlying_info[0]) if underlying_info[0] else 0
            elif underlying_code.startswith('rt_hk'):
                # 港股指数
                underlying_price = float(underlying_info[6]) if underlying_info[6] else 0
            else:
                underlying_price = 0

            if underlying_price <= 0:
                continue

            # 获取基金净值（T-1日）
            fund_nav_code = fund_code[2:]  # 去掉SH/SZ前缀
            nav_info = get_fund_nav_from_eastmoney(fund_nav_code)

            # 计算EST净值
            position = config['position']
            calibration = config['calibration']

            # 对于美股QDII，使用美元人民币中间价
            if underlying_code.startswith('gb_') or underlying_code.startswith('hf_'):
                est_nav = underlying_price * usdcny_rate * position * calibration
            else:
                # 港股资产（港币兑人民币汇率约为0.9）
                hkd_to_cny = 0.9
                est_nav = underlying_price * hkd_to_cny * position * calibration

            # 计算溢价率
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
            print(f"处理基金 {fund_code} 失败: {e}")
            continue

    # 按溢价率排序
    results.sort(key=lambda x: x['premium'], reverse=True)

    return {
        'funds': results,
        'total': len(results),
        'usdcny_rate': usdcny_rate,
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }


@router.get("/est/{fund_code}")
def get_fund_est(fund_code: str):
    """获取单只基金的EST净值估算"""

    # 标准化基金代码
    fund_code = fund_code.upper()
    if not fund_code.startswith('SH') and not fund_code.startswith('SZ'):
        # 尝试自动判断
        if fund_code.startswith('5'):
            fund_code = f'SH{fund_code}'
        else:
            fund_code = f'SZ{fund_code}'

    if fund_code not in LOF_FUND_CONFIG:
        return {'error': f'不支持的基金代码: {fund_code}'}

    config = LOF_FUND_CONFIG[fund_code]

    # 获取基金实时价格
    fund_data = get_sina_realtime([fund_code.lower()])
    fund_info = fund_data.get(fund_code.lower(), [])

    if len(fund_info) < 10:
        return {'error': '获取基金价格失败'}

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
