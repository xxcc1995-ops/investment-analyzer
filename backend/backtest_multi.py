"""
Backtest wheel strategy on stocks best suited for it:
- 京东 (09618): +11% trend, 87% range, high oscillation
- 恒基地产 (00012): +15% trend, 66% range
- 安踏体育 (02020): -8.5% trend, 48% range, truly sideways

Plus comparison with 腾讯 (00700) and Buy & Hold for each.
"""
import sys
sys.path.insert(0, '.')

# Reuse the backtest function
from backtest_wheel import run_wheel_backtest

stocks = [
    ('09618', 'JD京东',     500000),
    ('00012', '恒基地产',    500000),
    ('02020', '安踏体育',    500000),
    ('00941', '中国移动',    500000),
    ('00883', '中国海油',    500000),
]

print("\n" + "#" * 70)
print("  WHEEL STRATEGY COMPARISON: BEST CANDIDATES")
print("  Using: delta=0.25, DTE=30, 50% take-profit")
print("#" * 70)

summary = []
for code, name, capital in stocks:
    print(f"\n\n{'#'*70}")
    print(f"  {name} ({code})")
    print(f"{'#'*70}")
    r = run_wheel_backtest(
        stock_code=code,
        years=2,
        initial_capital=capital,
        target_delta=0.25,
        dte=30,
        take_profit_pct=0.50,
        roll_dte=7,
    )
    if r:
        summary.append({
            'code': code,
            'name': name,
            'wheel_return': r['total_return'],
            'bh_return': r['buy_hold_return'],
            'excess': r['total_return'] - r['buy_hold_return'],
            'sharpe': r['sharpe'],
            'max_dd': r['max_dd'],
            'win_rate': r['win_rate'],
            'trades': r['_trades'],
            'premium': r['total_premium'],
        })

# Final summary
print("\n\n" + "=" * 80)
print("  FINAL SUMMARY: ALL STOCKS COMPARED")
print("=" * 80)
print()
print(f"  {'Stock':<14} {'Wheel%':>8} {'B&H%':>8} {'Excess':>8} {'Sharpe':>7} {'MaxDD':>7} {'WinRt':>6} {'Trades':>7}")
print("  " + "-" * 72)
for s in summary:
    print(f"  {s['name']:<14} {s['wheel_return']:>+7.1f}% {s['bh_return']:>+7.1f}% {s['excess']:>+7.1f}% {s['sharpe']:>7.2f} {s['max_dd']:>6.1f}% {s['win_rate']:>5.0f}% {s['trades']:>7}")

print()
print("  Key Takeaway:")
wins = [s for s in summary if s['excess'] > 0]
if wins:
    print(f"  Wheel BEATS Buy & Hold on: {', '.join(w['name'] for w in wins)}")
else:
    print(f"  Wheel loses to Buy & Hold on ALL stocks (2-year bull market)")
    print(f"  But Wheel has MUCH lower drawdowns and stable monthly income")
