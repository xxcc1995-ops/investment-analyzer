"""Shared utility functions for backend services."""

import math
import logging
import requests
from typing import Optional, Any
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


def safe_float(val: Any, default: Optional[float] = None) -> Optional[float]:
    """Safely convert a value to float.

    Handles None, empty strings, '-', NaN, Inf, and non-numeric types.
    Returns `default` (None) on failure.
    """
    if val is None or val == '' or val == '-':
        return default
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (ValueError, TypeError):
        return default


def safe_float_or_zero(val: Any) -> float:
    """safe_float that returns 0.0 instead of None."""
    return safe_float(val, default=0.0)


def create_http_session(
    pool_connections: int = 10,
    pool_maxsize: int = 20,
    retries: int = 3,
    backoff_factor: float = 1.0,
    timeout: int = 15,
) -> requests.Session:
    """创建带连接池和重试的共享HTTP会话。

    Args:
        pool_connections: 连接池连接数
        pool_maxsize: 连接池最大连接数
        retries: 重试次数
        backoff_factor: 重试退避因子
        timeout: 默认超时秒数

    Returns:
        配置好的 requests.Session
    """
    session = requests.Session()
    adapter = HTTPAdapter(
        pool_connections=pool_connections,
        pool_maxsize=pool_maxsize,
        max_retries=Retry(
            total=retries,
            backoff_factor=backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
        ),
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    return session


# 全局共享HTTP会话（带连接池和重试）
shared_session = create_http_session()


# 腾讯行情接口的 Referer（部分接口要求）
_TENCENT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://stockapp.finance.qq.com/",
}


def fetch_tencent_names(symbols: list, timeout: int = 10) -> dict:
    """批量经腾讯 qt.gtimg.cn 取股票名称。

    统一各服务里重复的"腾讯行情取名称"实现（原本散布于 right_side_service /
    relative_valuation_service 等，各自重复 GBK 解析与 headers）。

    Args:
        symbols: 腾讯行情符号列表，如 ['sh600519','r_hk00700','sz000001','hk00700']。
        timeout: 请求超时秒数。

    Returns:
        {symbol: name}，如 {'sh600519':'贵州茅台'}。任意异常返回 {}（不抛）。
    """
    if not symbols:
        return {}
    try:
        url = f"https://qt.gtimg.cn/q={','.join(symbols)}"
        r = shared_session.get(url, headers=_TENCENT_HEADERS, timeout=timeout)
        r.encoding = "gbk"
        name_map: dict = {}
        for seg in r.text.split(";"):
            seg = seg.strip()
            if not seg or "=" not in seg:
                continue
            # 形如 v_sh600519="sh600519~贵州茅台~..."
            head, payload = seg.split("=", 1)
            sym = head.strip()
            if sym.startswith("v_"):  # 去掉 v_ 前缀
                sym = sym[2:]
            parts = payload.strip().strip('"').split("~")
            if len(parts) > 1 and parts[1].strip():
                name_map[sym] = parts[1].strip()
        return name_map
    except Exception as e:
        logger.warning(f"腾讯批量取名称失败: {e}")
        return {}
