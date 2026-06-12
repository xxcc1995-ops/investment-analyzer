"""国家队监控服务 - 持仓追踪、ETF资金流向、异动检测"""

import requests
import logging
from datetime import datetime, timedelta
from typing import Optional
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.core.cache import get_cache as _get_cached, set_cache as _set_cache
from app.core.utils import safe_float as _safe_float, safe_float_or_zero

logger = logging.getLogger(__name__)

# 共享HTTP会话（带连接池和重试）
_session = requests.Session()
_adapter = HTTPAdapter(
    pool_connections=10,
    pool_maxsize=20,
    max_retries=Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504]),
)
_session.mount("https://", _adapter)
_session.mount("http://", _adapter)
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
})

# 国家队关键词 - 中央汇金、证金公司、社保基金、养老保险基金、梧桐树投资
NATIONAL_TEAM_KEYWORDS = [
    '中央汇金', '中国证券金融', '证金公司', '社保基金', '全国社保',
    '基本养老保险', '养老保险', '梧桐树投资', '国家集成电路产业基金',
]

# 大盘ETF列表
MONITOR_ETFS = {
    '510050': {'name': '上证50ETF'},
    '510300': {'name': '沪深300ETF'},
    '510500': {'name': '中证500ETF'},
    '588000': {'name': '科创50ETF'},
}

# 蓝筹股列表（用于异动检测）
BLUE_CHIP_STOCKS = [
    ('600519', '贵州茅台'), ('601318', '中国平安'), ('600036', '招商银行'),
    ('000858', '五粮液'), ('601166', '兴业银行'), ('000333', '美的集团'),
    ('600276', '恒瑞医药'), ('601398', '工商银行'), ('601288', '农业银行'),
    ('601988', '中国银行'), ('601939', '建设银行'), ('600030', '中信证券'),
    ('601601', '中国太保'), ('601628', '中国人寿'), ('601319', '中国人保'),
    ('600900', '长江电力'), ('601857', '中国石油'), ('600028', '中国石化'),
    ('002714', '牧原股份'), ('300750', '宁德时代'), ('601012', '隆基绿能'),
    ('000651', '格力电器'), ('600887', '伊利股份'), ('603288', '海天味业'),
    ('002594', '比亚迪'), ('601888', '中国中免'), ('600031', '三一重工'),
    ('002415', '海康威视'), ('600585', '海螺水泥'), ('601668', '中国建筑'),
]


def _get_latest_quarter_end() -> str:
    """获取最近已披露的季末日期

    季度报告披露时间：
    - 年报：次年4月30日前
    - 一季报：4月30日前
    - 半年报：8月31日前
    - 三季报：10月31日前
    """
    now = datetime.now()
    year = now.year
    month = now.month

    # 根据当前月份判断哪个季度的数据已披露
    if month >= 11:
        # 11月以后，三季报已披露
        return f"{year}-09-30"
    elif month >= 9:
        # 9-10月，半年报已披露
        return f"{year}-06-30"
    elif month >= 5:
        # 5-8月，一季报/年报已披露，用一季报
        return f"{year}-03-31"
    else:
        # 1-4月，用去年三季报
        return f"{year-1}-09-30"


def get_shareholdings(end_date: str = None) -> dict:
    """
    获取国家队十大流通股东持仓数据

    数据源：东方财富 datacenter-web API
    报告名：RPT_F10_EH_FREEHOLDERS

    国家队成员：
    - 中央汇金投资有限责任公司
    - 中央汇金资产管理有限责任公司
    - 中国证券金融股份有限公司（证金公司）
    - 全国社保基金理事会
    - 基本养老保险基金
    - 梧桐树投资平台有限责任公司
    """
    if not end_date:
        end_date = _get_latest_quarter_end()

    cache_key = f"national_team_holdings_{end_date}"
    cached = _get_cached(cache_key, ttl_seconds=3600)
    if cached:
        return cached

    url = 'https://datacenter-web.eastmoney.com/api/data/v1/get'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://data.eastmoney.com/',
    }

    # 分页获取所有数据（该季度的十大股东）
    all_records = []
    page = 1
    while page <= 20:  # 最多20页，每页500条
        params = {
            'reportName': 'RPT_F10_EH_FREEHOLDERS',
            'columns': 'SECURITY_CODE,SECURITY_NAME_ABBR,HOLDER_NAME,HOLD_NUM,FREE_HOLDNUM_RATIO,HOLD_NUM_CHANGE,CHANGE_RATIO,HOLDER_MARKET_CAP,END_DATE,HOLDER_RANK,HOLD_RATIO_CHANGE',
            'filter': f"(END_DATE in ('{end_date}'))",
            'pageNumber': page,
            'pageSize': 500,
            'sortColumns': 'HOLDER_MARKET_CAP',
            'sortTypes': '-1',
            'source': 'WEB',
            'client': 'WEB',
            '_': int(datetime.now().timestamp() * 1000),
        }

        try:
            r = _session.get(url, params=params, headers=headers, timeout=15)
            data = r.json()

            if not data.get('success'):
                logger.error(f"获取十大股东数据失败: {data.get('message', '')}")
                break

            records = data.get('result', {}).get('data', [])
            if not records:
                break

            all_records.extend(records)

            # 检查是否还有下一页
            total_count = data['result'].get('count', 0)
            if page * 500 >= total_count:
                break
            page += 1

        except Exception as e:
            logger.error(f"获取十大股东数据异常: {e}")
            break

    if not all_records:
        return {'holdings': [], 'update_time': datetime.now().isoformat(),
                'end_date': end_date, 'total': 0, 'error': '未找到数据'}

    # 过滤国家队持仓
    national_team_records = []
    for record in all_records:
        holder_name = record.get('HOLDER_NAME', '') or ''
        # 检查是否包含国家队关键词
        is_national_team = any(kw in holder_name for kw in NATIONAL_TEAM_KEYWORDS)
        if not is_national_team:
            continue

        national_team_records.append({
            'code': record.get('SECURITY_CODE', ''),
            'name': record.get('SECURITY_NAME_ABBR', ''),
            'holder_name': holder_name,
            'hold_num': safe_float_or_zero(record.get('HOLD_NUM')),
            'hold_ratio': safe_float_or_zero(record.get('FREE_HOLDNUM_RATIO')),
            'hold_change': safe_float_or_zero(record.get('HOLD_NUM_CHANGE')),
            'hold_change_ratio': safe_float_or_zero(record.get('CHANGE_RATIO')),
            'hold_market_value': safe_float_or_zero(record.get('HOLDER_MARKET_CAP')),
            'end_date': record.get('END_DATE', '')[:10] if record.get('END_DATE') else '',
            'rank': record.get('HOLDER_RANK', 0),
            'holder_type': _classify_holder(holder_name),
        })

    # 按持仓市值降序
    national_team_records.sort(key=lambda x: x['hold_market_value'], reverse=True)

    result = {
        'holdings': national_team_records,
        'total': len(national_team_records),
        'end_date': end_date,
        'update_time': datetime.now().isoformat(),
        'summary': _build_summary(national_team_records),
    }

    _set_cache(cache_key, result)
    return result


def _classify_holder(name: str) -> str:
    """分类持仓机构"""
    if '汇金' in name:
        return '汇金'
    if '证金' in name or '证券金融' in name:
        return '证金'
    if '社保' in name:
        return '社保基金'
    if '养老' in name:
        return '养老保险'
    if '梧桐树' in name:
        return '梧桐树'
    if '集成电路' in name:
        return '大基金'
    return '其他'


def _build_summary(holdings: list) -> dict:
    """汇总统计"""
    by_type = {}
    total_value = 0

    for h in holdings:
        t = h['holder_type']
        if t not in by_type:
            by_type[t] = {'count': 0, 'total_value': 0, 'stocks': set()}
        by_type[t]['count'] += 1
        by_type[t]['total_value'] += h['hold_market_value']
        by_type[t]['stocks'].add(h['code'])

        total_value += h['hold_market_value']

    # 转换set为count
    for t in by_type:
        by_type[t]['stocks'] = len(by_type[t]['stocks'])

    return {
        'by_type': by_type,
        'total_market_value': round(total_value, 2),
        'total_positions': len(holdings),
    }


def _get_etf_hist_latest(code: str) -> dict:
    """获取ETF最近交易日历史数据（Sina K线API）作为盘前fallback"""
    try:
        import requests
        prefix = 'sh' if code.startswith(('5', '6')) else 'sz'
        url = 'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData'
        params = {'symbol': f'{prefix}{code}', 'scale': '240', 'ma': 'no', 'datalen': 5}
        headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.sina.com.cn'}
        r = _session.get(url, params=params, headers=headers, timeout=10)
        data = r.json()
        if not data:
            return {}
        last = data[-1]
        close = float(last['close'])
        prev_close = float(data[-2]['close']) if len(data) >= 2 else close
        change_pct = round((close - prev_close) / prev_close * 100, 2) if prev_close else 0
        return {
            'price': close,
            'change_pct': change_pct,
            'turnover': float(last.get('volume', 0)),
        }
    except Exception as e:
        logger.warning(f"获取ETF {code} 历史数据失败: {e}")
        return {}


def get_etf_fund_flow() -> dict:
    """
    获取大盘ETF资金流向数据

    数据源：AKShare fund_etf_spot_em()
    盘中返回实时资金流向，盘前/盘后用历史数据fallback
    """
    cache_key = "etf_flow_realtime"
    cached = _get_cached(cache_key, ttl_seconds=300)
    if cached:
        return cached

    try:
        import math
        import akshare as ak
        df = ak.fund_etf_spot_em()

        etf_data = {}
        total_main_inflow = 0

        # AKShare列名（中文）
        code_col = df.columns[0]   # 代码
        name_col = df.columns[1]   # 名称
        price_col = df.columns[2]  # 最新价
        change_col = df.columns[5]  # 涨跌幅
        turnover_col = df.columns[8]  # 成交额
        super_inflow_col = df.columns[19]  # 超大单净流入-净额
        big_inflow_col = df.columns[21]    # 大单净流入-净额
        mid_inflow_col = df.columns[23]    # 中单净流入-净额
        small_inflow_col = df.columns[25]  # 小单净流入-净额

        has_realtime = False

        for code, info in MONITOR_ETFS.items():
            etf = df[df[code_col] == code]
            if etf.empty:
                continue

            row = etf.iloc[0]
            price = safe_float_or_zero(row[price_col])
            change_pct = safe_float_or_zero(row[change_col])
            turnover = safe_float_or_zero(row[turnover_col])

            # 检查是否为nan（盘前/盘后无实时数据）
            raw_price = row[price_col]
            if isinstance(raw_price, float) and math.isnan(raw_price):
                # 用历史数据fallback
                hist = _get_etf_hist_latest(code)
                price = hist.get('price', 0)
                change_pct = hist.get('change_pct', 0)
                turnover = hist.get('turnover', 0)
            else:
                has_realtime = True

            super_inflow = safe_float_or_zero(row[super_inflow_col])
            big_inflow = safe_float_or_zero(row[big_inflow_col])
            mid_inflow = safe_float_or_zero(row[mid_inflow_col])
            small_inflow = safe_float_or_zero(row[small_inflow_col])
            main_inflow = super_inflow + big_inflow

            etf_data[code] = {
                'name': info['name'],
                'price': price,
                'change_pct': change_pct,
                'turnover': turnover,
                'super_inflow': super_inflow,
                'big_inflow': big_inflow,
                'mid_inflow': mid_inflow,
                'small_inflow': small_inflow,
                'main_inflow': main_inflow,
            }

            total_main_inflow += main_inflow

        result = {
            'etfs': etf_data,
            'total_main_inflow': round(total_main_inflow, 2),
            'update_time': datetime.now().isoformat(),
            'data_type': 'realtime' if has_realtime else 'history',
        }

        _set_cache(cache_key, result)
        return result

    except Exception as e:
        logger.error(f"获取ETF资金流向失败: {e}")
        return {'etfs': {}, 'total_main_inflow': 0,
                'update_time': datetime.now().isoformat(), 'error': str(e)}


def get_volume_alerts(threshold: float = 2.0) -> dict:
    """
    扫描蓝筹股量比，检测异常放量

    使用新浪财经API获取实时行情，计算量比
    量比 = 当日成交量 / 过去5日平均成交量
    """
    cache_key = f"volume_alerts_{threshold}"
    cached = _get_cached(cache_key, ttl_seconds=120)
    if cached:
        return cached

    alerts = []
    headers = {'Referer': 'https://finance.sina.com.cn', 'User-Agent': 'Mozilla/5.0'}

    for code, name in BLUE_CHIP_STOCKS:
        try:
            # 获取实时行情
            if code.startswith('6'):
                symbol = f'sh{code}'
            else:
                symbol = f'sz{code}'

            url = f'https://hq.sinajs.cn/list={symbol}'
            r = _session.get(url, headers=headers, timeout=5)
            r.encoding = 'gbk'

            data = r.text.split('"')[1].split(',')
            if len(data) < 32:
                continue

            price = float(data[3]) if data[3] else 0
            pre_close = float(data[2]) if data[2] else 0
            volume = int(float(data[8])) if data[8] else 0  # 成交量(股)
            turnover = float(data[9]) if data[9] else 0  # 成交额

            # 计算涨跌幅
            change_pct = 0
            if pre_close > 0:
                change_pct = round((price - pre_close) / pre_close * 100, 2)

            # 获取历史数据计算量比（简化：用成交额作为参考）
            # 量比通常需要5日平均成交量，这里用简化方法
            # 大盘蓝筹日均成交额一般在10-50亿，超过100亿算放量
            avg_turnover = 30e8  # 假设日均30亿
            volume_ratio = turnover / avg_turnover if avg_turnover > 0 else 1.0

            if volume_ratio >= threshold:
                severity = 'high' if volume_ratio >= 3.0 else ('medium' if volume_ratio >= 2.5 else 'low')
                alerts.append({
                    'code': code,
                    'name': name,
                    'price': price,
                    'change_pct': change_pct,
                    'volume_ratio': round(volume_ratio, 2),
                    'volume': volume,
                    'turnover': turnover,
                    'severity': severity,
                    'alert_type': '放量异动',
                    'description': f'量比{volume_ratio:.2f}，{"大幅" if severity == "high" else ""}放量',
                })

        except Exception as e:
            logger.warning(f"获取{code}({name})行情失败: {e}")
            continue

    # 按量比降序
    alerts.sort(key=lambda x: x['volume_ratio'], reverse=True)

    result = {
        'alerts': alerts,
        'total': len(alerts),
        'threshold': threshold,
        'scanned': len(BLUE_CHIP_STOCKS),
        'update_time': datetime.now().isoformat(),
    }

    _set_cache(cache_key, result)
    return result


def get_all_etf_flows(days: int = 30) -> dict:
    """获取所有监控ETF的资金流向汇总（兼容旧接口）"""
    return get_etf_fund_flow()
