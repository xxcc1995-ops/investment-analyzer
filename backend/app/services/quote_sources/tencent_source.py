"""腾讯行情数据源"""

import re
import logging
import requests
from typing import Optional
from datetime import datetime
from .base import BaseQuoteSource, QuoteData

logger = logging.getLogger(__name__)


class TencentSource(BaseQuoteSource):
    """腾讯行情数据源（主要用于港股）"""

    # 实时行情接口
    QUOTE_URL = "https://qt.gtimg.cn/q={symbol}"

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://stockapp.finance.qq.com/',
    }

    def __init__(self):
        self._session: Optional[requests.Session] = None
        self._connected = False

    @property
    def name(self) -> str:
        return "腾讯"

    def connect(self) -> bool:
        """创建HTTP会话"""
        try:
            self._session = requests.Session()
            self._session.headers.update(self.HEADERS)
            # 测试连接
            resp = self._session.get(
                self.QUOTE_URL.format(symbol='r_hk00700'),
                timeout=5
            )
            if resp.status_code == 200:
                self._connected = True
                logger.info("腾讯行情接口连接成功")
                return True
            else:
                self._connected = False
                return False
        except Exception as e:
            logger.warning(f"腾讯行情接口连接失败: {e}")
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
        """格式化股票代码为腾讯格式"""
        if market == 'HK':
            return f'r_hk{code.zfill(5)}'

        # A股
        if code.startswith('6'):
            return f'sh{code}'
        elif code.startswith(('0', '3')):
            return f'sz{code}'
        else:
            return f'sh{code}'

    def get_quote(self, code: str, market: str = 'A') -> Optional[QuoteData]:
        """获取单只股票实时行情"""
        if not self.is_connected():
            if not self.connect():
                return None

        try:
            symbol = self._format_symbol(code, market)
            url = self.QUOTE_URL.format(symbol=symbol)

            resp = self._session.get(url, timeout=10)
            resp.encoding = 'gbk'
            text = resp.text

            # 解析腾讯行情数据
            # 格式: v_r_hk00700="...~字段1~字段2~...";
            match = re.search(r'v_\w+="(.+)"', text)
            if not match:
                logger.warning(f"腾讯行情数据解析失败: {code}")
                return None

            data = match.group(1)
            if not data:
                return None

            fields = data.split('~')

            if market == 'HK':
                return self._parse_hk_quote(code, fields)
            else:
                return self._parse_a_quote(code, fields)

        except Exception as e:
            logger.warning(f"腾讯获取行情失败 {code}: {e}")
            return None

    def _parse_a_quote(self, code: str, fields: list) -> Optional[QuoteData]:
        """解析A股行情数据

        腾讯A股数据格式（50+个字段）：
        0: 股票代码
        1: 股票名称
        2: 股票代码（重复）
        3: 当前价格
        4: 昨收
        5: 开盘价
        6: 成交量（手）
        7: 外盘
        8: 内盘
        9: 买一价
        10: 买一量（手）
        11: 买二价
        ...
        19: 卖一价
        20: 卖一量（手）
        ...
        29: 涨跌额
        30: 涨跌幅(%)
        31: 最高价
        32: 最低价
        ...
        37: 成交额（万元）
        38: 换手率(%)
        39: 市盈率
        ...
        44: 最高价
        45: 最低价
        46: 振幅(%)
        47: 流通市值（亿）
        48: 总市值（亿）
        ...
        """
        try:
            if len(fields) < 49:
                return None

            name = fields[1]
            price = float(fields[3]) if fields[3] else 0
            pre_close = float(fields[4]) if fields[4] else 0
            open_price = float(fields[5]) if fields[5] else 0
            volume = float(fields[6]) * 100 if fields[6] else 0  # 手转换为股
            bid1_price = float(fields[9]) if fields[9] else 0
            bid1_volume = float(fields[10]) * 100 if fields[10] else 0
            ask1_price = float(fields[19]) if len(fields) > 19 and fields[19] else 0
            ask1_volume = float(fields[20]) * 100 if len(fields) > 20 and fields[20] else 0
            change_amount = float(fields[29]) if fields[29] else 0
            change_pct = float(fields[30]) if fields[30] else 0
            high = float(fields[31]) if fields[31] else 0
            low = float(fields[32]) if fields[32] else 0
            amount = float(fields[37]) * 10000 if fields[37] else 0  # 万元转换为元
            turnover_rate = float(fields[38]) if fields[38] else 0
            pe = float(fields[39]) if fields[39] else None

            now = datetime.now()

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
                turnover_rate=turnover_rate,
                pe=pe,
                bid1_price=bid1_price,
                bid1_volume=bid1_volume,
                ask1_price=ask1_price,
                ask1_volume=ask1_volume,
                timestamp=now.strftime('%Y-%m-%d %H:%M:%S'),
                trade_date=now.strftime('%Y-%m-%d'),
                source='腾讯',
                market='A',
            )
        except Exception as e:
            logger.warning(f"解析腾讯A股数据失败 {code}: {e}")
            return None

    def _parse_hk_quote(self, code: str, fields: list) -> Optional[QuoteData]:
        """解析港股行情数据

        腾讯港股数据格式（40+个字段）：
        0: 股票代码
        1: 股票中文名
        2: 股票英文名
        3: 当前价格（港币）
        4: 昨收（港币）
        5: 开盘价（港币）
        6: 成交量（股）
        7: 外盘
        8: 内盘
        9: 买一价
        10: 买一量
        11: 买二价
        ...
        19: 卖一价
        20: 卖一量
        ...
        29: 涨跌额
        30: 涨跌幅(%)
        31: 最高价
        32: 最低价
        ...
        37: 成交额（港币）
        38: 换手率(%)
        39: 市盈率
        ...
        """
        try:
            if len(fields) < 37:
                return None

            name = fields[1]
            price = float(fields[3]) if fields[3] else 0
            pre_close = float(fields[4]) if fields[4] else 0
            open_price = float(fields[5]) if fields[5] else 0
            volume = float(fields[6]) if fields[6] else 0
            bid1_price = float(fields[9]) if fields[9] else 0
            bid1_volume = float(fields[10]) if fields[10] else 0
            ask1_price = float(fields[19]) if len(fields) > 19 and fields[19] else 0
            ask1_volume = float(fields[20]) if len(fields) > 20 and fields[20] else 0
            change_amount = float(fields[29]) if fields[29] else 0
            change_pct = float(fields[30]) if fields[30] else 0
            high = float(fields[31]) if fields[31] else 0
            low = float(fields[32]) if fields[32] else 0
            amount = float(fields[37]) if fields[37] else 0

            now = datetime.now()

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
                bid1_price=bid1_price,
                bid1_volume=bid1_volume,
                ask1_price=ask1_price,
                ask1_volume=ask1_volume,
                timestamp=now.strftime('%Y-%m-%d %H:%M:%S'),
                trade_date=now.strftime('%Y-%m-%d'),
                source='腾讯',
                market='HK',
            )
        except Exception as e:
            logger.warning(f"解析腾讯港股数据失败 {code}: {e}")
            return None

    def get_batch_quotes(self, codes: list[str], market: str = 'A') -> dict[str, QuoteData]:
        """批量获取行情（腾讯支持批量查询）"""
        if not self.is_connected():
            if not self.connect():
                return {}

        try:
            # 构建批量查询符号
            symbols = [self._format_symbol(code, market) for code in codes]
            symbol_str = ','.join(symbols)

            url = self.QUOTE_URL.format(symbol=symbol_str)
            resp = self._session.get(url, timeout=15)
            resp.encoding = 'gbk'
            text = resp.text

            result = {}
            # 解析多只股票的数据
            pattern = r'v_(\w+)="(.+)"'
            matches = re.findall(pattern, text)

            for symbol, data in matches:
                if not data:
                    continue

                # 从symbol中提取原始代码
                if symbol.startswith('r_hk'):
                    code = symbol[4:]
                    hk_market = 'HK'
                elif symbol.startswith('sh'):
                    code = symbol[2:]
                    hk_market = 'A'
                elif symbol.startswith('sz'):
                    code = symbol[2:]
                    hk_market = 'A'
                else:
                    code = symbol
                    hk_market = 'A'

                fields = data.split('~')
                if hk_market == 'HK':
                    quote = self._parse_hk_quote(code, fields)
                else:
                    quote = self._parse_a_quote(code, fields)

                if quote:
                    result[code] = quote

            return result

        except Exception as e:
            logger.warning(f"腾讯批量获取行情失败: {e}")
            return {}
