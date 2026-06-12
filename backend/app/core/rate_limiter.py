"""限流器 - 令牌桶算法

用于限制对外部API的请求频率，避免被封禁。

用法:
    from app.core.rate_limiter import RateLimiter

    sina_limiter = RateLimiter(calls_per_second=10)

    def fetch_from_sina(url):
        sina_limiter.wait()  # 等待直到可以发送请求
        return requests.get(url)
"""

import time
import threading
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """简单的令牌桶限流器（线程安全）"""

    def __init__(self, calls_per_second: float = 5.0, name: str = ""):
        """
        Args:
            calls_per_second: 每秒允许的请求数
            name: 限流器名称（用于日志）
        """
        self._interval = 1.0 / calls_per_second
        self._last_call = 0.0
        self._lock = threading.Lock()
        self._name = name or f"limiter_{id(self)}"
        self._wait_count = 0

    def wait(self):
        """等待直到可以发送请求"""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call
            if elapsed < self._interval:
                wait_time = self._interval - elapsed
                time.sleep(wait_time)
                self._wait_count += 1
                if self._wait_count % 100 == 0:
                    logger.debug(f"限流器 {self._name}: 已等待 {self._wait_count} 次")
            self._last_call = time.monotonic()

    def reset(self):
        """重置限流器"""
        with self._lock:
            self._last_call = 0.0
            self._wait_count = 0


# ==================== 预定义限流器 ====================
# 根据各API的承受能力设置不同的限流

# 新浪财经API：较宽松
sina_limiter = RateLimiter(calls_per_second=10, name="sina")

# 东方财富API：中等
eastmoney_limiter = RateLimiter(calls_per_second=5, name="eastmoney")

# 集思录API：较严格（需要登录，容易被封）
jisilu_limiter = RateLimiter(calls_per_second=2, name="jisilu")

# 腾讯财经API：较宽松
tencent_limiter = RateLimiter(calls_per_second=10, name="tencent")

# Polymarket API：中等
polymarket_limiter = RateLimiter(calls_per_second=5, name="polymarket")

# Yahoo Finance API：较严格
yahoo_limiter = RateLimiter(calls_per_second=2, name="yahoo")
