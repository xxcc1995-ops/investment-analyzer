"""基金套利数据服务 - 从集思录获取LOF/ETF折溢价数据"""

import requests
import logging
import time
from typing import Optional, List, Dict
from datetime import datetime
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)

# 缓存: {cache_key: (data, timestamp)}
_cache: Dict[str, tuple] = {}
CACHE_TTL = 300  # 5分钟缓存

# 集思录登录态
_jisilu_session: Optional[requests.Session] = None
_jisilu_logged_in = False


def _get_cache(key: str) -> Optional[dict]:
    if key in _cache:
        data, ts = _cache[key]
        if time.time() - ts < CACHE_TTL:
            return data
        del _cache[key]
    return None


def _set_cache(key: str, data: dict):
    _cache[key] = (data, time.time())


def _parse_fee(fee_str: str) -> float:
    if not fee_str or fee_str == '-':
        return 0.0
    try:
        return float(fee_str.replace('%', ''))
    except (ValueError, TypeError):
        return 0.0


def _estimate_profit(price: float, nav: float, apply_fee: str, redeem_fee: str, direction: str) -> float:
    """预估套利收益率(%), 扣除交易费用"""
    if direction == "溢价":
        fee = _parse_fee(apply_fee)
        gross = (price - nav) / nav * 100
        return round(gross - fee, 3)
    else:
        fee = _parse_fee(redeem_fee)
        gross = (nav - price) / price * 100
        return round(gross - fee, 3)


class FundService:
    """基金套利数据服务"""

    JISILU_LOF_URLS = [
        'https://www.jisilu.cn/data/lof/stock_lof_list/',
        'https://www.jisilu.cn/data/lof/index_lof_list/',
    ]

    JISILU_AES_KEY = '397151C04723421F'

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.jisilu.cn/data/lof/',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'X-Requested-With': 'XMLHttpRequest',
    }

    @staticmethod
    def _jslencode(text: str, aes_key: str) -> str:
        """集思录AES加密 - ECB模式, PKCS7填充, 输出十六进制"""
        key = aes_key.encode('utf-8')
        src = text.encode('utf-8')
        # PKCS7 padding
        bs = 16
        pad_len = bs - len(src) % bs
        src = src + bytes([pad_len] * pad_len)
        cipher = Cipher(algorithms.AES(key), modes.ECB(), backend=default_backend())
        encryptor = cipher.encryptor()
        ct = encryptor.update(src) + encryptor.finalize()
        return ct.hex()

    @staticmethod
    def login(user_name: str, password: str) -> dict:
        """登录集思录, 获取完整数据权限"""
        global _jisilu_session, _jisilu_logged_in

        session = requests.Session()
        session.headers.update({
            'User-Agent': FundService.HEADERS['User-Agent'],
            'Referer': 'https://www.jisilu.cn/login/',
            'Origin': 'https://www.jisilu.cn',
        })

        # 先访问登录页获取cookie
        try:
            session.get('https://www.jisilu.cn/login/', timeout=15)
        except Exception as e:
            return {'success': False, 'error': f'访问登录页失败: {e}'}

        # AES加密用户名和密码
        enc_user = FundService._jslencode(user_name, FundService.JISILU_AES_KEY)
        enc_pass = FundService._jslencode(password, FundService.JISILU_AES_KEY)

        login_url = 'https://www.jisilu.cn/webapi/account/login_process/'
        login_data = {
            'return_url': '/',
            'user_name': enc_user,
            'password': enc_pass,
            'aes': '1',
            'auto_login': '1',
        }

        try:
            resp = session.post(login_url, data=login_data, timeout=15)
            result = resp.json()

            if result.get('code') == 200:
                _jisilu_session = session
                _jisilu_logged_in = True
                _cache.clear()
                return {'success': True, 'msg': '登录成功'}
            else:
                err_msg = result.get('msg', '登录失败')
                return {'success': False, 'error': err_msg}
        except Exception as e:
            return {'success': False, 'error': f'登录请求失败: {e}'}

    @staticmethod
    def get_login_status() -> dict:
        return {'logged_in': _jisilu_logged_in}

    @staticmethod
    def _get_session() -> requests.Session:
        """获取请求session(登录态或匿名)"""
        if _jisilu_session and _jisilu_logged_in:
            return _jisilu_session
        session = requests.Session()
        session.headers.update(FundService.HEADERS)
        return session

    @staticmethod
    def _fetch_jisilu_lof() -> List[dict]:
        """从集思录获取LOF数据"""
        all_funds = []
        session = FundService._get_session()

        for url in FundService.JISILU_LOF_URLS:
            try:
                headers = dict(FundService.HEADERS)
                resp = session.get(url, headers=headers, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                for row in data.get('rows', []):
                    cell = row.get('cell', {})
                    if cell:
                        all_funds.append(cell)
            except Exception as e:
                logger.warning(f"获取集思录数据失败 [{url}]: {e}")

        return all_funds

    @staticmethod
    def _fetch_akshare_lof() -> List[dict]:
        """从AKShare获取LOF数据(备用)"""
        try:
            import akshare as ak
            df = ak.fund_lof_spot_em()
            funds = []
            for _, row in df.iterrows():
                funds.append({
                    'fund_id': str(row.get('代码', '')),
                    'fund_nm': str(row.get('名称', '')),
                    'price': str(row.get('最新价', 0)),
                    'fund_nav': str(row.get('净值', 0)),
                    'nav_discount_rt': str(row.get('折溢价率', 0)),
                    'increase_rt': str(row.get('涨跌幅', 0)),
                    'volume': str(row.get('成交量', 0)),
                    'amount': 0,
                    'apply_fee': '',
                    'redeem_fee': '',
                    'apply_status': '',
                    'redeem_status': '',
                    'nav_dt': '',
                    'price_dt': datetime.now().strftime('%Y-%m-%d'),
                    'issuer_nm': '',
                })
            return funds
        except Exception as e:
            logger.warning(f"AKShare获取LOF数据失败: {e}")
            return []

    @staticmethod
    def _normalize_fund(cell: dict) -> Optional[dict]:
        """标准化基金数据"""
        try:
            fund_id = cell.get('fund_id', '')
            fund_nm = cell.get('fund_nm', '')
            price_str = cell.get('price', '0')
            nav_str = cell.get('fund_nav', '0')
            discount_str = cell.get('discount_rt', '-') or cell.get('nav_discount_rt', '-')

            try:
                price = float(price_str)
                nav = float(nav_str)
            except (ValueError, TypeError):
                return None

            if price <= 0 or nav <= 0:
                return None

            try:
                nav_discount_rt = float(discount_str) if discount_str and discount_str != '-' else None
            except (ValueError, TypeError):
                nav_discount_rt = None

            if nav_discount_rt is None:
                nav_discount_rt = round((price - nav) / nav * 100, 2)

            direction = "溢价" if nav_discount_rt > 0 else "折价"

            apply_fee = cell.get('apply_fee', '')
            redeem_fee = cell.get('redeem_fee', '')
            estimated_profit = _estimate_profit(price, nav, apply_fee, redeem_fee, direction)

            try:
                increase_rt = float(cell.get('increase_rt', 0))
            except (ValueError, TypeError):
                increase_rt = 0.0

            # volume: 成交量(万份)
            try:
                volume = float(cell.get('volume', 0))
            except (ValueError, TypeError):
                volume = 0.0

            # amount: 份额(万份)
            try:
                amount = int(cell.get('amount', 0))
            except (ValueError, TypeError):
                amount = 0

            # 计算成交额(万元): 成交量(万份) * 价格
            turnover = round(volume * price, 2)

            # 申购限额
            apply_limit = cell.get('apply_limit', '')
            if not apply_limit:
                min_amt = cell.get('min_amt', '') or ''
                if '限额' in min_amt:
                    # 从min_amt中提取限额信息
                    for line in min_amt.split('\n'):
                        if '限额' in line:
                            apply_limit = line.strip()
                            break
                if not apply_limit:
                    apply_limit = '无限额'

            return {
                'fund_id': fund_id,
                'fund_nm': fund_nm,
                'price': price,
                'fund_nav': nav,
                'nav_discount_rt': nav_discount_rt,
                'increase_rt': increase_rt,
                'volume': volume,
                'turnover': turnover,       # 成交额(万元)
                'amount': amount,
                'direction': direction,
                'apply_fee': apply_fee,
                'redeem_fee': redeem_fee,
                'apply_status': cell.get('apply_status', ''),
                'redeem_status': cell.get('redeem_status', ''),
                'apply_limit': apply_limit,
                'nav_dt': cell.get('nav_dt', ''),
                'price_dt': cell.get('price_dt', ''),
                'issuer_nm': cell.get('issuer_nm', ''),
                'estimated_profit': estimated_profit,
            }
        except Exception as e:
            logger.warning(f"标准化基金数据失败: {e}")
            return None

    @staticmethod
    def get_arbitrage_opportunities(
        min_threshold: float = 0.0,
        direction: str = "all",
        min_turnover: float = 300.0,
        open_subscribe_only: bool = True,
    ) -> dict:
        """获取套利机会

        Args:
            min_threshold: 最低折溢价率阈值(%), 绝对值
            direction: 筛选方向 - "all"/"溢价"/"折价"
            min_turnover: 最低成交额(万元), 默认300万
            open_subscribe_only: 仅显示开放申购的基金
        """
        cache_key = f"arb_{min_threshold}_{direction}_{min_turnover}_{open_subscribe_only}"
        cached = _get_cache(cache_key)
        if cached:
            return cached

        raw_funds = FundService._fetch_jisilu_lof()
        data_source = "集思录"

        if not raw_funds:
            raw_funds = FundService._fetch_akshare_lof()
            data_source = "AKShare"

        if not raw_funds:
            return {
                'funds': [],
                'total': 0,
                'total_before_filter': 0,
                'min_threshold': min_threshold,
                'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'data_source': '无数据',
                'logged_in': _jisilu_logged_in,
                'error': '无法获取基金数据',
            }

        total_before = len(raw_funds)

        # 标准化
        funds = []
        for cell in raw_funds:
            fund = FundService._normalize_fund(cell)
            if fund:
                funds.append(fund)

        # 筛选: 成交额 ≥ 300万
        if min_turnover > 0:
            funds = [f for f in funds if f['turnover'] >= min_turnover]

        # 筛选: 开放申购
        if open_subscribe_only:
            funds = [f for f in funds if '开放' in f.get('apply_status', '')]

        # 筛选: 折溢价方向
        if direction == "溢价":
            funds = [f for f in funds if f['nav_discount_rt'] > min_threshold]
        elif direction == "折价":
            funds = [f for f in funds if f['nav_discount_rt'] < -min_threshold]
        elif min_threshold > 0:
            funds = [f for f in funds if abs(f['nav_discount_rt']) > min_threshold]

        # 排序: 溢价率升序(溢价率越低, 套利空间越大)
        funds.sort(key=lambda x: x['nav_discount_rt'])

        result = {
            'funds': funds,
            'total': len(funds),
            'total_before_filter': total_before,
            'min_threshold': min_threshold,
            'min_turnover': min_turnover,
            'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'data_source': data_source,
            'logged_in': _jisilu_logged_in,
        }

        _set_cache(cache_key, result)
        return result

    @staticmethod
    def refresh_data() -> dict:
        _cache.clear()
        return FundService.get_arbitrage_opportunities()
