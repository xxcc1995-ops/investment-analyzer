"""Shared utility functions for backend services."""

import math
import requests
from typing import Optional, Any
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


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
