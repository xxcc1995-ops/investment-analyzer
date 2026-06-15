"""
Full real-data backtest with 100+ stocks

Uses:
- DataService.get_financial_indicators() for ROE/EPS/BPS/margins/growth
- East Money kline API for historical prices
- Multi-factor value composite scoring
"""

import json
import time
import os
import sys

# Add parent to path
sys.path.insert(0, os.path.dirname(__file__))

from app.services.data_service import DataService
from app.services.real_backtest import _fetch_kline

# 100+ quality A-share stocks covering all major sectors
STOCK_POOL = {
    # 银行 (10)
    '601398': {'name': '工商银行', 'market': '1', 'sector': '银行'},
    '601939': {'name': '建设银行', 'market': '1', 'sector': '银行'},
    '600036': {'name': '招商银行', 'market': '1', 'sector': '银行'},
    '601166': {'name': '兴业银行', 'market': '1', 'sector': '银行'},
    '600000': {'name': '浦发银行', 'market': '1', 'sector': '银行'},
    '000001': {'name': '平安银行', 'market': '0', 'sector': '银行'},
    '601288': {'name': '农业银行', 'market': '1', 'sector': '银行'},
    '601328': {'name': '交通银行', 'market': '1', 'sector': '银行'},
    '600016': {'name': '民生银行', 'market': '1', 'sector': '银行'},
    '601818': {'name': '光大银行', 'market': '1', 'sector': '银行'},
    # 白酒 (6)
    '600519': {'name': '贵州茅台', 'market': '1', 'sector': '白酒'},
    '000858': {'name': '五粮液', 'market': '0', 'sector': '白酒'},
    '000568': {'name': '泸州老窖', 'market': '0', 'sector': '白酒'},
    '002304': {'name': '洋河股份', 'market': '0', 'sector': '白酒'},
    '600809': {'name': '山西汾酒', 'market': '1', 'sector': '白酒'},
    '000799': {'name': '酒鬼酒', 'market': '0', 'sector': '白酒'},
    # 家电 (5)
    '000333': {'name': '美的集团', 'market': '0', 'sector': '家电'},
    '000651': {'name': '格力电器', 'market': '0', 'sector': '家电'},
    '600690': {'name': '海尔智家', 'market': '1', 'sector': '家电'},
    '002032': {'name': '苏泊尔', 'market': '0', 'sector': '家电'},
    '002508': {'name': '老板电器', 'market': '0', 'sector': '家电'},
    # 医药 (6)
    '600276': {'name': '恒瑞医药', 'market': '1', 'sector': '医药'},
    '300760': {'name': '迈瑞医疗', 'market': '0', 'sector': '医药'},
    '603259': {'name': '药明康德', 'market': '1', 'sector': '医药'},
    '000538': {'name': '云南白药', 'market': '0', 'sector': '医药'},
    '600436': {'name': '片仔癀', 'market': '1', 'sector': '医药'},
    '002007': {'name': '华兰生物', 'market': '0', 'sector': '医药'},
    # 新能源 (5)
    '300750': {'name': '宁德时代', 'market': '0', 'sector': '新能源'},
    '002594': {'name': '比亚迪', 'market': '0', 'sector': '新能源车'},
    '601012': {'name': '隆基绿能', 'market': '1', 'sector': '光伏'},
    '002459': {'name': '晶澳科技', 'market': '0', 'sector': '光伏'},
    '300274': {'name': '阳光电源', 'market': '0', 'sector': '光伏'},
    # 化工 (5)
    '600309': {'name': '万华化学', 'market': '1', 'sector': '化工'},
    '002601': {'name': '龙蟒佰利', 'market': '0', 'sector': '化工'},
    '600989': {'name': '宝丰能源', 'market': '1', 'sector': '化工'},
    '000830': {'name': '鲁西化工', 'market': '0', 'sector': '化工'},
    '600426': {'name': '华鲁恒升', 'market': '1', 'sector': '化工'},
    # 电力/能源 (5)
    '600900': {'name': '长江电力', 'market': '1', 'sector': '电力'},
    '601088': {'name': '中国神华', 'market': '1', 'sector': '煤炭'},
    '600585': {'name': '海螺水泥', 'market': '1', 'sector': '建材'},
    '601857': {'name': '中国石油', 'market': '1', 'sector': '石油'},
    '600028': {'name': '中国石化', 'market': '1', 'sector': '石油'},
    # 机械 (5)
    '600031': {'name': '三一重工', 'market': '1', 'sector': '机械'},
    '000338': {'name': '潍柴动力', 'market': '0', 'sector': '机械'},
    '002008': {'name': '大族激光', 'market': '0', 'sector': '机械'},
    '601100': {'name': '恒立液压', 'market': '1', 'sector': '机械'},
    '300124': {'name': '汇川技术', 'market': '0', 'sector': '机械'},
    # 保险/证券 (5)
    '601318': {'name': '中国平安', 'market': '1', 'sector': '保险'},
    '601601': {'name': '中国太保', 'market': '1', 'sector': '保险'},
    '600030': {'name': '中信证券', 'market': '1', 'sector': '证券'},
    '601688': {'name': '华泰证券', 'market': '1', 'sector': '证券'},
    '300059': {'name': '东方财富', 'market': '0', 'sector': '证券'},
    # 食品/消费 (5)
    '603288': {'name': '海天味业', 'market': '1', 'sector': '调味品'},
    '600887': {'name': '伊利股份', 'market': '1', 'sector': '乳制品'},
    '002714': {'name': '牧原股份', 'market': '0', 'sector': '养殖'},
    '300498': {'name': '温氏股份', 'market': '0', 'sector': '养殖'},
    '600298': {'name': '安琪酵母', 'market': '1', 'sector': '食品'},
    # 科技/电子 (5)
    '002415': {'name': '海康威视', 'market': '0', 'sector': '安防'},
    '002475': {'name': '立讯精密', 'market': '0', 'sector': '电子'},
    '603501': {'name': '韦尔股份', 'market': '1', 'sector': '半导体'},
    '002371': {'name': '北方华创', 'market': '0', 'sector': '半导体'},
    '300782': {'name': '卓胜微', 'market': '0', 'sector': '半导体'},
    # 地产/建筑 (5)
    '000002': {'name': '万科A', 'market': '0', 'sector': '地产'},
    '600048': {'name': '保利发展', 'market': '1', 'sector': '地产'},
    '001979': {'name': '招商蛇口', 'market': '0', 'sector': '地产'},
    '600019': {'name': '宝钢股份', 'market': '1', 'sector': '钢铁'},
    '601668': {'name': '中国建筑', 'market': '1', 'sector': '建筑'},
    # 交通运输 (5)
    '601006': {'name': '大秦铁路', 'market': '1', 'sector': '铁路'},
    '600009': {'name': '上海机场', 'market': '1', 'sector': '机场'},
    '601111': {'name': '中国国航', 'market': '1', 'sector': '航空'},
    '002352': {'name': '顺丰控股', 'market': '0', 'sector': '快递'},
    '601888': {'name': '中国中免', 'market': '1', 'sector': '免税'},
    # 其他 (5)
    '000725': {'name': '京东方A', 'market': '0', 'sector': '面板'},
    '601899': {'name': '紫金矿业', 'market': '1', 'sector': '矿业'},
    '002466': {'name': '天齐锂业', 'market': '0', 'sector': '锂矿'},
    '600050': {'name': '中国联通', 'market': '1', 'sector': '通信'},
    '002230': {'name': '科大讯飞', 'market': '0', 'sector': 'AI'},
}


def fetch_financial_data_batch(stocks: dict) -> dict:
    """Batch fetch financial data for all stocks"""
    cache_path = os.path.join(os.path.dirname(__file__), 'data', 'financial_cache.json')
    if os.path.exists(cache_path):
        with open(cache_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    result = {}
    total = len(stocks)
    for i, (code, info) in enumerate(stocks.items()):
        print(f'  [{i+1}/{total}] {info["name"]} ({code})...', end=' ')
        try:
            data = DataService.get_financial_indicators(code)
            reports = data.get('reports', [])
            if reports:
                latest = reports[0]
                result[code] = {
                    'roe': latest.get('roe'),
                    'eps': latest.get('eps'),
                    'bps': latest.get('bps'),
                    'revenue_growth': latest.get('revenue_growth'),
                    'profit_growth': latest.get('profit_growth'),
                    'gross_margin': latest.get('gross_margin'),
                    'net_margin': latest.get('net_margin'),
                    'debt_ratio': latest.get('debt_ratio'),
                    'pe': latest.get('pe'),
                    'pb': latest.get('pb'),
                }
                print(f'OK (ROE={latest.get("roe")}, PE={latest.get("pe")}, PB={latest.get("pb")})')
            else:
                print('No data')
        except Exception as e:
            print(f'Error: {e}')
        time.sleep(0.5)  # Rate limiting

    # Cache
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return result


def score_stock(fin: dict, price_change_1y: float) -> float:
    """Multi-factor value composite scoring"""
    roe = fin.get('roe')
    pe = fin.get('pe')
    pb = fin.get('pb')
    gross_margin = fin.get('gross_margin')
    debt_ratio = fin.get('debt_ratio')
    profit_growth = fin.get('profit_growth')
    div_yield = 0  # TODO: fetch dividend yield

    if not all([roe, pe, pb]):
        return 0
    if pe <= 0 or pe > 60:
        return 0
    if pb <= 0 or pb > 12:
        return 0
    if roe < 6:
        return 0

    score = 0

    # Quality (35 points)
    if roe >= 25: score += 35
    elif roe >= 20: score += 30
    elif roe >= 15: score += 25
    elif roe >= 12: score += 18
    elif roe >= 10: score += 12
    elif roe >= 8: score += 6

    # Gross margin bonus (10 points)
    if gross_margin and gross_margin > 50: score += 10
    elif gross_margin and gross_margin > 30: score += 6
    elif gross_margin and gross_margin > 15: score += 3

    # Valuation (30 points)
    if pe < 8: score += 18
    elif pe < 12: score += 15
    elif pe < 15: score += 12
    elif pe < 20: score += 8
    elif pe < 25: score += 5
    elif pe < 35: score += 2

    if pb < 0.8: score += 12
    elif pb < 1.2: score += 10
    elif pb < 2.0: score += 8
    elif pb < 3.0: score += 5
    elif pb < 5.0: score += 2

    # Growth (15 points)
    if profit_growth and profit_growth > 30: score += 15
    elif profit_growth and profit_growth > 20: score += 12
    elif profit_growth and profit_growth > 10: score += 8
    elif profit_growth and profit_growth > 5: score += 5
    elif profit_growth and profit_growth > 0: score += 2

    # Safety (10 points)
    if debt_ratio and debt_ratio < 30: score += 10
    elif debt_ratio and debt_ratio < 45: score += 7
    elif debt_ratio and debt_ratio < 55: score += 4
    elif debt_ratio and debt_ratio < 65: score += 2

    # Contrarian (10 points)
    if price_change_1y < -30: score += 10
    elif price_change_1y < -20: score += 8
    elif price_change_1y < -10: score += 5
    elif price_change_1y < 0: score += 3

    return score


def run_full_backtest():
    """Run full backtest with 100+ stocks"""
    print("="*60)
    print("FULL MARKET VALUE INVESTING BACKTEST")
    print("="*60)

    # Step 1: Fetch financial data
    print("\n[1/3] Fetching financial data...")
    fin_data = fetch_financial_data_batch(STOCK_POOL)
    print(f"Got financial data for {len(fin_data)} stocks")

    # Step 2: Fetch historical prices
    print("\n[2/3] Fetching historical prices...")
    all_klines = {}
    for code, info in STOCK_POOL.items():
        if code not in fin_data:
            continue
        klines = _fetch_kline(code, info['market'], '20200101', '20241231')
        if klines and len(klines) > 100:
            all_klines[code] = klines
            print(f"  {info['name']}: {len(klines)} days")
        time.sleep(0.3)

    # Fetch CSI300 benchmark
    benchmark = _fetch_kline('000300', '1', '20200101', '20241231')
    print(f"\nCSI300: {len(benchmark)} days, {benchmark[0]['close']:.2f} -> {benchmark[-1]['close']:.2f}")

    # Step 3: Run backtest
    print("\n[3/3] Running backtest...")
    initial_capital = 1000000
    holdings = {}
    cash = initial_capital
    portfolio_values = []
    trade_log = []
    dates = sorted(set(k['date'] for k in benchmark))
    last_rebalance = None
    top_n = 15

    for date in dates:
        holdings_value = 0
        for code, h in holdings.items():
            price = next((k['close'] for k in all_klines.get(code, []) if k['date'] == date), None)
            if price:
                holdings_value += h['shares'] * price

        total_value = cash + holdings_value
        portfolio_values.append({'date': date, 'value': round(total_value, 2)})

        # Rebalance every 6 months
        month = date[5:7]
        if month in ('01', '07') and (last_rebalance is None or last_rebalance != date[:7]):
            last_rebalance = date[:7]

            scores = []
            for code in all_klines:
                if code not in fin_data:
                    continue
                klines = all_klines[code]
                price = next((k['close'] for k in klines if k['date'] == date), None)
                if not price:
                    continue

                # 1-year price change
                one_year_ago = str(int(date[:4]) - 1) + date[4:]
                old_price = next((k['close'] for k in klines if k['date'] >= one_year_ago), None)
                change = ((price / old_price) - 1) * 100 if old_price else 0

                s = score_stock(fin_data[code], change)
                if s > 0:
                    scores.append({'code': code, 'name': STOCK_POOL[code]['name'], 'score': s, 'price': price})

            scores.sort(key=lambda x: x['score'], reverse=True)
            selected = scores[:top_n]
            selected_codes = {s['code'] for s in selected}

            # Sell
            for code in list(holdings.keys()):
                if code not in selected_codes:
                    price = next((k['close'] for k in all_klines.get(code, []) if k['date'] == date), None)
                    if price:
                        cash += holdings[code]['shares'] * price * 0.999
                        del holdings[code]

            # Buy
            target = (cash + holdings_value) * 0.95 / top_n
            for s in selected:
                code = s['code']
                price = s['price']
                cur = holdings.get(code, {}).get('shares', 0) * price
                if cur < target:
                    buy_val = target - cur
                    shares = int(buy_val / price / 100) * 100
                    if shares > 0 and cash >= shares * price * 1.001:
                        cash -= shares * price * 1.001
                        holdings[code] = {'shares': holdings.get(code, {}).get('shares', 0) + shares}
                        trade_log.append({'date': date, 'action': 'buy', 'code': code, 'name': s['name'], 'price': price})

    # Calculate results
    final = portfolio_values[-1]['value']
    total_ret = (final / initial_capital - 1) * 100
    years = len(dates) / 252
    annual_ret = ((final / initial_capital) ** (1/years) - 1) * 100
    bm_ret = (benchmark[-1]['close'] / benchmark[0]['close'] - 1) * 100
    bm_annual = ((benchmark[-1]['close'] / benchmark[0]['close']) ** (1/years) - 1) * 100

    peak = initial_capital
    max_dd = 0
    for pv in portfolio_values:
        if pv['value'] > peak: peak = pv['value']
        dd = (pv['value'] - peak) / peak * 100
        if dd < max_dd: max_dd = dd

    yearly = {}
    for pv in portfolio_values:
        y = pv['date'][:4]
        if y not in yearly: yearly[y] = {'start': pv['value'], 'end': pv['value']}
        yearly[y]['end'] = pv['value']
    yearly_ret = {y: round((v['end']/v['start']-1)*100, 2) for y, v in yearly.items()}

    # Print results
    print("\n" + "="*60)
    print("RESULTS")
    print("="*60)
    print(f"Strategy: Value Composite (ROE/PE/PB/Growth/Margin/Safety/Contrarian)")
    print(f"Period: 2020-01-01 ~ 2024-12-31")
    print(f"Universe: {len(all_klines)} stocks, Top {top_n}")
    print(f"Rebalance: Every 6 months")
    print()
    print(f"Total Return:      {total_ret:>8.2f}%")
    print(f"Annual Return:     {annual_ret:>8.2f}%")
    print(f"Benchmark Return:  {bm_ret:>8.2f}%")
    print(f"Benchmark Annual:  {bm_annual:>8.2f}%")
    print(f"Excess Return:     {annual_ret - bm_annual:>8.2f}%")
    print(f"Max Drawdown:      {max_dd:>8.2f}%")
    print(f"Total Trades:      {len(trade_log):>8d}")
    print()
    print("Yearly Returns:")
    for y, r in sorted(yearly_ret.items()):
        print(f"  {y}: {r:>8.2f}%")
    print()
    print("Final Holdings:")
    for code, h in sorted(holdings.items(), key=lambda x: x[1].get('shares', 0), reverse=True):
        name = STOCK_POOL.get(code, {}).get('name', code)
        price = next((k['close'] for k in all_klines.get(code, []) if k['date'] == dates[-1]), 0)
        value = h['shares'] * price
        print(f"  {name}: {h['shares']} shares @ {price:.2f} = {value:.0f}")


if __name__ == '__main__':
    run_full_backtest()
