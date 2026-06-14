"""基金相关公共工具函数

提供基金EST净值估算和持仓查询的共享基础设施：
- 带重试和连接池的HTTP会话
- 新浪/东方财富数据获取（带缓存和限流）
- 底层资产价格解析
- 市场状态判断
"""

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.core.cache import (
    TTL_DAILY,
    TTL_REALTIME,
    TTL_WEEKLY,
    cached,
    get_cache,
    get_realtime_ttl,
    set_cache,
)
from app.core.rate_limiter import eastmoney_limiter, sina_limiter
from app.core.utils import safe_float, safe_float_or_zero

logger = logging.getLogger(__name__)

# ==================== 共享HTTP会话 ====================
_session = requests.Session()
_adapter = HTTPAdapter(
    pool_connections=10,
    pool_maxsize=20,
    max_retries=Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
    ),
)
_session.mount("https://", _adapter)
_session.mount("http://", _adapter)
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
})


# ==================== 新浪数据获取 ====================


def get_sina_realtime(symbols: List[str]) -> Dict[str, List[str]]:
    """批量获取新浪财经实时行情数据（带缓存和限流）

    Args:
        symbols: 新浪格式的代码列表，如 ['sh501312', 'gb_qqq', 'rt_hkHSI']

    Returns:
        {symbol: [field0, field1, ...]} 字典
    """
    if not symbols:
        return {}

    cache_key = f"sina_rt:{','.join(sorted(symbols))}"
    cached_data = get_cache(cache_key, TTL_REALTIME)
    if cached_data is not None:
        return cached_data

    try:
        sina_limiter.wait()
        url = f"https://hq.sinajs.cn/list={','.join(symbols)}"
        headers = {"Referer": "https://finance.sina.com.cn/"}
        r = _session.get(url, headers=headers, timeout=10)
        r.encoding = "gbk"

        result: Dict[str, List[str]] = {}
        for line in r.text.strip().split("\n"):
            if '="' not in line:
                continue
            match = re.match(r'var hq_str_(\w+)="(.*)";', line)
            if match:
                symbol = match.group(1)
                data = match.group(2)
                if data:
                    result[symbol] = data.split(",")

        if result:
            set_cache(cache_key, result)
        return result
    except Exception as e:
        logger.warning(f"获取新浪实时数据失败 ({len(symbols)}个代码): {e}")
        return {}


# ==================== 东方财富基金净值 ====================


def get_fund_nav_from_eastmoney(fund_code: str) -> dict:
    """从东方财富获取基金最新官方净值（带缓存和限流）

    优先使用估值API（返回净值+估值），降级到历史净值API。

    Args:
        fund_code: 纯数字基金代码，如 '161130'

    Returns:
        {
            'fund_code': str,
            'name': str,
            'nav_date': str,       # 净值日期 YYYY-MM-DD
            'nav': float,          # 单位净值
            'est_nav': float,      # 估算净值（如有）
            'est_change': str,     # 估算涨跌幅%
            'est_time': str,       # 估算时间
        }
        失败返回空字典
    """
    if not fund_code:
        return {}

    cache_key = f"fund_nav:{fund_code}"
    ttl = get_realtime_ttl()
    cached_data = get_cache(cache_key, ttl)
    if cached_data is not None:
        return cached_data

    headers = {"Referer": "https://fund.eastmoney.com/"}

    # 方法1：东方财富基金估值API（包含最新净值和实时估值）
    try:
        eastmoney_limiter.wait()
        url = f"https://fundgz.1234567.com.cn/js/{fund_code}.js"
        r = _session.get(url, headers=headers, timeout=10)
        match = re.search(r"jsonpgz\((.*)\)", r.text)
        if match:
            data = json.loads(match.group(1))
            nav = safe_float(data.get("dwjz"), 0)
            if nav > 0:
                result = {
                    "fund_code": data.get("fundcode", fund_code),
                    "name": data.get("name", ""),
                    "nav_date": data.get("jzrq", ""),
                    "nav": nav,
                    "est_nav": safe_float(data.get("gsz"), 0),
                    "est_change": data.get("gszzl", "0"),
                    "est_time": data.get("gztime", ""),
                }
                set_cache(cache_key, result)
                return result
    except Exception as e:
        logger.debug(f"获取基金估值API失败 {fund_code}: {e}")

    # 方法2：东方财富历史净值API
    try:
        eastmoney_limiter.wait()
        url2 = f"https://fund.eastmoney.com/pingzhongdata/{fund_code}.js"
        r2 = _session.get(url2, headers=headers, timeout=10)
        m = re.search(r"Data_netWorthTrend\s*=\s*(\[.*?\]);", r2.text)
        if m:
            data = json.loads(m.group(1))
            if data:
                last = data[-1]
                nav_date = datetime.fromtimestamp(last["x"] / 1000).strftime(
                    "%Y-%m-%d"
                )
                result = {
                    "fund_code": fund_code,
                    "name": "",
                    "nav_date": nav_date,
                    "nav": last["y"],
                    "est_nav": 0,
                    "est_change": "0",
                    "est_time": "",
                }
                set_cache(cache_key, result)
                return result
    except Exception as e:
        logger.warning(f"获取基金净值失败 {fund_code}: {e}")

    return {}


def get_fund_nav_batch(fund_codes: List[str], max_workers: int = 5) -> Dict[str, dict]:
    """批量获取基金净值（并发执行，带缓存）

    使用线程池并发请求东方财富API，比串行调用快5-10倍。
    每个基金独立处理异常，一个失败不影响其他。

    Args:
        fund_codes: 纯数字基金代码列表，如 ['161130', '161125']
        max_workers: 最大并发数（默认5，避免触发限流）

    Returns:
        {fund_code: nav_info_dict} 字典，失败的基金不包含在结果中
    """
    if not fund_codes:
        return {}

    # 先检查缓存，只对未命中的基金发起请求
    results: Dict[str, dict] = {}
    codes_to_fetch: List[str] = []
    realtime_ttl = get_realtime_ttl()

    for code in fund_codes:
        cache_key = f"fund_nav:{code}"
        cached = get_cache(cache_key, realtime_ttl)
        if cached is not None:
            results[code] = cached
        else:
            codes_to_fetch.append(code)

    if not codes_to_fetch:
        return results

    # 并发获取未缓存的基金净值
    def _fetch_one(code: str) -> Tuple[str, Optional[dict]]:
        try:
            nav_info = get_fund_nav_from_eastmoney(code)
            return (code, nav_info if nav_info else None)
        except Exception as e:
            logger.debug(f"批量获取基金净值失败 {code}: {e}")
            return (code, None)

    with ThreadPoolExecutor(max_workers=min(max_workers, len(codes_to_fetch))) as executor:
        futures = {executor.submit(_fetch_one, code): code for code in codes_to_fetch}
        for future in as_completed(futures):
            try:
                code, nav_info = future.result(timeout=15)
                if nav_info:
                    results[code] = nav_info
            except Exception as e:
                logger.warning(f"批量获取基金净值异常: {e}")

    return results


# ==================== 汇率 ====================


def get_usdcny_rate() -> float:
    """获取美元人民币中间价（带缓存）

    优先从中国外汇交易中心获取，降级到新浪外汇。
    缓存1小时（汇率日内波动极小）。

    Returns:
        USD/CNY 汇率，失败返回默认值 7.25
    """
    cache_key = "usdcny_rate"
    cached_rate = get_cache(cache_key, TTL_DAILY)
    if cached_rate is not None:
        return cached_rate

    # 方法1：中国外汇交易中心
    try:
        url = "https://www.chinamoney.com.cn/r/cms/www/chinamoney/data/fx/ccpr.json"
        r = _session.get(url, timeout=10)
        data = r.json()
        for record in data.get("records", []):
            if record.get("ccyPair") == "USD/CNY":
                values = record.get("values", [{}])
                if values:
                    rate = safe_float(values[0].get("midPrice"))
                    if rate and rate > 0:
                        set_cache(cache_key, rate)
                        return rate
    except Exception as e:
        logger.debug(f"获取中国外汇交易中心汇率失败: {e}")

    # 方法2：新浪外汇
    try:
        sina_data = get_sina_realtime(["fx_susdcny"])
        if "fx_susdcny" in sina_data and len(sina_data["fx_susdcny"]) > 1:
            rate = safe_float(sina_data["fx_susdcny"][1])
            if rate and rate > 0:
                set_cache(cache_key, rate)
                return rate
    except Exception as e:
        logger.debug(f"获取新浪汇率失败: {e}")

    logger.warning("获取USD/CNY汇率失败，使用默认值 7.25")
    return 7.25


def get_hkdcny_rate() -> float:
    """获取港币人民币汇率（带缓存）

    优先从新浪外汇获取实时汇率，降级到基于USD/CNY和USD/HKD交叉计算。
    缓存1小时。

    Returns:
        HKD/CNY 汇率，失败返回默认值 0.92
    """
    cache_key = "hkdcny_rate"
    cached_rate = get_cache(cache_key, TTL_DAILY)
    if cached_rate is not None:
        return cached_rate

    # 方法1：新浪外汇直接获取 HKD/CNY
    try:
        sina_data = get_sina_realtime(["fx_shkdcny"])
        if "fx_shkdcny" in sina_data and len(sina_data["fx_shkdcny"]) > 1:
            rate = safe_float(sina_data["fx_shkdcny"][1])
            if rate and rate > 0:
                set_cache(cache_key, rate)
                return rate
    except Exception as e:
        logger.debug(f"获取新浪HKD/CNY汇率失败: {e}")

    # 方法2：通过USD/CNY和USD/HKD交叉计算
    try:
        usdcny = get_usdcny_rate()
        sina_data = get_sina_realtime(["fx_susdhkd"])
        if "fx_susdhkd" in sina_data and len(sina_data["fx_susdhkd"]) > 1:
            usdhkd = safe_float(sina_data["fx_susdhkd"][1])
            if usdhkd and usdhkd > 0:
                rate = round(usdcny / usdhkd, 4)
                set_cache(cache_key, rate)
                return rate
    except Exception as e:
        logger.debug(f"交叉计算HKD/CNY汇率失败: {e}")

    # 方法3：使用USD/CNY近似计算（USD/HKD约7.78-7.85）
    try:
        usdcny = get_usdcny_rate()
        rate = round(usdcny / 7.82, 4)  # 近似中间值
        set_cache(cache_key, rate)
        return rate
    except Exception:
        pass

    logger.warning("获取HKD/CNY汇率失败，使用默认值 0.92")
    return 0.92


# ==================== EST历史准确度跟踪 ====================

# 存储结构：{fund_code: [{"date", "est_nav", "official_nav", "deviation"}, ...]}
_est_accuracy_history: Dict[str, list] = {}
_MAX_HISTORY_DAYS = 60  # 保留最近60个交易日


def record_est_accuracy(fund_code: str, est_nav: float, official_nav: float, nav_date: str = ""):
    """记录EST估算净值与官方净值的偏差，用于准确度回测

    Args:
        fund_code: 基金代码
        est_nav: EST估算净值
        official_nav: 官方净值
        nav_date: 净值日期
    """
    if not est_nav or not official_nav or official_nav <= 0:
        return

    deviation = round((est_nav - official_nav) / official_nav * 100, 4)
    record = {
        "date": nav_date or datetime.now().strftime("%Y-%m-%d"),
        "est_nav": round(est_nav, 4),
        "official_nav": round(official_nav, 4),
        "deviation": deviation,
        "abs_deviation": abs(deviation),
    }

    if fund_code not in _est_accuracy_history:
        _est_accuracy_history[fund_code] = []

    history = _est_accuracy_history[fund_code]
    # 避免同一天重复记录
    if history and history[-1]["date"] == record["date"]:
        history[-1] = record
    else:
        history.append(record)

    # 保留最近N天
    if len(history) > _MAX_HISTORY_DAYS:
        _est_accuracy_history[fund_code] = history[-_MAX_HISTORY_DAYS:]


def get_est_accuracy_stats(fund_code: str = "") -> dict:
    """获取EST估算准确度统计

    Args:
        fund_code: 指定基金代码，空字符串表示全部基金汇总

    Returns:
        {
            "total_records": int,
            "avg_deviation": float,       # 平均偏差%
            "avg_abs_deviation": float,   # 平均绝对偏差%
            "max_abs_deviation": float,   # 最大绝对偏差%
            "accuracy_rate": float,       # 偏差<0.5%的比率
            "recent_records": list,       # 最近10条记录
        }
    """
    if fund_code:
        records = _est_accuracy_history.get(fund_code, [])
    else:
        records = []
        for code_records in _est_accuracy_history.values():
            records.extend(code_records)

    if not records:
        return {
            "total_records": 0,
            "avg_deviation": 0,
            "avg_abs_deviation": 0,
            "max_abs_deviation": 0,
            "accuracy_rate": 0,
            "recent_records": [],
        }

    deviations = [r["deviation"] for r in records]
    abs_deviations = [r["abs_deviation"] for r in records]
    accurate_count = sum(1 for d in abs_deviations if d < 0.5)

    return {
        "total_records": len(records),
        "avg_deviation": round(sum(deviations) / len(deviations), 4),
        "avg_abs_deviation": round(sum(abs_deviations) / len(abs_deviations), 4),
        "max_abs_deviation": round(max(abs_deviations), 4),
        "accuracy_rate": round(accurate_count / len(records) * 100, 2),
        "recent_records": records[-10:],
    }


# ==================== 市场状态 ====================


def determine_market_status() -> str:
    """判断当前市场状态

    Returns:
        'us_market_open'  - 美股交易中
        'a_share_open'    - A股交易中
        'hk_market_open'  - 港股交易中
        'weekend'         - 周末
        'closed'          - 非交易时间
    """
    now = datetime.now()
    weekday = now.weekday()  # 0=Monday, 6=Sunday

    if weekday >= 5:
        return "weekend"

    hour, minute = now.hour, now.minute

    # A股: 9:30-11:30, 13:00-15:00
    a_share_open = False
    if (hour == 9 and minute >= 30) or (10 <= hour <= 11) or (hour == 11 and minute <= 30):
        a_share_open = True
    if 13 <= hour <= 14 or (hour == 15 and minute == 0):
        a_share_open = True

    # 港股: 9:30-12:00, 13:00-16:00
    hk_market_open = False
    if (hour == 9 and minute >= 30) or (10 <= hour <= 11) or (hour == 12 and minute == 0):
        hk_market_open = True
    if 13 <= hour <= 15 or (hour == 16 and minute == 0):
        hk_market_open = True

    # 美股（夏令时北京时间）: 21:30-4:00
    us_market_open = False
    if hour >= 21 or hour < 4:
        us_market_open = True
    if hour == 21 and minute >= 30:
        us_market_open = True

    if us_market_open:
        return "us_market_open"
    elif a_share_open:
        return "a_share_open"
    elif hk_market_open:
        return "hk_market_open"
    else:
        return "closed"


# ==================== 底层资产价格解析 ====================


def parse_underlying_price(
    underlying_code: str, raw_data: List[str]
) -> Optional[Dict]:
    """解析新浪底层资产行情数据

    Args:
        underlying_code: 底层资产代码，如 'gb_qqq', 'hf_GC', 'rt_hkHSI'
        raw_data: 新浪返回的原始字段列表

    Returns:
        {
            'price': float,         # 当前价
            'prev_close': float,    # 前收盘
            'open': float,          # 开盘价
            'high': float,          # 最高价
            'low': float,           # 最低价
            'name': str,            # 名称
            'change_pct': float,    # 涨跌幅%
        }
        解析失败返回 None
    """
    if not raw_data or len(raw_data) < 2:
        return None

    try:
        if underlying_code.startswith("gb_"):
            # 美股ETF: [name, price, ...open, prev_close, high, low, ...]
            price = safe_float(raw_data[1], 0)
            prev_close = safe_float(raw_data[6], 0)
            open_price = safe_float(raw_data[5], 0)
            high = safe_float(raw_data[7], 0)
            low = safe_float(raw_data[8], 0)
            name = raw_data[0] if raw_data[0] else underlying_code

        elif underlying_code.startswith("hf_"):
            # 期货: [price, ...open, high, low, ...prev_close, ...]
            price = safe_float(raw_data[0], 0)
            prev_close = safe_float(raw_data[7], 0) if len(raw_data) > 7 else price
            open_price = safe_float(raw_data[2], 0) if len(raw_data) > 2 else 0
            high = safe_float(raw_data[3], 0) if len(raw_data) > 3 else 0
            low = safe_float(raw_data[4], 0) if len(raw_data) > 4 else 0
            name = underlying_code

        elif underlying_code.startswith("rt_hk"):
            # 港股指数: [...open, prev_close, ..., price, high, low, ...]
            price = safe_float(raw_data[6], 0)
            prev_close = safe_float(raw_data[3], 0) if len(raw_data) > 3 else price
            open_price = safe_float(raw_data[2], 0) if len(raw_data) > 2 else 0
            high = safe_float(raw_data[4], 0) if len(raw_data) > 4 else 0
            low = safe_float(raw_data[5], 0) if len(raw_data) > 5 else 0
            name = underlying_code

        else:
            logger.warning(f"不支持的底层资产类型: {underlying_code}")
            return None

        if price <= 0:
            return None

        change_pct = (
            round((price - prev_close) / prev_close * 100, 2)
            if prev_close > 0
            else 0
        )

        return {
            "price": price,
            "prev_close": prev_close,
            "open": open_price,
            "high": high,
            "low": low,
            "name": name,
            "change_pct": change_pct,
        }
    except (IndexError, ValueError, TypeError) as e:
        logger.warning(f"解析底层资产数据失败 {underlying_code}: {e}")
        return None


# ==================== 基金代码标准化 ====================


def normalize_fund_code(fund_code: str, valid_codes: Optional[set] = None) -> Optional[str]:
    """标准化LOF基金代码为 SH/SZ 前缀格式

    Args:
        fund_code: 用户输入的基金代码（可能无前缀）
        valid_codes: 合法代码集合（可选，用于自动判断前缀）

    Returns:
        标准化后的代码如 'SH501312'，无效返回 None
    """
    code = fund_code.strip().upper()

    # 已有前缀
    if code.startswith("SH") or code.startswith("SZ"):
        if valid_codes is None or code in valid_codes:
            return code
        return None

    # 纯数字，自动判断前缀
    if not code.isdigit():
        return None

    if valid_codes is not None:
        sh_code = f"SH{code}"
        sz_code = f"SZ{code}"
        if sh_code in valid_codes:
            return sh_code
        if sz_code in valid_codes:
            return sz_code
        return None

    # 无校验集合时按规则推断
    if code.startswith("5"):
        return f"SH{code}"
    elif code.startswith("1"):
        return f"SZ{code}"
    else:
        return None


def get_sina_fund_code(fund_code: str) -> str:
    """将 SH/SZ 前缀基金代码转换为新浪格式（小写）

    Args:
        fund_code: 'SH501312' -> 'sh501312'

    Returns:
        新浪格式代码
    """
    return fund_code.lower()


# ==================== 响应格式 ====================


def make_error_response(message: str, **extra) -> dict:
    """构造统一的错误响应"""
    resp = {"error": True, "message": message, **extra}
    return resp


def make_success_response(data: dict, **extra) -> dict:
    """构造统一的成功响应，自动附加 update_time"""
    resp = {
        "error": False,
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        **data,
        **extra,
    }
    return resp
