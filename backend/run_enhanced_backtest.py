"""Enhanced backtest with real financial data for 34 stocks"""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from app.services.real_backtest import _fetch_kline

# Load data
with open('data/financial_cache.json', 'r', encoding='utf-8') as f:
    fin_data = json.load(f)

cache_dir = 'data/backtest_cache'
STOCK_NAMES = {
    '000333': '美的集团', '000338': '潍柴动力', '000568': '泸州老窖', '000651': '格力电器',
    '000858': '五粮液', '002008': '大族激光', '002032': '苏泊尔', '002415': '海康威视',
    '002475': '立讯精密', '002508': '老板电器', '002594': '比亚迪', '002714': '牧原股份',
    '000002': '万科A', '000538': '云南白药', '000725': '京东方A', '000799': '酒鬼酒',
    '000830': '鲁西化工', '002007': '华兰生物', '002230': '科大讯飞', '002304': '洋河股份',
    '002352': '顺丰控股', '002371': '北方华创', '002459': '晶澳科技', '002466': '天齐锂业',
    '002601': '龙蟒佰利', '300059': '东方财富', '300124': '汇川技术', '300274': '阳光电源',
    '300498': '温氏股份', '300750': '宁德时代', '300760': '迈瑞医疗', '300782': '卓胜微',
    '300976': '达瑞电子', '301029': '怡合达',
}

def score_stock(fin, price, price_1y_ago):
    """Enhanced multi-factor scoring"""
    roe = fin.get('roe')
    eps = fin.get('eps')
    bps = fin.get('bps')
    gm = fin.get('gross_margin')
    debt = fin.get('debt_ratio')
    rg = fin.get('revenue_growth')
    pg = fin.get('profit_growth')

    if not all([roe, eps, bps]) or roe < 6 or eps <= 0 or bps <= 0:
        return 0

    # Calculate PE/PB from EPS/BPS and current price
    pe = price / eps if eps > 0 else 999
    pb = price / bps if bps > 0 else 999

    if pe <= 0 or pe > 60 or pb <= 0 or pb > 15:
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
    if gm and gm > 50: score += 10
    elif gm and gm > 30: score += 6
    elif gm and gm > 15: score += 3

    # Valuation - PE (18 points)
    if pe < 8: score += 18
    elif pe < 12: score += 15
    elif pe < 15: score += 12
    elif pe < 20: score += 8
    elif pe < 25: score += 5
    elif pe < 35: score += 2

    # Valuation - PB (12 points)
    if pb < 0.8: score += 12
    elif pb < 1.2: score += 10
    elif pb < 2.0: score += 8
    elif pb < 3.0: score += 5
    elif pb < 5.0: score += 2

    # Growth (15 points)
    if pg and pg > 30: score += 15
    elif pg and pg > 20: score += 12
    elif pg and pg > 10: score += 8
    elif pg and pg > 5: score += 5
    elif pg and pg > 0: score += 2

    # Safety (10 points)
    if debt and debt < 30: score += 10
    elif debt and debt < 45: score += 7
    elif debt and debt < 55: score += 4
    elif debt and debt < 65: score += 2

    # Contrarian (10 points)
    if price_1y_ago and price_1y_ago > 0:
        change = (price / price_1y_ago - 1) * 100
        if change < -30: score += 10
        elif change < -20: score += 8
        elif change < -10: score += 5
        elif change < 0: score += 3

    return score


# Load klines
all_klines = {}
for code in STOCK_NAMES:
    fpath = os.path.join(cache_dir, f'{code}_20200101_20241231.json')
    if os.path.exists(fpath):
        with open(fpath, 'r') as f:
            all_klines[code] = json.load(f)

# Load benchmark
bm_path = os.path.join(cache_dir, '000300_20200101_20241231.json')
with open(bm_path, 'r') as f:
    benchmark = json.load(f)

print(f'Stocks: {len(all_klines)}, Benchmark: {len(benchmark)} days')

# Run backtest
initial_capital = 1000000
holdings = {}
cash = initial_capital
portfolio_values = []
trade_log = []
dates = sorted(set(k['date'] for k in benchmark))
last_rebalance = None
top_n = 10

for date in dates:
    holdings_value = 0
    for code, h in holdings.items():
        price = next((k['close'] for k in all_klines.get(code, []) if k['date'] == date), None)
        if price:
            holdings_value += h['shares'] * price

    total_value = cash + holdings_value
    portfolio_values.append({'date': date, 'value': round(total_value, 2)})

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

            one_year_ago = str(int(date[:4]) - 1) + date[4:]
            old_price = next((k['close'] for k in klines if k['date'] >= one_year_ago), None)

            s = score_stock(fin_data[code], price, old_price)
            if s > 0:
                scores.append({'code': code, 'name': STOCK_NAMES.get(code, code), 'score': s, 'price': price})

        scores.sort(key=lambda x: x['score'], reverse=True)
        selected = scores[:top_n]
        selected_codes = {s['code'] for s in selected}

        for code in list(holdings.keys()):
            if code not in selected_codes:
                price = next((k['close'] for k in all_klines.get(code, []) if k['date'] == date), None)
                if price:
                    cash += holdings[code]['shares'] * price * 0.999
                    del holdings[code]

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

# Results
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

# Sharpe ratio
import numpy as np
values = [pv['value'] for pv in portfolio_values]
returns = np.diff(values) / values[:-1]
sharpe = (np.mean(returns) * 252 - 0.02) / (np.std(returns) * np.sqrt(252)) if np.std(returns) > 0 else 0

print()
print('='*60)
print('ENHANCED VALUE COMPOSITE BACKTEST (REAL DATA)')
print('='*60)
print(f'Strategy: Multi-factor (ROE/PE/PB/Growth/Margin/Safety/Contrarian)')
print(f'Period: 2020-01-01 ~ 2024-12-31')
print(f'Universe: {len(all_klines)} stocks, Top {top_n}')
print(f'Rebalance: Every 6 months')
print()
print(f'Total Return:      {total_ret:>8.2f}%')
print(f'Annual Return:     {annual_ret:>8.2f}%')
print(f'Benchmark Return:  {bm_ret:>8.2f}%')
print(f'Benchmark Annual:  {bm_annual:>8.2f}%')
print(f'Excess Return:     {annual_ret - bm_annual:>8.2f}%')
print(f'Sharpe Ratio:      {sharpe:>8.2f}')
print(f'Max Drawdown:      {max_dd:>8.2f}%')
print(f'Total Trades:      {len(trade_log):>8d}')
print()
print('Yearly Returns:')
for y, r in sorted(yearly_ret.items()):
    print(f'  {y}: {r:>8.2f}%')
print()
print('Final Holdings:')
for code, h in sorted(holdings.items(), key=lambda x: x[1].get('shares', 0), reverse=True):
    name = STOCK_NAMES.get(code, code)
    price = next((k['close'] for k in all_klines.get(code, []) if k['date'] == dates[-1]), 0)
    value = h['shares'] * price
    print(f'  {name}: {h["shares"]} shares @ {price:.2f} = {value:.0f}')
