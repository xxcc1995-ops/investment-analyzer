"""
财务数据获取器

使用AKShare获取真实财务指标：
- ROE（净资产收益率）
- 毛利率
- 营收增长率
- 净利润增长率
- 资产负债率

AKShare的stock_financial_analysis_indicator返回GBK编码的列名，
通过位置索引映射。
"""

import akshare as ak
import numpy as np
import pandas as pd
import logging
import time
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)

# AKShare财务指标列位置映射（GBK编码，按位置索引）
COL_MAP = {
    'date': 0,           # 日期
    'eps_diluted': 1,    # 摊薄每股收益
    'roe': 11,           # 净资产收益率(%)
    'revenue_growth': 12, # 主营业务收入增长率(%)
    'operating_margin': 15, # 营业利润率(%)
    'gross_margin': 21,  # 销售毛利率(%)
    'net_profit_growth': 32, # 净利润增长率(%)
    'debt_ratio': 61,    # 资产负债率(%)
    'current_ratio': 45, # 流动比率
}


def get_financial_indicators(symbol: str, start_year: int = 2020) -> Optional[pd.DataFrame]:
    """
    获取单只股票的财务指标

    Args:
        symbol: 股票代码（6位）
        start_year: 开始年份

    Returns:
        DataFrame with columns: [date, roe, gross_margin, revenue_growth, profit_growth, debt_ratio]
    """
    try:
        time.sleep(0.2)  # AKShare限速
        df = ak.stock_financial_analysis_indicator(symbol=symbol, start_year=start_year)

        if df is None or df.empty:
            return None

        # 按位置提取列
        result = pd.DataFrame()
        result['date'] = pd.to_datetime(df.iloc[:, COL_MAP['date']])
        result['roe'] = pd.to_numeric(df.iloc[:, COL_MAP['roe']], errors='coerce')
        result['gross_margin'] = pd.to_numeric(df.iloc[:, COL_MAP['gross_margin']], errors='coerce')
        result['revenue_growth'] = pd.to_numeric(df.iloc[:, COL_MAP['revenue_growth']], errors='coerce')
        result['profit_growth'] = pd.to_numeric(df.iloc[:, COL_MAP['net_profit_growth']], errors='coerce')
        result['debt_ratio'] = pd.to_numeric(df.iloc[:, COL_MAP['debt_ratio']], errors='coerce')
        result['operating_margin'] = pd.to_numeric(df.iloc[:, COL_MAP['operating_margin']], errors='coerce')

        result = result.sort_values('date').reset_index(drop=True)

        return result

    except Exception as e:
        logger.warning(f"Failed to get financial data for {symbol}: {e}")
        return None


def get_batch_financials(symbols: List[str], start_year: int = 2020,
                         progress_callback=None) -> Dict[str, pd.DataFrame]:
    """
    批量获取财务数据

    Args:
        symbols: 股票代码列表
        start_year: 开始年份
        progress_callback: 进度回调 (current, total)

    Returns:
        {symbol: DataFrame}
    """
    result = {}
    total = len(symbols)

    for i, symbol in enumerate(symbols):
        if progress_callback:
            progress_callback(i + 1, total)

        df = get_financial_indicators(symbol, start_year)
        if df is not None and len(df) > 0:
            result[symbol] = df

        if (i + 1) % 20 == 0:
            logger.info(f"Fetched financials: {i + 1}/{total}, {len(result)} valid")

    logger.info(f"Financial data fetch complete: {len(result)}/{total} stocks")
    return result


def get_latest_financials(symbols: List[str]) -> pd.DataFrame:
    """
    获取每只股票的最新财务指标

    Returns:
        DataFrame with columns: [code, roe, gross_margin, revenue_growth, profit_growth, debt_ratio]
    """
    rows = []

    for symbol in symbols:
        df = get_financial_indicators(symbol, start_year=2022)
        if df is not None and len(df) > 0:
            latest = df.iloc[-1]
            rows.append({
                'code': symbol,
                'roe': latest.get('roe', 15.0),
                'gross_margin': latest.get('gross_margin', 30.0),
                'revenue_growth': latest.get('revenue_growth', 10.0),
                'profit_growth': latest.get('profit_growth', 10.0),
                'debt_ratio': latest.get('debt_ratio', 50.0),
                'operating_margin': latest.get('operating_margin', 15.0),
            })

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows)


def enrich_snapshot_with_financials(snapshot: pd.DataFrame,
                                     financials: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    用真实财务数据增强快照

    将AKShare获取的ROE/毛利率/增长率等填充到snapshot中
    """
    df = snapshot.copy()

    for code, fin_df in financials.items():
        if fin_df.empty:
            continue

        latest = fin_df.iloc[-1]
        mask = df['code'] == code

        if mask.any():
            if 'roe' in latest and not pd.isna(latest['roe']):
                df.loc[mask, 'roe'] = latest['roe']
            if 'gross_margin' in latest and not pd.isna(latest['gross_margin']):
                df.loc[mask, 'gross_margin'] = latest['gross_margin']
            if 'revenue_growth' in latest and not pd.isna(latest['revenue_growth']):
                df.loc[mask, 'revenue_growth'] = latest['revenue_growth']
            if 'profit_growth' in latest and not pd.isna(latest['profit_growth']):
                df.loc[mask, 'profit_growth'] = latest['profit_growth']
            if 'debt_ratio' in latest and not pd.isna(latest['debt_ratio']):
                df.loc[mask, 'debt_ratio'] = latest['debt_ratio']

    return df
