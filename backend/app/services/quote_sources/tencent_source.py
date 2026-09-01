"""腾讯行情数据源（含日内分时、五档盘口、5分钟K线）

本模块在原有快照行情基础上，为「日内实时做T」扩展：
1. 五档买卖盘解析（qt.gtimg.cn 返回 fields[9..28]）
2. 分时线接口（web.ifzq.gtimg.cn/appstock/app/minute/query）
3. 5分钟K线接口（web.ifzq.gtimg.cn/appstock/app/kline/mkline）

数据源可靠性（遵循 CLAUDE.md「宁可空着不要不可靠数据」）：
- 实时快照 + 五档：腾讯 qt.gtimg.cn，与 CLAUDE.md 登记的港股源一致，高可靠
- 分时线 / 5分钟K：腾讯 web.ifzq.gtimg.cn，与现有 _fetch_a_historical 同域名族
- 无逐笔：免费源不提供，UI 须明确标注「最细粒度 1 分钟分时 + 实时五档」
- 解析失败 / 字段缺失：返回 None 或空列表 + 明确原因，绝不编造
"""

import re
import logging
import requests
from typing import Optional
from datetime import datetime
from .base import BaseQuoteSource, QuoteData

logger = logging.getLogger(__name__)


class TencentSource(BaseQuoteSource):
    """腾讯行情数据源（主要用于港股，含日内分时与五档盘口）"""

    # 实时行情接口（含五档买卖盘）
    QUOTE_URL = "https://qt.gtimg.cn/q={symbol}"
    # 分时线接口（当日1分钟分时）
    MINUTE_URL = "https://web.ifzq.gtimg.cn/appstock/app/minute/query?code={symbol}"
    # 多分钟K线接口（5分钟K，用于日内支撑压力计算）
    MKLINE_URL = "https://web.ifzq.gtimg.cn/appstock/app/kline/mkline?param={param}"

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
        """创建HTTP会话（带连接池和重试）"""
        try:
            self._session = self._create_session(pool_connections=5, pool_maxsize=10, retries=2)
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

    def _format_kline_symbol(self, code: str, market: str = 'A') -> str:
        """格式化K线/分时用的代码（无 r_ 前缀）"""
        if market == 'HK':
            return f'hk{code.zfill(5)}'
        if code.startswith('6'):
            return f'sh{code}'
        elif code.startswith(('0', '3')):
            return f'sz{code}'
        return f'sh{code}'

    @staticmethod
    def _parse_5_levels(fields: list) -> dict:
        """解析五档买卖盘

        腾讯 qt.gtimg.cn 字段索引：
        9-10  买一价/量, 11-12 买二, 13-14 买三, 15-16 买四, 17-18 买五
        19-20 卖一价/量, 21-22 卖二, 23-24 卖三, 25-26 卖四, 27-28 卖五

        港股量为股，A股量字段单位为手（×100 转股）。
        """
        def _f(idx):
            try:
                return float(fields[idx]) if idx < len(fields) and fields[idx] else 0.0
            except (ValueError, TypeError):
                return 0.0

        return {
            'bid1_price': _f(9), 'bid1_volume': _f(10),
            'bid2_price': _f(11), 'bid2_volume': _f(12),
            'bid3_price': _f(13), 'bid3_volume': _f(14),
            'bid4_price': _f(15), 'bid4_volume': _f(16),
            'bid5_price': _f(17), 'bid5_volume': _f(18),
            'ask1_price': _f(19), 'ask1_volume': _f(20),
            'ask2_price': _f(21), 'ask2_volume': _f(22),
            'ask3_price': _f(23), 'ask3_volume': _f(24),
            'ask4_price': _f(25), 'ask4_volume': _f(26),
            'ask5_price': _f(27), 'ask5_volume': _f(28),
        }

    def get_quote(self, code: str, market: str = 'A') -> Optional[QuoteData]:
        """获取单只股票实时行情（含五档买卖盘）"""
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
        """解析A股行情数据（含五档）

        腾讯A股数据格式（50+个字段）：
        0: 股票代码, 1: 股票名称, 2: 代码重复, 3: 当前价, 4: 昨收, 5: 开盘
        6: 成交量（手）, 9-18: 买一~买五价/量, 19-28: 卖一~卖五价/量
        29: 涨跌额, 30: 涨跌幅, 31: 最高, 32: 最低, 37: 成交额（万元）
        38: 换手率, 39: 市盈率
        """
        try:
            if len(fields) < 37:
                return None

            levels = self._parse_5_levels(fields)
            name = fields[1]
            price = float(fields[3]) if fields[3] else 0
            pre_close = float(fields[4]) if fields[4] else 0
            open_price = float(fields[5]) if fields[5] else 0
            volume = float(fields[6]) * 100 if fields[6] else 0  # 手→股
            change_amount = float(fields[29]) if fields[29] else 0
            change_pct = float(fields[30]) if fields[30] else 0
            high = float(fields[31]) if fields[31] else 0
            low = float(fields[32]) if fields[32] else 0
            amount = float(fields[37]) * 10000 if fields[37] else 0  # 万元→元
            turnover_rate = float(fields[38]) if fields[38] else 0
            pe = float(fields[39]) if fields[39] else None

            now = datetime.now()

            # A股量字段为「手」，五档量也需 ×100
            for k in levels:
                if k.endswith('volume'):
                    levels[k] = levels[k] * 100

            return QuoteData(
                code=code, name=name, price=price, open=open_price,
                high=high, low=low, pre_close=pre_close, volume=volume,
                amount=amount, change_pct=change_pct, change_amount=change_amount,
                turnover_rate=turnover_rate, pe=pe,
                bid1_price=levels['bid1_price'], bid1_volume=levels['bid1_volume'],
                ask1_price=levels['ask1_price'], ask1_volume=levels['ask1_volume'],
                bid2_price=levels['bid2_price'], bid2_volume=levels['bid2_volume'],
                bid3_price=levels['bid3_price'], bid3_volume=levels['bid3_volume'],
                bid4_price=levels['bid4_price'], bid4_volume=levels['bid4_volume'],
                bid5_price=levels['bid5_price'], bid5_volume=levels['bid5_volume'],
                ask2_price=levels['ask2_price'], ask2_volume=levels['ask2_volume'],
                ask3_price=levels['ask3_price'], ask3_volume=levels['ask3_volume'],
                ask4_price=levels['ask4_price'], ask4_volume=levels['ask4_volume'],
                ask5_price=levels['ask5_price'], ask5_volume=levels['ask5_volume'],
                timestamp=now.strftime('%Y-%m-%d %H:%M:%S'),
                trade_date=now.strftime('%Y-%m-%d'),
                source='腾讯', market='A',
            )
        except Exception as e:
            logger.warning(f"解析腾讯A股数据失败 {code}: {e}")
            return None

    def _parse_hk_quote(self, code: str, fields: list) -> Optional[QuoteData]:
        """解析港股行情数据（含五档）

        腾讯港股数据格式（实测 2026-08-06，与A股布局一致）：
        0: 市场标识(100), 1: 中文名, 2: 代码, 3: 现价(港币), 4: 昨收, 5: 开盘
        6: 成交量（股）, 9-18: 买一~买五价/量, 19-28: 卖一~卖五价/量
        29: 成交量(重复), 30: 行情时间字符串 'YYYY/MM/DD HH:MM:SS'
        31: 涨跌额, 32: 涨跌幅(%), 33: 最高, 34: 最低, 37: 成交额（港币）

        ⚠️ 历史 bug（2026-08-06 修复）：原实现把 29/30 当涨跌额/涨跌幅，
        导致 float('2026/08/06 14:39:25') 抛异常，整个港股行情解析失败返回 None。
        """
        try:
            if len(fields) < 38:
                return None

            def _f(idx: int) -> float:
                """安全取浮点，非数值返回 0（不编造数据）"""
                try:
                    v = fields[idx]
                    return float(v) if v not in (None, '', '-') else 0.0
                except (ValueError, TypeError, IndexError):
                    return 0.0

            levels = self._parse_5_levels(fields)
            name = fields[1]
            price = _f(3)
            pre_close = _f(4)
            open_price = _f(5)
            volume = _f(6)
            change_amount = _f(31)
            change_pct = _f(32)
            high = _f(33)
            low = _f(34)
            amount = _f(37)

            # 行情时间用接口返回的真实时间（而非本地时间），格式 2026/08/06 14:39:25
            raw_time = str(fields[30]).strip() if len(fields) > 30 else ''
            now = datetime.now()
            if raw_time and '/' in raw_time:
                quote_time = raw_time.replace('/', '-')
            else:
                quote_time = now.strftime('%Y-%m-%d %H:%M:%S')

            return QuoteData(
                code=code, name=name, price=price, open=open_price,
                high=high, low=low, pre_close=pre_close, volume=volume,
                amount=amount, change_pct=change_pct, change_amount=change_amount,
                bid1_price=levels['bid1_price'], bid1_volume=levels['bid1_volume'],
                ask1_price=levels['ask1_price'], ask1_volume=levels['ask1_volume'],
                bid2_price=levels['bid2_price'], bid2_volume=levels['bid2_volume'],
                bid3_price=levels['bid3_price'], bid3_volume=levels['bid3_volume'],
                bid4_price=levels['bid4_price'], bid4_volume=levels['bid4_volume'],
                bid5_price=levels['bid5_price'], bid5_volume=levels['bid5_volume'],
                ask2_price=levels['ask2_price'], ask2_volume=levels['ask2_volume'],
                ask3_price=levels['ask3_price'], ask3_volume=levels['ask3_volume'],
                ask4_price=levels['ask4_price'], ask4_volume=levels['ask4_volume'],
                ask5_price=levels['ask5_price'], ask5_volume=levels['ask5_volume'],
                timestamp=quote_time,
                trade_date=quote_time[:10],
                source='腾讯', market='HK',
            )
        except Exception as e:
            logger.warning(f"解析腾讯港股数据失败 {code}: {e}")
            return None

    def get_order_book(self, code: str, market: str = 'HK') -> Optional[dict]:
        """获取五档买卖盘结构化数据

        返回：
        {
            'bids': [{'price','volume'}, ...5档],
            'asks': [{'price','volume'}, ...5档],
            'spread': 卖一-买一价差,
            'spread_pct': 价差占比(%),
            'mid_price': 中间价,
            'imbalance': 买盘总量-卖盘总量（盘口失衡，正=买盘强）,
            'imbalance_pct': 失衡比例(%),
        }
        """
        quote = self.get_quote(code, market)
        if not quote:
            return None

        bids = [
            {'price': quote.bid1_price, 'volume': quote.bid1_volume},
            {'price': quote.bid2_price, 'volume': quote.bid2_volume},
            {'price': quote.bid3_price, 'volume': quote.bid3_volume},
            {'price': quote.bid4_price, 'volume': quote.bid4_volume},
            {'price': quote.bid5_price, 'volume': quote.bid5_volume},
        ]
        asks = [
            {'price': quote.ask1_price, 'volume': quote.ask1_volume},
            {'price': quote.ask2_price, 'volume': quote.ask2_volume},
            {'price': quote.ask3_price, 'volume': quote.ask3_volume},
            {'price': quote.ask4_price, 'volume': quote.ask4_volume},
            {'price': quote.ask5_price, 'volume': quote.ask5_volume},
        ]

        spread = quote.ask1_price - quote.bid1_price if quote.ask1_price > 0 and quote.bid1_price > 0 else 0
        mid_price = (quote.ask1_price + quote.bid1_price) / 2 if spread > 0 else quote.price
        spread_pct = round(spread / mid_price * 100, 3) if mid_price > 0 else 0

        total_bid = sum(b['volume'] for b in bids)
        total_ask = sum(a['volume'] for a in asks)
        imbalance = total_bid - total_ask
        imbalance_pct = round(imbalance / (total_bid + total_ask) * 100, 2) if (total_bid + total_ask) > 0 else 0

        return {
            'bids': bids,
            'asks': asks,
            'spread': round(spread, 3),
            'spread_pct': spread_pct,
            'mid_price': round(mid_price, 3),
            'total_bid_volume': total_bid,
            'total_ask_volume': total_ask,
            'imbalance': imbalance,
            'imbalance_pct': imbalance_pct,
            'current_price': quote.price,
            'timestamp': quote.timestamp,
        }

    def get_minute_kline(self, code: str, market: str = 'HK') -> list[dict]:
        """获取当日1分钟分时线

        腾讯接口：web.ifzq.gtimg.cn/appstock/app/minute/query?code=hk00700
        实测返回结构（2026-08-06 验证）：
          data.hk00700.data.data = ["0930 491.0 847107 415969176.6", ...]
          每行：时间(HHMM) 价格 累计成交量 累计成交额（空格分隔字符串）
          data.hk00700.qt.hk00700 = 盘口数组（量字段全0，免费源不提供真实五档量）

        每条记录：{'time': 'HH:MM', 'price': float, 'avg': float(累计均价), 'volume': float(当分钟增量)}
        """
        if not self.is_connected():
            if not self.connect():
                return []

        try:
            # 分时接口用无 r_ 前缀的代码（hk00700），r_ 前缀会报 code param error
            ksymbol = self._format_kline_symbol(code, market)
            url = self.MINUTE_URL.format(symbol=ksymbol)
            resp = self._session.get(url, timeout=10)
            data = resp.json()

            if data.get('code') not in (0, None) and not data.get('data'):
                logger.debug(f"腾讯分时接口返回异常 {code}: {data.get('msg', '')}")
                return []

            raw = data.get('data', {})
            # 定位分时对象：key 为 hk00700（无r_）
            minute_obj = None
            for key in (ksymbol, self._format_symbol(code, market), f'bk_{ksymbol}'):
                if key in raw and isinstance(raw[key], dict):
                    minute_obj = raw[key]
                    break
            if minute_obj is None:
                for v in raw.values():
                    if isinstance(v, dict) and ('data' in v or 'qt' in v):
                        minute_obj = v
                        break
            if minute_obj is None:
                return []

            # 分时列表路径：minute_obj.data.data（dict嵌套）或 minute_obj.qd
            qd = []
            d = minute_obj.get('data')
            if isinstance(d, dict):
                qd = d.get('data') or d.get('qd') or []
            elif isinstance(d, list):
                qd = d
            elif isinstance(minute_obj.get('qd'), list):
                qd = minute_obj['qd']
            if not qd:
                return []

            result = []
            prev_cum_vol = 0.0
            for row in qd:
                # 港股分时行格式为空格分隔字符串 "0930 491.0 847107 415969176.6"
                if isinstance(row, str):
                    parts = row.split()
                elif isinstance(row, (list, tuple)):
                    parts = [str(x) for x in row]
                else:
                    continue
                if len(parts) < 2:
                    continue
                try:
                    time_str = parts[0]
                    # 格式化 "0930" → "09:30"
                    if len(time_str) == 4 and time_str.isdigit():
                        time_str = f"{time_str[:2]}:{time_str[2:]}"
                    price = float(parts[1])
                    if price <= 0:
                        continue
                    cum_vol = float(parts[2]) if len(parts) > 2 else 0
                    cum_amount = float(parts[3]) if len(parts) > 3 else 0
                    # 当分钟增量成交量（接口给的是累计量）
                    minute_vol = max(cum_vol - prev_cum_vol, 0.0)
                    prev_cum_vol = cum_vol
                    # 累计均价（近似VWAP）
                    avg = cum_amount / cum_vol if cum_vol > 0 else price
                    result.append({
                        'time': time_str,
                        'price': price,
                        'avg': round(avg, 3),
                        'volume': minute_vol,
                    })
                except (ValueError, TypeError, IndexError):
                    continue

            return result

        except Exception as e:
            logger.warning(f"腾讯分时线获取失败 {code}: {e}")
            return []

    def get_5min_kline(self, code: str, market: str = 'HK', count: int = 300) -> list[dict]:
        """获取5分钟K线（用于日内支撑压力计算）

        腾讯接口：web.ifzq.gtimg.cn/appstock/app/kline/mkline?param=hk00700,m5,,300
        返回 data.hk00700.m5 = [[time, open, close, high, low, volume], ...]
        （字段顺序与现有 _fetch_a_historical 的 fqkline 一致：date/open/close/high/low/volume）

        每条记录：{'time': str, 'open': float, 'close': float, 'high': float, 'low': float, 'volume': float}
        """
        if not self.is_connected():
            if not self.connect():
                return []

        try:
            ksymbol = self._format_kline_symbol(code, market)  # hk00700
            param = f"{ksymbol},m5,,{count}"
            url = self.MKLINE_URL.format(param=param)
            resp = self._session.get(url, timeout=10)
            data = resp.json()

            raw = data.get('data', {})
            kline_obj = raw.get(ksymbol) or raw.get(symbol) if (symbol := self._format_symbol(code, market)) else None
            if kline_obj is None:
                for v in raw.values():
                    if isinstance(v, dict) and ('m5' in v or 'data' in v):
                        kline_obj = v
                        break
            if kline_obj is None:
                return []

            rows = kline_obj.get('m5') or kline_obj.get('data') or []
            result = []
            for row in rows:
                if not row or len(row) < 6:
                    continue
                try:
                    result.append({
                        'time': str(row[0]),
                        'open': float(row[1]),
                        'close': float(row[2]),
                        'high': float(row[3]),
                        'low': float(row[4]),
                        'volume': float(row[5]),
                    })
                except (ValueError, TypeError, IndexError):
                    continue
            return result

        except Exception as e:
            logger.warning(f"腾讯5分钟K线获取失败 {code}: {e}")
            return []

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
