"""行情数据源抽象基类"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


@dataclass
class QuoteData:
    """标准化的行情数据结构"""
    code: str  # 股票代码
    name: str  # 股票名称
    price: float  # 最新价
    open: float  # 开盘价
    high: float  # 最高价
    low: float  # 最低价
    pre_close: float  # 昨收价
    volume: float  # 成交量（股）
    amount: float  # 成交额（元）
    change_pct: float  # 涨跌幅(%)
    change_amount: float = 0.0  # 涨跌额
    turnover_rate: float = 0.0  # 换手率(%)
    pe: Optional[float] = None  # 市盈率(TTM)
    pb: Optional[float] = None  # 市净率
    total_market_cap: Optional[float] = None  # 总市值（元）
    circulating_market_cap: Optional[float] = None  # 流通市值（元）
    bid1_price: float = 0.0  # 买一价
    bid1_volume: float = 0.0  # 买一量（股）
    ask1_price: float = 0.0  # 卖一价
    ask1_volume: float = 0.0  # 卖一量（股）
    timestamp: str = ''  # 行情时间
    trade_date: str = ''  # 交易日期
    source: str = ''  # 数据来源标识
    market: str = ''  # 市场: A/HK

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'code': self.code,
            'name': self.name,
            'price': self.price,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'pre_close': self.pre_close,
            'volume': self.volume,
            'amount': self.amount,
            'change_pct': self.change_pct,
            'change_amount': self.change_amount,
            'turnover_rate': self.turnover_rate,
            'pe': self.pe,
            'pb': self.pb,
            'market_cap': round(self.total_market_cap / 1e8, 2) if self.total_market_cap else None,
            'circulating_market_cap': round(self.circulating_market_cap / 1e8, 2) if self.circulating_market_cap else None,
            'bid1_price': self.bid1_price,
            'bid1_volume': self.bid1_volume,
            'ask1_price': self.ask1_price,
            'ask1_volume': self.ask1_volume,
            'trade_time': self.timestamp,
            'trade_date': self.trade_date,
            'source': self.source,
            'market': self.market,
        }


class BaseQuoteSource(ABC):
    """行情数据源基类"""

    def _create_session(
        self,
        pool_connections: int = 5,
        pool_maxsize: int = 10,
        retries: int = 2,
        backoff_factor: float = 0.3,
    ) -> requests.Session:
        """创建带连接池和重试的HTTP会话

        Args:
            pool_connections: 连接池连接数
            pool_maxsize: 连接池最大连接数
            retries: 重试次数
            backoff_factor: 重试退避因子

        Returns:
            配置好的requests.Session
        """
        session = requests.Session()
        retry = Retry(
            total=retries,
            backoff_factor=backoff_factor,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(
            pool_connections=pool_connections,
            pool_maxsize=pool_maxsize,
            max_retries=retry,
        )
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    @property
    @abstractmethod
    def name(self) -> str:
        """数据源名称"""
        pass

    @abstractmethod
    def connect(self) -> bool:
        """连接数据源，返回是否成功"""
        pass

    @abstractmethod
    def disconnect(self):
        """断开连接"""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """检查连接状态"""
        pass

    @abstractmethod
    def get_quote(self, code: str, market: str = 'A') -> Optional[QuoteData]:
        """获取单只股票实时行情

        Args:
            code: 股票代码
            market: 市场类型 'A' 或 'HK'

        Returns:
            QuoteData 或 None（如果获取失败）
        """
        pass

    def get_batch_quotes(self, codes: list[str], market: str = 'A') -> dict[str, QuoteData]:
        """批量获取行情（默认逐个获取，子类可覆盖实现批量接口）

        Args:
            codes: 股票代码列表
            market: 市场类型

        Returns:
            {code: QuoteData} 字典
        """
        result = {}
        for code in codes:
            quote = self.get_quote(code, market)
            if quote:
                result[code] = quote
        return result

    def _format_code(self, code: str, market: str = 'A') -> str:
        """格式化股票代码为数据源所需的格式"""
        if market == 'HK':
            # 港股代码补零到5位
            return code.zfill(5)
        return code

    def _calc_change_pct(self, price: float, pre_close: float) -> float:
        """计算涨跌幅"""
        if pre_close and pre_close > 0:
            return round((price - pre_close) / pre_close * 100, 2)
        return 0.0
