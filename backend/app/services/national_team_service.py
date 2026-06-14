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

# 股票行业分类映射（国家队常持仓标的）
STOCK_INDUSTRY_MAP = {
    # 银行
    '601398': '银行', '601288': '银行', '601988': '银行', '601939': '银行',
    '600036': '银行', '601166': '银行', '600016': '银行', '601818': '银行',
    '601328': '银行', '600000': '银行', '000001': '银行', '002142': '银行',
    '601998': '银行', '600015': '银行', '600919': '银行', '601009': '银行',
    # 保险
    '601318': '保险', '601601': '保险', '601628': '保险', '601319': '保险',
    '601336': '保险', '601330': '保险',
    # 券商
    '600030': '券商', '601211': '券商', '601688': '券商', '600999': '券商',
    '601377': '券商', '600958': '券商', '000776': '券商', '601881': '券商',
    # 白酒
    '600519': '白酒', '000858': '白酒', '002304': '白酒', '600809': '白酒',
    '000568': '白酒', '603369': '白酒', '000596': '白酒',
    # 医药
    '600276': '医药', '000538': '医药', '300760': '医药', '600196': '医药',
    '002007': '医药', '300015': '医药', '000963': '医药',
    # 家电
    '000333': '家电', '000651': '家电', '002032': '家电', '600690': '家电',
    # 新能源/汽车
    '300750': '新能源', '601012': '新能源', '002594': '新能源', '600438': '新能源',
    '002459': '新能源',
    # 石油石化
    '601857': '石油石化', '600028': '石油石化',
    # 电力/公用事业
    '600900': '电力', '600886': '电力', '601985': '电力', '003816': '电力',
    # 建筑/基建
    '601668': '建筑', '601390': '建筑', '601186': '建筑',
    # 消费/食品
    '600887': '消费', '603288': '消费', '601888': '消费', '600882': '消费',
    # 机械/制造
    '600031': '机械', '000157': '机械', '601100': '机械',
    # 科技/电子
    '002415': '科技', '000725': '科技', '603501': '科技', '002230': '科技',
    # 建材
    '600585': '建材', '000401': '建材',
    # 农业
    '002714': '农业', '600438': '农业',
    # 通信
    '600050': '通信', '601728': '通信',
    # 地产
    '001979': '地产', '600048': '地产', '000002': '地产',
    # 钢铁
    '600019': '钢铁', '000898': '钢铁',
    # 交通运输
    '601006': '交运', '600029': '交运', '601111': '交运',
}


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


def _get_recent_quarter_ends(count: int = 4) -> list:
    """获取最近N个已披露的季末日期列表（从新到旧）"""
    now = datetime.now()
    year = now.year
    month = now.month

    # 所有可能的季末日期
    all_quarters = []
    for y in range(year - 2, year + 1):
        for q in ['03-31', '06-30', '09-30', '12-31']:
            all_quarters.append(f"{y}-{q}")

    # 根据当前月份确定最新已披露季度
    latest = _get_latest_quarter_end()

    # 从latest往前取count个
    try:
        idx = all_quarters.index(latest)
        result = all_quarters[max(0, idx - count + 1):idx + 1]
        result.reverse()  # 从新到旧
        return result
    except ValueError:
        return [latest]


def _get_stock_5day_avg_turnover(code: str) -> float:
    """获取股票过去5个交易日平均成交额（元），用于计算真实量比"""
    try:
        prefix = 'sh' if code.startswith(('5', '6')) else 'sz'
        url = 'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData'
        params = {'symbol': f'{prefix}{code}', 'scale': '240', 'ma': 'no', 'datalen': 10}
        r = _session.get(url, params=params, timeout=8)
        data = r.json()
        if not data or len(data) < 2:
            return 0
        # 取最近5个交易日（不含今天最后一条，因为可能是盘中数据）
        recent = data[-6:-1] if len(data) >= 6 else data[:-1]
        if not recent:
            return 0
        avg_turnover = sum(float(d.get('volume', 0)) for d in recent) / len(recent)
        return avg_turnover
    except Exception as e:
        logger.warning(f"获取{code}历史成交额失败: {e}")
        return 0


def _find_etf_column(df, *keywords) -> str:
    """在DataFrame中查找包含关键词的列名，返回第一个匹配的列名"""
    for col in df.columns:
        col_str = str(col)
        for kw in keywords:
            if kw in col_str:
                return col
    return None


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
    首次加载约15秒，5分钟缓存内秒开
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

        # AKShare列名 - 使用关键词匹配，避免硬编码索引导致版本更新后崩溃
        code_col = _find_etf_column(df, '代码') or df.columns[0]
        name_col = _find_etf_column(df, '名称') or df.columns[1]
        price_col = _find_etf_column(df, '最新价') or df.columns[2]
        change_col = _find_etf_column(df, '涨跌幅') or df.columns[5]
        turnover_col = _find_etf_column(df, '成交额') or df.columns[8]
        super_inflow_col = _find_etf_column(df, '超大单净流入-净额', '超大单')
        big_inflow_col = _find_etf_column(df, '大单净流入-净额', '大单净流入')
        mid_inflow_col = _find_etf_column(df, '中单净流入-净额', '中单净流入')
        small_inflow_col = _find_etf_column(df, '小单净流入-净额', '小单净流入')

        # 检查资金流向列是否找到
        has_flow_cols = all([super_inflow_col, big_inflow_col, mid_inflow_col, small_inflow_col])
        if not has_flow_cols:
            logger.warning(f"ETF资金流向列匹配不完整: super={super_inflow_col}, big={big_inflow_col}, mid={mid_inflow_col}, small={small_inflow_col}")
            logger.warning(f"可用列: {list(df.columns)}")

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

            # 安全读取资金流向列（列可能不存在）
            super_inflow = safe_float_or_zero(row.get(super_inflow_col, 0)) if super_inflow_col else 0
            big_inflow = safe_float_or_zero(row.get(big_inflow_col, 0)) if big_inflow_col else 0
            mid_inflow = safe_float_or_zero(row.get(mid_inflow_col, 0)) if mid_inflow_col else 0
            small_inflow = safe_float_or_zero(row.get(small_inflow_col, 0)) if small_inflow_col else 0
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

            # 获取过去5个交易日平均成交额，计算真实量比
            avg_turnover = _get_stock_5day_avg_turnover(code)
            if avg_turnover <= 0:
                # 历史数据获取失败时跳过，不使用硬编码值
                continue
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


# ============================================================
# 新增功能：龙虎榜机构席位、大宗交易、ETF份额、股东人数、综合研判
# ============================================================

def get_dragon_tiger_board(days: int = 5) -> dict:
    """
    龙虎榜机构席位监控

    数据源：AKShare stock_lhb_jgmmtj_em（东方财富龙虎榜-机构买卖每日统计）
    重点筛选机构专用席位的大额交易，追踪机构资金方向
    """
    cache_key = f"dragon_tiger_{days}"
    cached = _get_cached(cache_key, ttl_seconds=1800)
    if cached:
        return cached

    try:
        import akshare as ak
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

        # 机构买卖每日统计
        df = ak.stock_lhb_jgmmtj_em(start_date=start_date, end_date=end_date)

        if df.empty:
            return {'records': [], 'summary': {}, 'update_time': datetime.now().isoformat()}

        records = []
        for _, row in df.iterrows():
            records.append({
                'code': str(row.get('代码', '')),
                'name': str(row.get('名称', '')),
                'close_price': safe_float_or_zero(row.get('收盘价')),
                'change_pct': safe_float_or_zero(row.get('涨跌幅')),
                'buy_inst_count': int(safe_float_or_zero(row.get('买方机构数'))),
                'sell_inst_count': int(safe_float_or_zero(row.get('卖方机构数'))),
                'inst_buy_amount': safe_float_or_zero(row.get('机构买入总额')),
                'inst_sell_amount': safe_float_or_zero(row.get('机构卖出总额')),
                'inst_net_amount': safe_float_or_zero(row.get('机构买入净额')),
                'market_turnover': safe_float_or_zero(row.get('市场总成交额')),
                'inst_net_ratio': safe_float_or_zero(row.get('机构净买额占总成交额比')),
                'turnover_rate': safe_float_or_zero(row.get('换手率')),
                'float_market_cap': safe_float_or_zero(row.get('流通市值')),
                'reason': str(row.get('上榜原因', '')),
                'date': str(row.get('上榜日期', '')),
            })

        # 汇总统计
        total_buy = sum(r['inst_buy_amount'] for r in records)
        total_sell = sum(r['inst_sell_amount'] for r in records)
        total_net = sum(r['inst_net_amount'] for r in records)
        net_buy_count = sum(1 for r in records if r['inst_net_amount'] > 0)
        net_sell_count = sum(1 for r in records if r['inst_net_amount'] < 0)

        # 按净买入排序
        records.sort(key=lambda x: x['inst_net_amount'], reverse=True)

        summary = {
            'total_buy': round(total_buy, 2),
            'total_sell': round(total_sell, 2),
            'total_net': round(total_net, 2),
            'net_buy_count': net_buy_count,
            'net_sell_count': net_sell_count,
            'total_records': len(records),
            'date_range': f'{start_date} ~ {end_date}',
        }

        result = {
            'records': records,
            'summary': summary,
            'update_time': datetime.now().isoformat(),
        }

        _set_cache(cache_key, result)
        return result

    except Exception as e:
        logger.error(f"获取龙虎榜数据失败: {e}")
        return {'records': [], 'summary': {}, 'update_time': datetime.now().isoformat(), 'error': str(e)}


def get_block_trades(days: int = 5) -> dict:
    """
    大宗交易机构监控

    数据源：AKShare stock_dzjy_mrmx（大宗交易每日明细）
    筛选买方或卖方为"机构专用"的交易
    """
    cache_key = f"block_trades_{days}"
    cached = _get_cached(cache_key, ttl_seconds=1800)
    if cached:
        return cached

    try:
        import akshare as ak
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

        # 大宗交易明细
        df = ak.stock_dzjy_mrmx(start_date=start_date, end_date=end_date)

        if df.empty:
            return {'records': [], 'summary': {}, 'update_time': datetime.now().isoformat()}

        records = []
        inst_records = []
        for _, row in df.iterrows():
            buyer = str(row.get('买方营业部', ''))
            seller = str(row.get('卖方营业部', ''))
            is_inst_buy = '机构专用' in buyer
            is_inst_sell = '机构专用' in seller

            record = {
                'code': str(row.get('证券代码', '')),
                'name': str(row.get('证券简称', '')),
                'trade_date': str(row.get('交易日期', '')),
                'price': safe_float_or_zero(row.get('成交价')),
                'volume': safe_float_or_zero(row.get('成交量')),
                'amount': safe_float_or_zero(row.get('成交额')),
                'buyer': buyer,
                'seller': seller,
                'is_inst_buy': is_inst_buy,
                'is_inst_sell': is_inst_sell,
                'inst_direction': '机构买入' if is_inst_buy else ('机构卖出' if is_inst_sell else '非机构'),
            }
            records.append(record)
            if is_inst_buy or is_inst_sell:
                inst_records.append(record)

        # 汇总
        inst_buy_amount = sum(r['amount'] for r in inst_records if r['is_inst_buy'])
        inst_sell_amount = sum(r['amount'] for r in inst_records if r['is_inst_sell'])

        records.sort(key=lambda x: x['amount'], reverse=True)
        inst_records.sort(key=lambda x: x['amount'], reverse=True)

        summary = {
            'total_trade_count': len(records),
            'inst_trade_count': len(inst_records),
            'inst_buy_amount': round(inst_buy_amount, 2),
            'inst_sell_amount': round(inst_sell_amount, 2),
            'inst_net_amount': round(inst_buy_amount - inst_sell_amount, 2),
            'date_range': f'{start_date} ~ {end_date}',
        }

        result = {
            'records': inst_records,  # 只返回机构相关交易
            'all_count': len(records),
            'summary': summary,
            'update_time': datetime.now().isoformat(),
        }

        _set_cache(cache_key, result)
        return result

    except Exception as e:
        logger.error(f"获取大宗交易数据失败: {e}")
        return {'records': [], 'summary': {}, 'update_time': datetime.now().isoformat(), 'error': str(e)}


def get_etf_share_changes() -> dict:
    """
    ETF份额变动追踪

    数据源：AKShare fund_etf_scale_sse（上交所ETF规模）+ fund_etf_scale_szse（深交所ETF规模）
    份额大幅增加通常意味着国家队等大资金申购入场
    """
    cache_key = "etf_share_changes"
    cached = _get_cached(cache_key, ttl_seconds=3600)
    if cached:
        return cached

    try:
        import akshare as ak
        today = datetime.now().strftime('%Y%m%d')
        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y%m%d')

        target_etfs = ['510050', '510300', '510500', '588000', '588080', '159919', '159915']

        # 获取最新规模数据
        latest_data = {}
        for date_str in [today, (datetime.now() - timedelta(days=1)).strftime('%Y%m%d'),
                         (datetime.now() - timedelta(days=2)).strftime('%Y%m%d')]:
            try:
                df_sse = ak.fund_etf_scale_sse(date=date_str)
                if not df_sse.empty:
                    for _, row in df_sse.iterrows():
                        code = str(row.get('基金代码', ''))
                        if code in target_etfs:
                            latest_data[code] = {
                                'name': str(row.get('基金简称', '')),
                                'date': str(row.get('统计日期', '')),
                                'shares': safe_float_or_zero(row.get('基金份额')),
                            }
                    if latest_data:
                        break
            except Exception:
                continue

        # 获取一周前数据做对比
        week_ago_data = {}
        for date_str in [week_ago, (datetime.now() - timedelta(days=8)).strftime('%Y%m%d'),
                         (datetime.now() - timedelta(days=9)).strftime('%Y%m%d')]:
            try:
                df_sse = ak.fund_etf_scale_sse(date=date_str)
                if not df_sse.empty:
                    for _, row in df_sse.iterrows():
                        code = str(row.get('基金代码', ''))
                        if code in target_etfs:
                            week_ago_data[code] = {
                                'shares': safe_float_or_zero(row.get('基金份额')),
                            }
                    if week_ago_data:
                        break
            except Exception:
                continue

        # 计算变动
        etf_changes = []
        for code in target_etfs:
            if code not in latest_data:
                continue
            latest = latest_data[code]
            prev_shares = week_ago_data.get(code, {}).get('shares', 0)
            change = latest['shares'] - prev_shares if prev_shares else 0
            change_pct = (change / prev_shares * 100) if prev_shares else 0

            etf_changes.append({
                'code': code,
                'name': latest['name'],
                'latest_date': latest['date'],
                'latest_shares': latest['shares'],
                'week_ago_shares': prev_shares,
                'share_change': change,
                'share_change_pct': round(change_pct, 2),
                'signal': '大幅申购' if change_pct > 5 else ('申购' if change_pct > 1 else ('赎回' if change_pct < -1 else '平稳')),
            })

        etf_changes.sort(key=lambda x: x['share_change_pct'], reverse=True)

        result = {
            'etfs': etf_changes,
            'update_time': datetime.now().isoformat(),
        }

        _set_cache(cache_key, result)
        return result

    except Exception as e:
        logger.error(f"获取ETF份额变动失败: {e}")
        return {'etfs': [], 'update_time': datetime.now().isoformat(), 'error': str(e)}


def get_shareholder_changes(stock_codes: list = None) -> dict:
    """
    股东人数变动监控

    数据源：AKShare stock_main_stock_holder（十大股东数据，含股东总数字段）
    股东人数大幅减少 = 筹码集中 = 机构可能在吸筹

    注意：stock_shareholder_change_ths 返回的是大股东增减持记录，不是股东人数变化。
    正确数据源是 stock_main_stock_holder，其 股东总数 字段才是真正的股东人数。
    """
    if not stock_codes:
        # 默认监控主要蓝筹股
        stock_codes = ['600519', '601318', '600036', '000858', '601398',
                       '601288', '601988', '601939', '600030', '300750']

    cache_key = f"shareholder_changes_{'_'.join(stock_codes[:5])}"
    cached = _get_cached(cache_key, ttl_seconds=7200)
    if cached:
        return cached

    try:
        import akshare as ak
        results = []

        for code in stock_codes:
            try:
                df = ak.stock_main_stock_holder(stock=code)
                if df.empty:
                    continue

                # 按截止日期排序，取有股东总数的记录
                df_sorted = df.sort_values('截至日期', ascending=False)
                valid_records = []
                seen_dates = set()
                for _, row in df_sorted.iterrows():
                    d = str(row.get('截至日期', ''))
                    sh_count = row.get('股东总数')
                    if d and d not in seen_dates and sh_count is not None and str(sh_count) != 'nan':
                        seen_dates.add(d)
                        avg_shares = row.get('平均持股数')
                        valid_records.append({
                            'date': d,
                            'shareholder_count': int(sh_count),
                            'avg_shares': safe_float_or_zero(avg_shares),
                        })
                        if len(valid_records) >= 5:
                            break

                if not valid_records:
                    continue

                latest = valid_records[0]
                prev = valid_records[1] if len(valid_records) > 1 else None

                # 计算变动
                count_change = 0
                count_change_pct = 0
                if prev and prev['shareholder_count'] > 0:
                    count_change = latest['shareholder_count'] - prev['shareholder_count']
                    count_change_pct = round(count_change / prev['shareholder_count'] * 100, 2)

                # 判断信号
                if count_change_pct < -5:
                    signal = '大幅集中'
                elif count_change_pct < -2:
                    signal = '集中'
                elif count_change_pct > 5:
                    signal = '大幅分散'
                elif count_change_pct > 2:
                    signal = '分散'
                else:
                    signal = '平稳'

                results.append({
                    'code': code,
                    'name': '',
                    'latest_date': latest['date'],
                    'shareholder_count': latest['shareholder_count'],
                    'avg_shares': latest['avg_shares'],
                    'prev_date': prev['date'] if prev else '',
                    'prev_shareholder_count': prev['shareholder_count'] if prev else 0,
                    'count_change': count_change,
                    'count_change_pct': count_change_pct,
                    'signal': signal,
                    'history': valid_records,
                })
            except Exception as e:
                logger.warning(f"获取{code}股东数据失败: {e}")
                continue

        # 按变动率排序（集中度增加的排前面）
        results.sort(key=lambda x: x['count_change_pct'])

        result = {
            'stocks': results,
            'total': len(results),
            'update_time': datetime.now().isoformat(),
        }

        _set_cache(cache_key, result)
        return result

    except Exception as e:
        logger.error(f"获取股东人数变动失败: {e}")
        return {'stocks': [], 'update_time': datetime.now().isoformat(), 'error': str(e)}


def get_northbound_flow() -> dict:
    """
    北向资金（沪深港通）监控

    数据源：AKShare stock_hsgt_fund_flow_summary_em（东方财富北向资金汇总）
    北向资金是外资进入A股的主要通道，是机构最关注的资金信号之一
    """
    cache_key = "northbound_flow"
    cached = _get_cached(cache_key, ttl_seconds=600)
    if cached:
        return cached

    try:
        import akshare as ak

        # 获取北向资金汇总（当日数据）
        df_summary = ak.stock_hsgt_fund_flow_summary_em()

        today_data = {}
        if not df_summary.empty:
            for _, row in df_summary.iterrows():
                direction = str(row.get('资金方向', ''))
                board = str(row.get('板块', ''))
                net_buy = safe_float_or_zero(row.get('成交净买额'))
                net_flow = safe_float_or_zero(row.get('资金净流入'))
                balance = safe_float_or_zero(row.get('当日资金余额'))
                trade_status = row.get('交易状态')

                if direction == '北向':
                    if '沪' in board:
                        today_data['sh_connect'] = {
                            'name': '沪股通',
                            'net_buy': net_buy,
                            'net_flow': net_flow,
                            'balance': balance,
                            'trade_status': trade_status,
                        }
                    elif '深' in board:
                        today_data['sz_connect'] = {
                            'name': '深股通',
                            'net_buy': net_buy,
                            'net_flow': net_flow,
                            'balance': balance,
                            'trade_status': trade_status,
                        }

        # 获取历史数据（近30天趋势）
        # 注意：东方财富从2024年8月后不再提供详细的北向资金净买入数据
        # 该数据仅供参考，实时数据需通过其他渠道获取
        df_hist = ak.stock_hsgt_hist_em(symbol='北向资金')
        hist_data = []
        data_available = False
        if not df_hist.empty:
            recent = df_hist.tail(60)
            for _, row in recent.iterrows():
                d = row.get('日期')
                net_buy = row.get('当日成交净买额')
                flow = row.get('当日资金流入')
                if d is not None:
                    nb_val = safe_float_or_zero(net_buy) if net_buy is not None and str(net_buy) != 'nan' else 0
                    flow_val = safe_float_or_zero(flow) if flow is not None and str(flow) != 'nan' else 0
                    if nb_val != 0 or flow_val != 0:
                        data_available = True
                    hist_data.append({
                        'date': str(d),
                        'net_buy': nb_val,
                        'net_flow': flow_val,
                    })
            # 只保留最近30条
            hist_data = hist_data[-30:]

        # 汇总
        sh_net = today_data.get('sh_connect', {}).get('net_buy', 0)
        sz_net = today_data.get('sz_connect', {}).get('net_buy', 0)
        total_net = sh_net + sz_net

        result = {
            'today': today_data,
            'total_net_buy': round(total_net, 2),
            'history': hist_data,
            'data_available': data_available,
            'data_note': '东方财富北向资金详细数据从2024年8月后不再更新，当日净买额仅供参考' if not data_available else '',
            'update_time': datetime.now().isoformat(),
            'data_source': '东方财富-沪深港通',
        }

        _set_cache(cache_key, result)
        return result

    except Exception as e:
        logger.error(f"获取北向资金数据失败: {e}")
        return {'today': {}, 'total_net_buy': 0, 'history': [],
                'update_time': datetime.now().isoformat(), 'error': str(e)}


def get_margin_trading() -> dict:
    """
    融资融券监控

    数据源：AKShare stock_margin_sse（上交所融资融券）+ stock_margin_szse（深交所）
    融资余额增加 = 杠杆资金看多；融券余额增加 = 看空力量增加
    """
    cache_key = "margin_trading"
    cached = _get_cached(cache_key, ttl_seconds=1800)
    if cached:
        return cached

    try:
        import akshare as ak
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=10)).strftime('%Y%m%d')

        # 上交所融资融券
        sh_data = []
        try:
            df_sh = ak.stock_margin_sse(start_date=start_date, end_date=end_date)
            if not df_sh.empty:
                for _, row in df_sh.iterrows():
                    sh_data.append({
                        'date': str(row.get('信用交易日期', '')),
                        'margin_balance': safe_float_or_zero(row.get('融资余额')),
                        'margin_buy': safe_float_or_zero(row.get('融资买入额')),
                        'short_balance_vol': safe_float_or_zero(row.get('融券余量')),
                        'short_balance_val': safe_float_or_zero(row.get('融券余量金额')),
                        'short_sell_vol': safe_float_or_zero(row.get('融券卖出量')),
                        'total_balance': safe_float_or_zero(row.get('融资融券余额')),
                    })
        except Exception as e:
            logger.warning(f"获取上交所融资融券失败: {e}")

        # 深交所融资融券（只获取最新一天，该函数不支持日期范围）
        sz_latest = None
        try:
            df_sz = ak.stock_margin_szse()
            if not df_sz.empty:
                row = df_sz.iloc[-1]
                sz_latest = {
                    'margin_balance': safe_float_or_zero(row.get('融资余额')) * 1e8,  # 原始单位亿元
                    'margin_buy': safe_float_or_zero(row.get('融资买入额')) * 1e8,
                    'short_balance_val': safe_float_or_zero(row.get('融券余额')) * 1e8,
                    'total_balance': safe_float_or_zero(row.get('融资融券余额')) * 1e8,
                }
        except Exception as e:
            logger.warning(f"获取深交所融资融券失败: {e}")

        # 计算趋势
        trend = 'neutral'
        margin_change = 0
        if len(sh_data) >= 2:
            latest = sh_data[-1]
            prev = sh_data[-2]
            margin_change = latest['margin_balance'] - prev['margin_balance']
            if margin_change > 1e9:
                trend = 'increasing'  # 融资余额增加，看多
            elif margin_change < -1e9:
                trend = 'decreasing'  # 融资余额减少，看空

        result = {
            'sh_data': sh_data,
            'latest_sh': sh_data[-1] if sh_data else None,
            'latest_sz': sz_latest,
            'trend': trend,
            'margin_change': round(margin_change, 2),
            'update_time': datetime.now().isoformat(),
            'data_source': '上交所+深交所融资融券',
        }

        _set_cache(cache_key, result)
        return result

    except Exception as e:
        logger.error(f"获取融资融券数据失败: {e}")
        return {'sh_data': [], 'latest_sz': None, 'trend': 'unknown',
                'update_time': datetime.now().isoformat(), 'error': str(e)}


# ============================================================
# 新增功能：持仓趋势、行业配置、市场走势相关性
# ============================================================

def get_holdings_trend(stock_codes: list = None) -> dict:
    """
    国家队持仓历史趋势（多季度对比）

    获取最近4个季度的持仓数据，展示各机构持仓变化趋势。
    用于判断国家队是在持续增持还是减持。
    """
    cache_key = "holdings_trend"
    cached = _get_cached(cache_key, ttl_seconds=7200)
    if cached:
        return cached

    try:
        quarters = _get_recent_quarter_ends(4)
        # 获取每个季度的持仓数据
        quarter_data = {}
        for q in quarters:
            q_result = get_shareholdings(q)
            quarter_data[q] = q_result.get('holdings', [])

        # 按 (股票代码, 机构类型) 聚合
        trend_map = {}
        for q in quarters:
            for h in quarter_data[q]:
                key = (h['code'], h['holder_type'])
                if key not in trend_map:
                    trend_map[key] = {
                        'code': h['code'],
                        'name': h['name'],
                        'holder_type': h['holder_type'],
                        'holder_name': h['holder_name'],
                        'quarters': {},
                    }
                trend_map[key]['quarters'][q] = {
                    'hold_num': h['hold_num'],
                    'hold_ratio': h['hold_ratio'],
                    'hold_market_value': h['hold_market_value'],
                    'hold_change': h['hold_change'],
                }

        # 计算趋势指标
        trends = []
        for key, data in trend_map.items():
            q_data = data['quarters']
            sorted_qs = sorted(q_data.keys())
            if len(sorted_qs) < 2:
                continue

            first = q_data[sorted_qs[0]]
            last = q_data[sorted_qs[-1]]
            total_change = last['hold_num'] - first['hold_num']
            total_change_pct = round(
                total_change / first['hold_num'] * 100, 2
            ) if first['hold_num'] > 0 else 0

            # 判断趋势方向
            values = [q_data[q]['hold_num'] for q in sorted_qs]
            if all(values[i] >= values[i-1] for i in range(1, len(values))):
                trend_dir = '持续增持'
            elif all(values[i] <= values[i-1] for i in range(1, len(values))):
                trend_dir = '持续减持'
            elif total_change > 0:
                trend_dir = '总体增持'
            elif total_change < 0:
                trend_dir = '总体减持'
            else:
                trend_dir = '持平'

            # 只保留有变化的记录
            if total_change != 0:
                trends.append({
                    **data,
                    'total_change': total_change,
                    'total_change_pct': total_change_pct,
                    'trend_direction': trend_dir,
                    'latest_value': last['hold_market_value'],
                })

        # 按变动幅度排序
        trends.sort(key=lambda x: abs(x['total_change_pct']), reverse=True)

        result = {
            'trends': trends,
            'quarters': quarters,
            'total_records': len(trends),
            'update_time': datetime.now().isoformat(),
        }

        _set_cache(cache_key, result)
        return result

    except Exception as e:
        logger.error(f"获取持仓趋势失败: {e}")
        return {'trends': [], 'quarters': [], 'update_time': datetime.now().isoformat(), 'error': str(e)}


def get_industry_allocation(end_date: str = None) -> dict:
    """
    国家队持仓行业配置分析

    将持仓按行业分类，分析国家队的行业偏好和配置权重。
    帮助判断国家队重点布局哪些行业。
    """
    cache_key = f"industry_allocation_{end_date or 'latest'}"
    cached = _get_cached(cache_key, ttl_seconds=7200)
    if cached:
        return cached

    try:
        holdings_data = get_shareholdings(end_date)
        holdings = holdings_data.get('holdings', [])
        report_end_date = holdings_data.get('end_date', '')

        if not holdings:
            return {'industries': {}, 'total_value': 0, 'end_date': report_end_date,
                    'update_time': datetime.now().isoformat()}

        # 按行业分组
        by_industry = {}
        for h in holdings:
            industry = STOCK_INDUSTRY_MAP.get(h['code'], '其他')
            if industry not in by_industry:
                by_industry[industry] = {
                    'total_value': 0,
                    'stock_count': 0,
                    'stocks': set(),
                    'holder_types': set(),
                    'top_stocks': [],
                }
            by_industry[industry]['total_value'] += h['hold_market_value']
            by_industry[industry]['stocks'].add(h['code'])
            by_industry[industry]['holder_types'].add(h['holder_type'])
            by_industry[industry]['top_stocks'].append({
                'code': h['code'],
                'name': h['name'],
                'value': h['hold_market_value'],
                'holder_type': h['holder_type'],
            })

        # 计算权重和格式化
        total_value = sum(v['total_value'] for v in by_industry.values())
        industries = {}
        for name, data in sorted(by_industry.items(), key=lambda x: x[1]['total_value'], reverse=True):
            # 每个行业取持仓市值Top5
            data['top_stocks'].sort(key=lambda x: x['value'], reverse=True)
            industries[name] = {
                'total_value': round(data['total_value'], 2),
                'weight': round(data['total_value'] / total_value * 100, 2) if total_value > 0 else 0,
                'stock_count': len(data['stocks']),
                'holder_types': sorted(data['holder_types']),
                'top_stocks': data['top_stocks'][:5],
            }

        result = {
            'industries': industries,
            'total_value': round(total_value, 2),
            'industry_count': len(industries),
            'end_date': report_end_date,
            'update_time': datetime.now().isoformat(),
        }

        _set_cache(cache_key, result)
        return result

    except Exception as e:
        logger.error(f"获取行业配置失败: {e}")
        return {'industries': {}, 'total_value': 0, 'update_time': datetime.now().isoformat(), 'error': str(e)}


def get_market_context() -> dict:
    """
    市场走势背景分析

    获取沪深300指数近期走势，与国家队信号结合分析。
    包括：指数趋势、估值水平、成交量变化。
    """
    cache_key = "market_context"
    cached = _get_cached(cache_key, ttl_seconds=1800)
    if cached:
        return cached

    try:
        import akshare as ak

        # 获取沪深300指数日线数据
        df = ak.stock_zh_index_daily(symbol='sh000300')
        if df.empty:
            return {'error': '无法获取沪深300数据', 'update_time': datetime.now().isoformat()}

        # 取最近60个交易日
        recent = df.tail(60)
        index_data = []
        for _, row in recent.iterrows():
            index_data.append({
                'date': str(row.get('date', '')),
                'close': safe_float_or_zero(row.get('close')),
                'volume': safe_float_or_zero(row.get('volume')),
            })

        # 计算趋势指标
        if len(index_data) >= 20:
            latest_close = index_data[-1]['close']
            ma5 = sum(d['close'] for d in index_data[-5:]) / 5
            ma20 = sum(d['close'] for d in index_data[-20:]) / 20
            ma60 = sum(d['close'] for d in index_data[-60:]) / 60 if len(index_data) >= 60 else ma20

            # 近20日涨跌幅
            change_20d = round((latest_close - index_data[-20]['close']) / index_data[-20]['close'] * 100, 2)
            # 近5日涨跌幅
            change_5d = round((latest_close - index_data[-5]['close']) / index_data[-5]['close'] * 100, 2)

            # 趋势判断
            if latest_close > ma5 > ma20:
                trend = '强势上涨'
            elif latest_close > ma20:
                trend = '震荡偏强'
            elif latest_close < ma5 < ma20:
                trend = '弱势下跌'
            elif latest_close < ma20:
                trend = '震荡偏弱'
            else:
                trend = '横盘整理'

            # 成交量趋势
            recent_vol = sum(d['volume'] for d in index_data[-5:]) / 5
            prev_vol = sum(d['volume'] for d in index_data[-10:-5]) / 5 if len(index_data) >= 10 else recent_vol
            vol_change = round((recent_vol - prev_vol) / prev_vol * 100, 2) if prev_vol > 0 else 0

            summary = {
                'latest_close': round(latest_close, 2),
                'ma5': round(ma5, 2),
                'ma20': round(ma20, 2),
                'ma60': round(ma60, 2),
                'change_5d': change_5d,
                'change_20d': change_20d,
                'trend': trend,
                'vol_change_pct': vol_change,
                'vol_trend': '放量' if vol_change > 20 else ('缩量' if vol_change < -20 else '平稳'),
            }
        else:
            summary = {}

        result = {
            'index_data': index_data[-30:],  # 返回最近30天
            'summary': summary,
            'index_name': '沪深300',
            'update_time': datetime.now().isoformat(),
        }

        _set_cache(cache_key, result)
        return result

    except Exception as e:
        logger.error(f"获取市场走势失败: {e}")
        return {'index_data': [], 'summary': {}, 'update_time': datetime.now().isoformat(), 'error': str(e)}


def get_comprehensive_assessment() -> dict:
    """
    综合研判评分系统

    将所有信号综合打分，给出国家队动向的综合研判：
    - 持仓变动（季报数据）
    - ETF资金流向
    - 龙虎榜机构方向
    - 大宗交易机构方向
    - ETF份额变动
    """
    cache_key = "comprehensive_assessment"
    cached = _get_cached(cache_key, ttl_seconds=1800)
    if cached:
        return cached

    signals = []
    total_score = 0

    # 1. ETF资金流向信号
    try:
        etf_flow = get_etf_fund_flow()
        total_inflow = etf_flow.get('total_main_inflow', 0)
        if total_inflow > 5e8:
            score = min(30, total_inflow / 5e8 * 10)
            signals.append({
                'name': 'ETF主力资金',
                'score': round(score, 1),
                'direction': '流入',
                'detail': f'主力净流入 {total_inflow/1e8:.2f}亿',
                'weight': '高',
            })
            total_score += score
        elif total_inflow < -5e8:
            score = max(-30, total_inflow / 5e8 * 10)
            signals.append({
                'name': 'ETF主力资金',
                'score': round(score, 1),
                'direction': '流出',
                'detail': f'主力净流出 {abs(total_inflow)/1e8:.2f}亿',
                'weight': '高',
            })
            total_score += score
        else:
            signals.append({
                'name': 'ETF主力资金',
                'score': 0,
                'direction': '中性',
                'detail': f'主力净流入 {total_inflow/1e8:.2f}亿',
                'weight': '高',
            })
    except Exception:
        signals.append({'name': 'ETF主力资金', 'score': 0, 'direction': '数据异常', 'detail': '', 'weight': '高'})

    # 2. 龙虎榜机构信号
    try:
        dt_data = get_dragon_tiger_board(days=3)
        dt_summary = dt_data.get('summary', {})
        dt_net = dt_summary.get('total_net', 0)
        if dt_net > 0:
            score = min(25, dt_net / 1e9 * 5)
            signals.append({
                'name': '龙虎榜机构',
                'score': round(score, 1),
                'direction': '净买入',
                'detail': f'机构净买入 {dt_net/1e8:.2f}亿，{dt_summary.get("net_buy_count", 0)}只净买入',
                'weight': '中',
            })
            total_score += score
        elif dt_net < 0:
            score = max(-25, dt_net / 1e9 * 5)
            signals.append({
                'name': '龙虎榜机构',
                'score': round(score, 1),
                'direction': '净卖出',
                'detail': f'机构净卖出 {abs(dt_net)/1e8:.2f}亿，{dt_summary.get("net_sell_count", 0)}只净卖出',
                'weight': '中',
            })
            total_score += score
        else:
            signals.append({'name': '龙虎榜机构', 'score': 0, 'direction': '中性', 'detail': '无数据', 'weight': '中'})
    except Exception:
        signals.append({'name': '龙虎榜机构', 'score': 0, 'direction': '数据异常', 'detail': '', 'weight': '中'})

    # 3. 大宗交易信号
    try:
        bt_data = get_block_trades(days=3)
        bt_summary = bt_data.get('summary', {})
        bt_net = bt_summary.get('inst_net_amount', 0)
        if bt_net > 0:
            score = min(20, bt_net / 5e8 * 5)
            signals.append({
                'name': '大宗交易机构',
                'score': round(score, 1),
                'direction': '净买入',
                'detail': f'机构大宗净买入 {bt_net/1e8:.2f}亿',
                'weight': '中',
            })
            total_score += score
        elif bt_net < 0:
            score = max(-20, bt_net / 5e8 * 5)
            signals.append({
                'name': '大宗交易机构',
                'score': round(score, 1),
                'direction': '净卖出',
                'detail': f'机构大宗净卖出 {abs(bt_net)/1e8:.2f}亿',
                'weight': '中',
            })
            total_score += score
        else:
            signals.append({'name': '大宗交易机构', 'score': 0, 'direction': '中性', 'detail': '无机构交易', 'weight': '中'})
    except Exception:
        signals.append({'name': '大宗交易机构', 'score': 0, 'direction': '数据异常', 'detail': '', 'weight': '中'})

    # 4. ETF份额变动信号
    try:
        etf_share = get_etf_share_changes()
        etfs = etf_share.get('etfs', [])
        if etfs:
            avg_change_pct = sum(e.get('share_change_pct', 0) for e in etfs) / len(etfs)
            if avg_change_pct > 2:
                score = min(25, avg_change_pct * 3)
                signals.append({
                    'name': 'ETF份额变动',
                    'score': round(score, 1),
                    'direction': '净申购',
                    'detail': f'近一周ETF份额平均变动 {avg_change_pct:.2f}%',
                    'weight': '高',
                })
                total_score += score
            elif avg_change_pct < -2:
                score = max(-25, avg_change_pct * 3)
                signals.append({
                    'name': 'ETF份额变动',
                    'score': round(score, 1),
                    'direction': '净赎回',
                    'detail': f'近一周ETF份额平均变动 {avg_change_pct:.2f}%',
                    'weight': '高',
                })
                total_score += score
            else:
                signals.append({
                    'name': 'ETF份额变动',
                    'score': 0,
                    'direction': '中性',
                    'detail': f'近一周ETF份额平均变动 {avg_change_pct:.2f}%',
                    'weight': '高',
                })
    except Exception:
        signals.append({'name': 'ETF份额变动', 'score': 0, 'direction': '数据异常', 'detail': '', 'weight': '高'})

    # 5. 北向资金信号
    try:
        nb_data = get_northbound_flow()
        nb_net = nb_data.get('total_net_buy', 0)
        if nb_net > 0:
            score = min(25, nb_net / 10 * 5)
            signals.append({
                'name': '北向资金',
                'score': round(score, 1),
                'direction': '净买入',
                'detail': f'北向资金净买入 {nb_net:.2f}亿',
                'weight': '高',
            })
            total_score += score
        elif nb_net < 0:
            score = max(-25, nb_net / 10 * 5)
            signals.append({
                'name': '北向资金',
                'score': round(score, 1),
                'direction': '净卖出',
                'detail': f'北向资金净卖出 {abs(nb_net):.2f}亿',
                'weight': '高',
            })
            total_score += score
        else:
            signals.append({'name': '北向资金', 'score': 0, 'direction': '中性', 'detail': '无数据或休市', 'weight': '高'})
    except Exception:
        signals.append({'name': '北向资金', 'score': 0, 'direction': '数据异常', 'detail': '', 'weight': '高'})

    # 6. 融资融券信号
    try:
        margin_data = get_margin_trading()
        margin_trend = margin_data.get('trend', 'neutral')
        margin_change = margin_data.get('margin_change', 0)
        if margin_trend == 'increasing':
            score = min(15, margin_change / 1e9 * 3)
            signals.append({
                'name': '融资融券',
                'score': round(score, 1),
                'direction': '融资增加',
                'detail': f'融资余额变动 {margin_change/1e8:.2f}亿，杠杆资金看多',
                'weight': '中',
            })
            total_score += score
        elif margin_trend == 'decreasing':
            score = max(-15, margin_change / 1e9 * 3)
            signals.append({
                'name': '融资融券',
                'score': round(score, 1),
                'direction': '融资减少',
                'detail': f'融资余额变动 {margin_change/1e8:.2f}亿，杠杆资金撤退',
                'weight': '中',
            })
            total_score += score
        else:
            signals.append({'name': '融资融券', 'score': 0, 'direction': '中性', 'detail': '融资余额变动不大', 'weight': '中'})
    except Exception:
        signals.append({'name': '融资融券', 'score': 0, 'direction': '数据异常', 'detail': '', 'weight': '中'})

    # 7. 市场走势背景信号
    try:
        market = get_market_context()
        m_summary = market.get('summary', {})
        m_trend = m_summary.get('trend', '')
        change_20d = m_summary.get('change_20d', 0)
        if m_trend in ('强势上涨', '震荡偏强'):
            # 市场偏强时，国家队入场意愿更强，信号加成
            score = min(10, change_20d / 2)
            signals.append({
                'name': '市场走势',
                'score': round(score, 1),
                'direction': m_trend,
                'detail': f'沪深300近20日{change_20d:+.2f}%，{m_trend}，市场环境利于入场',
                'weight': '低',
            })
            total_score += score
        elif m_trend in ('弱势下跌', '震荡偏弱'):
            # 市场偏弱时，国家队可能逆势增持（护盘）
            score = max(-10, change_20d / 4)  # 弱势时扣分较少，因为可能是护盘
            signals.append({
                'name': '市场走势',
                'score': round(score, 1),
                'direction': m_trend,
                'detail': f'沪深300近20日{change_20d:+.2f}%，{m_trend}，关注护盘可能',
                'weight': '低',
            })
            total_score += score
        else:
            signals.append({'name': '市场走势', 'score': 0, 'direction': '中性', 'detail': '市场横盘整理', 'weight': '低'})
    except Exception:
        signals.append({'name': '市场走势', 'score': 0, 'direction': '数据异常', 'detail': '', 'weight': '低'})

    # 综合评级
    total_score = round(total_score, 1)
    if total_score >= 50:
        assessment = '强烈看多'
        description = '多维信号共振，国家队大概率在积极入场'
    elif total_score >= 25:
        assessment = '偏多'
        description = '多数信号偏正面，国家队可能在逐步增持'
    elif total_score >= 10:
        assessment = '中性偏多'
        description = '部分信号偏正面，国家队动向不明确'
    elif total_score >= -10:
        assessment = '中性'
        description = '信号不一致或偏中性，无法判断方向'
    elif total_score >= -25:
        assessment = '中性偏空'
        description = '部分信号偏负面，需关注减持风险'
    elif total_score >= -50:
        assessment = '偏空'
        description = '多数信号偏负面，国家队可能在减持'
    else:
        assessment = '强烈看空'
        description = '多维信号均偏空，国家队大概率在减持'

    result = {
        'total_score': total_score,
        'assessment': assessment,
        'description': description,
        'signals': signals,
        'update_time': datetime.now().isoformat(),
    }

    _set_cache(cache_key, result)
    return result
