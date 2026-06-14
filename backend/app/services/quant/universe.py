"""
股票池构建

动态构建符合量化策略要求的股票池：
- 排除 ST/*ST
- 上市天数过滤
- 流动性过滤（日均成交额）
- 市值过滤
- 涨跌停检查
"""

import numpy as np
import pandas as pd
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict

from .data_provider import get_stock_snapshot

logger = logging.getLogger(__name__)


def build_universe(
    min_market_cap: float = 2e9,
    max_market_cap: Optional[float] = None,
    min_avg_turnover: float = 5e6,
    min_listing_days: int = 250,
    exclude_st: bool = True,
    exclude_new: bool = True,
) -> pd.DataFrame:
    """
    构建股票池

    Args:
        min_market_cap: 最低市值（元），默认20亿
        max_market_cap: 最高市值（元），None表示不限
        min_avg_turnover: 最低日均成交额（元），默认500万
        min_listing_days: 最低上市天数，默认250个交易日（约1年）
        exclude_st: 排除ST股票
        exclude_new: 排除次新股

    Returns:
        符合条件的股票DataFrame
    """
    snapshot = get_stock_snapshot()
    if snapshot is None or snapshot.empty:
        logger.error("Cannot build universe: no snapshot data")
        return pd.DataFrame()

    df = snapshot.copy()

    # 1. 排除ST
    if exclude_st:
        df = df[~df['name'].str.contains('ST|\\*ST|退市', case=False, na=False)]

    # 2. 排除停牌（最新价为0或NaN）
    df = df[df['close'].notna() & (df['close'] > 0)]

    # 3. 市值过滤
    if 'market_cap' in df.columns:
        df = df[df['market_cap'].notna()]
        df = df[df['market_cap'] >= min_market_cap]
        if max_market_cap is not None:
            df = df[df['market_cap'] <= max_market_cap]

    # 4. 成交额过滤
    if 'amount' in df.columns:
        df = df[df['amount'].notna()]
        df = df[df['amount'] >= min_avg_turnover]

    # 5. 排除涨跌停（涨跌幅接近10%的股票无法交易）
    if 'pct_chg' in df.columns:
        df = df[df['pct_chg'].notna()]
        df = df[(df['pct_chg'] > -9.9) & (df['pct_chg'] < 9.9)]

    # 6. 只保留A股主板（排除北交所等）
    df = df[df['code'].str.match(r'^(00|30|60)')]

    df = df.reset_index(drop=True)
    logger.info(f"Universe built: {len(df)} stocks")
    return df


def check_tradeable(code: str, pct_chg: float) -> bool:
    """
    检查股票是否可交易

    Args:
        code: 股票代码
        pct_chg: 当日涨跌幅（%）

    Returns:
        是否可交易
    """
    # 涨跌停检查（A股10%限制，创业板/科创板20%）
    if code.startswith('30') or code.startswith('68'):
        # 创业板/科创板 20%涨跌停
        return abs(pct_chg) < 19.9
    else:
        # 主板 10%涨跌停
        return abs(pct_chg) < 9.9


def filter_universe_for_strategy(
    universe: pd.DataFrame,
    strategy_type: str = 'multi_factor',
    codes_with_data: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    根据策略类型进一步过滤股票池

    Args:
        universe: 基础股票池
        strategy_type: 策略类型
        codes_with_data: 有历史数据的股票代码列表

    Returns:
        过滤后的股票池
    """
    df = universe.copy()

    # 只保留有历史数据的股票
    if codes_with_data is not None:
        df = df[df['code'].isin(codes_with_data)]

    if strategy_type == 'mean_reversion':
        # 均值回归：聚焦中盘股（20-500亿）
        if 'market_cap' in df.columns:
            df = df[(df['market_cap'] >= 2e9) & (df['market_cap'] <= 50e9)]

    elif strategy_type == 'trend_following':
        # 趋势跟踪：需要足够的流动性
        if 'amount' in df.columns:
            df = df[df['amount'] >= 1e7]  # 日均成交1000万+

    elif strategy_type == 'pairs_trading':
        # 配对交易：需要同行业股票
        pass  # 由配对策略自行处理

    elif strategy_type == 'multi_factor':
        # 多因子：全市场
        pass

    return df


def get_sector_mapping() -> Dict[str, str]:
    """
    获取行业分类映射

    简化版：基于股票代码前缀的粗略分类
    实际应使用申万行业分类
    """
    return {
        # 金融
        '601': 'finance', '600000': 'finance', '600015': 'finance',
        '600016': 'finance', '600036': 'finance', '601318': 'finance',
        '601328': 'finance', '601398': 'finance', '601939': 'finance',
        '601988': 'finance', '601998': 'finance',
        # 白酒/消费
        '600519': 'consumer', '000858': 'consumer', '000568': 'consumer',
        '600809': 'consumer', '002304': 'consumer',
        # 医药
        '600276': 'pharma', '000538': 'pharma', '300760': 'pharma',
        # 科技
        '002415': 'tech', '300750': 'tech', '600703': 'tech',
        # 新能源
        '300274': 'energy', '601012': 'energy', '600438': 'energy',
    }


def get_industry_from_code(code: str) -> str:
    """从代码获取行业（简化版）"""
    mapping = get_sector_mapping()
    # 先精确匹配
    if code in mapping:
        return mapping[code]
    # 再前缀匹配
    for prefix, sector in mapping.items():
        if code.startswith(prefix):
            return sector
    return 'other'
