"""集中式缓存工具 - 支持TTL的内存缓存"""

import time
from functools import wraps
from typing import Any, Dict, Optional, Tuple

_cache: Dict[str, Tuple[Any, float]] = {}


def get_cache(key: str, ttl_seconds: int = 300) -> Optional[Any]:
    """获取缓存值，过期返回None"""
    if key in _cache:
        data, ts = _cache[key]
        if time.time() - ts < ttl_seconds:
            return data
        del _cache[key]
    return None


def set_cache(key: str, data: Any):
    """设置缓存值"""
    _cache[key] = (data, time.time())


def clear_cache(prefix: str = ""):
    """清除缓存，可选前缀过滤"""
    if not prefix:
        _cache.clear()
    else:
        keys_to_del = [k for k in _cache if k.startswith(prefix)]
        for k in keys_to_del:
            del _cache[k]


def cached(ttl_seconds: int = 300, key_prefix: str = ""):
    """装饰器缓存，支持TTL

    用法:
        @cached(ttl_seconds=300)
        def get_data():
            ...

        @cached(ttl_seconds=60, key_prefix="stock")
        def get_stock(code: str):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存key
            parts = [key_prefix or func.__name__]
            if args:
                parts.extend(str(a) for a in args)
            if kwargs:
                parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = ":".join(parts)

            # 尝试获取缓存
            result = get_cache(cache_key, ttl_seconds)
            if result is not None:
                return result

            # 执行函数并缓存
            result = func(*args, **kwargs)
            if result is not None:
                set_cache(cache_key, result)
            return result
        return wrapper
    return decorator
