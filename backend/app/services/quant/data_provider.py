"""
统一数据层

数据源：
- AKShare: 日线OHLCV（ak.stock_zh_a_hist）、全市场快照（ak.stock_zh_a_spot_em）、指数（ak.stock_zh_index_daily_em）
- EastMoney: 财务报表（复用 data_service.py）
- 磁盘缓存：pickle文件，避免重复API调用

参考模式：cb_backtest_service.py 的缓存+限速架构
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

logger = logging.getLogger(__name__)

# 缓存目录
CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '..', '.cache', 'quant_backtest')
os.makedirs(CACHE_DIR, exist_ok=True)

# AKShare 调用限速
_last_call_time = 0
MIN_CALL_INTERVAL = 0.15  # 150ms


def _rate_limit():
    """AKShare 调用限速"""
    global _last_call_time
    elapsed = time.time() - _last_call_time
    if elapsed < MIN_CALL_INTERVAL:
        time.sleep(MIN_CALL_INTERVAL - elapsed)
    _last_call_time = time.time()


def _cache_path(key: str) -> str:
    """缓存文件路径"""
    safe_key = key.replace("/", "_").replace("\\", "_").replace(":", "_")
    return os.path.join(CACHE_DIR, f"{safe_key}.pkl")


def _load_cache(key: str, ttl_hours: float = 72) -> Optional[pd.DataFrame]:
    """从磁盘缓存加载"""
    path = _cache_path(key)
    if not os.path.exists(path):
        return None
    try:
        mtime = os.path.getmtime(path)
        if (time.time() - mtime) > ttl_hours * 3600:
            return None
        with open(path, 'rb') as f:
            return pickle.load(f)
    except Exception as e:
        logger.warning(f"Cache load failed for {key}: {e}")
        return None


def _save_cache(key: str, data: pd.DataFrame):
    """保存到磁盘缓存"""
    try:
        path = _cache_path(key)
        with open(path, 'wb') as f:
            pickle.dump(data, f)
    except Exception as e:
        logger.warning(f"Cache save failed for {key}: {e}")


def get_stock_ohlcv(symbol: str, start_date: str, end_date: str,
                    adjust: str = "qfq", use_cache: bool = True) -> Optional[pd.DataFrame]:
    """
    获取A股日线OHLCV数据

    Args:
        symbol: 股票代码（6位，如 "000001"）
        start_date: 开始日期 "YYYY-MM-DD"
        end_date: 结束日期 "YYYY-MM-DD"
        adjust: 复权方式 "qfq"=前复权, "hfq"=后复权, ""=不复权
        use_cache: 是否使用缓存

    Returns:
        DataFrame with columns: [date, open, high, low, close, volume, amount]
    """
    cache_key = f"ohlcv_{symbol}_{start_date}_{end_date}_{adjust}"

    if use_cache:
        cached = _load_cache(cache_key, ttl_hours=72)
        if cached is not None:
            return cached

    try:
        _rate_limit()
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
            adjust=adjust
        )

        if df is None or df.empty:
            logger.warning(f"No OHLCV data for {symbol}")
            return None

        # 标准化列名
        df = df.rename(columns={
            '日期': 'date', '开盘': 'open', '收盘': 'close',
            '最高': 'high', '最低': 'low', '成交量': 'volume',
            '成交额': 'amount', '涨跌幅': 'pct_chg'
        })

        # 确保日期格式
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)

        # 只保留需要的列
        cols = ['date', 'open', 'high', 'low', 'close', 'volume', 'amount']
        if 'pct_chg' in df.columns:
            cols.append('pct_chg')
        df = df[[c for c in cols if c in df.columns]]

        if use_cache:
            _save_cache(cache_key, df)

        return df

    except Exception as e:
        logger.error(f"Failed to fetch OHLCV for {symbol}: {e}")
        return None


def get_stock_snapshot(use_cache: bool = True) -> Optional[pd.DataFrame]:
    """
    获取全A股实时快照（PE/PB/市值/换手率等）

    使用 ak.stock_zh_a_spot_em() 一次性获取全市场数据

    Returns:
        DataFrame with columns: [code, name, pe_ttm, pb, market_cap, turnover_rate, ...]
    """
    cache_key = "a_share_snapshot"

    if use_cache:
        cached = _load_cache(cache_key, ttl_hours=1)  # 快照数据1小时缓存
        if cached is not None:
            return cached

    try:
        _rate_limit()
        df = ak.stock_zh_a_spot_em()

        if df is None or df.empty:
            logger.warning("No snapshot data")
            return None

        # 标准化列名
        df = df.rename(columns={
            '代码': 'code', '名称': 'name',
            '最新价': 'close', '涨跌幅': 'pct_chg',
            '市盈率-动态': 'pe_ttm', '市净率': 'pb',
            '总市值': 'market_cap', '流通市值': 'float_market_cap',
            '换手率': 'turnover_rate', '量比': 'volume_ratio',
            '60日涨跌幅': 'pct_60d', '年初至今涨跌幅': 'pct_ytd',
            '成交额': 'amount',
        })

        # 过滤有效数据
        df = df[df['code'].notna()].copy()

        # 确保数值类型
        for col in ['close', 'pe_ttm', 'pb', 'market_cap', 'float_market_cap',
                     'turnover_rate', 'pct_chg', 'amount']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        if use_cache:
            _save_cache(cache_key, df)

        return df

    except Exception as e:
        logger.error(f"Failed to fetch snapshot: {e}")
        return None


def get_index_daily(symbol: str = "000300", start_date: str = "2018-01-01",
                    end_date: str = "2025-12-31", use_cache: bool = True) -> Optional[pd.DataFrame]:
    """
    获取指数日线数据

    Args:
        symbol: 指数代码，如 "000300"(沪深300), "000905"(中证500), "000852"(中证1000)
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        DataFrame with columns: [date, open, high, low, close, volume, amount]
    """
    cache_key = f"index_{symbol}_{start_date}_{end_date}"

    if use_cache:
        cached = _load_cache(cache_key, ttl_hours=72)
        if cached is not None:
            return cached

    try:
        _rate_limit()
        df = ak.stock_zh_index_daily_em(symbol=f"sh{symbol}")

        if df is None or df.empty:
            # 尝试深市
            _rate_limit()
            df = ak.stock_zh_index_daily_em(symbol=f"sz{symbol}")

        if df is None or df.empty:
            logger.warning(f"No index data for {symbol}")
            return None

        # 标准化列名
        df = df.rename(columns={
            '日期': 'date', '开盘': 'open', '收盘': 'close',
            '最高': 'high', '最低': 'low', '成交量': 'volume',
            '成交额': 'amount'
        })

        df['date'] = pd.to_datetime(df['date'])
        df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
        df = df.sort_values('date').reset_index(drop=True)

        if use_cache:
            _save_cache(cache_key, df)

        return df

    except Exception as e:
        logger.error(f"Failed to fetch index {symbol}: {e}")
        return None


def get_batch_ohlcv(symbols: List[str], start_date: str, end_date: str,
                    adjust: str = "qfq", use_cache: bool = True,
                    progress_callback=None) -> Dict[str, pd.DataFrame]:
    """
    批量获取多只股票的OHLCV数据

    Args:
        symbols: 股票代码列表
        start_date: 开始日期
        end_date: 结束日期
        adjust: 复权方式
        use_cache: 是否使用缓存
        progress_callback: 进度回调 (current, total)

    Returns:
        {symbol: DataFrame} 字典
    """
    result = {}
    total = len(symbols)

    for i, symbol in enumerate(symbols):
        if progress_callback:
            progress_callback(i + 1, total)

        df = get_stock_ohlcv(symbol, start_date, end_date, adjust, use_cache)
        if df is not None and len(df) > 60:  # 至少60个交易日数据
            result[symbol] = df

        # 每50只股票暂停一下，避免API限制
        if (i + 1) % 50 == 0:
            time.sleep(1.0)
            logger.info(f"Fetched {i + 1}/{total} stocks")

    logger.info(f"Batch fetch complete: {len(result)}/{total} stocks with valid data")
    return result


def get_financial_snapshot(symbol: str) -> Optional[Dict]:
    """
    获取单只股票的基本面数据（从全市场快照中提取）

    避免逐只调用，使用缓存的全市场快照
    """
    snapshot = get_stock_snapshot()
    if snapshot is None:
        return None

    row = snapshot[snapshot['code'] == symbol]
    if row.empty:
        return None

    return row.iloc[0].to_dict()
