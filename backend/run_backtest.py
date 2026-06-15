"""Real data backtest script"""
from app.services.real_backtest import _fetch_kline, score_stock_real

FINANCIAL_DATA = {
    '601398': {'pe': 5.5, 'pb': 0.6, 'roe': 12, 'name': '工商银行'},
    '601939': {'pe': 5.8, 'pb': 0.65, 'roe': 13, 'name': '建设银行'},
    '600036': {'pe': 7.5, 'pb': 1.05, 'roe': 16, 'name': '招商银行'},
    '601318': {'pe': 9.0, 'pb': 1.1, 'roe': 16, 'name': '中国平安'},
    '600519': {'pe': 25.0, 'pb': 7.5, 'roe': 30, 'name': '贵州茅台'},
    '000858': {'pe': 18.0, 'pb': 4.5, 'roe': 25, 'name': '五粮液'},
    '000568': {'pe': 20.0, 'pb': 6.0, 'roe': 28, 'name': '泸州老窖'},
    '002304': {'pe': 15.0, 'pb': 3.0, 'roe': 20, 'name': '洋河股份'},
    '000333': {'pe': 12.0, 'pb': 3.0, 'roe': 25, 'name': '美的集团'},
    '000651': {'pe': 8.0, 'pb': 1.8, 'roe': 22, 'name': '格力电器'},
    '600690': {'pe': 13.0, 'pb': 2.2, 'roe': 18, 'name': '海尔智家'},
    '603288': {'pe': 35.0, 'pb': 8.0, 'roe': 28, 'name': '海天味业'},
    '300750': {'pe': 22.0, 'pb': 5.0, 'roe': 20, 'name': '宁德时代'},
    '002594': {'pe': 18.0, 'pb': 3.5, 'roe': 15, 'name': '比亚迪'},
    '002415': {'pe': 18.0, 'pb': 4.0, 'roe': 22, 'name': '海康威视'},
    '600309': {'pe': 12.0, 'pb': 2.5, 'roe': 20, 'name': '万华化学'},
    '600900': {'pe': 18.0, 'pb': 3.5, 'roe': 15, 'name': '长江电力'},
    '601088': {'pe': 9.0, 'pb': 1.3, 'roe': 15, 'name': '中国神华'},
    '600585': {'pe': 8.0, 'pb': 1.0, 'roe': 18, 'name': '海螺水泥'},
    '600031': {'pe': 10.0, 'pb': 1.5, 'roe': 15, 'name': '三一重工'},
    '000338': {'pe': 9.0, 'pb': 1.3, 'roe': 14, 'name': '潍柴动力'},
    '000002': {'pe': 6.0, 'pb': 0.6, 'roe': 10, 'name': '万科A'},
    '600048': {'pe': 5.5, 'pb': 0.7, 'roe': 12, 'name': '保利发展'},
    '601888': {'pe': 22.0, 'pb': 4.5, 'roe': 20, 'name': '中国中免'},
    '300059': {'pe': 25.0, 'pb': 4.0, 'roe': 18, 'name': '东方财富'},
    '002475': {'pe': 20.0, 'pb': 4.5, 'roe': 20, 'name': '立讯精密'},
    '000725': {'pe': 15.0, 'pb': 1.2, 'roe': 8, 'name': '京东方A'},
}

STOCK_UNIVERSE = {
    '601398': {'name': '工商银行', 'market': '1'},
    '601939': {'name': '建设银行', 'market': '1'},
    '600036': {'name': '招商银行', 'market': '1'},
    '601318': {'name': '中国平安', 'market': '1'},
    '600519': {'name': '贵州茅台', 'market': '1'},
    '000858': {'name': '五粮液', 'market': '0'},
    '000568': {'name': '泸州老窖', 'market': '0'},
    '002304': {'name': '洋河股份', 'market': '0'},
    '000333': {'name': '美的集团', 'market': '0'},
    '000651': {'name': '格力电器', 'market': '0'},
    '600690': {'name': '海尔智家', 'market': '1'},
    '603288': {'name': '海天味业', 'market': '1'},
    '300750': {'name': '宁德时代', 'market': '0'},
    '002594': {'name': '比亚迪', 'market': '0'},
    '002415': {'name': '海康威视', 'market': '0'},
    '600309': {'name': '万华化学', 'market': '1'},
    '600900': {'name': '长江电力', 'market': '1'},
    '601088': {'name': '中国神华', 'market': '1'},
    '600585': {'name': '海螺水泥', 'market': '1'},
    '600031': {'name': '三一重工', 'market': '1'},
    '000338': {'name': '潍柴动力', 'market': '0'},
    '000002': {'name': '万科A', 'market': '0'},
    '600048': {'name': '保利发展', 'market': '1'},
    '601888': {'name': '中国中免', 'market': '1'},
    '300059': {'name': '东方财富', 'market': '0'},
    '002475': {'name': '立讯精密', 'market': '0'},
    '000725': {'name': '京东方A', 'market': '0'},
}

# Fetch historical data
print("Fetching real historical data...")
all_klines = {}
for code, info in STOCK_UNIVERSE.items():
    klines = _fetch_kline(code, info['market'], '20200101', '20241231')
    if klines:
        all_klines[code] = klines
        print(f"  {info['name']}: {len(klines)} days, {klines[0]['close']:.2f} -> {klines[-1]['close']:.2f}")

benchmark = _fetch_kline('000300', '1', '20200101', '20241231')
print(f"\nCSI300: {len(benchmark)} days, {benchmark[0]['close']:.2f} -> {benchmark[-1]['close']:.2f}")

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
        for code, info in STOCK_UNIVERSE.items():
            klines = all_klines.get(code, [])
            price = next((k['close'] for k in klines if k['date'] == date), None)
            if not price:
                continue

            fin = FINANCIAL_DATA.get(code, {})
            pe = fin.get('pe', 999)
            pb = fin.get('pb', 99)
            roe = fin.get('roe', 0)

            one_year_ago = str(int(date[:4]) - 1) + date[4:]
            old_price = next((k['close'] for k in klines if k['date'] >= one_year_ago), None)
            change = ((price / old_price) - 1) * 100 if old_price else 0

            s = score_stock_real(pe, pb, roe, change)
            if s > 0:
                scores.append({'code': code, 'name': info['name'], 'score': s, 'price': price})

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

print("\n" + "="*60)
print("REAL DATA BACKTEST RESULTS")
print("="*60)
print(f"Strategy: Value Composite (PE/PB/ROE/Contrarian)")
print(f"Period: 2020-01-01 ~ 2024-12-31")
print(f"Universe: {len(STOCK_UNIVERSE)} stocks, Top {top_n}")
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
    name = STOCK_UNIVERSE.get(code, {}).get('name', code)
    price = next((k['close'] for k in all_klines.get(code, []) if k['date'] == dates[-1]), 0)
    value = h['shares'] * price
    print(f"  {name}: {h['shares']} shares @ {price:.2f} = {value:.0f}")
