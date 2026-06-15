"""
真实数据回测引擎

使用东方财富API获取真实历史数据，运行价值投资策略回测。
这是验证策略有效性的最终测试。
"""

import httpx
import json
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "backtest_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# A股核心股票池（30只覆盖各行业的蓝筹+成长股）
STOCK_UNIVERSE = {
    # 银行
    '601398': {'name': '工商银行', 'sector': '银行', 'market': '1'},
    '601939': {'name': '建设银行', 'sector': '银行', 'market': '1'},
    '600036': {'name': '招商银行', 'sector': '银行', 'market': '1'},
    # 保险
    '601318': {'name': '中国平安', 'sector': '保险', 'market': '1'},
    # 白酒
    '600519': {'name': '贵州茅台', 'sector': '白酒', 'market': '1'},
    '000858': {'name': '五粮液', 'sector': '白酒', 'market': '0'},
    '000568': {'name': '泸州老窖', 'sector': '白酒', 'market': '0'},
    '002304': {'name': '洋河股份', 'sector': '白酒', 'market': '0'},
    # 家电
    '000333': {'name': '美的集团', 'sector': '家电', 'market': '0'},
    '000651': {'name': '格力电器', 'sector': '家电', 'market': '0'},
    '600690': {'name': '海尔智家', 'sector': '家电', 'market': '1'},
    # 医药
    '603288': {'name': '海天味业', 'sector': '调味品', 'market': '1'},
    # 新能源
    '300750': {'name': '宁德时代', 'sector': '新能源', 'market': '0'},
    '002594': {'name': '比亚迪', 'sector': '新能源车', 'market': '0'},
    # 科技
    '002415': {'name': '海康威视', 'sector': '安防', 'market': '0'},
    # 化工
    '600309': {'name': '万华化学', 'sector': '化工', 'market': '1'},
    # 电力
    '600900': {'name': '长江电力', 'sector': '电力', 'market': '1'},
    # 煤炭
    '601088': {'name': '中国神华', 'sector': '煤炭', 'market': '1'},
    # 建材
    '600585': {'name': '海螺水泥', 'sector': '建材', 'market': '1'},
    # 机械
    '600031': {'name': '三一重工', 'sector': '机械', 'market': '1'},
    '000338': {'name': '潍柴动力', 'sector': '机械', 'market': '0'},
    # 地产
    '000002': {'name': '万科A', 'sector': '地产', 'market': '0'},
    '600048': {'name': '保利发展', 'sector': '地产', 'market': '1'},
    # 免税
    '601888': {'name': '中国中免', 'sector': '免税', 'market': '1'},
    # 券商
    '300059': {'name': '东方财富', 'sector': '券商', 'market': '0'},
    # 电子
    '002475': {'name': '立讯精密', 'sector': '电子', 'market': '0'},
    # 面板
    '000725': {'name': '京东方A', 'sector': '面板', 'market': '0'},
}


def _fetch_kline(code: str, market: str = '1', start: str = '20200101', end: str = '20241231') -> List[dict]:
    """从东方财富获取历史K线数据"""
    cache_key = f"{code}_{start}_{end}.json"
    cache_path = os.path.join(CACHE_DIR, cache_key)

    # 检查缓存
    if os.path.exists(cache_path):
        with open(cache_path, 'r') as f:
            return json.load(f)

    url = 'http://push2his.eastmoney.com/api/qt/stock/kline/get'
    params = {
        'secid': f'{market}.{code}',
        'fields1': 'f1,f2,f3,f4,f5,f6',
        'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
        'klt': '101', 'fqt': '1', 'beg': start, 'end': end,
    }

    try:
        r = httpx.get(url, params=params, timeout=15)
        data = r.json()
        klines = data.get('data', {}).get('klines', [])
        result = []
        for k in klines:
            parts = k.split(',')
            if len(parts) >= 7:
                result.append({
                    'date': parts[0],
                    'open': float(parts[1]),
                    'close': float(parts[2]),
                    'high': float(parts[3]),
                    'low': float(parts[4]),
                    'volume': float(parts[5]),
                    'amount': float(parts[6]),
                })
        # 缓存
        with open(cache_path, 'w') as f:
            json.dump(result, f)
        return result
    except Exception as e:
        logger.warning(f"Failed to fetch kline for {code}: {e}")
        return []


def _fetch_financial_data(code: str) -> dict:
    """获取财务指标（ROE、PE、PB等）"""
    cache_key = f"fin_{code}.json"
    cache_path = os.path.join(CACHE_DIR, cache_key)

    if os.path.exists(cache_path):
        with open(cache_path, 'r') as f:
            return json.load(f)

    url = 'http://datacenter.eastmoney.com/securities/api/data/get'
    params = {
        'type': 'RPT_LICO_FN_CPD',
        'sty': 'SECURITY_CODE,REPORT_DATE,BASIC_EPS,BPS,WEIGHTAVG_ROE,TOTAL_OPERATE_INCOME,PARENT_NETPROFIT,TOTAL_OPERATE_INCOME_YOY,PARENT_NETPROFIT_YOY',
        'filter': f'(SECURITY_CODE="{code}")',
        'p': '1', 'ps': '20', 'sr': '-1', 'st': 'REPORT_DATE',
    }

    try:
        r = httpx.get(url, params=params, timeout=15)
        data = r.json()
        result = data.get('result', {}).get('data', [])
        with open(cache_path, 'w') as f:
            json.dump(result, f)
        return result
    except Exception as e:
        logger.warning(f"Failed to fetch financials for {code}: {e}")
        return []


def _fetch_stock_basic(code: str, market: str = '1') -> dict:
    """获取单只股票的PE/PB/ROE"""
    cache_key = f"basic_{code}.json"
    cache_path = os.path.join(CACHE_DIR, cache_key)

    if os.path.exists(cache_path):
        with open(cache_path, 'r') as f:
            return json.load(f)

    url = 'http://push2.eastmoney.com/api/qt/stock/get'
    params = {
        'secid': f'{market}.{code}',
        'fields': 'f162,f167,f173',
    }

    try:
        r = httpx.get(url, params=params, timeout=10)
        data = r.json().get('data', {})
        result = {
            'pe': (data.get('f162') or 0) / 100,  # 东方财富PE*100
            'pb': (data.get('f167') or 0) / 100,   # 东方财富PB*100
            'roe': (data.get('f173') or 0) / 100,   # 东方财富ROE*100
        }
        with open(cache_path, 'w') as f:
            json.dump(result, f)
        return result
    except Exception as e:
        logger.warning(f"Failed to fetch basic for {code}: {e}")
        return {'pe': None, 'pb': None, 'roe': None}


def _fetch_pe_pb_snapshot() -> dict:
    """获取股票池的PE/PB/ROE快照"""
    result = {}
    for code, info in STOCK_UNIVERSE.items():
        basic = _fetch_stock_basic(code, info['market'])
        result[code] = basic
    return result


def score_stock_real(pe: float, pb: float, roe: float, price_change_1y: float) -> float:
    """
    真实数据的价值投资综合评分

    简化版（因为实时获取所有财务指标太慢）：
    - 估值因子（40分）：PE + PB
    - 质量因子（35分）：ROE
    - 动量因子（25分）：1年涨跌幅（逆向思维：跌多了反而加分）
    """
    score = 0.0

    # 排除不合格
    if pe is None or pe <= 0 or pe > 80:
        return 0
    if pb is None or pb <= 0 or pb > 10:
        return 0
    if roe is None or roe < 5:
        return 0

    # PE评分（20分）
    if pe < 8: score += 20
    elif pe < 12: score += 17
    elif pe < 15: score += 14
    elif pe < 20: score += 10
    elif pe < 25: score += 6
    elif pe < 35: score += 3

    # PB评分（20分）
    if pb < 0.8: score += 20
    elif pb < 1.2: score += 17
    elif pb < 2.0: score += 14
    elif pb < 3.0: score += 10
    elif pb < 5.0: score += 5

    # ROE评分（35分）
    if roe >= 25: score += 35
    elif roe >= 20: score += 30
    elif roe >= 15: score += 25
    elif roe >= 12: score += 18
    elif roe >= 10: score += 12
    elif roe >= 8: score += 6

    # 逆向动量（25分）- 过去1年跌得多的加分
    if price_change_1y < -30: score += 25
    elif price_change_1y < -20: score += 20
    elif price_change_1y < -10: score += 15
    elif price_change_1y < 0: score += 10
    elif price_change_1y < 10: score += 5

    return score


def run_real_backtest(
    start_date: str = '2020-01-01',
    end_date: str = '2024-12-31',
    top_n: int = 10,
    rebalance_months: int = 6,
    initial_capital: float = 1000000,
) -> dict:
    """
    用真实数据运行价值投资策略回测

    策略逻辑：
    1. 每6个月调仓一次
    2. 用PE/PB/ROE综合评分选股
    3. 等权重配置Top N
    4. 对比沪深300

    Returns:
        完整回测结果
    """
    # 获取所有股票的历史数据
    print("Fetching historical data...")
    all_klines = {}
    for code, info in STOCK_UNIVERSE.items():
        klines = _fetch_kline(code, info['market'], start_date.replace('-', ''), end_date.replace('-', ''))
        if klines:
            all_klines[code] = klines
            print(f"  {info['name']}: {len(klines)} days")

    # 获取沪深300基准
    benchmark = _fetch_kline('000300', '1', start_date.replace('-', ''), end_date.replace('-', ''))

    if not all_klines or not benchmark:
        return {"error": "数据获取失败"}

    # 获取PE/PB快照
    pe_pb = _fetch_pe_pb_snapshot()

    # 构建日期序列
    dates = sorted(set(k['date'] for k in benchmark))
    holdings = {}  # {code: {'shares': int, 'cost': float}}
    cash = initial_capital
    portfolio_values = []
    trade_log = []
    last_rebalance_month = None

    for date in dates:
        # 计算当日持仓市值
        holdings_value = 0
        for code, h in holdings.items():
            klines = all_klines.get(code, [])
            price = next((k['close'] for k in klines if k['date'] == date), None)
            if price:
                holdings_value += h['shares'] * price

        total_value = cash + holdings_value
        portfolio_values.append({'date': date, 'value': round(total_value, 2)})

        # 调仓逻辑（每N个月）
        month = int(date[:7].replace('-', ''))
        if last_rebalance_month is None or (month - last_rebalance_month) >= rebalance_months * 100 // 100:
            # 评分选股
            scores = []
            for code, info in STOCK_UNIVERSE.items():
                klines = all_klines.get(code, [])
                if not klines:
                    continue

                # 获取当前价格
                price = next((k['close'] for k in klines if k['date'] == date), None)
                if not price or price <= 0:
                    continue

                # 获取PE/PB/ROE
                snap = pe_pb.get(code, {})
                pe = snap.get('pe')
                pb = snap.get('pb')
                roe = snap.get('roe')

                # 计算1年涨跌幅
                one_year_ago = (datetime.strptime(date, '%Y-%m-%d') - timedelta(days=365)).strftime('%Y-%m-%d')
                old_price = next((k['close'] for k in klines if k['date'] >= one_year_ago), None)
                price_change = ((price / old_price) - 1) * 100 if old_price else 0

                s = score_stock_real(pe, pb, roe, price_change)
                if s > 0:
                    scores.append({'code': code, 'name': info['name'], 'sector': info['sector'], 'score': s, 'price': price, 'pe': pe, 'pb': pb, 'roe': roe})

            scores.sort(key=lambda x: x['score'], reverse=True)
            selected = scores[:top_n]
            selected_codes = {s['code'] for s in selected}

            # 卖出不在新列表中的持仓
            for code in list(holdings.keys()):
                if code not in selected_codes:
                    price = next((k['close'] for k in all_klines.get(code, []) if k['date'] == date), None)
                    if price:
                        sell_value = holdings[code]['shares'] * price
                        cash += sell_value * 0.999  # 手续费
                        trade_log.append({'date': date, 'action': 'sell', 'code': code, 'price': price})

            # 买入新股票
            target_per_stock = (cash + holdings_value) * 0.95 / top_n
            for s in selected:
                code = s['code']
                price = s['price']
                current_shares = holdings.get(code, {}).get('shares', 0)
                current_value = current_shares * price

                if current_value < target_per_stock:
                    buy_value = target_per_stock - current_value
                    buy_shares = int(buy_value / price / 100) * 100
                    if buy_shares > 0 and cash >= buy_shares * price * 1.001:
                        cash -= buy_shares * price * 1.001
                        if code in holdings:
                            holdings[code]['shares'] += buy_shares
                        else:
                            holdings[code] = {'shares': buy_shares, 'cost': price}
                        trade_log.append({'date': date, 'action': 'buy', 'code': code, 'name': s['name'], 'price': price, 'shares': buy_shares})

            last_rebalance_month = month

    # 计算指标
    final_value = portfolio_values[-1]['value']
    total_return = (final_value / initial_capital - 1) * 100
    years = len(dates) / 252
    annual_return = ((final_value / initial_capital) ** (1 / years) - 1) * 100

    # 基准收益
    bm_initial = benchmark[0]['close']
    bm_final = benchmark[-1]['close']
    bm_return = (bm_final / bm_initial - 1) * 100
    bm_annual = ((bm_final / bm_initial) ** (1 / years) - 1) * 100

    # 最大回撤
    peak = initial_capital
    max_dd = 0
    for pv in portfolio_values:
        if pv['value'] > peak:
            peak = pv['value']
        dd = (pv['value'] - peak) / peak * 100
        if dd < max_dd:
            max_dd = dd

    # 年度收益
    yearly = {}
    for pv in portfolio_values:
        y = pv['date'][:4]
        if y not in yearly:
            yearly[y] = {'start': pv['value'], 'end': pv['value']}
        yearly[y]['end'] = pv['value']
    yearly_returns = {y: round((v['end'] / v['start'] - 1) * 100, 2) for y, v in yearly.items()}

    return {
        'strategy': '价值投资综合策略（真实数据）',
        'period': f'{start_date} ~ {end_date}',
        'stocks_in_universe': len(STOCK_UNIVERSE),
        'top_n': top_n,
        'rebalance_months': rebalance_months,
        'total_return': round(total_return, 2),
        'annual_return': round(annual_return, 2),
        'benchmark_return': round(bm_return, 2),
        'benchmark_annual': round(bm_annual, 2),
        'excess_return': round(annual_return - bm_annual, 2),
        'max_drawdown': round(max_dd, 2),
        'total_trades': len(trade_log),
        'yearly_returns': yearly_returns,
        'equity_curve': portfolio_values,
        'benchmark_curve': [{'date': k['date'], 'value': round(initial_capital * k['close'] / bm_initial, 2)} for k in benchmark],
    }
