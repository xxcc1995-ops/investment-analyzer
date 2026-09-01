"""通达信行情数据源"""

import socket
import logging
from typing import Optional
from datetime import datetime
from pytdx.hq import TdxHq_API
from .base import BaseQuoteSource, QuoteData

logger = logging.getLogger(__name__)

# 每个TDX服务器的连接超时（秒）- 原来无超时可导致单次连接挂起2分钟
TDX_CONNECT_TIMEOUT = 5
# 每次API调用的超时（秒）
TDX_REQUEST_TIMEOUT = 8

# 通达信公共行情服务器列表
TDX_SERVERS = [
    ('119.147.212.81', 7709),   # 招商证券
    ('112.74.214.43', 7727),    # 广发证券
    ('221.231.141.60', 7709),   # 华泰证券
    ('101.227.73.20', 7709),    # 申万宏源
    ('101.227.77.254', 7709),   # 申万宏源
    ('14.215.128.18', 7709),    # 广发证券
    ('59.173.18.140', 7709),    # 国泰君安
    ('218.75.126.9', 7709),     # 财富证券
    ('115.238.56.198', 7709),   # 浙商证券
    ('124.160.88.183', 7709),   # 浙商证券
    ('218.108.98.244', 7709),   # 浙商证券
    ('218.108.47.69', 7709),    # 浙商证券
    ('180.153.39.51', 7709),    # 申万宏源
]

# 市场代码映射
MARKET_MAP = {
    'sh': 1,  # 上海
    'sz': 0,  # 深圳
    'hk': 2,  # 港股（通达信港股市场代码）
}


class TDXSource(BaseQuoteSource):
    """通达信行情数据源"""

    def __init__(self):
        self._api: Optional[TdxHq_API] = None
        self._connected = False
        self._current_server = None
        self._server_index = 0

    @property
    def name(self) -> str:
        return "通达信"

    def connect(self) -> bool:
        """连接通达信行情服务器（带超时保护）"""
        for i in range(len(TDX_SERVERS)):
            server_idx = (self._server_index + i) % len(TDX_SERVERS)
            host, port = TDX_SERVERS[server_idx]
            try:
                if self._api:
                    try:
                        self._api.disconnect()
                    except Exception:
                        pass

                self._api = TdxHq_API()
                # pytdx的connect底层用socket，设置全局socket超时防止挂起
                old_timeout = socket.getdefaulttimeout()
                socket.setdefaulttimeout(TDX_CONNECT_TIMEOUT)
                try:
                    self._api.connect(host, port)
                finally:
                    socket.setdefaulttimeout(old_timeout)

                self._connected = True
                self._current_server = (host, port)
                self._server_index = server_idx
                logger.info(f"通达信连接成功: {host}:{port}")
                return True
            except Exception as e:
                logger.warning(f"通达信连接失败 {host}:{port}: {e}")
                continue

        self._connected = False
        logger.error("所有通达信服务器均不可用")
        return False

    def disconnect(self):
        """断开连接"""
        if self._api:
            try:
                self._api.disconnect()
            except Exception:
                pass
            self._api = None
        self._connected = False

    def is_connected(self) -> bool:
        """检查连接状态（带超时保护）"""
        if not self._connected or not self._api:
            return False
        try:
            old_timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(TDX_REQUEST_TIMEOUT)
            try:
                self._api.get_security_count(1)
            finally:
                socket.setdefaulttimeout(old_timeout)
            return True
        except Exception:
            self._connected = False
            return False

    def _get_market_and_code(self, code: str, market: str = 'A') -> tuple[int, str]:
        """解析市场和代码"""
        if market == 'HK':
            return 2, code.zfill(5)

        # A股自动判断市场
        if code.startswith(('6', '5', '9')):
            return 1, code  # 上海
        elif code.startswith(('0', '1', '2', '3')):
            return 0, code  # 深圳
        elif code.startswith(('4', '8')):
            return 0, code  # 新三板/北交所
        else:
            return 0, code

    def get_quote(self, code: str, market: str = 'A') -> Optional[QuoteData]:
        """获取单只股票实时行情"""
        if not self.is_connected():
            if not self.connect():
                return None

        try:
            mkt, stock_code = self._get_market_and_code(code, market)

            # 使用 get_security_quotes 获取行情
            quotes = self._api.get_security_quotes([(mkt, stock_code)])
            if not quotes or len(quotes) == 0:
                return None

            q = quotes[0]

            price = q.get('price', 0)
            pre_close = q.get('last_close', 0)
            open_price = q.get('open', 0)
            high = q.get('high', 0)
            low = q.get('low', 0)
            volume = q.get('vol', 0)  # 成交量（手）
            amount = q.get('amount', 0)  # 成交额

            # 通达信成交量单位是手，转换为股
            volume_shares = volume * 100

            change_pct = self._calc_change_pct(price, pre_close)
            change_amount = round(price - pre_close, 3) if pre_close else 0

            # 获取买卖盘
            bid1_price = q.get('bid1', 0)
            bid1_volume = q.get('bid_vol1', 0) * 100  # 转换为股
            ask1_price = q.get('ask1', 0)
            ask1_volume = q.get('ask_vol1', 0) * 100  # 转换为股

            # 股票名称（通达信返回的是GBK编码）
            name = q.get('code', stock_code)
            try:
                # 尝试获取股票名称
                name = q.get('name', stock_code)
                if isinstance(name, bytes):
                    name = name.decode('gbk', errors='ignore')
            except Exception:
                name = stock_code

            now = datetime.now()

            return QuoteData(
                code=code,
                name=name,
                price=price,
                open=open_price,
                high=high,
                low=low,
                pre_close=pre_close,
                volume=volume_shares,
                amount=amount,
                change_pct=change_pct,
                change_amount=change_amount,
                bid1_price=bid1_price,
                bid1_volume=bid1_volume,
                ask1_price=ask1_price,
                ask1_volume=ask1_volume,
                timestamp=now.strftime('%Y-%m-%d %H:%M:%S'),
                trade_date=now.strftime('%Y-%m-%d'),
                source='通达信',
                market=market,
            )

        except Exception as e:
            logger.warning(f"通达信获取行情失败 {code}: {e}")
            self._connected = False
            return None

    def get_batch_quotes(self, codes: list[str], market: str = 'A') -> dict[str, QuoteData]:
        """批量获取行情（通达信支持批量查询）"""
        if not self.is_connected():
            if not self.connect():
                return {}

        try:
            # 构建查询参数
            params = []
            code_map = {}
            for code in codes:
                mkt, stock_code = self._get_market_and_code(code, market)
                params.append((mkt, stock_code))
                code_map[stock_code] = code

            # 通达信每次最多查询80只
            result = {}
            batch_size = 80
            for i in range(0, len(params), batch_size):
                batch = params[i:i + batch_size]
                quotes = self._api.get_security_quotes(batch)

                if quotes:
                    for q in quotes:
                        stock_code = q.get('code', '')
                        original_code = code_map.get(stock_code, stock_code)

                        price = q.get('price', 0)
                        pre_close = q.get('last_close', 0)
                        volume = q.get('vol', 0) * 100
                        amount = q.get('amount', 0)

                        now = datetime.now()

                        quote_data = QuoteData(
                            code=original_code,
                            name=q.get('name', stock_code),
                            price=price,
                            open=q.get('open', 0),
                            high=q.get('high', 0),
                            low=q.get('low', 0),
                            pre_close=pre_close,
                            volume=volume,
                            amount=amount,
                            change_pct=self._calc_change_pct(price, pre_close),
                            change_amount=round(price - pre_close, 3) if pre_close else 0,
                            bid1_price=q.get('bid1', 0),
                            bid1_volume=q.get('bid_vol1', 0) * 100,
                            ask1_price=q.get('ask1', 0),
                            ask1_volume=q.get('ask_vol1', 0) * 100,
                            timestamp=now.strftime('%Y-%m-%d %H:%M:%S'),
                            trade_date=now.strftime('%Y-%m-%d'),
                            source='通达信',
                            market=market,
                        )
                        result[original_code] = quote_data

            return result

        except Exception as e:
            logger.warning(f"通达信批量获取行情失败: {e}")
            self._connected = False
            return {}
