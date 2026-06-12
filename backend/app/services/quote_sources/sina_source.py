"""新浪行情数据源"""

import re
import logging
import requests
from typing import Optional
from datetime import datetime
from .base import BaseQuoteSource, QuoteData

logger = logging.getLogger(__name__)


class SinaSource(BaseQuoteSource):
    """新浪行情数据源"""

    # A股行情接口
    A_QUOTE_URL = "https://hq.sinajs.cn/list={symbol}"
    # 行情接口请求头
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://finance.sina.com.cn/',
    }

    def __init__(self):
        self._session: Optional[requests.Session] = None
        self._connected = False

    @property
    def name(self) -> str:
        return "新浪"

    def connect(self) -> bool:
        """创建HTTP会话（带连接池和重试）"""
        try:
            self._session = self._create_session(pool_connections=5, pool_maxsize=10, retries=2)
            self._session.headers.update(self.HEADERS)
            # 测试连接
            resp = self._session.get(
                self.A_QUOTE_URL.format(symbol='sh000001'),
                timeout=5
            )
            if resp.status_code == 200:
                self._connected = True
                logger.info("新浪行情接口连接成功")
                return True
            else:
                self._connected = False
                return False
        except Exception as e:
            logger.warning(f"新浪行情接口连接失败: {e}")
            self._connected = False
            return False

    def disconnect(self):
        """关闭会话"""
        if self._session:
            self._session.close()
            self._session = None
        self._connected = False

    def is_connected(self) -> bool:
        """检查连接状态"""
        return self._connected and self._session is not None

    def _format_symbol(self, code: str, market: str = 'A') -> str:
        """格式化股票代码为新浪格式"""
        if market == 'HK':
            return f'hk{code.zfill(5)}'

        # A股自动判断市场
        if code.startswith('6'):
            return f'sh{code}'
        elif code.startswith(('0', '3')):
            return f'sz{code}'
        elif code.startswith('8') or code.startswith('4'):
            return f'bj{code}'  # 北交所
        else:
            return f'sh{code}'

    def get_quote(self, code: str, market: str = 'A') -> Optional[QuoteData]:
        """获取单只股票实时行情"""
        if not self.is_connected():
            if not self.connect():
                return None

        try:
            symbol = self._format_symbol(code, market)
            url = self.A_QUOTE_URL.format(symbol=symbol)

            resp = self._session.get(url, timeout=10)
            resp.encoding = 'gbk'
            text = resp.text

            # 解析新浪行情数据
            # 格式: var hq_str_sh600000="浦发银行,10.00,9.98,...";
            match = re.search(r'var hq_str_\w+="(.+)"', text)
            if not match:
                logger.warning(f"新浪行情数据解析失败: {code}")
                return None

            data = match.group(1)
            if not data:
                return None

            fields = data.split(',')

            if market == 'HK':
                return self._parse_hk_quote(code, fields)
            else:
                return self._parse_a_quote(code, fields)

        except Exception as e:
            logger.warning(f"新浪获取行情失败 {code}: {e}")
            return None

    def _parse_a_quote(self, code: str, fields: list) -> Optional[QuoteData]:
        """解析A股行情数据

        新浪A股数据格式（33个字段）：
        0: 股票名称
        1: 今日开盘价
        2: 昨日收盘价
        3: 当前价格
        4: 今日最高价
        5: 今日最低价
        6: 竞买价（买一）
        7: 竞卖价（卖一）
        8: 成交量（股）
        9: 成交额（元）
        ...
        30: 日期
        31: 时间
        """
        try:
            if len(fields) < 32:
                return None

            name = fields[0]
            open_price = float(fields[1]) if fields[1] else 0
            pre_close = float(fields[2]) if fields[2] else 0
            price = float(fields[3]) if fields[3] else 0
            high = float(fields[4]) if fields[4] else 0
            low = float(fields[5]) if fields[5] else 0
            bid1 = float(fields[6]) if fields[6] else 0
            ask1 = float(fields[7]) if fields[7] else 0
            volume = float(fields[8]) if fields[8] else 0
            amount = float(fields[9]) if fields[9] else 0
            trade_date = fields[30] if len(fields) > 30 else ''
            trade_time = fields[31] if len(fields) > 31 else ''

            change_pct = self._calc_change_pct(price, pre_close)
            change_amount = round(price - pre_close, 3) if pre_close else 0

            return QuoteData(
                code=code,
                name=name,
                price=price,
                open=open_price,
                high=high,
                low=low,
                pre_close=pre_close,
                volume=volume,
                amount=amount,
                change_pct=change_pct,
                change_amount=change_amount,
                bid1_price=bid1,
                bid1_volume=0,  # 新浪不直接返回买卖量
                ask1_price=ask1,
                ask1_volume=0,
                timestamp=f"{trade_date} {trade_time}",
                trade_date=trade_date,
                source='新浪',
                market='A',
            )
        except Exception as e:
            logger.warning(f"解析新浪A股数据失败 {code}: {e}")
            return None

    def _parse_hk_quote(self, code: str, fields: list) -> Optional[QuoteData]:
        """解析港股行情数据

        新浪港股数据格式：
        0: 股票中文名
        1: 股票英文名
        2: 开盘价
        3: 昨收
        4: 最高价
        5: 最低价
        6: 当前价
        7: 涨跌额
        8: 涨跌幅(%)
        9: 买入价
        10: 卖出价
        11: 成交量（股）
        12: 成交额（元）
        ...
        17: 日期
        """
        try:
            if len(fields) < 18:
                return None

            name = fields[0]
            open_price = float(fields[2]) if fields[2] else 0
            pre_close = float(fields[3]) if fields[3] else 0
            high = float(fields[4]) if fields[4] else 0
            low = float(fields[5]) if fields[5] else 0
            price = float(fields[6]) if fields[6] else 0
            change_amount = float(fields[7]) if fields[7] else 0
            change_pct = float(fields[8]) if fields[8] else 0
            bid1 = float(fields[9]) if fields[9] else 0
            ask1 = float(fields[10]) if fields[10] else 0
            volume = float(fields[11]) if fields[11] else 0
            amount = float(fields[12]) if fields[12] else 0
            trade_date = fields[17] if len(fields) > 17 else ''

            return QuoteData(
                code=code,
                name=name,
                price=price,
                open=open_price,
                high=high,
                low=low,
                pre_close=pre_close,
                volume=volume,
                amount=amount,
                change_pct=change_pct,
                change_amount=change_amount,
                bid1_price=bid1,
                bid1_volume=0,
                ask1_price=ask1,
                ask1_volume=0,
                timestamp=trade_date,
                trade_date=trade_date,
                source='新浪',
                market='HK',
            )
        except Exception as e:
            logger.warning(f"解析新浪港股数据失败 {code}: {e}")
            return None

    def get_batch_quotes(self, codes: list[str], market: str = 'A') -> dict[str, QuoteData]:
        """批量获取行情（新浪支持批量查询）"""
        if not self.is_connected():
            if not self.connect():
                return {}

        try:
            # 构建批量查询符号
            symbols = [self._format_symbol(code, market) for code in codes]
            symbol_str = ','.join(symbols)

            url = self.A_QUOTE_URL.format(symbol=symbol_str)
            resp = self._session.get(url, timeout=15)
            resp.encoding = 'gbk'
            text = resp.text

            result = {}
            # 解析多只股票的数据
            pattern = r'var hq_str_(\w+)="(.+)"'
            matches = re.findall(pattern, text)

            for symbol, data in matches:
                if not data:
                    continue

                # 从symbol中提取原始代码
                if symbol.startswith('sh'):
                    code = symbol[2:]
                elif symbol.startswith('sz'):
                    code = symbol[2:]
                elif symbol.startswith('bj'):
                    code = symbol[2:]
                elif symbol.startswith('hk'):
                    code = symbol[2:]
                else:
                    code = symbol

                fields = data.split(',')
                if market == 'HK':
                    quote = self._parse_hk_quote(code, fields)
                else:
                    quote = self._parse_a_quote(code, fields)

                if quote:
                    result[code] = quote

            return result

        except Exception as e:
            logger.warning(f"新浪批量获取行情失败: {e}")
            return {}
