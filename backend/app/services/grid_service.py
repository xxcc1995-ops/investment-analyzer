"""网格交易服务 - 网格生成、历史回测、仓位分析"""

import time
import math
import requests
from typing import Optional
from datetime import datetime, timedelta

from app.services.vi_service import _get_hk_stock_data

# ============================================================
# Cache
# ============================================================

from app.core.cache import get_cache as _base_get_cache, set_cache as _set_cached
_CACHE_TTL = 600

def _get_cached(key: str):
    return _base_get_cache(key, ttl_seconds=_CACHE_TTL)


# ============================================================
# Historical Data
# ============================================================

def _fetch_hk_historical(code: str = '00700', days: int = 252) -> list[dict]:
    """Fetch HK stock historical OHLCV data via Tencent Finance API."""
    try:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days + 30)).strftime('%Y-%m-%d')
        url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get'
        params = {'param': f'hk{code},day,{start_date},{end_date},{days + 30},qfq'}
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if 'data' in data and f'hk{code}' in data['data']:
            klines = data['data'][f'hk{code}']
            rows = klines.get('qfqday') or klines.get('day') or []
            records = []
            for row in rows:
                if len(row) >= 6:
                    records.append({
                        'date': str(row[0]),
                        'open': float(row[1]),
                        'high': float(row[3]),
                        'low': float(row[4]),
                        'close': float(row[2]),
                        'volume': float(row[5]),
                    })
            return records
    except Exception:
        pass
    return []


# ============================================================
# ATR
# ============================================================

def calculate_atr(highs: list[float], lows: list[float],
                  closes: list[float], period: int = 14) -> float:
    """Average True Range."""
    if len(closes) < period + 1:
        return 0

    trs = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1])
        )
        trs.append(tr)

    if len(trs) < period:
        return sum(trs) / len(trs) if trs else 0

    atr = sum(trs[:period]) / period
    for i in range(period, len(trs)):
        atr = (atr * (period - 1) + trs[i]) / period

    return round(atr, 4)


# ============================================================
# Grid Generation
# ============================================================

def generate_grid_levels(
    current_price: float,
    grid_type: str = 'equal_distance',
    num_grids_up: int = 10,
    num_grids_down: int = 10,
    grid_width: float = None,
    atr: float = None,
    atr_multiplier: float = 1.0,
) -> list[dict]:
    """Generate grid levels around current price."""
    if grid_width is None and atr is not None:
        grid_width = atr * atr_multiplier
    elif grid_width is None:
        grid_width = current_price * 0.02  # default 2%

    grid_width = max(grid_width, current_price * 0.005)  # min 0.5%

    levels = []

    if grid_type == 'equal_distance':
        base = current_price
        for i in range(-num_grids_down, num_grids_up + 1):
            price = round(base + i * grid_width, 2)
            if price <= 0:
                continue
            level_type = 'buy' if i < 0 else ('sell' if i > 0 else 'current')
            levels.append({
                'price': price,
                'index': i,
                'distance_pct': round((price - current_price) / current_price * 100, 2),
                'type': level_type,
            })
    else:  # equal_ratio
        ratio = 1 + (grid_width / current_price)
        base = current_price
        for i in range(-num_grids_down, num_grids_up + 1):
            price = round(base * (ratio ** i), 2)
            if price <= 0:
                continue
            level_type = 'buy' if i < 0 else ('sell' if i > 0 else 'current')
            levels.append({
                'price': price,
                'index': i,
                'distance_pct': round((price - current_price) / current_price * 100, 2),
                'type': level_type,
            })

    return levels


# ============================================================
# Position Sizing
# ============================================================

def calculate_grid_positions(total_capital: float, num_grids: int,
                             sizing_method: str = 'equal',
                             current_price: float = 100) -> list[dict]:
    """Calculate position size per grid level."""
    if sizing_method == 'equal':
        capital_per_grid = total_capital / num_grids
        shares_per_grid = int(capital_per_grid / current_price / 100) * 100
        shares_per_grid = max(shares_per_grid, 100)
        return [{'method': 'equal', 'shares': shares_per_grid,
                 'capital': round(shares_per_grid * current_price, 2)}] * num_grids
    else:  # pyramid - more at lower prices
        # Allocate more capital to lower grid levels
        weights = list(range(1, num_grids + 1))
        total_weight = sum(weights)
        positions = []
        for w in weights:
            capital = total_capital * w / total_weight
            shares = int(capital / current_price / 100) * 100
            shares = max(shares, 100)
            positions.append({'method': 'pyramid', 'shares': shares,
                              'capital': round(shares * current_price, 2)})
        positions.reverse()  # more shares at lower levels
        return positions


# ============================================================
# Grid Simulation
# ============================================================

def simulate_grid_trading(
    historical_prices: list[dict],
    grid_levels: list[dict],
    shares_per_grid: int,
    initial_capital: float,
    trading_cost_pct: float = 0.001,
) -> dict:
    """Simulate grid trading over historical data."""
    if not historical_prices or not grid_levels:
        return _empty_simulation()

    level_prices = sorted([lv['price'] for lv in grid_levels])

    # Track positions: dict of {level_price: {'shares': n, 'entry_price': p}}
    positions = {}
    trades = []
    realized_pnl = 0
    total_cost = 0
    equity_curve = []
    peak_equity = initial_capital
    max_drawdown = 0

    for day in historical_prices:
        low, high, close = day['low'], day['high'], day['close']
        day_trades = 0

        # Check buy signals: price drops to or below grid level
        for level in level_prices:
            if level >= close and level not in positions and low <= level:
                # Buy at grid level
                cost = shares_per_grid * level
                fee = cost * trading_cost_pct
                if cost + fee <= initial_capital - total_cost:
                    positions[level] = {'shares': shares_per_grid, 'entry_price': level}
                    total_cost += cost + fee
                    trades.append({
                        'date': day['date'], 'action': 'buy', 'price': level,
                        'level': level, 'shares': shares_per_grid,
                        'cost': round(cost + fee, 2), 'pnl': 0,
                    })
                    day_trades += 1

        # Check sell signals: price rises to or above grid level + 1
        for level in sorted(level_prices, reverse=True):
            if level in positions and high >= level:
                # Find the next higher level for sell target
                idx = level_prices.index(level)
                if idx + 1 < len(level_prices):
                    sell_target = level_prices[idx + 1]
                else:
                    sell_target = level * 1.02  # 2% above

                if high >= sell_target:
                    pos = positions[level]
                    sell_price = sell_target
                    revenue = pos['shares'] * sell_price
                    fee = revenue * trading_cost_pct
                    pnl = (sell_price - pos['entry_price']) * pos['shares'] - fee * 2
                    realized_pnl += pnl
                    total_cost -= pos['shares'] * pos['entry_price']
                    del positions[level]
                    trades.append({
                        'date': day['date'], 'action': 'sell', 'price': sell_price,
                        'level': level, 'shares': pos['shares'],
                        'revenue': round(revenue - fee, 2), 'pnl': round(pnl, 2),
                    })
                    day_trades += 1

        # Track equity
        position_value = sum(p['shares'] * close for p in positions.values())
        total_equity = initial_capital - total_cost + position_value + realized_pnl
        equity_curve.append({'date': day['date'], 'equity': round(total_equity, 2)})

        peak_equity = max(peak_equity, total_equity)
        drawdown = (peak_equity - total_equity) / peak_equity * 100
        max_drawdown = max(max_drawdown, drawdown)

    # Final stats
    num_trades = len([t for t in trades if t['action'] == 'buy'])
    winning_trades = len([t for t in trades if t['action'] == 'sell' and t.get('pnl', 0) > 0])
    total_sells = len([t for t in trades if t['action'] == 'sell'])
    win_rate = round(winning_trades / total_sells * 100, 1) if total_sells > 0 else 0

    # Unrealized P&L from remaining positions
    last_price = historical_prices[-1]['close'] if historical_prices else 0
    unrealized = sum((last_price - p['entry_price']) * p['shares'] for p in positions.values())

    total_return = round((realized_pnl + unrealized) / initial_capital * 100, 2)

    return {
        'trades': trades[-50:],  # last 50 trades for display
        'total_trades': len(trades),
        'num_buys': num_trades,
        'num_sells': total_sells,
        'realized_pnl': round(realized_pnl, 2),
        'unrealized_pnl': round(unrealized, 2),
        'total_pnl': round(realized_pnl + unrealized, 2),
        'total_return_pct': total_return,
        'win_rate': win_rate,
        'max_drawdown': round(max_drawdown, 2),
        'equity_curve': equity_curve,
        'open_positions': len(positions),
        'position_details': [
            {'level': lv, 'shares': pos['shares'], 'entry': pos['entry_price'],
             'unrealized': round((last_price - pos['entry_price']) * pos['shares'], 2)}
            for lv, pos in positions.items()
        ],
    }


def _empty_simulation() -> dict:
    return {
        'trades': [], 'total_trades': 0, 'num_buys': 0, 'num_sells': 0,
        'realized_pnl': 0, 'unrealized_pnl': 0, 'total_pnl': 0,
        'total_return_pct': 0, 'win_rate': 0, 'max_drawdown': 0,
        'equity_curve': [], 'open_positions': 0, 'position_details': [],
    }


# ============================================================
# Grid Status
# ============================================================

def get_grid_status(current_price: float, grid_levels: list[dict]) -> dict:
    """Show current grid position status."""
    nearest_level = None
    min_dist = float('inf')

    for lv in grid_levels:
        dist = abs(lv['price'] - current_price)
        if dist < min_dist:
            min_dist = dist
            nearest_level = lv

    # Find next buy/sell triggers
    buy_levels = sorted([lv for lv in grid_levels if lv['type'] == 'buy'],
                        key=lambda x: x['price'], reverse=True)
    sell_levels = sorted([lv for lv in grid_levels if lv['type'] == 'sell'],
                         key=lambda x: x['price'])

    next_buy = buy_levels[0] if buy_levels else None
    next_sell = sell_levels[0] if sell_levels else None

    return {
        'current_price': current_price,
        'nearest_level': nearest_level,
        'next_buy': next_buy,
        'next_sell': next_sell,
        'total_levels': len(grid_levels),
        'buy_levels': len(buy_levels),
        'sell_levels': len(sell_levels),
    }


# ============================================================
# Breakeven Analysis
# ============================================================

def breakeven_analysis(grid_width: float, shares_per_grid: int,
                       current_price: float,
                       trading_cost_pct: float = 0.001) -> dict:
    """Calculate break-even grid width considering trading costs."""
    # Cost per round trip (buy + sell)
    cost_per_share = current_price * trading_cost_pct * 2
    min_grid_width = cost_per_share
    min_grid_pct = round(cost_per_share / current_price * 100, 2)

    # Profit per grid trade at given width
    profit_per_trade = (grid_width - cost_per_share) * shares_per_grid
    profit_pct = round(grid_width / current_price * 100, 2)

    return {
        'min_grid_width': round(min_grid_width, 2),
        'min_grid_pct': min_grid_pct,
        'current_grid_width': round(grid_width, 2),
        'current_grid_pct': round(grid_width / current_price * 100, 2),
        'profit_per_trade': round(profit_per_trade, 2),
        'is_profitable': grid_width > min_grid_width,
        'trading_cost_per_share': round(cost_per_share, 4),
    }


# ============================================================
# Main Analysis
# ============================================================

def analyze_grid_trading(
    stock_code: str = '00700',
    grid_type: str = 'equal_distance',
    num_grids_up: int = 10,
    num_grids_down: int = 10,
    grid_width_pct: float = None,
    total_capital: float = 1000000,
    hist_days: int = 252,
    sizing_method: str = 'equal',
) -> dict:
    """Full grid trading analysis."""
    cache_key = f"grid_{stock_code}_{grid_type}_{num_grids_up}_{num_grids_down}_{grid_width_pct}_{total_capital}_{hist_days}_{sizing_method}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    # Get current price
    hk_data = _get_hk_stock_data(stock_code)
    if not hk_data:
        return {'error': f'无法获取 {stock_code} 实时行情', 'update_time': datetime.now().isoformat()}

    current_price = hk_data['price']

    # Get historical data
    hist_data = _fetch_hk_historical(stock_code, hist_days)
    if not hist_data:
        return {'error': '无法获取历史数据', 'update_time': datetime.now().isoformat()}

    # Calculate ATR
    highs = [d['high'] for d in hist_data]
    lows = [d['low'] for d in hist_data]
    closes = [d['close'] for d in hist_data]
    atr = calculate_atr(highs, lows, closes, 14)

    # 52-week range
    high_52w = max(highs[-252:]) if len(highs) >= 252 else max(highs)
    low_52w = min(lows[-252:]) if len(lows) >= 252 else min(lows)

    # Grid width
    if grid_width_pct:
        grid_width = current_price * grid_width_pct / 100
    else:
        grid_width = atr * 1.0

    # Generate grid levels
    grid_levels = generate_grid_levels(
        current_price, grid_type, num_grids_up, num_grids_down,
        grid_width, atr
    )

    # Position sizing
    positions = calculate_grid_positions(total_capital, len(grid_levels),
                                         sizing_method, current_price)
    shares_per_grid = positions[0]['shares'] if positions else 100

    # Simulation
    simulation = simulate_grid_trading(hist_data, grid_levels, shares_per_grid,
                                       total_capital)

    # Grid status
    status = get_grid_status(current_price, grid_levels)

    # Breakeven
    be = breakeven_analysis(grid_width, shares_per_grid, current_price)

    # Annualized return
    years = hist_days / 252
    if years > 0 and simulation['total_return_pct'] > 0:
        cagr = round((1 + simulation['total_return_pct'] / 100) ** (1 / years) - 1, 4) * 100
    else:
        cagr = simulation['total_return_pct']

    result = {
        'stock_name': hk_data['name'],
        'current_price': current_price,
        'high_52w': round(high_52w, 2),
        'low_52w': round(low_52w, 2),
        'atr': round(atr, 2),
        'atr_pct': round(atr / current_price * 100, 2),
        'grid_type': grid_type,
        'grid_width': round(grid_width, 2),
        'grid_width_pct': round(grid_width / current_price * 100, 2),
        'grid_levels': grid_levels,
        'shares_per_grid': shares_per_grid,
        'capital_per_grid': round(shares_per_grid * current_price, 2),
        'total_levels': len(grid_levels),
        'simulation': simulation,
        'status': status,
        'breakeven': be,
        'cagr': round(cagr, 2),
        'hist_days': len(hist_data),
        'update_time': datetime.now().isoformat(),
    }

    _set_cached(cache_key, result)
    return result


def get_philosophy() -> dict:
    """Grid trading methodology."""
    return {
        'title': '网格交易策略',
        'subtitle': '在价格波动中自动低买高卖',
        'concepts': [
            {
                'name': '等距网格',
                'desc': '每个网格间距相等，适合价格在窄幅区间震荡的标的',
                'formula': 'Level[i] = Base + i × Width',
            },
            {
                'name': '等比网格',
                'desc': '每个网格间距按固定比例递增，适合价格波动较大的标的',
                'formula': 'Level[i] = Base × (1 + Ratio)^i',
            },
        ],
        'scoring': {
            'title': '网格参数优化',
            'dimensions': [
                {'name': '网格宽度', 'desc': '基于ATR计算，太窄被手续费吃掉利润，太宽资金闲置'},
                {'name': '网格数量', 'desc': '上行/下行各10-15格为宜，覆盖主要波动区间'},
                {'name': '仓位管理', 'desc': '等额分配或金字塔加仓（低价多买）'},
                {'name': '交易成本', 'desc': '确保网格利润 > 2×交易成本'},
            ],
        },
        'risks': [
            '趋势行情：单边上涨会踏空，单边下跌会不断买入被套',
            '震荡区间突破：价格突破网格上下界后策略失效',
            '资金耗尽：下跌过深时网格资金可能不够继续买入',
            '交易成本：频繁交易的手续费会侵蚀利润',
            '流动性风险：极端行情下可能无法按网格价成交',
        ],
        'rules': [
            '网格宽度至少覆盖2倍交易成本',
            '总资金分N份，每份只用于一个网格',
            '设置止损线：价格跌破最下方网格一定比例时停止买入',
            '定期评估：震荡区间变化时调整网格参数',
            '适合长期横盘震荡的标的（如腾讯近期走势）',
        ],
    }
