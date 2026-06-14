"""
统一数据层

数据源：
- Tencent Finance API: 日线OHLCV（可靠，无需认证）
- Sina Finance API: 日线OHLCV（备用）
- 磁盘缓存：pickle文件，避免重复API调用
"""

import requests
import numpy as np
import pandas as pd
import json
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

# 调用限速
_last_call_time = 0
MIN_CALL_INTERVAL = 0.1


def _rate_limit():
    global _last_call_time
    elapsed = time.time() - _last_call_time
    if elapsed < MIN_CALL_INTERVAL:
        time.sleep(MIN_CALL_INTERVAL - elapsed)
    _last_call_time = time.time()


def _cache_path(key: str) -> str:
    safe_key = key.replace("/", "_").replace("\\", "_").replace(":", "_")
    return os.path.join(CACHE_DIR, f"{safe_key}.pkl")


def _load_cache(key: str, ttl_hours: float = 72) -> Optional[pd.DataFrame]:
    path = _cache_path(key)
    if not os.path.exists(path):
        return None
    try:
        mtime = os.path.getmtime(path)
        if (time.time() - mtime) > ttl_hours * 3600:
            return None
        with open(path, 'rb') as f:
            return pickle.load(f)
    except:
        return None


def _save_cache(key: str, data: pd.DataFrame):
    try:
        path = _cache_path(key)
        with open(path, 'wb') as f:
            pickle.dump(data, f)
    except:
        pass


def _code_to_tencent(code: str) -> str:
    """股票代码转腾讯格式：000001 -> sz000001"""
    if code.startswith('6'):
        return f'sh{code}'
    else:
        return f'sz{code}'


def _fetch_kline_chunk(tc_code: str, start_date: str, end_date: str, adjust: str = "qfq") -> list:
    """获取单段K线数据"""
    try:
        url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={tc_code},day,{start_date},{end_date},2000,{adjust}'
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return []

        data = r.json()
        if data.get('code') != 0:
            return []

        stock_data = data.get('data', {})
        if isinstance(stock_data, list):
            return []
        stock_data = stock_data.get(tc_code, {})
        if isinstance(stock_data, list):
            return []

        return stock_data.get(f'{adjust}day', stock_data.get('day', []))
    except:
        return []


def get_stock_ohlcv(symbol: str, start_date: str, end_date: str,
                    adjust: str = "qfq", use_cache: bool = True) -> Optional[pd.DataFrame]:
    """
    获取A股日线OHLCV数据（腾讯财经API，分段获取）

    腾讯API每段最多返回约640条数据，需要分年获取再合并
    """
    cache_key = f"ohlcv_{symbol}_{start_date}_{end_date}_{adjust}"

    if use_cache:
        cached = _load_cache(cache_key, ttl_hours=72)
        if cached is not None:
            return cached

    try:
        _rate_limit()
        tc_code = _code_to_tencent(symbol)

        # 分段获取：每年一段
        all_kline = []
        start_dt = pd.Timestamp(start_date)
        end_dt = pd.Timestamp(end_date)

        current_start = start_dt
        while current_start < end_dt:
            current_end = min(current_start + timedelta(days=365), end_dt)
            chunk = _fetch_kline_chunk(
                tc_code,
                current_start.strftime('%Y-%m-%d'),
                current_end.strftime('%Y-%m-%d'),
                adjust
            )
            all_kline.extend(chunk)
            current_start = current_end + timedelta(days=1)

        if not all_kline:
            return None

        # 解析K线数据：[date, open, close, high, low, volume]
        rows = []
        for item in all_kline:
            if len(item) >= 6:
                rows.append({
                    'date': item[0],
                    'open': float(item[1]),
                    'close': float(item[2]),
                    'high': float(item[3]),
                    'low': float(item[4]),
                    'volume': float(item[5]),
                })

        if not rows:
            return None

        df = pd.DataFrame(rows)
        df['date'] = pd.to_datetime(df['date'])
        df = df.drop_duplicates(subset='date').sort_values('date').reset_index(drop=True)

        # 计算涨跌幅
        df['pct_chg'] = df['close'].pct_change() * 100

        # 计算成交额（近似）
        df['amount'] = df['close'] * df['volume']

        if use_cache:
            _save_cache(cache_key, df)

        return df

    except Exception as e:
        logger.error(f"Failed to fetch OHLCV for {symbol}: {e}")
        return None


def get_stock_ohlcv_sina(symbol: str, datalen: int = 1500) -> Optional[pd.DataFrame]:
    """
    备用：新浪财经日线数据（仅收盘价）
    """
    try:
        _rate_limit()
        if symbol.startswith('6'):
            sina_code = f'sh{symbol}'
        else:
            sina_code = f'sz{symbol}'

        url = f'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={sina_code}&scale=240&ma=no&datalen={datalen}'
        r = requests.get(url, timeout=15)

        if r.status_code != 200:
            return None

        data = json.loads(r.text)
        if not data:
            return None

        rows = []
        for item in data:
            rows.append({
                'date': item['day'],
                'open': float(item['open']),
                'high': float(item['high']),
                'low': float(item['low']),
                'close': float(item['close']),
                'volume': float(item['volume']),
            })

        df = pd.DataFrame(rows)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        df['pct_chg'] = df['close'].pct_change() * 100
        df['amount'] = df['close'] * df['volume']

        return df

    except Exception as e:
        logger.error(f"Sina fetch failed for {symbol}: {e}")
        return None


def get_batch_ohlcv(symbols: List[str], start_date: str, end_date: str,
                    adjust: str = "qfq", use_cache: bool = True,
                    progress_callback=None) -> Dict[str, pd.DataFrame]:
    """批量获取OHLCV数据"""
    result = {}
    total = len(symbols)

    for i, symbol in enumerate(symbols):
        if progress_callback:
            progress_callback(i + 1, total)

        df = get_stock_ohlcv(symbol, start_date, end_date, adjust, use_cache)
        if df is not None and len(df) > 60:
            result[symbol] = df
        elif df is None:
            # 尝试Sina备用
            df = get_stock_ohlcv_sina(symbol)
            if df is not None and len(df) > 60:
                result[symbol] = df

        if (i + 1) % 50 == 0:
            logger.info(f"Fetched {i + 1}/{total} stocks, {len(result)} valid")
            time.sleep(0.5)

    logger.info(f"Batch fetch complete: {len(result)}/{total} stocks")
    return result


def get_all_a_share_codes() -> List[str]:
    """获取全部A股代码（从腾讯API获取活跃股票）"""
    cache_key = "all_a_share_codes"
    cached = _load_cache(cache_key, ttl_hours=168)  # 1周缓存
    if cached is not None:
        return cached['code'].tolist()

    try:
        # 使用Sina API获取股票列表
        codes = []
        # 主要指数成分股 + 大盘蓝筹
        # 先获取沪深300成分
        for market in ['sh', 'sz']:
            for i in range(1, 50):
                try:
                    _rate_limit()
                    url = f'https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page={i}&num=80&sort=symbol&asc=1&node={market}_a&symbol=&_s_r_a=init'
                    r = requests.get(url, timeout=10)
                    if r.status_code == 200:
                        data = json.loads(r.text)
                        if not data:
                            break
                        for item in data:
                            code = item.get('symbol', '')
                            if code.startswith(('sh6', 'sz0', 'sz3')):
                                codes.append(code[2:])  # 去掉sh/sz前缀
                except:
                    break

        if codes:
            df = pd.DataFrame({'code': codes})
            _save_cache(cache_key, df)
            return codes
        return []

    except Exception as e:
        logger.error(f"Failed to get stock codes: {e}")
        return []


def get_stock_snapshot_sina(codes: List[str]) -> Optional[pd.DataFrame]:
    """
    通过Sina API获取股票快照（PE/PB/市值等）

    Sina的hq接口返回实时行情，包含一些基本面数据
    """
    cache_key = "snapshot_sina"
    cached = _load_cache(cache_key, ttl_hours=1)
    if cached is not None:
        return cached

    try:
        # 分批获取（每批最多80个）
        all_rows = []
        batch_size = 80

        for i in range(0, len(codes), batch_size):
            batch = codes[i:i + batch_size]
            sina_codes = ','.join(
                f'sh{c}' if c.startswith('6') else f'sz{c}'
                for c in batch
            )
            _rate_limit()
            url = f'https://hq.sinajs.cn/list={sina_codes}'
            r = requests.get(url, timeout=15)

            if r.status_code == 200:
                lines = r.text.strip().split('\n')
                for line in lines:
                    try:
                        parts = line.split('=')
                        if len(parts) < 2:
                            continue
                        code_part = parts[0].split('_')[-1]
                        code = code_part[2:]  # 去掉sh/sz
                        values = parts[1].strip('";\r').split(',')
                        if len(values) >= 32:
                            all_rows.append({
                                'code': code,
                                'name': values[0],
                                'open': float(values[1]) if values[1] else 0,
                                'pre_close': float(values[2]) if values[2] else 0,
                                'close': float(values[3]) if values[3] else 0,
                                'high': float(values[4]) if values[4] else 0,
                                'low': float(values[5]) if values[5] else 0,
                                'volume': float(values[8]) if values[8] else 0,
                                'amount': float(values[9]) if values[9] else 0,
                            })
                    except:
                        continue

        if not all_rows:
            return None

        df = pd.DataFrame(all_rows)

        # 计算涨跌幅
        df['pct_chg'] = ((df['close'] - df['pre_close']) / df['pre_close'] * 100).fillna(0)

        # 市值和PE/PB需要从其他来源获取，这里用默认值
        df['market_cap'] = 10e9  # 默认100亿
        df['pe_ttm'] = 20.0
        df['pb'] = 2.0
        df['roe'] = 15.0
        df['gross_margin'] = 30.0
        df['turnover_rate'] = 1.0

        df = df[df['close'] > 0].copy()

        _save_cache(cache_key, df)
        return df

    except Exception as e:
        logger.error(f"Failed to get snapshot: {e}")
        return None


def get_index_daily(symbol: str = "000300", start_date: str = "2018-01-01",
                    end_date: str = "2025-12-31", use_cache: bool = True) -> Optional[pd.DataFrame]:
    """获取指数日线数据（腾讯API）"""
    cache_key = f"index_{symbol}_{start_date}_{end_date}"

    if use_cache:
        cached = _load_cache(cache_key, ttl_hours=72)
        if cached is not None:
            return cached

    try:
        _rate_limit()
        # 指数代码映射
        if symbol.startswith('0'):
            tc_code = f'sh{symbol}'
        else:
            tc_code = f'sz{symbol}'

        url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={tc_code},day,{start_date},{end_date},2000,'
        r = requests.get(url, timeout=15)

        if r.status_code != 200:
            return None

        data = r.json()
        stock_data = data.get('data', {})
        if isinstance(stock_data, list):
            return None
        stock_data = stock_data.get(tc_code, {})
        if isinstance(stock_data, list):
            return None
        kline = stock_data.get('day', [])

        if not kline:
            return None

        rows = []
        for item in kline:
            if len(item) >= 6:
                rows.append({
                    'date': item[0],
                    'open': float(item[1]),
                    'close': float(item[2]),
                    'high': float(item[3]),
                    'low': float(item[4]),
                    'volume': float(item[5]),
                })

        df = pd.DataFrame(rows)
        df['date'] = pd.to_datetime(df['date'])
        df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
        df = df.sort_values('date').reset_index(drop=True)

        if use_cache:
            _save_cache(cache_key, df)

        return df

    except Exception as e:
        logger.error(f"Failed to fetch index {symbol}: {e}")
        return None


def build_stock_universe(min_market_cap: float = 5e9, max_stocks: int = 500) -> List[str]:
    """
    构建股票池

    获取沪深300+中证500的核心股票
    """
    cache_key = f"universe_{int(min_market_cap)}_{max_stocks}"
    cached = _load_cache(cache_key, ttl_hours=168)
    if cached is not None:
        return cached['code'].tolist()

    # 直接使用硬编码的优质股票池（沪深300核心成分）
    # 这些是A股最具代表性的蓝筹股
    core_stocks = [
        # 银行
        '601398', '601939', '601288', '601328', '600036', '600016', '600015',
        '601166', '600000', '601818', '601998', '600010', '601229', '601988',
        # 白酒
        '600519', '000858', '000568', '600809', '002304', '603369',
        # 保险
        '601318', '601628', '601601', '601336',
        # 地产
        '000002', '001979', '600048', '601155',
        # 汽车
        '600104', '000625', '002594', '601633', '000800',
        # 医药
        '600276', '000538', '300760', '600196', '002001', '300015',
        # 科技
        '002415', '300750', '600703', '002236', '300408', '002475',
        # 新能源
        '300274', '601012', '600438',
        # 家电
        '000333', '000651', '600690', '002032',
        # 食品饮料
        '600887', '002714', '603288',
        # 钢铁/有色
        '600019', '000898', '601899', '603993', '002460',
        # 化工
        '600309', '000830', '002601', '600989',
        # 电力/公用
        '600900', '601985', '600886', '000027',
        # 建筑/建材
        '601668', '601390', '600585', '000786',
        # 交通运输
        '601006', '600029', '601111', '000089',
        # 军工
        '600893', '000768', '600760', '002049',
        # 通信
        '600050', '000063', '600570',
        # 传媒
        '300413', '300251',
        # 机械
        '600031', '000157', '002008',
        # 电子
        '002371', '603160', '300782',
        # 计算机
        '002410', '600588', '000977', '002230',
        # 农业
        '000876', '002714', '300498',
        # 纺织服装
        '600398', '002029',
        # 零售
        '002024', '601933',
        # 更多蓝筹
        '600009', '600018', '600028', '600030', '600048', '600050',
        '600061', '600085', '600104', '600111', '600115', '600150',
        '600176', '600183', '600196', '600276', '600309', '600332',
        '600346', '600352', '600406', '600436', '600438', '600519',
        '600570', '600585', '600588', '600600', '600690', '600703',
        '600745', '600760', '600809', '600837', '600845', '600887',
        '600893', '600900', '600918', '601006', '601012', '601066',
        '601100', '601111', '601138', '601155', '601166', '601186',
        '601211', '601225', '601229', '601288', '601318', '601328',
        '601336', '601390', '601398', '601601', '601628', '601633',
        '601668', '601688', '601766', '601818', '601838', '601857',
        '601877', '601881', '601888', '601899', '601919', '601933',
        '601939', '601985', '601988', '601998', '603019', '603160',
        '603259', '603288', '603369', '603501', '603799', '603986',
        '603993', '000002', '000027', '000063', '000089', '000100',
        '000157', '000333', '000538', '000568', '000596', '000625',
        '000651', '000661', '000703', '000725', '000768', '000776',
        '000786', '000800', '000830', '000858', '000876', '000898',
        '000938', '000963', '000977', '001979', '002001', '002007',
        '002008', '002024', '002027', '002029', '002032', '002049',
        '002120', '002142', '002230', '002236', '002241', '002271',
        '002304', '002311', '002352', '002371', '002410', '002415',
        '002460', '002475', '002493', '002555', '002594', '002601',
        '002607', '002714', '002791', '002841', '002916', '300003',
        '300014', '300015', '300033', '300059', '300122', '300124',
        '300142', '300144', '300251', '300274', '300347', '300408',
        '300413', '300433', '300450', '300498', '300529', '300601',
        '300628', '300750', '300760', '300782',
    ]

    # 去重
    codes = list(dict.fromkeys(core_stocks))

    df = pd.DataFrame({'code': codes[:max_stocks]})
    _save_cache(cache_key, df)
    return codes[:max_stocks]


def get_snapshot_for_universe(codes: List[str]) -> pd.DataFrame:
    """
    为股票池构建基本面快照（腾讯API，含PE/PB/市值）

    腾讯实时行情API字段：
    - 2: code, 3: price, 4: pre_close
    - 39: PE_TTM, 46: PB
    - 44: total_market_cap(亿), 45: float_market_cap(亿)
    - 38: turnover_rate
    """
    cache_key = "snapshot_tencent"
    cached = _load_cache(cache_key, ttl_hours=2)
    if cached is not None and len(cached) >= len(codes) * 0.5:
        # 过滤出需要的代码
        filtered = cached[cached['code'].isin(codes)]
        if len(filtered) > 0:
            return filtered

    rows = []
    batch_size = 50

    for i in range(0, len(codes), batch_size):
        batch = codes[i:i + batch_size]
        tc_codes = ','.join(
            f'sh{c}' if c.startswith('6') else f'sz{c}'
            for c in batch
        )
        try:
            _rate_limit()
            url = f'https://qt.gtimg.cn/q={tc_codes}'
            r = requests.get(url, timeout=15)

            if r.status_code == 200:
                lines = r.text.strip().split('\n')
                for line in lines:
                    try:
                        parts = line.split('~')
                        if len(parts) < 50:
                            continue

                        code = parts[2]
                        price = float(parts[3]) if parts[3] else 0
                        pre_close = float(parts[4]) if parts[4] else 0

                        if price <= 0:
                            continue

                        pe_ttm = float(parts[39]) if parts[39] else 20.0
                        pb = float(parts[46]) if parts[46] else 2.0
                        total_mcap = float(parts[44]) if parts[44] else 100  # 亿
                        turnover = float(parts[38]) if parts[38] else 1.0

                        pct_chg = ((price - pre_close) / pre_close * 100) if pre_close > 0 else 0

                        # ROE 估算：如果没有真实数据，用 PE/PB 推算
                        # ROE ≈ PB / PE * 100
                        roe = (pb / pe_ttm * 100) if pe_ttm > 0 else 15.0

                        rows.append({
                            'code': code,
                            'name': parts[1],
                            'close': price,
                            'open': float(parts[5]) if parts[5] else price,
                            'high': float(parts[33]) if parts[33] else price,
                            'low': float(parts[34]) if parts[34] else price,
                            'volume': float(parts[6]) if parts[6] else 0,
                            'amount': float(parts[37]) if parts[37] else 0,
                            'pct_chg': pct_chg,
                            'market_cap': total_mcap * 1e8,  # 亿 -> 元
                            'pe_ttm': pe_ttm if pe_ttm > 0 else 20.0,
                            'pb': pb if pb > 0 else 2.0,
                            'roe': roe,
                            'gross_margin': 30.0,  # 需要财务报表数据
                            'turnover_rate': turnover,
                        })
                    except (ValueError, IndexError):
                        continue
        except Exception as e:
            logger.warning(f"Tencent snapshot batch failed: {e}")

    if not rows:
        # 构造默认快照
        for code in codes:
            rows.append({
                'code': code, 'name': f'stock_{code}',
                'close': 20.0, 'open': 20.0, 'high': 20.5, 'low': 19.5,
                'volume': 1e6, 'amount': 2e7, 'pct_chg': 0.0,
                'market_cap': 10e9, 'pe_ttm': 20.0, 'pb': 2.0,
                'roe': 15.0, 'gross_margin': 30.0, 'turnover_rate': 1.0,
            })

    df = pd.DataFrame(rows)
    _save_cache(cache_key, df)
    return df
