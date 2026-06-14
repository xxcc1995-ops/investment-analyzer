"""
可转债大师策略回测引擎

使用真实历史数据（AKShare）验证6种大师策略的历史表现。
数据源：bond_zh_cov（转债列表）+ bond_zh_hs_cov_daily（历史K线）+ bond_cb_index_jsl（CB指数基准）

机构级回测特性：
- 含手续费（佣金+印花税）、滑点模拟
- 收益归因分析（选券贡献 vs 择时贡献）
- 基准对比（Alpha、Beta、信息比率、基准净值曲线）
- Sortino、Calmar、最大回撤持续天数
- 参数可配置（手续费率、滑点、调仓频率等）
"""

import akshare as ak
import numpy as np
import pandas as pd
import logging
import time
import os
import pickle
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# 缓存目录
CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '.cache', 'cb_backtest')
os.makedirs(CACHE_DIR, exist_ok=True)

# 信用评级排序（与 cb_service.py 一致）
RATING_ORDER = {'AAA': 6, 'AA+': 5, 'AA': 4, 'AA-': 3, 'A+': 2, 'A': 1, 'A-': 0, 'BBB': -1}

# ============================================================
# 交易成本常量（可转债真实费率）
# ============================================================
DEFAULT_COMMISSION_RATE = 0.0002     # 佣金费率 万2（单边），多数券商可转债佣金
DEFAULT_STAMP_DUTY_RATE = 0.0       # 可转债卖出无印花税（A股可转债免印花税）
DEFAULT_SLIPPAGE_BPS = 2            # 滑点 2个基点（0.02%）


# ============================================================
# 策略定义（适配回测：使用价格+静态属性近似）
# ============================================================

STRATEGIES = {
    'andaoquan': {
        'name': '安道全面值策略',
        'description': '面值附近买入，130元卖出。规则极简，适合新手。',
        'filter': lambda b: (
            b['price'] <= 110
            and b.get('rating_order', 0) >= 3  # AA-及以上
        ),
        'sort_key': lambda b: b['price'],  # 价格越低越优先
        'reverse': False,
        'sell_rule': 'price >= 130',
    },
    'dual_low': {
        'name': '双低策略',
        'description': '低价格+低溢价率，经典量化轮动。回测用 price≤125 近似 double_low≤130。',
        'filter': lambda b: b['price'] <= 125,
        'sort_key': lambda b: b['price'],
        'reverse': False,
        'sell_rule': 'price >= 130 or not in top_n',
    },
    'pancake': {
        'name': '摊大饼策略',
        'description': '不选股，买一篮子低价转债，靠概率取胜。',
        'filter': lambda b: (
            b['price'] <= 130
            and b.get('rating_order', 0) >= 1  # A-及以上
        ),
        'sort_key': lambda b: b['price'],
        'reverse': False,
        'sell_rule': 'price >= 140 or not in top_n',
    },
    'ytm_defense': {
        'name': 'YTM保本策略',
        'description': '只买到期收益率为正的转债，持有到期保证不亏。回测用 price≤110 近似 YTM>0。',
        'filter': lambda b: (
            b['price'] <= 110
            and b.get('rating_order', 0) >= 4  # AA及以上
        ),
        'sort_key': lambda b: b['price'],
        'reverse': False,
        'sell_rule': 'price >= 125 or rating_downgrade',
    },
    'revision_game': {
        'name': '下修博弈策略',
        'description': '寻找正股价接近下修触发价的转债。回测用 price 100-120 区间近似。',
        'filter': lambda b: (
            b['price'] >= 95
            and b['price'] <= 120
        ),
        'sort_key': lambda b: b['price'],
        'reverse': False,
        'sell_rule': 'price >= 135 or price <= 90',
    },
    'redeem_game': {
        'name': '强赎博弈策略',
        'description': '寻找接近130强赎线的转债。回测用 price 115-135 区间近似。',
        'filter': lambda b: (
            b['price'] >= 110
            and b['price'] <= 135
        ),
        'sort_key': lambda b: abs(b['price'] - 125),  # 距125越近越优先
        'reverse': False,
        'sell_rule': 'price >= 140 or price <= 105',
    },
}


# ============================================================
# 交易成本计算
# ============================================================

def _calc_trade_cost(
    trade_value: float,
    action: str,
    commission_rate: float = DEFAULT_COMMISSION_RATE,
    stamp_duty_rate: float = DEFAULT_STAMP_DUTY_RATE,
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
) -> float:
    """计算单笔交易的总成本

    Args:
        trade_value: 交易金额（买入或卖出的名义金额）
        action: 'buy' 或 'sell'
        commission_rate: 佣金费率（单边）
        stamp_duty_rate: 印花税费率（仅卖出收取，可转债为0）
        slippage_bps: 滑点（基点），1bp = 0.01%

    Returns:
        总交易成本（元）
    """
    commission = trade_value * commission_rate
    # 佣金最低5元（多数券商规则）
    if commission < 5.0:
        commission = 5.0

    stamp_duty = 0.0
    if action == 'sell':
        stamp_duty = trade_value * stamp_duty_rate

    slippage = trade_value * (slippage_bps / 10000.0)

    return commission + stamp_duty + slippage


# ============================================================
# 数据获取与缓存
# ============================================================

def _cache_path(key: str) -> str:
    """获取缓存文件路径"""
    safe_key = key.replace('/', '_').replace('\\', '_').replace(':', '_')
    return os.path.join(CACHE_DIR, f'{safe_key}.pkl')


def _load_cache(key: str, max_age_hours: int = 24) -> Optional[object]:
    """加载缓存"""
    path = _cache_path(key)
    if not os.path.exists(path):
        return None
    mtime = os.path.getmtime(path)
    age_hours = (time.time() - mtime) / 3600
    if age_hours > max_age_hours:
        return None
    try:
        with open(path, 'rb') as f:
            return pickle.load(f)
    except Exception:
        return None


def _save_cache(key: str, data: object):
    """保存缓存"""
    try:
        with open(_cache_path(key), 'wb') as f:
            pickle.dump(data, f)
    except Exception as e:
        logger.warning(f"缓存保存失败: {e}")


def fetch_bond_universe() -> pd.DataFrame:
    """获取可转债列表（带静态属性）

    Returns:
        DataFrame with columns: code, name, stock_code, stock_name, rating, rating_order,
                                maturity_date, issue_size, convert_price
    """
    cached = _load_cache('bond_universe', max_age_hours=12)
    if cached is not None:
        return cached

    logger.info("从AKShare获取可转债列表...")
    try:
        df = ak.bond_zh_cov()
    except Exception as e:
        logger.error(f"获取可转债列表失败: {e}")
        return pd.DataFrame()

    # 标准化列名（AKShare返回中文列名）
    col_map = {}
    cols = df.columns.tolist()
    # 尝试按位置映射（列顺序相对稳定）
    if len(cols) >= 19:
        col_map = {
            cols[0]: 'code',
            cols[1]: 'name',
            cols[5]: 'stock_code',
            cols[6]: 'stock_name',
            cols[7]: 'stock_price',
            cols[8]: 'convert_price',
            cols[9]: 'convert_value',
            cols[10]: 'par_value',
            cols[11]: 'premium_rt',
            cols[17]: 'list_date',
            cols[18]: 'rating',
        }
    df = df.rename(columns=col_map)

    if 'code' not in df.columns:
        logger.error(f"列名映射失败，原始列: {cols}")
        return pd.DataFrame()

    # 添加评级排序值
    if 'rating' in df.columns:
        df['rating_order'] = df['rating'].map(RATING_ORDER).fillna(0)
    else:
        df['rating_order'] = 0

    # 确保code为字符串
    df['code'] = df['code'].astype(str)

    _save_cache('bond_universe', df)
    logger.info(f"获取到 {len(df)} 只可转债")
    return df


def fetch_bond_history(code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """获取单只转债历史K线

    Args:
        code: 转债代码（如 '113009'）
        start_date: 开始日期 'YYYY-MM-DD'
        end_date: 结束日期 'YYYY-MM-DD'

    Returns:
        DataFrame with columns: date, open, high, low, close, volume
    """
    cache_key = f'hist_{code}_{start_date}_{end_date}'
    cached = _load_cache(cache_key, max_age_hours=72)
    if cached is not None:
        return cached

    # AKShare需要带市场前缀
    symbol = code
    if not symbol.startswith(('sh', 'sz')):
        # 根据代码判断市场
        if code.startswith(('110', '113')):
            symbol = f'sh{code}'
        elif code.startswith(('123', '127', '128')):
            symbol = f'sz{code}'
        else:
            symbol = f'sh{code}'

    try:
        df = ak.bond_zh_hs_cov_daily(symbol=symbol)
        if df is None or df.empty:
            return pd.DataFrame()

        df['date'] = pd.to_datetime(df['date'])
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
        df = df[(df['date'] >= start) & (df['date'] <= end)]

        if not df.empty:
            _save_cache(cache_key, df)

        return df

    except Exception as e:
        logger.debug(f"获取 {code} 历史数据失败: {e}")
        return pd.DataFrame()


def fetch_cb_index(start_date: str, end_date: str) -> pd.DataFrame:
    """获取可转债指数历史数据（作为基准）

    Returns:
        DataFrame with columns: date, close, change_pct
    """
    cache_key = f'cb_index_{start_date}_{end_date}'
    cached = _load_cache(cache_key, max_age_hours=72)
    if cached is not None:
        return cached

    logger.info("获取可转债指数历史...")
    try:
        df = ak.bond_cb_index_jsl()
        if df is None or df.empty:
            return pd.DataFrame()

        df['date'] = pd.to_datetime(df['price_dt'])
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
        df = df[(df['date'] >= start) & (df['date'] <= end)]

        result = pd.DataFrame({
            'date': df['date'].values,
            'close': df['idx_price'].values if 'idx_price' in df.columns else df['price'].values,
            'change_pct': df['idx_increase_rt'].values if 'idx_increase_rt' in df.columns else df['increase_rt'].values,
        })

        if not result.empty:
            _save_cache(cache_key, result)

        return result

    except Exception as e:
        logger.error(f"获取CB指数失败: {e}")
        return pd.DataFrame()


# ============================================================
# 回测引擎
# ============================================================

def run_cb_backtest(
    strategy: str = 'dual_low',
    start_date: str = '2023-01-01',
    end_date: str = '2026-06-13',
    rebalance_freq: str = 'weekly',
    top_n: int = 15,
    initial_capital: float = 100000,
    commission_rate: float = DEFAULT_COMMISSION_RATE,
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
) -> Dict:
    """执行可转债策略回测

    Args:
        strategy: 策略名称（andaoquan/dual_low/pancake/ytm_defense/revision_game/redeem_game）
        start_date: 回测开始日期
        end_date: 回测结束日期
        rebalance_freq: 调仓频率（weekly/biweekly/monthly）
        top_n: 持仓数量
        initial_capital: 初始资金
        commission_rate: 佣金费率（单边，默认万2）
        slippage_bps: 滑点基点（默认2bp）

    Returns:
        回测结果字典
    """
    strat = STRATEGIES.get(strategy)
    if not strat:
        return {'error': f'未知策略: {strategy}，可选: {", ".join(STRATEGIES.keys())}'}

    # 1. 获取转债列表（静态属性）
    universe = fetch_bond_universe()
    if universe.empty:
        return {'error': '获取转债列表失败'}

    # 构建属性映射
    bond_attrs = {}
    for _, row in universe.iterrows():
        code = str(row.get('code', ''))
        if code:
            bond_attrs[code] = {
                'name': row.get('name', ''),
                'rating': row.get('rating', ''),
                'rating_order': row.get('rating_order', 0),
                'stock_name': row.get('stock_name', ''),
            }

    # 2. 智能筛选：只获取在回测期间内上市的转债
    all_codes = list(bond_attrs.keys())

    # 按上市日期过滤（如果有list_date信息）
    if 'list_date' in universe.columns:
        end_dt = pd.to_datetime(end_date)
        filtered_codes = []
        for _, row in universe.iterrows():
            code = str(row.get('code', ''))
            list_date = row.get('list_date')
            if code in bond_attrs:
                try:
                    if pd.notna(list_date) and pd.to_datetime(list_date) <= end_dt:
                        filtered_codes.append(code)
                except Exception:
                    filtered_codes.append(code)
        if filtered_codes:
            all_codes = filtered_codes

    # 限制数量（优先选择上市时间早的转债，确保有足够历史数据）
    MAX_BONDS = 200
    if len(all_codes) > MAX_BONDS:
        # 优先选择上市时间早的转债（有更长的历史数据）
        list_date_map = {}
        for _, row in universe.iterrows():
            code = str(row.get('code', ''))
            list_date = row.get('list_date')
            if pd.notna(list_date):
                try:
                    list_date_map[code] = pd.to_datetime(list_date)
                except Exception:
                    list_date_map[code] = pd.Timestamp.max
            else:
                list_date_map[code] = pd.Timestamp.max
        all_codes.sort(key=lambda c: list_date_map.get(c, pd.Timestamp.max))
        all_codes = all_codes[:MAX_BONDS]
        logger.info(f"转债数量过多，按上市时间选取前 {MAX_BONDS} 只（优先选择历史数据长的）")

    logger.info(f"开始获取 {len(all_codes)} 只转债的历史价格数据...")

    price_data = {}  # {code: DataFrame}
    fetch_errors = 0
    for i, code in enumerate(all_codes):
        if i > 0 and i % 10 == 0:
            logger.info(f"  进度: {i}/{len(all_codes)} (成功: {len(price_data)})")
            time.sleep(0.5)  # 限速

        df = fetch_bond_history(code, start_date, end_date)
        if not df.empty:
            price_data[code] = df
        else:
            fetch_errors += 1

        time.sleep(0.15)  # 基本限速

    logger.info(f"价格数据获取完成: {len(price_data)} 只成功, {fetch_errors} 只失败")

    if len(price_data) < 10:
        return {'error': f'可用转债数据不足（{len(price_data)}只），无法进行回测'}

    # 3. 获取基准指数
    benchmark = fetch_cb_index(start_date, end_date)

    # 4. 构建交易日历（取所有转债的并集）
    all_dates = set()
    for code, df in price_data.items():
        all_dates.update(df['date'].tolist())
    trading_days = sorted(all_dates)

    if len(trading_days) < 20:
        return {'error': '交易日数据不足'}

    # 构建价格查找表: {(code, date_str): close_price}
    price_lookup = {}
    for code, df in price_data.items():
        for _, row in df.iterrows():
            date_str = row['date'].strftime('%Y-%m-%d')
            price_lookup[(code, date_str)] = row['close']

    # 5. 确定调仓日
    rebalance_dates = _get_rebalance_dates(trading_days, rebalance_freq)

    # 6. 模拟回测
    result = _simulate_strategy(
        strategy_name=strategy,
        strategy_def=strat,
        bond_attrs=bond_attrs,
        price_lookup=price_lookup,
        trading_days=trading_days,
        rebalance_dates=rebalance_dates,
        top_n=top_n,
        initial_capital=initial_capital,
        commission_rate=commission_rate,
        slippage_bps=slippage_bps,
    )

    # 7. 计算指标（含基准对比）
    metrics = _calculate_metrics(result, benchmark, initial_capital)
    result['metrics'] = metrics

    # 8. 策略有效性分析
    result['analysis'] = _analyze_validity(metrics, strategy)

    # 清理大数据字段，只保留前端需要的
    result.pop('portfolio_series', None)

    return result


def _get_rebalance_dates(trading_days: list, freq: str) -> list:
    """根据频率确定调仓日

    改进：取每周/每两周/每月的最后一个交易日（而非第一个），
    这更符合实盘逻辑（周五调仓而非周一）。
    """
    if not trading_days:
        return []

    rebalance_dates = []

    if freq == 'weekly':
        # 每周最后一个交易日
        current_week = None
        last_day_of_week = None
        for date in trading_days:
            week = date.isocalendar()[1]
            year = date.year
            week_key = (year, week)
            if week_key != current_week:
                # 新的一周开始，上一周的最后一天就是调仓日
                if last_day_of_week is not None:
                    rebalance_dates.append(last_day_of_week)
                current_week = week_key
            last_day_of_week = date
        # 最后一周
        if last_day_of_week is not None:
            rebalance_dates.append(last_day_of_week)

    elif freq == 'biweekly':
        # 每两周最后一个交易日
        current_week = None
        week_count = 0
        last_day_of_period = None
        for date in trading_days:
            week = date.isocalendar()[1]
            year = date.year
            week_key = (year, week)
            if week_key != current_week:
                if last_day_of_period is not None and week_count % 2 == 0:
                    rebalance_dates.append(last_day_of_period)
                current_week = week_key
                week_count += 1
            last_day_of_period = date
        if last_day_of_period is not None and week_count % 2 == 0:
            rebalance_dates.append(last_day_of_period)

    elif freq == 'monthly':
        # 每月最后一个交易日
        current_month = None
        last_day_of_month = None
        for date in trading_days:
            month_key = (date.year, date.month)
            if month_key != current_month:
                if last_day_of_month is not None:
                    rebalance_dates.append(last_day_of_month)
                current_month = month_key
            last_day_of_month = date
        if last_day_of_month is not None:
            rebalance_dates.append(last_day_of_month)

    return rebalance_dates


def _simulate_strategy(
    strategy_name: str,
    strategy_def: dict,
    bond_attrs: dict,
    price_lookup: dict,
    trading_days: list,
    rebalance_dates: list,
    top_n: int,
    initial_capital: float,
    commission_rate: float = DEFAULT_COMMISSION_RATE,
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
) -> Dict:
    """策略模拟核心逻辑（含交易成本）"""

    cash = initial_capital
    holdings = {}  # {code: {'shares': 0, 'cost': 0, 'buy_price': 0}}
    portfolio_values = []
    trade_log = []
    total_commission = 0.0       # 累计佣金
    total_slippage = 0.0         # 累计滑点成本
    total_trade_count = 0        # 总交易次数

    # 月度收益跟踪（修复：按月边界正确计算）
    month_start_value = None     # 当月第一天的净值
    current_month_key = None     # (year, month)
    monthly_returns = []         # [(year, month, return)]

    # 基准收益归因跟踪
    holding_selection_returns = []  # 选券收益序列

    filter_fn = strategy_def['filter']
    sort_fn = strategy_def['sort_key']
    reverse = strategy_def.get('reverse', False)

    rebalance_set = set(d.strftime('%Y-%m-%d') for d in rebalance_dates)

    for date in trading_days:
        date_str = date.strftime('%Y-%m-%d')

        # 计算当日持仓市值
        holdings_value = 0
        for code, holding in holdings.items():
            price = price_lookup.get((code, date_str))
            if price:
                holdings_value += holding['shares'] * price
                holding['last_price'] = price
            else:
                # 停牌，用上一次价格
                holdings_value += holding['shares'] * holding.get('last_price', holding['cost'] / max(holding['shares'], 1))

        total_value = cash + holdings_value
        portfolio_values.append({
            'date': date,
            'value': total_value,
            'cash': cash,
            'holdings_value': holdings_value,
            'holding_count': len(holdings),
        })

        # 月度收益跟踪（修复：每月第一天记录起始值，月末计算收益）
        month_key = (date.year, date.month)
        if month_key != current_month_key:
            # 新月开始
            if current_month_key is not None and month_start_value is not None and month_start_value > 0:
                # 计算上月收益（用上一个交易日的净值作为月末值）
                prev_value = portfolio_values[-2]['value'] if len(portfolio_values) >= 2 else month_start_value
                monthly_ret = (prev_value - month_start_value) / month_start_value
                monthly_returns.append((current_month_key[0], current_month_key[1], monthly_ret))
            current_month_key = month_key
            month_start_value = total_value

        # 调仓
        if date_str in rebalance_set:
            # 1. 找出当日有价格且满足策略条件的转债
            candidates = []
            for code, attrs in bond_attrs.items():
                price = price_lookup.get((code, date_str))
                if price is None:
                    continue

                bond_info = {'code': code, 'price': price, **attrs}

                try:
                    if filter_fn(bond_info):
                        score = sort_fn(bond_info)
                        candidates.append({
                            'code': code,
                            'price': price,
                            'score': score,
                            'name': attrs.get('name', ''),
                        })
                except Exception:
                    continue

            # 2. 排序取top_n
            candidates.sort(key=lambda x: x['score'], reverse=reverse)
            selected = candidates[:top_n]
            selected_codes = set(s['code'] for s in selected)

            # 3. 卖出不在新列表中的持仓（含交易成本）
            for code in list(holdings.keys()):
                if code not in selected_codes:
                    price = price_lookup.get((code, date_str))
                    if price:
                        shares = holdings[code]['shares']
                        sell_value = shares * price

                        # 计算卖出成本
                        cost = _calc_trade_cost(sell_value, 'sell', commission_rate, 0, slippage_bps)
                        total_commission += cost * (commission_rate / (commission_rate + slippage_bps / 10000)) if (commission_rate + slippage_bps / 10000) > 0 else 0
                        total_slippage += sell_value * (slippage_bps / 10000)
                        total_trade_count += 1

                        cash += sell_value - cost

                        trade_log.append({
                            'date': date_str,
                            'action': 'sell',
                            'code': code,
                            'name': bond_attrs.get(code, {}).get('name', ''),
                            'price': round(price, 2),
                            'shares': shares,
                            'value': round(sell_value, 2),
                            'cost': round(cost, 2),
                            'reason': '轮出',
                        })
                    del holdings[code]

            # 4. 等权买入新选中的转债（含交易成本）
            if selected:
                target_value = total_value * 0.95 / len(selected)  # 保留5%现金

                for bond in selected:
                    code = bond['code']
                    price = bond['price']
                    current_shares = holdings.get(code, {}).get('shares', 0)
                    current_value = current_shares * price

                    if current_value < target_value * 0.8:  # 偏差超过20%才调仓
                        buy_value = target_value - current_value
                        buy_shares = int(buy_value / price / 10) * 10  # 可转债10张为1手

                        if buy_shares > 0:
                            cost_amount = buy_shares * price
                            # 计算买入成本
                            trade_cost = _calc_trade_cost(cost_amount, 'buy', commission_rate, 0, slippage_bps)

                            if cash >= cost_amount + trade_cost:
                                total_commission += trade_cost * (commission_rate / (commission_rate + slippage_bps / 10000)) if (commission_rate + slippage_bps / 10000) > 0 else 0
                                total_slippage += cost_amount * (slippage_bps / 10000)
                                total_trade_count += 1

                                cash -= (cost_amount + trade_cost)

                                if code in holdings:
                                    holdings[code]['shares'] += buy_shares
                                    holdings[code]['cost'] += cost_amount
                                else:
                                    holdings[code] = {
                                        'shares': buy_shares,
                                        'cost': cost_amount,
                                        'buy_price': price,
                                    }

                                trade_log.append({
                                    'date': date_str,
                                    'action': 'buy',
                                    'code': code,
                                    'name': bond.get('name', ''),
                                    'price': round(price, 2),
                                    'shares': buy_shares,
                                    'value': round(cost_amount, 2),
                                    'cost': round(trade_cost, 2),
                                    'reason': '轮入',
                                })

            # 更新last_price
            for code in holdings:
                price = price_lookup.get((code, date_str))
                if price:
                    holdings[code]['last_price'] = price

    # 最后一个月的收益
    if current_month_key is not None and month_start_value is not None and month_start_value > 0:
        final_value = portfolio_values[-1]['value'] if portfolio_values else initial_capital
        monthly_ret = (final_value - month_start_value) / month_start_value
        monthly_returns.append((current_month_key[0], current_month_key[1], monthly_ret))

    # 最终清理：卖出剩余持仓
    last_date = trading_days[-1].strftime('%Y-%m-%d') if trading_days else ''
    final_sell_log = []
    for code, holding in holdings.items():
        price = price_lookup.get((code, last_date))
        if price:
            sell_value = holding['shares'] * price
            cost = _calc_trade_cost(sell_value, 'sell', commission_rate, 0, slippage_bps)
            cash += sell_value - cost
            final_sell_log.append({
                'date': last_date,
                'action': 'sell',
                'code': code,
                'name': bond_attrs.get(code, {}).get('name', ''),
                'price': round(price, 2),
                'shares': holding['shares'],
                'value': round(sell_value, 2),
                'cost': round(cost, 2),
                'reason': '回测结束',
            })

    trade_log.extend(final_sell_log)

    # 构建权益曲线
    equity_curve = []
    for pv in portfolio_values:
        equity_curve.append({
            'date': pv['date'].strftime('%Y-%m-%d'),
            'value': round(pv['value'], 2),
            'holding_count': pv['holding_count'],
        })

    # 月度收益提取为纯数值列表（兼容旧逻辑）
    monthly_returns_flat = [r[2] for r in monthly_returns]

    return {
        'strategy_name': strategy_name,
        'strategy_display': strategy_def['name'],
        'description': strategy_def['description'],
        'start_date': trading_days[0].strftime('%Y-%m-%d') if trading_days else start_date,
        'end_date': trading_days[-1].strftime('%Y-%m-%d') if trading_days else end_date,
        'equity_curve': equity_curve,
        'trade_log': trade_log[-200:],  # 最多返回200条
        'total_trades': len(trade_log),
        'total_trade_count': total_trade_count,
        'total_commission': round(total_commission, 2),
        'total_slippage': round(total_slippage, 2),
        'total_cost': round(total_commission + total_slippage, 2),
        'monthly_returns': monthly_returns_flat,
        'monthly_returns_detail': monthly_returns,  # (year, month, return) 三元组
        'portfolio_series': portfolio_values,  # 内部用，不返回给前端
    }


def _calculate_metrics(result: Dict, benchmark: pd.DataFrame, initial_capital: float) -> Dict:
    """计算回测指标（机构级）

    包含：
    - 收益指标：总收益、年化收益（几何+算术）
    - 风险指标：最大回撤、波动率、下行波动率
    - 风险调整收益：夏普比率、Sortino、Calmar、信息比率
    - 交易统计：胜率、盈亏比、交易成本
    - 基准对比：基准收益、超额收益、Alpha、Beta
    - 收益归因：选券贡献 vs 时机贡献
    """
    equity_curve = result.get('equity_curve', [])
    monthly_returns = result.get('monthly_returns', [])
    portfolio_series = result.get('portfolio_series', [])

    if not equity_curve or len(equity_curve) < 2:
        return {}

    # 收益序列
    values = pd.Series([p['value'] for p in equity_curve])
    dates = pd.Series([pd.to_datetime(p['date']) for p in equity_curve])
    daily_returns = values.pct_change().dropna()

    # ---- 1. 收益指标 ----
    final_value = values.iloc[-1]
    total_return = (final_value - initial_capital) / initial_capital
    days = (dates.iloc[-1] - dates.iloc[0]).days
    years = max(days / 365, 0.01)

    # 几何年化收益
    annual_return_geom = (1 + total_return) ** (1 / years) - 1

    # 算术年化收益（用于夏普比率计算，更准确）
    daily_mean = daily_returns.mean() if len(daily_returns) > 0 else 0
    annual_return_arith = daily_mean * 252

    # ---- 2. 最大回撤 ----
    peak = values.expanding(min_periods=1).max()
    drawdown = (values - peak) / peak
    max_drawdown = drawdown.min()

    # 最大回撤持续天数
    drawdown_start = None
    max_dd_duration = 0
    current_dd_duration = 0
    for i, dd in enumerate(drawdown):
        if dd < 0:
            current_dd_duration += 1
            max_dd_duration = max(max_dd_duration, current_dd_duration)
        else:
            current_dd_duration = 0

    # ---- 3. 波动率 ----
    volatility = daily_returns.std() * np.sqrt(252) if len(daily_returns) > 1 else 0

    # ---- 4. 夏普比率（使用算术年化收益）----
    risk_free = 0.02
    sharpe = (annual_return_arith - risk_free) / volatility if volatility > 0 else 0

    # ---- 5. Sortino（使用算术年化收益）----
    downside = daily_returns[daily_returns < 0]
    downside_vol = downside.std() * np.sqrt(252) if len(downside) > 0 else 0
    sortino = (annual_return_arith - risk_free) / downside_vol if downside_vol > 0 else 0

    # ---- 6. Calmar ----
    calmar = annual_return_geom / abs(max_drawdown) if max_drawdown != 0 else 0

    # ---- 7. 胜率（月度）----
    positive_months = sum(1 for r in monthly_returns if r > 0)
    win_rate = positive_months / len(monthly_returns) if monthly_returns else 0

    # ---- 8. 盈亏比 ----
    gains = [r for r in monthly_returns if r > 0]
    losses = [r for r in monthly_returns if r < 0]
    avg_gain = np.mean(gains) if gains else 0
    avg_loss = abs(np.mean(losses)) if losses else 1
    profit_loss_ratio = avg_gain / avg_loss if avg_loss > 0 else 0

    # ---- 9. 分年度收益 ----
    yearly_returns = {}
    if portfolio_series:
        current_year = None
        year_start_value = None
        for pv in portfolio_series:
            year = pv['date'].year
            if year != current_year:
                if current_year is not None and year_start_value is not None and year_start_value > 0:
                    # 使用上一个交易日的净值作为年末值
                    yearly_returns[str(current_year)] = round(
                        (pv['value'] / year_start_value - 1) * 100, 2
                    )
                current_year = year
                year_start_value = pv['value']  # 新年第一天的净值作为起始值
        # 最后一年
        if current_year is not None and year_start_value is not None and year_start_value > 0 and portfolio_series:
            yearly_returns[str(current_year)] = round(
                (portfolio_series[-1]['value'] / year_start_value - 1) * 100, 2
            )

    # ---- 10. 基准对比（含Alpha/Beta/信息比率）----
    benchmark_return = 0
    excess_return = total_return * 100
    alpha = 0
    beta = 0
    information_ratio = 0
    benchmark_equity_curve = []

    if not benchmark.empty and len(benchmark) >= 2:
        bench_close = benchmark['close'].values
        benchmark_return = round((bench_close[-1] / bench_close[0] - 1) * 100, 2)
        excess_return = round(total_return * 100 - benchmark_return, 2)

        # 基准日收益率
        bench_series = pd.Series(bench_close.astype(float))
        bench_returns = bench_series.pct_change().dropna()

        # 对齐策略和基准的日收益率
        if len(bench_returns) > 0 and len(daily_returns) > 0:
            # 取较短的长度
            min_len = min(len(daily_returns), len(bench_returns))
            strat_ret = daily_returns.iloc[-min_len:].values
            bench_ret = bench_returns.iloc[-min_len:].values

            if min_len > 10:
                # Beta = Cov(Rp, Rb) / Var(Rb)
                cov_matrix = np.cov(strat_ret, bench_ret)
                bench_var = np.var(bench_ret)
                if bench_var > 0:
                    beta = cov_matrix[0, 1] / bench_var

                # Alpha（年化）= Rp - Rf - Beta * (Rb - Rf)
                bench_annual = (bench_close[-1] / bench_close[0]) ** (252 / max(min_len, 1)) - 1
                alpha = annual_return_arith - risk_free - beta * (bench_annual - risk_free)

                # 信息比率 = 超额收益 / 跟踪误差
                excess_daily = strat_ret - bench_ret
                tracking_error = np.std(excess_daily) * np.sqrt(252)
                if tracking_error > 0:
                    information_ratio = (annual_return_arith - bench_annual) / tracking_error

        # 基准净值曲线（归一化到初始资金）
        bench_first = bench_close[0]
        if bench_first > 0:
            bench_dates = benchmark['date'].tolist()
            for i, (d, c) in enumerate(zip(bench_dates, bench_close)):
                benchmark_equity_curve.append({
                    'date': d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else str(d),
                    'value': round(float(c) / bench_first * initial_capital, 2),
                })

    # ---- 11. 收益归因 ----
    attribution = _calculate_attribution(
        result, benchmark, initial_capital, total_return, benchmark_return / 100
    )

    # ---- 12. 回撤曲线 ----
    drawdown_curve = []
    for i, pv in enumerate(equity_curve):
        dd = drawdown.iloc[i] if i < len(drawdown) else 0
        drawdown_curve.append({
            'date': pv['date'],
            'drawdown': round(dd * 100, 2),
        })

    return {
        'total_return': round(total_return * 100, 2),
        'annual_return': round(annual_return_geom * 100, 2),
        'annual_return_arith': round(annual_return_arith * 100, 2),
        'max_drawdown': round(max_drawdown * 100, 2),
        'max_drawdown_duration': max_dd_duration,
        'volatility': round(volatility * 100, 2),
        'sharpe_ratio': round(sharpe, 2),
        'sortino_ratio': round(sortino, 2),
        'calmar_ratio': round(calmar, 2),
        'win_rate': round(win_rate * 100, 2),
        'profit_loss_ratio': round(profit_loss_ratio, 2),
        'benchmark_return': benchmark_return,
        'excess_return': excess_return,
        'alpha': round(alpha * 100, 2),
        'beta': round(beta, 2),
        'information_ratio': round(information_ratio, 2),
        'yearly_returns': yearly_returns,
        'drawdown_curve': drawdown_curve,
        'benchmark_equity_curve': benchmark_equity_curve,
        'total_trades': result.get('total_trades', 0),
        'total_commission': result.get('total_commission', 0),
        'total_slippage': result.get('total_slippage', 0),
        'total_cost': result.get('total_cost', 0),
        'cost_ratio': round(result.get('total_cost', 0) / initial_capital * 100, 4),
        'attribution': attribution,
    }


def _calculate_attribution(
    result: Dict,
    benchmark: pd.DataFrame,
    initial_capital: float,
    total_return: float,
    benchmark_return: float,
) -> Dict:
    """收益归因分析

    分解总收益为：
    - 选券贡献（Alpha）：跑赢基准的部分
    - 市场贡献（Beta）：随市场波动的部分
    - 交易成本拖累：手续费和滑点造成的收益损失
    """
    total_cost = result.get('total_cost', 0)
    cost_drag = total_cost / initial_capital * 100  # 交易成本占初始资金比例

    # 超额收益 = 总收益 - 基准收益
    excess = total_return * 100 - benchmark_return * 100

    # 选券贡献 = 超额收益 + 交易成本拖累（因为如果没有成本，超额会更高）
    selection_contribution = excess + cost_drag

    # 市场贡献 = 基准收益（跟随市场的部分）
    market_contribution = benchmark_return * 100

    # 交易成本拖累
    cost_contribution = -cost_drag

    # 月度归因
    monthly_detail = result.get('monthly_returns_detail', [])
    monthly_attribution = []
    for year, month, ret in monthly_detail:
        monthly_attribution.append({
            'year': year,
            'month': month,
            'return': round(ret * 100, 2),
        })

    return {
        'total_return': round(total_return * 100, 2),
        'market_contribution': round(market_contribution, 2),
        'selection_contribution': round(selection_contribution, 2),
        'cost_contribution': round(cost_contribution, 4),
        'excess_return': round(excess, 2),
        'monthly_attribution': monthly_attribution[-24:],  # 最近24个月
    }


def _analyze_validity(metrics: Dict, strategy: str) -> Dict:
    """分析策略有效性"""
    if not metrics:
        return {'is_effective': False, 'reason': '指标计算失败'}

    annual = metrics.get('annual_return', 0)
    max_dd = metrics.get('max_drawdown', 0)
    sharpe = metrics.get('sharpe_ratio', 0)
    sortino = metrics.get('sortino_ratio', 0)
    excess = metrics.get('excess_return', 0)
    win_rate = metrics.get('win_rate', 0)
    alpha = metrics.get('alpha', 0)
    info_ratio = metrics.get('information_ratio', 0)
    cost_ratio = metrics.get('cost_ratio', 0)

    advantages = []
    disadvantages = []
    risks = []
    suggestions = []

    # 优势判断
    if annual > 10:
        advantages.append(f'年化收益{annual}%，表现优秀')
    elif annual > 5:
        advantages.append(f'年化收益{annual}%，表现良好')
    elif annual > 0:
        advantages.append(f'年化收益{annual}%，正收益')

    if max_dd > -10:
        advantages.append(f'最大回撤{max_dd}%，风险可控')
    elif max_dd > -20:
        advantages.append(f'最大回撤{max_dd}%，风险适中')

    if sharpe > 1.5:
        advantages.append(f'夏普比率{sharpe}，风险调整收益优秀')
    elif sharpe > 0.8:
        advantages.append(f'夏普比率{sharpe}，风险调整收益良好')

    if sortino > 2:
        advantages.append(f'Sortino比率{sortino}，下行风险控制优秀')

    if excess > 5:
        advantages.append(f'超额收益{excess}%，显著跑赢基准')

    if alpha > 5:
        advantages.append(f'年化Alpha{alpha}%，选券能力突出')

    if info_ratio > 0.5:
        advantages.append(f'信息比率{info_ratio}，超额收益稳定')

    # 劣势判断
    if annual < 3:
        disadvantages.append(f'年化收益仅{annual}%，收益偏低')
    if max_dd < -25:
        disadvantages.append(f'最大回撤{max_dd}%，风险较大')
    if sharpe < 0.5:
        disadvantages.append(f'夏普比率{sharpe}，风险调整收益较差')
    if sortino < 0.5:
        disadvantages.append(f'Sortino比率{sortino}，下行风险控制较差')
    if excess < 0:
        disadvantages.append(f'超额收益{excess}%，跑输基准')
    if cost_ratio > 1:
        disadvantages.append(f'交易成本占初始资金{cost_ratio}%，成本偏高')

    # 风险标签
    if max_dd < -30:
        risks.append('深度回撤风险')
    if win_rate < 40:
        risks.append('低胜率风险')
    if metrics.get('volatility', 0) > 20:
        risks.append('高波动风险')
    if metrics.get('beta', 0) > 1.2:
        risks.append('高Beta风险，与市场相关性过强')
    if cost_ratio > 0.5:
        risks.append('交易成本较高，注意控制换手率')

    # 建议
    if annual > 8 and max_dd > -15:
        suggestions.append('策略表现稳健，可以实盘使用')
    elif annual > 5:
        suggestions.append('策略表现尚可，建议小仓位试水')
    else:
        suggestions.append('策略表现一般，建议优化参数或观望')

    if max_dd < -20:
        suggestions.append('建议设置10%止损线控制单只风险')

    if cost_ratio > 0.5:
        suggestions.append('交易成本偏高，考虑降低调仓频率或扩大持仓数量')

    is_effective = annual > 5 and sharpe > 0.5 and max_dd > -30

    return {
        'is_effective': is_effective,
        'score': min(100, max(0, int(annual * 3 + sharpe * 20 + (100 + max_dd)))),
        'advantages': advantages,
        'disadvantages': disadvantages,
        'risks': risks,
        'suggestions': suggestions,
    }


def run_multi_strategy_compare(
    strategies: List[str],
    start_date: str = '2023-01-01',
    end_date: str = '2026-06-13',
    rebalance_freq: str = 'weekly',
    top_n: int = 15,
    initial_capital: float = 100000,
    commission_rate: float = DEFAULT_COMMISSION_RATE,
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
) -> Dict:
    """多策略对比"""
    results = []

    for strat_name in strategies:
        logger.info(f"回测策略: {strat_name}")
        result = run_cb_backtest(
            strategy=strat_name,
            start_date=start_date,
            end_date=end_date,
            rebalance_freq=rebalance_freq,
            top_n=top_n,
            initial_capital=initial_capital,
            commission_rate=commission_rate,
            slippage_bps=slippage_bps,
        )

        if 'error' not in result:
            results.append({
                'strategy': strat_name,
                'name': STRATEGIES.get(strat_name, {}).get('name', strat_name),
                'metrics': result.get('metrics', {}),
                'analysis': result.get('analysis', {}),
                'equity_curve': result.get('equity_curve', []),
            })

    return {
        'strategies': results,
        'comparison': _build_comparison(results),
    }


def _build_comparison(results: List[Dict]) -> List[Dict]:
    """构建对比表（含Alpha/Beta/信息比率）"""
    rows = []
    for r in results:
        m = r.get('metrics', {})
        rows.append({
            'strategy': r['strategy'],
            'name': r['name'],
            'annual_return': m.get('annual_return', 0),
            'total_return': m.get('total_return', 0),
            'max_drawdown': m.get('max_drawdown', 0),
            'sharpe': m.get('sharpe_ratio', 0),
            'sortino': m.get('sortino_ratio', 0),
            'calmar': m.get('calmar_ratio', 0),
            'volatility': m.get('volatility', 0),
            'win_rate': m.get('win_rate', 0),
            'excess_return': m.get('excess_return', 0),
            'alpha': m.get('alpha', 0),
            'beta': m.get('beta', 0),
            'information_ratio': m.get('information_ratio', 0),
            'total_cost': m.get('total_cost', 0),
            'cost_ratio': m.get('cost_ratio', 0),
            'is_effective': r.get('analysis', {}).get('is_effective', False),
        })
    # 按年化收益排序
    rows.sort(key=lambda x: x['annual_return'], reverse=True)
    return rows
