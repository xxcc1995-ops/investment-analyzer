"""可转债双低轮动策略服务 - 从集思录获取可转债数据"""

import requests
import logging
import time
from typing import Optional, List, Dict
from datetime import datetime

logger = logging.getLogger(__name__)

# 缓存
_cache: Dict[str, tuple] = {}
CACHE_TTL = 300  # 5分钟缓存


def _get_cache(key: str) -> Optional[dict]:
    if key in _cache:
        data, ts = _cache[key]
        if time.time() - ts < CACHE_TTL:
            return data
        del _cache[key]
    return None


def _set_cache(key: str, data: dict):
    _cache[key] = (data, time.time())


def _safe_float(val, default=0.0) -> float:
    try:
        if val is None or val == '' or val == '-':
            return default
        return float(val)
    except (ValueError, TypeError):
        return default


class CBService:
    """可转债双低轮动策略服务"""

    JISILU_CB_URL = 'https://www.jisilu.cn/data/cbnew/cb_list/'

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.jisilu.cn/data/cbnew/',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'X-Requested-With': 'XMLHttpRequest',
    }

    @staticmethod
    def _get_session():
        """复用集思录登录态"""
        from app.services.fund_service import _jisilu_session, _jisilu_logged_in
        if _jisilu_session and _jisilu_logged_in:
            return _jisilu_session
        session = requests.Session()
        session.headers.update(CBService.HEADERS)
        return session

    @staticmethod
    def _fetch_jisilu_cb() -> List[dict]:
        """从集思录获取可转债数据"""
        session = CBService._get_session()
        try:
            headers = dict(CBService.HEADERS)
            resp = session.get(CBService.JISILU_CB_URL, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            rows = []
            for row in data.get('rows', []):
                cell = row.get('cell', {})
                if cell:
                    rows.append(cell)
            return rows
        except Exception as e:
            logger.warning(f"获取集思录可转债数据失败: {e}")
            return []

    @staticmethod
    def _normalize_cb(cell: dict) -> Optional[dict]:
        """标准化可转债数据"""
        try:
            bond_id = cell.get('bond_id', '')
            bond_nm = cell.get('bond_nm', '')
            stock_id = cell.get('stock_id', '')
            stock_nm = cell.get('stock_nm', '')

            price = _safe_float(cell.get('price', 0))
            if price <= 0:
                return None

            # 转股价和转股价值
            convert_price = _safe_float(cell.get('convert_price', 0))
            convert_value = _safe_float(cell.get('convert_value', 0))
            if convert_value <= 0 and convert_price > 0:
                # 转股价值 = 正股价格 / 转股价 * 100
                stock_price = _safe_float(cell.get('sprice', 0))
                if stock_price > 0:
                    convert_value = round(stock_price / convert_price * 100, 2)

            # 转股溢价率
            premium_rt = _safe_float(cell.get('premium_rt', 0))
            if premium_rt == 0 and convert_value > 0:
                premium_rt = round((price - convert_value) / convert_value * 100, 2)

            # 双低值 = 转债价格 + 转股溢价率
            double_low = round(price + premium_rt, 2)

            # 到期时间
            maturity_dt = cell.get('maturity_dt', '')
            year_left = _safe_float(cell.get('year_left', 0))

            # 信用评级
            rating_cd = cell.get('rating_cd', '')

            # 剩余规模(亿)
            curr_iss_amt = _safe_float(cell.get('curr_iss_amt', 0))

            # 成交额(万)
            volume = _safe_float(cell.get('volume', 0))
            amount = _safe_float(cell.get('amount', 0))
            turnover = amount if amount > 0 else volume * price / 10

            # 正股价
            stock_price = _safe_float(cell.get('sprice', 0))
            # 正股涨跌幅
            stock_change = _safe_float(cell.get('sincrease_rt', 0))
            # 转债涨跌幅
            bond_change = _safe_float(cell.get('increase_rt', 0))

            # 是否强赎
            force_redeem = cell.get('force_redeem', '')
            # 是否到期
            is_matured = year_left <= 0

            return {
                'bond_id': bond_id,
                'bond_nm': bond_nm,
                'stock_id': stock_id,
                'stock_nm': stock_nm,
                'price': price,
                'convert_price': convert_price,
                'convert_value': convert_value,
                'premium_rt': premium_rt,
                'double_low': double_low,
                'maturity_dt': maturity_dt,
                'year_left': year_left,
                'rating_cd': rating_cd,
                'curr_iss_amt': curr_iss_amt,
                'turnover': round(turnover, 2),
                'stock_price': stock_price,
                'stock_change': stock_change,
                'bond_change': bond_change,
                'force_redeem': force_redeem,
                'is_matured': is_matured,
            }
        except Exception as e:
            logger.warning(f"标准化可转债数据失败: {e}")
            return None

    @staticmethod
    def get_double_low_list(
        max_double_low: float = 130.0,
        min_rating: str = 'A',
        min_year_left: float = 1.0,
        min_turnover: float = 100.0,
        top_n: int = 20,
        exclude_st: bool = True,
        exclude_force_redeem: bool = True,
    ) -> dict:
        """获取双低排名

        Args:
            max_double_low: 双低值上限，默认130
            min_rating: 最低信用评级，默认A
            min_year_left: 最低剩余年限，默认1年
            min_turnover: 最低成交额(万)，默认100万
            top_n: 返回前N只，默认20
            exclude_st: 排除ST
            exclude_force_redeem: 排除已公告强赎
        """
        cache_key = f"cb_{max_double_low}_{min_rating}_{min_year_left}_{min_turnover}_{top_n}_{exclude_st}_{exclude_force_redeem}"
        cached = _get_cache(cache_key)
        if cached:
            return cached

        raw_bonds = CBService._fetch_jisilu_cb()

        if not raw_bonds:
            return {
                'bonds': [],
                'total': 0,
                'total_before_filter': 0,
                'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'error': '无法获取可转债数据',
            }

        total_before = len(raw_bonds)

        # 标准化
        bonds = []
        for cell in raw_bonds:
            bond = CBService._normalize_cb(cell)
            if bond:
                bonds.append(bond)

        # 筛选: 排除ST
        if exclude_st:
            bonds = [b for b in bonds if 'ST' not in b['bond_nm'] and 'ST' not in b['stock_nm']]

        # 筛选: 排除已公告强赎
        if exclude_force_redeem:
            bonds = [b for b in bonds if not b['force_redeem']]

        # 筛选: 剩余年限
        if min_year_left > 0:
            bonds = [b for b in bonds if b['year_left'] >= min_year_left]

        # 筛选: 成交额
        if min_turnover > 0:
            bonds = [b for b in bonds if b['turnover'] >= min_turnover]

        # 筛选: 双低值上限
        if max_double_low > 0:
            bonds = [b for b in bonds if b['double_low'] <= max_double_low]

        # 筛选: 信用评级
        rating_order = {'AAA': 6, 'AA+': 5, 'AA': 4, 'AA-': 3, 'A+': 2, 'A': 1, 'A-': 0}
        min_rating_val = rating_order.get(min_rating, 0)
        bonds = [b for b in bonds if rating_order.get(b['rating_cd'], 0) >= min_rating_val]

        # 排序: 双低值升序
        bonds.sort(key=lambda x: x['double_low'])

        # 取前N只
        top_bonds = bonds[:top_n]

        result = {
            'bonds': top_bonds,
            'total': len(bonds),
            'total_before_filter': total_before,
            'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'max_double_low': max_double_low,
            'top_n': top_n,
        }

        _set_cache(cache_key, result)
        return result

    @staticmethod
    def refresh_data() -> dict:
        _cache.clear()
        return CBService.get_double_low_list()
