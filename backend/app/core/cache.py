"""集中式缓存工具 - 支持TTL的内存缓存

特性:
- LRU淘汰（最大2000条）
- 分层TTL常量
- 交易时间感知（收盘后延长缓存）
- 文件持久化（静态数据）
- 线程安全
"""

import json
import os
import time
import threading
import logging
from collections import OrderedDict
from functools import wraps
from typing import Any, Dict, Optional, Tuple
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

# ==================== TTL常量 ====================
TTL_REALTIME = 30           # 实时行情（30秒）
TTL_DAILY    = 3600         # 每日数据（1小时）：行业排名、资金流
TTL_WEEKLY   = 86400        # 每周数据（24小时）：GDP、CPI、PMI、LPR
TTL_STATIC   = 86400 * 30   # 静态数据（30天）：估值历史、分红记录
TTL_SEARCH   = 3600         # 搜索结果（1小时）

# ==================== 缓存配置 ====================
MAX_CACHE_SIZE = 2000       # 最大缓存条目数
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", ".cache")

# ==================== 内部状态 ====================
_cache: OrderedDict[str, Tuple[Any, float]] = OrderedDict()
_lock = threading.Lock()


def _is_trading_hours() -> bool:
    """判断A股是否在交易时间内（周一至周五 9:15-15:00 CST）"""
    cst = timezone(timedelta(hours=8))
    now = datetime.now(cst)
    if now.weekday() >= 5:  # 周末
        return False
    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=0, second=0, microsecond=0)
    return market_open <= now <= market_close


def _file_cache_path(key: str) -> str:
    """获取文件缓存路径"""
    safe_key = key.replace(":", "_").replace("/", "_").replace("\\", "_")
    return os.path.join(CACHE_DIR, f"{safe_key}.json")


def get_cache(key: str, ttl_seconds: int = TTL_DAILY) -> Optional[Any]:
    """获取缓存值，过期返回None

    优先从内存缓存获取，其次从文件缓存获取（仅静态数据）。
    """
    with _lock:
        # 1. 检查内存缓存
        if key in _cache:
            data, ts = _cache[key]
            if time.time() - ts < ttl_seconds:
                # LRU: 移到末尾
                _cache.move_to_end(key)
                return data
            # 已过期，删除
            del _cache[key]

    # 2. 检查文件缓存（仅对静态数据）
    if ttl_seconds >= TTL_WEEKLY:
        path = _file_cache_path(key)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    stored = json.load(f)
                if time.time() - stored["ts"] < ttl_seconds:
                    # 从文件恢复到内存
                    with _lock:
                        _cache[key] = (stored["data"], stored["ts"])
                        _cache.move_to_end(key)
                        _evict_if_needed()
                    logger.debug(f"从文件缓存恢复: {key}")
                    return stored["data"]
            except Exception as e:
                logger.debug(f"读取文件缓存失败 {key}: {e}")

    return None


def set_cache(key: str, data: Any, persist: bool = False):
    """设置缓存值

    Args:
        key: 缓存键
        data: 缓存数据
        persist: 是否持久化到文件（用于静态数据）
    """
    with _lock:
        if key in _cache:
            _cache.move_to_end(key)
        _cache[key] = (data, time.time())
        _evict_if_needed()

    # 文件持久化
    if persist:
        _persist_to_file(key, data)


def clear_cache(prefix: str = ""):
    """清除缓存，可选前缀过滤

    Args:
        prefix: 缓存键前缀，为空则清除所有
    """
    with _lock:
        if not prefix:
            _cache.clear()
        else:
            keys_to_del = [k for k in _cache if k.startswith(prefix)]
            for k in keys_to_del:
                del _cache[k]

    # 同时清除文件缓存
    if prefix:
        _clear_file_cache(prefix)


def get_realtime_ttl() -> int:
    """获取实时数据的TTL（交易时间30秒，收盘后300秒）"""
    return TTL_REALTIME if _is_trading_hours() else 300


def get_cache_stats() -> dict:
    """获取缓存统计信息"""
    with _lock:
        return {
            "size": len(_cache),
            "max_size": MAX_CACHE_SIZE,
            "is_trading_hours": _is_trading_hours(),
            "keys": list(_cache.keys())[:20],  # 只返回前20个key
        }


def _evict_if_needed():
    """LRU淘汰：超出最大数量时淘汰最久未访问的条目"""
    while len(_cache) > MAX_CACHE_SIZE:
        _cache.popitem(last=False)
        logger.debug("LRU淘汰一个缓存条目")


def _persist_to_file(key: str, data: Any):
    """将缓存数据持久化到文件"""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        path = _file_cache_path(key)
        with open(path, "w", encoding="utf-8") as f:
            # 存储原始key以便后续还原
            json.dump({"key": key, "data": data, "ts": time.time()}, f, ensure_ascii=False)
        logger.debug(f"持久化缓存到文件: {key}")
    except Exception as e:
        logger.debug(f"持久化缓存失败 {key}: {e}")


def _clear_file_cache(prefix: str):
    """清除文件缓存"""
    try:
        if not os.path.exists(CACHE_DIR):
            return
        for filename in os.listdir(CACHE_DIR):
            if filename.endswith(".json"):
                filepath = os.path.join(CACHE_DIR, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        stored = json.load(f)
                    # 优先使用存储的原始key
                    original_key = stored.get("key", "")
                    if not original_key:
                        # 兼容旧格式：从文件名还原
                        safe_key = filename[:-5]
                        original_key = safe_key.replace("_", ":")
                    if original_key.startswith(prefix):
                        os.remove(filepath)
                        logger.debug(f"删除文件缓存: {filename}")
                except Exception:
                    # 读取失败的文件跳过
                    pass
    except Exception as e:
        logger.debug(f"清除文件缓存失败: {e}")


def cached(ttl_seconds: int = TTL_DAILY, key_prefix: str = "", persist: bool = False):
    """装饰器缓存，支持TTL

    用法:
        @cached(ttl_seconds=TTL_DAILY)
        def get_data():
            ...

        @cached(ttl_seconds=TTL_WEEKLY, key_prefix="macro", persist=True)
        def get_gdp():
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
                set_cache(cache_key, result, persist=persist)
            return result
        return wrapper
    return decorator
