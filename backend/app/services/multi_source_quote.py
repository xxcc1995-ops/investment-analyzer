"""多数据源行情服务 - 支持自动故障切换"""

import logging
import time
from typing import Optional
from .quote_sources.base import BaseQuoteSource, QuoteData
from .quote_sources.tdx_source import TDXSource
from .quote_sources.sina_source import SinaSource
from .quote_sources.eastmoney_source import EastmoneySource
from .quote_sources.tencent_source import TencentSource

logger = logging.getLogger(__name__)


class MultiSourceQuoteService:
    """多数据源行情服务

    支持自动故障切换：
    - A股: 通达信 -> 新浪 -> 东方财富
    - 港股: 通达信 -> 腾讯 -> 东方财富
    """

    def __init__(self):
        # 初始化数据源
        self._tdx = TDXSource()
        self._sina = SinaSource()
        self._eastmoney = EastmoneySource()
        self._tencent = TencentSource()

        # 数据源优先级配置
        self._sources = {
            'A': [
                ('通达信', self._tdx),
                ('新浪', self._sina),
                ('东方财富', self._eastmoney),
            ],
            'HK': [
                ('通达信', self._tdx),
                ('腾讯', self._tencent),
                ('东方财富', self._eastmoney),
            ],
        }

        # 数据源健康状态
        self._health_status: dict[str, bool] = {
            '通达信': True,
            '新浪': True,
            '东方财富': True,
            '腾讯': True,
        }

        # 上次健康检查时间
        self._last_check: dict[str, float] = {
            '通达信': 0,
            '新浪': 0,
            '东方财富': 0,
            '腾讯': 0,
        }

        # 健康检查间隔（秒）
        self._health_check_interval = 60

        # 当前使用的数据源
        self._current_source: dict[str, str] = {
            'A': '通达信',
            'HK': '通达信',
        }

    def _is_source_healthy(self, source_name: str) -> bool:
        """检查数据源是否健康（带冷却恢复）"""
        now = time.time()
        last_check = self._last_check.get(source_name, 0)

        # 如果数据源不健康，检查冷却期是否已过
        if not self._health_status.get(source_name, True):
            if now - last_check > self._health_check_interval:
                # 冷却期结束，允许重试（乐观重置为健康）
                logger.info(f"数据源 {source_name} 冷却期({self._health_check_interval}s)结束，允许重试")
                self._health_status[source_name] = True

        return self._health_status.get(source_name, True)

    def _mark_source_healthy(self, source_name: str):
        """标记数据源为健康"""
        self._health_status[source_name] = True
        self._last_check[source_name] = time.time()

    def _mark_source_unhealthy(self, source_name: str, error: str = ''):
        """标记数据源为不健康"""
        self._health_status[source_name] = False
        self._last_check[source_name] = time.time()
        logger.warning(f"数据源 {source_name} 标记为不健康: {error}")

    def get_quote(self, code: str, market: str = 'A') -> Optional[QuoteData]:
        """获取实时行情，自动故障切换

        Args:
            code: 股票代码
            market: 'A' 或 'HK'

        Returns:
            QuoteData 或 None
        """
        sources = self._sources.get(market, [])
        errors = []

        for source_name, source in sources:
            # 跳过不健康的数据源（除非所有数据源都不健康）
            if not self._is_source_healthy(source_name):
                logger.debug(f"跳过不健康数据源: {source_name}")
                continue

            try:
                # 尝试连接
                if not source.is_connected():
                    if not source.connect():
                        self._mark_source_unhealthy(source_name, "连接失败")
                        continue

                # 获取行情
                quote = source.get_quote(code, market)
                if quote:
                    self._mark_source_healthy(source_name)
                    self._current_source[market] = source_name
                    logger.debug(f"使用 {source_name} 获取 {code} 行情成功")
                    return quote
                else:
                    errors.append(f"{source_name}: 返回空数据")

            except Exception as e:
                self._mark_source_unhealthy(source_name, str(e))
                errors.append(f"{source_name}: {str(e)}")
                logger.warning(f"数据源 {source_name} 获取行情异常: {e}")
                continue

        # 所有健康数据源都失败，尝试不健康的数据源（可能已恢复）
        for source_name, source in sources:
            if self._is_source_healthy(source_name):
                continue  # 已经尝试过了

            try:
                if not source.is_connected():
                    if not source.connect():
                        continue

                quote = source.get_quote(code, market)
                if quote:
                    self._mark_source_healthy(source_name)
                    self._current_source[market] = source_name
                    logger.info(f"数据源 {source_name} 已恢复，获取 {code} 行情成功")
                    return quote

            except Exception as e:
                continue

        logger.error(f"所有数据源均不可用 [{market}]: {'; '.join(errors)}")
        return None

    def get_batch_quotes(self, codes: list[str], market: str = 'A') -> dict[str, QuoteData]:
        """批量获取行情

        Args:
            codes: 股票代码列表
            market: 'A' 或 'HK'

        Returns:
            {code: QuoteData} 字典
        """
        sources = self._sources.get(market, [])

        for source_name, source in sources:
            if not self._is_source_healthy(source_name):
                continue

            try:
                if not source.is_connected():
                    if not source.connect():
                        self._mark_source_unhealthy(source_name, "连接失败")
                        continue

                result = source.get_batch_quotes(codes, market)
                if result:
                    self._mark_source_healthy(source_name)
                    self._current_source[market] = source_name
                    logger.debug(f"使用 {source_name} 批量获取 {len(result)} 条行情")
                    return result

            except Exception as e:
                self._mark_source_unhealthy(source_name, str(e))
                logger.warning(f"数据源 {source_name} 批量获取行情异常: {e}")
                continue

        # 降级为逐个获取
        logger.warning("批量获取失败，降级为逐个获取")
        result = {}
        for code in codes:
            quote = self.get_quote(code, market)
            if quote:
                result[code] = quote
        return result

    def get_source_status(self) -> dict:
        """获取所有数据源状态

        Returns:
            数据源状态信息
        """
        return {
            'current_source': self._current_source.copy(),
            'health_status': self._health_status.copy(),
            'sources': {
                'A': [name for name, _ in self._sources['A']],
                'HK': [name for name, _ in self._sources['HK']],
            },
            'connected': {
                '通达信': self._tdx.is_connected(),
                '新浪': self._sina.is_connected(),
                '东方财富': self._eastmoney.is_connected(),
                '腾讯': self._tencent.is_connected(),
            }
        }

    def reconnect_all(self):
        """重新连接所有数据源"""
        logger.info("重新连接所有数据源...")
        self._tdx.disconnect()
        self._sina.disconnect()
        self._eastmoney.disconnect()
        self._tencent.disconnect()

        # 重置健康状态
        for name in self._health_status:
            self._health_status[name] = True
            self._last_check[name] = 0

    def get_current_source(self, market: str = 'A') -> str:
        """获取当前使用的数据源名称"""
        return self._current_source.get(market, '通达信')


# 全局实例
multi_source_service = MultiSourceQuoteService()
