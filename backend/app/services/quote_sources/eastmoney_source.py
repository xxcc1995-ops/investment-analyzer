"""东方财富行情数据源"""

import logging
import requests
from typing import Optional
from datetime import datetime
from .base import BaseQuoteSource, QuoteData

logger = logging.getLogger(__name__)


class EastmoneySource(BaseQuoteSource):
    """东方财富行情数据源"""

    # 实时行情接口
    QUOTE_URL = "https://push2.eastmoney.com/api/qt/stock/get"
    # 批量行情接口
    BATCH_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get"

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://quote.eastmoney.com/',
    }

    # 市场前缀映射
    # 0: 深圳, 1: 上海, 116: 港股
    MARKET_PREFIX = {
        'A_sh': 1,
        'A_sz': 0,
        'HK': 116,
    }

    def __init__(self):
        self._session: Optional[requests.Session] = None
        self._connected = False

    @property
    def name(self) -> str:
        return "东方财富"

    def connect(self) -> bool:
        """创建HTTP会话"""
        try:
            self._session = requests.Session()
            self._session.headers.update(self.HEADERS)
            # 测试连接
            resp = self._session.get(
                self.QUOTE_URL,
                params={
                    'secid': '1.000001',
                    'fields': 'f43,f44,f45,f46,f47,f48,f57,f58,f60',
                    'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
                },
                timeout=5
            )
            if resp.status_code == 200:
                self._connected = True
                logger.info("东方财富行情接口连接成功")
                return True
            else:
                self._connected = False
                return False
        except Exception as e:
            logger.warning(f"东方财富行情接口连接失败: {e}")
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

    def _get_secid(self, code: str, market: str = 'A') -> str:
        """获取东方财富证券ID格式

        格式: 市场代码.股票代码
        1: 上海, 0: 深圳, 116: 港股
        """
        if market == 'HK':
            return f'116.{code.zfill(5)}'

        # A股自动判断市场
        if code.startswith(('6', '5', '9')):
            return f'1.{code}'  # 上海
        elif code.startswith(('0', '1', '2', '3')):
            return f'0.{code}'  # 深圳
        elif code.startswith(('4', '8')):
            return f'0.{code}'  # 北交所/新三板
        else:
            return f'1.{code}'

    def get_quote(self, code: str, market: str = 'A') -> Optional[QuoteData]:
        """获取单只股票实时行情"""
        if not self.is_connected():
            if not self.connect():
                return None

        try:
            secid = self._get_secid(code, market)

            params = {
                'secid': secid,
                'fields': 'f43,f44,f45,f46,f47,f48,f51,f52,f55,f57,f58,f60,f116,f117,f162,f167,f168,f169,f170,f171',
                'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
            }

            resp = self._session.get(self.QUOTE_URL, params=params, timeout=10)
            data = resp.json()

            if not data.get('data'):
                logger.warning(f"东方财富行情数据为空: {code}")
                return None

            d = data['data']

            # 东方财富价格单位是分（除以100或1000）
            # 港股价格单位是厘（除以1000）
            divisor = 1000 if market == 'HK' else 100

            price = d.get('f43', 0) / divisor
            pre_close = d.get('f60', 0) / divisor
            open_price = d.get('f44', 0) / divisor
            high = d.get('f45', 0) / divisor
            low = d.get('f46', 0) / divisor
            volume = d.get('f47', 0)  # 成交量（股）
            amount = d.get('f48', 0)  # 成交额（元）

            change_pct = self._calc_change_pct(price, pre_close)
            change_amount = round(price - pre_close, 3) if pre_close else 0

            # PE(TTM) 和 PB
            pe = d.get('f162', 0) / 100 if d.get('f162') else None
            pb = d.get('f167', 0) / 100 if d.get('f167') else None

            # 总市值和流通市值
            total_market_cap = d.get('f116', 0)
            circulating_market_cap = d.get('f117', 0)

            # 换手率
            turnover_rate = d.get('f168', 0) / 100 if d.get('f168') else 0

            name = d.get('f58', code)
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
                pb=pb,
                total_market_cap=total_market_cap,
                circulating_market_cap=circulating_market_cap,
                timestamp=now.strftime('%Y-%m-%d %H:%M:%S'),
                trade_date=now.strftime('%Y-%m-%d'),
                source='东方财富',
                market=market,
            )

        except Exception as e:
            logger.warning(f"东方财富获取行情失败 {code}: {e}")
            return None

    def get_batch_quotes(self, codes: list[str], market: str = 'A') -> dict[str, QuoteData]:
        """批量获取行情"""
        if not self.is_connected():
            if not self.connect():
                return {}

        try:
            # 构建secids
            secids = [self._get_secid(code, market) for code in codes]
            secids_str = ','.join(secids)

            params = {
                'secids': secids_str,
                'fields': 'f12,f14,f2,f3,f4,f5,f6,f7,f8,f15,f16,f17,f18',
                'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
                'fltt': 2,
                'invt': 2,
            }

            resp = self._session.get(self.BATCH_URL, params=params, timeout=15)
            data = resp.json()

            result = {}
            diff = data.get('data', {}).get('diff', [])

            if diff:
                for item in diff:
                    code = item.get('f12', '')
                    if not code:
                        continue

                    price = item.get('f2', 0)
                    if price == '-':
                        continue

                    price = float(price)
                    pre_close = float(item.get('f18', 0))
                    change_pct = float(item.get('f3', 0))
                    change_amount = float(item.get('f4', 0))
                    volume = float(item.get('f5', 0))
                    amount = float(item.get('f6', 0))
                    high = float(item.get('f15', 0))
                    low = float(item.get('f16', 0))
                    open_price = float(item.get('f17', 0))
                    turnover_rate = float(item.get('f8', 0))
                    name = item.get('f14', code)

                    now = datetime.now()

                    quote = QuoteData(
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
                        timestamp=now.strftime('%Y-%m-%d %H:%M:%S'),
                        trade_date=now.strftime('%Y-%m-%d'),
                        source='东方财富',
                        market=market,
                    )
                    result[code] = quote

            return result

        except Exception as e:
            logger.warning(f"东方财富批量获取行情失败: {e}")
            return {}
