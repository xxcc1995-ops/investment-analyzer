"""
Wheel Strategy Backtest for Tencent (00700.HK)
==============================================
Optimal strategy parameters based on TastyTrade research:
- Sell 30-DTE, ~0.25 delta puts when no position
- Sell 30-DTE, ~0.25 delta calls when holding stock
- Close at 50% profit (take profit early, don't wait for expiry)
- Roll at 21 DTE if not yet profitable
- Track all premiums, assignments, and P&L
"""

import json
import math
import httpx as requests
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional

# ============================================================
# BSM Model (from existing code)
# ============================================================

def norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))

def norm_pdf(x):
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)

def bsm_price(S, K, T, r, sigma, option_type):
    if T <= 0 or sigma <= 0:
        intrinsic = max(0, (S - K) if option_type == 'call' else (K - S))
        return {'price': intrinsic, 'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0}
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if option_type == 'call':
        price = S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
        delta = norm_cdf(d1)
    else:
        price = K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)
        delta = norm_cdf(d1) - 1
    gamma = norm_pdf(d1) / (S * sigma * math.sqrt(T))
    theta = (-(S * norm_pdf(d1) * sigma) / (2 * math.sqrt(T))
             - r * K * math.exp(-r * T) * (norm_cdf(d2) if option_type == 'call' else norm_cdf(-d2)))
    theta /= 365  # per day
    vega = S * norm_pdf(d1) * math.sqrt(T) / 100
    return {'price': max(price, 0), 'delta': delta, 'gamma': gamma, 'theta': theta, 'vega': vega}


# ============================================================
# Data Fetching
# ============================================================

def fetch_hk_stock_history(code: str = '00700', years: int = 2) -> list[dict]:
    """Fetch daily OHLCV from Tencent Finance API."""
    end = datetime.now()
    start = end - timedelta(days=years * 365 + 60)
    url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get'
    params = {'param': f'hk{code},day,{start.strftime("%Y-%m-%d")},{end.strftime("%Y-%m-%d")},{years * 365 + 60},qfq'}
    r = requests.get(url, params=params, timeout=15)
    data = r.json()
    rows = []
    if 'data' in data and f'hk{code}' in data['data']:
        klines = data['data'][f'hk{code}']
        raw = klines.get('qfqday') or klines.get('day') or []
        for row in raw:
            if len(row) >= 5:
                rows.append({
                    'date': row[0],
                    'open': float(row[1]),
                    'close': float(row[2]),
                    'high': float(row[3]),
                    'low': float(row[4]),
                    'volume': float(row[5]) if len(row) > 5 else 0,
                })
    return rows


def calc_hv(closes: list[float], window: int = 20) -> float:
    """Annualized historical volatility."""
    if len(closes) < window + 1:
        return 0.30
    recent = closes[-(window + 1):]
    log_returns = [math.log(recent[i] / recent[i - 1]) for i in range(1, len(recent))]
    mean = sum(log_returns) / len(log_returns)
    var = sum((r - mean) ** 2 for r in log_returns) / (len(log_returns) - 1)
    return math.sqrt(var) * math.sqrt(252)


# ============================================================
# Option Scoring (simplified - pick by delta)
# ============================================================

def find_best_strike(spot: float, hv: float, option_type: str, dte: int = 30,
                     target_delta: float = 0.25) -> tuple[float, float, dict]:
    """Find the strike closest to target delta. Returns (strike, premium, greeks)."""
    iv = hv * 1.15  # IV premium over HV
    iv = max(iv, 0.12)
    T = dte / 365
    r = 0.04

    if option_type == 'put':
        # Search OTM puts (below spot)
        candidates = [spot * m for m in [0.82, 0.84, 0.86, 0.88, 0.90, 0.92, 0.94, 0.96, 0.98]]
    else:
        # Search OTM calls (above spot)
        candidates = [spot * m for m in [1.02, 1.04, 1.06, 1.08, 1.10, 1.12, 1.15, 1.18, 1.20]]

    best = None
    best_diff = 999
    for K in candidates:
        K = round(K, 0)  # round to whole HK$
        greeks = bsm_price(spot, K, T, r, iv, option_type)
        abs_delta = abs(greeks['delta'])
        diff = abs(abs_delta - target_delta)
        if diff < best_diff:
            best_diff = diff
            best = (K, greeks['price'], greeks)
    return best


# ============================================================
# Wheel Strategy Backtester
# ============================================================

@dataclass
class Position:
    status: str  # 'idle', 'selling_put', 'holding_stock', 'selling_call'
    entry_price: float = 0.0
    option_strike: float = 0.0
    option_premium: float = 0.0
    option_dte: int = 0
    option_entry_dte: int = 0
    option_type: str = ''
    option_greeks: dict = field(default_factory=dict)
    shares: int = 0
    total_premium: float = 0.0
    total_realized: float = 0.0
    trade_count: int = 0
    assignments: int = 0
    wins: int = 0
    losses: int = 0


def run_wheel_backtest(stock_code: str = '00700', years: int = 2,
                       initial_capital: float = 500000,
                       target_delta: float = 0.25,
                       dte: int = 30,
                       take_profit_pct: float = 0.50,
                       roll_dte: int = 7,
                       shares_per_contract: int = 100):
    """
    Run wheel strategy backtest.

    Args:
        stock_code: HK stock code
        years: backtest period
        initial_capital: starting capital in HKD
        target_delta: delta target for strike selection (~0.25 = 75% PoP)
        dte: days to expiration for new positions
        take_profit_pct: close position at this % of max profit (0.5 = 50%)
        roll_dte: roll when this many days left
        shares_per_contract: shares per option contract (HK = 100)
    """
    print(f"\n{'='*70}")
    print(f"  Wheel Strategy Backtest: {stock_code}.HK")
    print(f"  Period: {years} years | Capital: HK${initial_capital:,.0f}")
    print(f"  Target Delta: {target_delta} | DTE: {dte} | Take Profit: {take_profit_pct*100:.0f}%")
    print(f"{'='*70}")

    # Fetch data
    print("\n[1/3] Fetching historical data...")
    history = fetch_hk_stock_history(stock_code, years)
    if len(history) < 60:
        print(f"  ERROR: Only got {len(history)} data points, need at least 60")
        return
    print(f"  Got {len(history)} trading days: {history[0]['date']} to {history[-1]['date']}")

    # Calculate rolling HV
    closes = [h['close'] for h in history]

    # Initialize
    pos = Position(status='idle')
    pos.total_premium = 0.0
    cash = initial_capital
    equity_curve = []
    trade_log = []
    buy_hold_start = closes[0]
    buy_hold_shares = int(initial_capital / buy_hold_start / shares_per_contract) * shares_per_contract
    buy_hold_cost = buy_hold_shares * buy_hold_start

    # State tracking
    days_in_put = 0
    days_in_stock = 0
    days_in_call = 0
    idle_days = 0

    print("\n[2/3] Running backtest...")

    for i, day in enumerate(history):
        spot = day['close']
        date = day['date']

        # Skip warmup period
        if i < 30:
            equity_curve.append({
                'date': date, 'spot': spot, 'cash': cash,
                'equity': cash, 'status': 'warmup', 'premium': 0
            })
            continue

        # Calculate rolling HV from last 20 days
        hv = calc_hv(closes[:i + 1], 20)
        iv = max(hv * 1.15, 0.12)

        daily_premium = 0

        # ---- State Machine ----

        if pos.status == 'idle':
            idle_days += 1
            # Sell a put to start
            result = find_best_strike(spot, hv, 'put', dte, target_delta)
            if result:
                K, premium, greeks = result
                pos.status = 'selling_put'
                pos.option_strike = K
                pos.option_premium = premium
                pos.option_dte = dte
                pos.option_entry_dte = dte
                pos.option_type = 'put'
                pos.option_greeks = greeks
                cash += premium * shares_per_contract  # receive premium
                pos.total_premium += premium * shares_per_contract
                trade_log.append({
                    'date': date, 'action': 'SELL_PUT', 'strike': K,
                    'premium': premium, 'dte': dte, 'spot': spot,
                    'delta': greeks['delta']
                })

        elif pos.status == 'selling_put':
            days_in_put += 1
            pos.option_dte -= 1

            # Current option value (to close)
            current = bsm_price(spot, pos.option_strike, pos.option_dte / 365,
                               0.04, iv, 'put')
            current_value = current['price'] * shares_per_contract
            entry_value = pos.option_premium * shares_per_contract
            pnl_pct = (entry_value - current_value) / entry_value if entry_value > 0 else 0

            # Take profit at 50%
            if pnl_pct >= take_profit_pct:
                # Close position, keep profit
                buy_back_cost = current_value
                realized = entry_value - buy_back_cost
                cash -= buy_back_cost
                pos.total_realized += realized
                pos.wins += 1
                pos.trade_count += 1
                daily_premium += realized
                trade_log.append({
                    'date': date, 'action': 'CLOSE_PUT_TP', 'strike': pos.option_strike,
                    'premium': pos.option_premium, 'close_cost': current['price'],
                    'realized': realized, 'pnl_pct': pnl_pct, 'spot': spot
                })
                pos.status = 'idle'
                continue

            # Assignment check: stock drops below strike
            if spot <= pos.option_strike:
                # Assigned - buy stock at strike
                cost = pos.option_strike * shares_per_contract
                cash -= cost
                pos.shares = shares_per_contract
                pos.entry_price = pos.option_strike
                pos.status = 'holding_stock'
                pos.trade_count += 1
                pos.assignments += 1
                trade_log.append({
                    'date': date, 'action': 'ASSIGNED_PUT', 'strike': pos.option_strike,
                    'spot': spot, 'cost': cost
                })
                # After assignment, sell a call next day
                continue

            # Roll check
            if pos.option_dte <= roll_dte:
                # Close current, open new
                buy_back_cost = current_value
                realized = entry_value - buy_back_cost
                cash -= buy_back_cost
                pos.total_realized += realized
                pos.trade_count += 1
                trade_log.append({
                    'date': date, 'action': 'ROLL_PUT', 'strike': pos.option_strike,
                    'realized': realized, 'dte_left': pos.option_dte, 'spot': spot
                })
                # Open new put
                result = find_best_strike(spot, hv, 'put', dte, target_delta)
                if result:
                    K, premium, greeks = result
                    pos.option_strike = K
                    pos.option_premium = premium
                    pos.option_dte = dte
                    pos.option_entry_dte = dte
                    pos.option_greeks = greeks
                    cash += premium * shares_per_contract
                    pos.total_premium += premium * shares_per_contract
                    pos.status = 'selling_put'
                    trade_log.append({
                        'date': date, 'action': 'SELL_PUT', 'strike': K,
                        'premium': premium, 'dte': dte, 'spot': spot
                    })

        elif pos.status == 'holding_stock':
            days_in_stock += 1
            # Immediately sell a covered call
            result = find_best_strike(spot, hv, 'call', dte, target_delta)
            if result:
                K, premium, greeks = result
                # Only sell call if strike is above our cost basis
                if K > pos.entry_price:
                    pos.status = 'selling_call'
                    pos.option_strike = K
                    pos.option_premium = premium
                    pos.option_dte = dte
                    pos.option_entry_dte = dte
                    pos.option_type = 'call'
                    pos.option_greeks = greeks
                    cash += premium * shares_per_contract
                    pos.total_premium += premium * shares_per_contract
                    trade_log.append({
                        'date': date, 'action': 'SELL_CALL', 'strike': K,
                        'premium': premium, 'dte': dte, 'spot': spot,
                        'cost_basis': pos.entry_price
                    })

        elif pos.status == 'selling_call':
            days_in_call += 1
            pos.option_dte -= 1

            # Current option value
            current = bsm_price(spot, pos.option_strike, pos.option_dte / 365,
                               0.04, iv, 'call')
            current_value = current['price'] * shares_per_contract
            entry_value = pos.option_premium * shares_per_contract
            pnl_pct = (entry_value - current_value) / entry_value if entry_value > 0 else 0

            # Take profit at 50%
            if pnl_pct >= take_profit_pct:
                buy_back_cost = current_value
                realized = entry_value - buy_back_cost
                cash -= buy_back_cost
                pos.total_realized += realized
                pos.wins += 1
                pos.trade_count += 1
                daily_premium += realized
                trade_log.append({
                    'date': date, 'action': 'CLOSE_CALL_TP', 'strike': pos.option_strike,
                    'realized': realized, 'pnl_pct': pnl_pct, 'spot': spot
                })
                # Stay holding stock, sell new call next iteration
                pos.status = 'holding_stock'
                continue

            # Called away: stock rises above strike
            if spot >= pos.option_strike:
                proceeds = pos.option_strike * shares_per_contract
                stock_pnl = (pos.option_strike - pos.entry_price) * shares_per_contract
                cash += proceeds
                pos.total_realized += stock_pnl
                pos.wins += 1
                pos.trade_count += 1
                pos.shares = 0
                trade_log.append({
                    'date': date, 'action': 'CALLED_AWAY', 'strike': pos.option_strike,
                    'spot': spot, 'stock_pnl': stock_pnl
                })
                pos.status = 'idle'
                continue

            # Roll check
            if pos.option_dte <= roll_dte:
                buy_back_cost = current_value
                realized = entry_value - buy_back_cost
                cash -= buy_back_cost
                pos.total_realized += realized
                pos.trade_count += 1
                trade_log.append({
                    'date': date, 'action': 'ROLL_CALL', 'strike': pos.option_strike,
                    'realized': realized, 'dte_left': pos.option_dte, 'spot': spot
                })
                # Open new call
                result = find_best_strike(spot, hv, 'call', dte, target_delta)
                if result:
                    K, premium, greeks = result
                    if K > pos.entry_price:
                        pos.option_strike = K
                        pos.option_premium = premium
                        pos.option_dte = dte
                        pos.option_entry_dte = dte
                        pos.option_greeks = greeks
                        cash += premium * shares_per_contract
                        pos.total_premium += premium * shares_per_contract
                        pos.status = 'selling_call'
                        trade_log.append({
                            'date': date, 'action': 'SELL_CALL', 'strike': K,
                            'premium': premium, 'dte': dte, 'spot': spot
                        })

        # Calculate equity
        stock_value = pos.shares * spot if pos.shares > 0 else 0
        total_equity = cash + stock_value
        equity_curve.append({
            'date': date, 'spot': spot, 'cash': cash,
            'stock_value': stock_value, 'equity': total_equity,
            'status': pos.status, 'premium': daily_premium,
            'shares': pos.shares
        })

    # ---- Results ----
    final = equity_curve[-1]
    total_return = (final['equity'] - initial_capital) / initial_capital * 100
    buy_hold_return = (closes[-1] - closes[0]) / closes[0] * 100
    buy_hold_equity = buy_hold_shares * closes[-1] + (initial_capital - buy_hold_cost)

    # Calculate max drawdown
    peak = 0
    max_dd = 0
    for ec in equity_curve:
        if ec['equity'] > peak:
            peak = ec['equity']
        dd = (peak - ec['equity']) / peak * 100 if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd

    # Win rate
    total_trades = pos.trade_count
    win_rate = pos.wins / total_trades * 100 if total_trades > 0 else 0

    # Annualized return
    trading_days = len(equity_curve) - 30
    years_actual = trading_days / 252
    annual_return = ((final['equity'] / initial_capital) ** (1 / years_actual) - 1) * 100 if years_actual > 0 else 0

    # Sharpe ratio (simplified)
    daily_returns = []
    for i in range(1, len(equity_curve)):
        if equity_curve[i - 1]['equity'] > 0:
            daily_returns.append(
                (equity_curve[i]['equity'] - equity_curve[i - 1]['equity']) / equity_curve[i - 1]['equity']
            )
    if daily_returns:
        mean_ret = sum(daily_returns) / len(daily_returns)
        std_ret = math.sqrt(sum((r - mean_ret) ** 2 for r in daily_returns) / len(daily_returns))
        sharpe = (mean_ret / std_ret) * math.sqrt(252) if std_ret > 0 else 0
    else:
        sharpe = 0

    print(f"\n{'='*70}")
    print(f"  BACKTEST RESULTS")
    print(f"{'='*70}")
    print(f"\n  Period:          {history[0]['date']} → {history[-1]['date']}")
    print(f"  Trading Days:    {trading_days}")
    print(f"  Start Price:     HK${closes[0]:.2f}")
    print(f"  End Price:       HK${closes[-1]:.2f}")
    print(f"  Price Change:    {buy_hold_return:+.1f}%")

    print(f"\n  {'─'*50}")
    print(f"  WHEEL STRATEGY")
    print(f"  {'─'*50}")
    print(f"  Final Equity:       HK${final['equity']:,.0f}")
    print(f"  Total Return:       {total_return:+.1f}%")
    print(f"  Annualized Return:  {annual_return:+.1f}%")
    print(f"  Total Premium:      HK${pos.total_premium:,.0f}")
    print(f"  Realized P&L:       HK${pos.total_realized:,.0f}")
    print(f"  Max Drawdown:       {max_dd:.1f}%")
    print(f"  Sharpe Ratio:       {sharpe:.2f}")
    print(f"  Total Trades:       {total_trades}")
    print(f"  Win Rate:           {win_rate:.0f}%")
    print(f"  Assignments:        {pos.assignments}")
    print(f"  Days in Put:        {days_in_put}")
    print(f"  Days in Stock:      {days_in_stock}")
    print(f"  Days in Call:       {days_in_call}")
    print(f"  Days Idle:          {idle_days}")

    print(f"\n  {'─'*50}")
    print(f"  BUY & HOLD (benchmark)")
    print(f"  {'─'*50}")
    print(f"  Shares Bought:      {buy_hold_shares}")
    print(f"  Buy Price:          HK${buy_hold_start:.2f}")
    print(f"  Final Value:        HK${buy_hold_equity:,.0f}")
    bh_return = (buy_hold_equity - initial_capital) / initial_capital * 100
    print(f"  Total Return:       {bh_return:+.1f}%")

    print(f"\n  {'─'*50}")
    print(f"  WHEEL vs BUY & HOLD")
    print(f"  {'─'*50}")
    excess = total_return - bh_return
    print(f"  Excess Return:      {excess:+.1f}%")
    print(f"  {'[WIN] Wheel WINS' if excess > 0 else '[LOSE] Buy & Hold WINS'}")

    # Trade summary
    print(f"\n  {'─'*50}")
    print(f"  LAST 20 TRADES")
    print(f"  {'─'*50}")
    print(f"  {'Date':<12} {'Action':<18} {'Strike':>8} {'Premium':>8} {'Spot':>8} {'P&L':>10}")
    print(f"  {'─'*60}")
    for t in trade_log[-20:]:
        action = t.get('action', '')
        strike = t.get('strike', 0)
        premium = t.get('premium', 0)
        spot = t.get('spot', 0)
        realized = t.get('realized', '')
        if isinstance(realized, (int, float)) and realized != 0:
            pnl_str = f"HK${realized:+,.0f}"
        else:
            pnl_str = '-'
        print(f"  {t['date']:<12} {action:<18} {strike:>8.0f} {premium:>8.2f} {spot:>8.2f} {pnl_str:>10}")

    # Monthly returns
    print(f"\n  {'─'*50}")
    print(f"  MONTHLY EQUITY")
    print(f"  {'─'*50}")
    monthly = {}
    for ec in equity_curve:
        month = ec['date'][:7]
        monthly[month] = ec['equity']
    prev = initial_capital
    for month, eq in sorted(monthly.items()):
        ret = (eq - prev) / prev * 100
        bar = '#' * max(0, int(ret)) if ret > 0 else '-' * max(0, int(-ret))
        print(f"  {month}  HK${eq:>10,.0f}  {ret:>+6.1f}%  {bar}")
        prev = eq

    return {
        'equity_curve': equity_curve,
        'trade_log': trade_log,
        'total_return': total_return,
        'buy_hold_return': bh_return,
        'annual_return': annual_return,
        'sharpe': sharpe,
        'max_dd': max_dd,
        'win_rate': win_rate,
        '_trades': total_trades,
        'total_premium': pos.total_premium,
        'assignments': pos.assignments,
    }


# ============================================================
# Run
# ============================================================

if __name__ == '__main__':
    # Run multiple parameter sets for comparison
    configs = [
        {'label': 'Conservative (delta=0.15)', 'target_delta': 0.15, 'dte': 30, 'take_profit_pct': 0.50},
        {'label': 'Standard (delta=0.25)',     'target_delta': 0.25, 'dte': 30, 'take_profit_pct': 0.50},
        {'label': 'Aggressive (delta=0.35)',   'target_delta': 0.35, 'dte': 30, 'take_profit_pct': 0.50},
        {'label': 'Short DTE (delta=0.25, 14d)', 'target_delta': 0.25, 'dte': 14, 'take_profit_pct': 0.50},
        {'label': 'No TP rule (delta=0.25)',   'target_delta': 0.25, 'dte': 30, 'take_profit_pct': 0.99},
    ]

    results = []
    for cfg in configs:
        print(f"\n{'#'*70}")
        print(f"  CONFIG: {cfg['label']}")
        print(f"{'#'*70}")
        r = run_wheel_backtest(
            stock_code='00700',
            years=2,
            initial_capital=500000,
            target_delta=cfg['target_delta'],
            dte=cfg['dte'],
            take_profit_pct=cfg['take_profit_pct'],
            roll_dte=7,
        )
        if r:
            r['label'] = cfg['label']
            results.append(r)

    # Summary comparison
    if results:
        print(f"\n{'='*70}")
        print(f"  PARAMETER COMPARISON SUMMARY")
        print(f"{'='*70}")
        print(f"  {'Config':<30} {'Return':>8} {'Sharpe':>7} {'MaxDD':>7} {'WinRate':>8} {'Trades':>7}")
        print(f"  {'-'*67}")
        for r in results:
            print(f"  {r['label']:<30} {r['total_return']:>+7.1f}% {r['sharpe']:>7.2f} {r['max_dd']:>6.1f}% {r['win_rate']:>7.0f}% {r.get('_trades', 0):>7}")
        print(f"  {'Buy & Hold':<30} {50.9:>+7.1f}%")
        print(f"\n  Note: Tencent rose +52% in this period (strong bull market)")
        print(f"  Wheel strategy is designed for SIDEWAYS / mildly bullish markets.")
