"""可转债双低轮动策略服务 - 从集思录获取可转债数据，支持多维度质量评分

机构级增强：
- 多源容错：集思录优先，AKShare(东方财富)兜底
- 纯债价值计算（现金流折现）
- 税后到期收益率
- 三低策略（低价格+低溢价+低规模）
- 强赎风险量化
- 下修概率评估
- 交易时间感知缓存TTL
"""

import requests
import logging
import time
import threading
from typing import Optional, List, Dict, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

from app.core.cache import get_cache as _get_cache, set_cache as _set_cache, clear_cache as _clear_cache, get_realtime_ttl as _get_realtime_ttl
from app.core.utils import safe_float as _safe_float

# ==================== 多源容错健康追踪 ====================
_source_health_lock = threading.Lock()
_source_health = {
    'jisilu': {'healthy': True, 'last_fail': 0, 'cooldown': 60},
    'akshare': {'healthy': True, 'last_fail': 0, 'cooldown': 60},
}


def _mark_source_fail(source: str):
    with _source_health_lock:
        _source_health[source]['healthy'] = False
        _source_health[source]['last_fail'] = time.time()


def _mark_source_ok(source: str):
    with _source_health_lock:
        _source_health[source]['healthy'] = True


def _is_source_healthy(source: str) -> bool:
    with _source_health_lock:
        info = _source_health[source]
        if info['healthy']:
            return True
        # 冷却期过后自动恢复
        if time.time() - info['last_fail'] > info['cooldown']:
            info['healthy'] = True
            return True
        return False


class CBService:
    """可转债双低轮动策略服务（增强版：多维度质量评分）"""

    JISILU_CB_URL = 'https://www.jisilu.cn/data/cbnew/cb_list/'

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.jisilu.cn/data/cbnew/',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'X-Requested-With': 'XMLHttpRequest',
    }

    # 信用评级排序
    RATING_ORDER = {'AAA': 6, 'AA+': 5, 'AA': 4, 'AA-': 3, 'A+': 2, 'A': 1, 'A-': 0, 'BBB': -1}

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
    def _fetch_akshare_cb() -> List[dict]:
        """从AKShare(东方财富)获取可转债数据 — 集思录不可用时的兜底"""
        try:
            import akshare as ak
            df = ak.bond_zh_cov()
            if df is None or df.empty:
                return []

            # AKShare返回的列名（中文），需要映射到集思录格式
            # 列名可能随版本变化，使用防御性映射
            col_map = {}
            cols = list(df.columns)

            # 按位置和关键字双重匹配
            for i, col in enumerate(cols):
                col_str = str(col)
                if '代码' in col_str and '正股' not in col_str:
                    col_map['bond_id'] = i
                elif '名称' in col_str and '正股' not in col_str:
                    col_map['bond_nm'] = i
                elif '正股代码' in col_str:
                    col_map['stock_id'] = i
                elif '正股名称' in col_str:
                    col_map['stock_nm'] = i
                elif col_str == '正股价' or (i == 7 and '价' in col_str):
                    col_map['sprice'] = i
                elif '转股价' in col_str and '值' not in col_str:
                    col_map['convert_price'] = i
                elif '转股价值' in col_str:
                    col_map['convert_value'] = i
                elif '溢价率' in col_str:
                    col_map['premium_rt'] = i
                elif '信用评级' in col_str or '评级' in col_str:
                    col_map['rating_cd'] = i
                elif '剩余规模' in col_str or '现价' == col_str:
                    pass  # handled separately
                elif '面值' in col_str:
                    col_map['price'] = i
                elif '申购日期' in col_str or '上市时间' in col_str:
                    pass  # skip dates

            rows = []
            for _, row in df.iterrows():
                try:
                    def safe_get(key):
                        idx = col_map.get(key)
                        if idx is not None and idx < len(row):
                            val = row.iloc[idx]
                            if val is not None and str(val) != 'nan':
                                return val
                        return ''

                    bond_id = str(safe_get('bond_id'))
                    if not bond_id:
                        continue

                    cell = {
                        'bond_id': bond_id,
                        'bond_nm': str(safe_get('bond_nm')),
                        'stock_id': str(safe_get('stock_id')),
                        'stock_nm': str(safe_get('stock_nm')),
                        'price': safe_get('price'),
                        'convert_price': safe_get('convert_price'),
                        'convert_value': safe_get('convert_value'),
                        'premium_rt': safe_get('premium_rt'),
                        'rating_cd': str(safe_get('rating_cd')),
                        'sprice': safe_get('sprice'),
                        # AKShare不提供的字段，设为空/默认值
                        'ytm_rt': '',
                        'put_ytm_rt': '',
                        'next_put_dt': '',
                        'convert_dt': '',
                        'force_redeem': '',
                        'redeem_price': '',
                        'dividend_yield': '',
                        'market_cap': '',
                        'curr_iss_amt': '',
                        'volume': '',
                        'amount': '',
                        'year_left': '',
                        'maturity_dt': '',
                        'orig_iss_amt': '',
                        'stock_pe': '',
                        'stock_pb': '',
                        'convert_flag': '',
                        'increase_rt': '',
                        'sincrease_rt': '',
                    }
                    rows.append(cell)
                except Exception:
                    continue

            logger.info(f"AKShare获取可转债数据成功: {len(rows)}只")
            return rows

        except Exception as e:
            logger.warning(f"AKShare获取可转债数据失败: {e}")
            return []

    @staticmethod
    def _fetch_cb_data() -> Tuple[List[dict], str]:
        """多源容错获取可转债数据

        Returns:
            (rows, data_source): 数据行列表 + 数据来源标识
            data_source: 'jisilu' / 'akshare' / 'none'
        """
        # 1. 优先集思录
        if _is_source_healthy('jisilu'):
            rows = CBService._fetch_jisilu_cb()
            if rows:
                _mark_source_ok('jisilu')
                return rows, 'jisilu'
            else:
                _mark_source_fail('jisilu')

        # 2. AKShare兜底
        if _is_source_healthy('akshare'):
            rows = CBService._fetch_akshare_cb()
            if rows:
                _mark_source_ok('akshare')
                return rows, 'akshare'
            else:
                _mark_source_fail('akshare')

        return [], 'none'

    @staticmethod
    def _normalize_cb(cell: dict) -> Optional[dict]:
        """标准化可转债数据（增强版：提取更多字段）"""
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

            # ===== 新增字段 =====

            # 到期收益率（税前，%）
            ytm_rt = _safe_float(cell.get('ytm_rt', 0))
            # 回售收益率（税前，%）
            put_ytm_rt = _safe_float(cell.get('put_ytm_rt', 0))
            # 下次回售日
            next_put_dt = cell.get('next_put_dt', '')
            # 转股起始日
            convert_dt = cell.get('convert_dt', '')
            # 发行规模(亿)
            orig_iss_amt = _safe_float(cell.get('orig_iss_amt', 0))
            # 正股PE
            stock_pe = _safe_float(cell.get('stock_pe', 0))
            # 正股PB
            stock_pb = _safe_float(cell.get('stock_pb', 0))
            # 是否进入转股期
            convert_flag = cell.get('convert_flag', '')
            # 强赎触发价
            redeem_price = _safe_float(cell.get('redeem_price', 0))
            # 正股股息率
            dividend_yield = _safe_float(cell.get('dividend_yield', 0))
            # 正股市值(亿)
            market_cap = _safe_float(cell.get('market_cap', 0))

            # 计算：距强赎触发距离（%）— 正股还需涨多少才触发强赎
            redeem_distance = 0
            if convert_value > 0 and redeem_price > 0 and convert_price > 0:
                redeem_distance = round((redeem_price / convert_price * 100 - convert_value) / convert_value * 100, 2)
            elif convert_value > 0:
                # 一般强赎触发条件：正股价 >= 转股价 * 130%
                trigger_value = 130  # 转股价值达到130
                if convert_value < trigger_value:
                    redeem_distance = round((trigger_value - convert_value) / convert_value * 100, 2)
                else:
                    redeem_distance = 0  # 已满足强赎条件

            # 计算：转股比率（已转股/发行比例）
            convert_ratio = 0
            if orig_iss_amt > 0 and curr_iss_amt >= 0:
                convert_ratio = round((1 - curr_iss_amt / orig_iss_amt) * 100, 2)

            # ===== 新增：纯债价值、税后YTM、三低值、强赎量化、下修概率 =====

            # 构建中间字典用于计算
            interim = {
                'price': price, 'ytm_rt': ytm_rt, 'year_left': year_left,
                'convert_value': convert_value, 'premium_rt': premium_rt,
                'force_redeem': force_redeem, 'redeem_distance': redeem_distance,
                'redeem_price': redeem_price, 'next_put_dt': next_put_dt,
                'convert_flag': convert_flag, 'curr_iss_amt': curr_iss_amt,
            }

            pure_bond_value = CBService._calc_pure_bond_value(interim)
            ytm_after_tax = CBService._calc_after_tax_ytm(interim)
            triple_low = round(price + premium_rt + curr_iss_amt * 10, 2)
            redeem_risk = CBService._quantify_force_redeem_risk(interim)
            revision_prob = CBService._score_revision_probability(interim)

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
                # 新增字段
                'ytm_rt': ytm_rt,
                'put_ytm_rt': put_ytm_rt,
                'next_put_dt': next_put_dt,
                'convert_dt': convert_dt,
                'orig_iss_amt': orig_iss_amt,
                'stock_pe': stock_pe,
                'stock_pb': stock_pb,
                'convert_flag': convert_flag,
                'redeem_price': redeem_price,
                'dividend_yield': dividend_yield,
                'market_cap': market_cap,
                'redeem_distance': redeem_distance,
                'convert_ratio': convert_ratio,
                # 机构级新增字段
                'pure_bond_value': pure_bond_value,
                'ytm_after_tax': ytm_after_tax,
                'triple_low': triple_low,
                'redeem_risk': redeem_risk,
                'revision_prob': revision_prob,
            }
        except Exception as e:
            logger.warning(f"标准化可转债数据失败: {e}")
            return None

    # ===== 纯债价值 & 税后YTM & 强赎量化 =====

    @staticmethod
    def _estimate_coupon_rate(bond: dict) -> float:
        """估算票面利率（基于价格和到期收益率反推）

        可转债通常采用阶梯利率（第一年0.2-0.5%，逐年递增，最后一年1.5-2.5%）。
        这里用近似公式反推平均票面利率。
        """
        price = bond.get('price', 0)
        ytm = bond.get('ytm_rt', 0) / 100  # % -> 小数
        year_left = bond.get('year_left', 0)

        if year_left <= 0.5 or price <= 0:
            return 0.01  # 默认1%

        # 近似公式：coupon ≈ (price * ytm + (100 - price) / year_left) / 100
        # 即年化利息 ≈ 持有收益 + 年化资本利得
        coupon = (price * ytm + (100 - price) / year_left) / 100
        return max(coupon, 0.002)  # 最低0.2%

    @staticmethod
    def _calc_pure_bond_value(bond: dict) -> float:
        """计算纯债价值（现金流折现）

        纯债价值 = 未来各年利息现值 + 到期面值现值
        折现率：使用到期收益率（市场一致），若YTM<=0则用3%保守折现率

        现金流模型（以year_left=3.5为例）：
          t=1: coupon (整数年利息)
          t=2: coupon
          t=3: coupon * fractional (部分年利息，如0.5年)
          t=3.5: face (到期兑付面值，含最后一年剩余时间的利息已折算)
        注意：不重复计算利息。整数年循环到 years_int-1，最后一年按 fractional 比例计算。
        """
        face = 100.0
        year_left = bond.get('year_left', 0)
        ytm = bond.get('ytm_rt', 0) / 100
        price = bond.get('price', 0)

        if year_left <= 0 or price <= 0:
            return price

        coupon_rate = CBService._estimate_coupon_rate(bond)

        # 折现率：YTM>0用YTM，否则用3%保守估计
        discount_rate = max(ytm, 0.03)

        pv = 0.0
        years_int = int(year_left)
        fractional = year_left - years_int

        # 前 years_int-1 年：全额利息
        for t in range(1, years_int):
            pv += face * coupon_rate / (1 + discount_rate) ** t

        # 最后一年：如果 fractional > 0，利息按比例；否则全额利息
        if fractional > 0:
            # 部分年利息（例如 year_left=3.5，第3年只拿0.5年利息）
            pv += face * coupon_rate * fractional / (1 + discount_rate) ** years_int
        else:
            # 整数年，最后一年全额利息
            pv += face * coupon_rate / (1 + discount_rate) ** years_int

        # 到期面值
        pv += face / (1 + discount_rate) ** year_left

        return round(pv, 2)

    @staticmethod
    def _calc_after_tax_ytm(bond: dict, tax_rate: float = 0.20) -> float:
        """计算税后到期收益率

        个人投资者：利息收入扣20%所得税，面值差额（100-买入价）免税。
        税后YTM = 使税后现金流现值 = 当前价格的折现率

        现金流模型与纯债价值一致，避免 fractional year 利息重复计算。
        """
        price = bond.get('price', 0)
        year_left = bond.get('year_left', 0)
        ytm_pretax = bond.get('ytm_rt', 0)

        if year_left <= 0 or price <= 0:
            return ytm_pretax

        coupon_rate = CBService._estimate_coupon_rate(bond)
        face = 100.0
        years_int = int(year_left)
        fractional = year_left - years_int

        def npv_after_tax(rate):
            if rate <= -1:
                return float('inf')
            total = 0.0
            # 前 years_int-1 年：全额利息（税后）
            for t in range(1, years_int):
                total += face * coupon_rate * (1 - tax_rate) / (1 + rate) ** t
            # 最后一年：部分或全额利息（税后）
            if fractional > 0:
                total += face * coupon_rate * fractional * (1 - tax_rate) / (1 + rate) ** years_int
            else:
                total += face * coupon_rate * (1 - tax_rate) / (1 + rate) ** years_int
            # 到期面值（免税）
            total += face / (1 + rate) ** year_left
            return total - price

        # 二分法求解，迭代50次精度约2^-50
        low, high = -0.05, 0.20
        for _ in range(50):
            mid = (low + high) / 2
            if npv_after_tax(mid) > 0:
                low = mid
            else:
                high = mid

        return round((low + high) / 2 * 100, 2)

    @staticmethod
    def _quantify_force_redeem_risk(bond: dict) -> dict:
        """量化强赎风险

        Returns:
            dict with keys:
            - redeem_risk_level: 'high'/'medium'/'low'/'none'
            - days_to_redeem_estimate: int or None
            - redeem_price_impact: 被强赎时的价格变动
            - redeem_timeline: 人类可读的时间线
            - is_in_redeem_zone: bool
        """
        force_redeem = bond.get('force_redeem', '')
        convert_value = bond.get('convert_value', 0)
        price = bond.get('price', 0)
        redeem_distance = bond.get('redeem_distance', 999)
        redeem_price = bond.get('redeem_price', 0)

        result = {
            'redeem_risk_level': 'none',
            'days_to_redeem_estimate': None,
            'redeem_price_impact': 0,
            'redeem_timeline': '',
            'is_in_redeem_zone': False,
        }

        # 已公告强赎
        if force_redeem:
            result['redeem_risk_level'] = 'high'
            result['redeem_timeline'] = '已公告强赎，需尽快转股或卖出'
            result['redeem_price_impact'] = round(price - 101.5, 2) if price > 0 else 0
            result['is_in_redeem_zone'] = True
            return result

        # 转股价值>=130，满足强赎条件
        if convert_value >= 130:
            result['redeem_risk_level'] = 'high'
            result['is_in_redeem_zone'] = True
            result['redeem_timeline'] = f'转股价值{convert_value:.0f}已超130，随时可能触发强赎'
            result['redeem_price_impact'] = round(price - 101.5, 2) if price > 101.5 else 0
            result['days_to_redeem_estimate'] = 15
            return result

        # 接近130阈值
        if redeem_distance <= 5:
            result['redeem_risk_level'] = 'medium'
            result['redeem_timeline'] = f'距强赎触发仅{redeem_distance:.1f}%，正股上涨即触发'
            result['days_to_redeem_estimate'] = max(1, int(redeem_distance / 2))
            result['redeem_price_impact'] = round(price - 101.5, 2) if price > 101.5 else 0
            return result

        if redeem_distance <= 15:
            result['redeem_risk_level'] = 'low'
            result['redeem_timeline'] = f'距强赎触发{redeem_distance:.1f}%，短期内可能接近'
            return result

        result['redeem_timeline'] = f'距强赎触发{redeem_distance:.1f}%，暂无风险'
        return result

    @staticmethod
    def _score_revision_probability(bond: dict) -> dict:
        """评估下修概率

        因素：
        1. 转股价值相对于下修触发线（通常为转股价的85%）的距离
        2. 距回售日的时间（越近，公司下修压力越大）
        3. 剩余期限（越短，促转股动力越强）
        4. 是否已进入转股期
        """
        score = 0
        factors = []

        cv = bond.get('convert_value', 0)
        year_left = bond.get('year_left', 0)
        next_put_dt = bond.get('next_put_dt', '')
        convert_flag = bond.get('convert_flag', '')

        # 转股价值在70-95区间：接近下修触发线
        if 70 <= cv <= 85:
            score += 40
            factors.append('接近下修触发线')
        elif 85 < cv <= 95:
            score += 25
            factors.append('下修空间存在')
        elif cv < 70:
            score += 20
            factors.append('深度虚值，下修动力强')

        # 距回售日越近，压力越大
        if next_put_dt:
            try:
                put_date = datetime.strptime(str(next_put_dt), '%Y-%m-%d')
                days_to_put = (put_date - datetime.now()).days
                if 0 < days_to_put <= 180:
                    score += 30
                    factors.append(f'距回售日{days_to_put}天')
                elif 180 < days_to_put <= 365:
                    score += 15
                    factors.append(f'距回售日{days_to_put}天')
            except Exception:
                pass

        # 剩余期限短，促转股压力大
        if 0.5 <= year_left <= 2:
            score += 15
            factors.append('剩余期限短，促转股压力大')

        # 已进入转股期
        if convert_flag:
            score += 10
            factors.append('已进入转股期')

        probability = min(score, 100)
        if probability >= 60:
            level = 'high'
        elif probability >= 35:
            level = 'medium'
        else:
            level = 'low'

        return {
            'revision_probability': probability,
            'revision_level': level,
            'revision_factors': factors,
        }

    # ===== 5维度质量评分系统 =====

    @staticmethod
    def _score_valuation(bond: dict) -> Tuple[int, str]:
        """维度1：双低估值（满分25）— 越低越好"""
        dl = bond.get('double_low', 999)
        if dl <= 100:
            return 25, '极低估'
        elif dl <= 110:
            return 23, '低估'
        elif dl <= 120:
            return 20, '偏低估'
        elif dl <= 130:
            return 16, '合理'
        elif dl <= 140:
            return 10, '偏高估'
        elif dl <= 150:
            return 5, '高估'
        else:
            return 0, '极高估'

    @staticmethod
    def _score_bond_floor(bond: dict) -> Tuple[int, str]:
        """维度2：债底保护（满分25）— 纯债价值溢价率 + 税后YTM"""
        score = 0
        parts = []

        # 纯债价值溢价（满分15）：价格越接近纯债价值，债底保护越强
        pbv = bond.get('pure_bond_value', 0)
        price = bond.get('price', 0)
        if pbv > 0 and price > 0:
            pbv_premium = (price - pbv) / pbv * 100
            if pbv_premium <= 0:
                score += 15
                parts.append('破净')
            elif pbv_premium <= 5:
                score += 13
                parts.append('接近债底')
            elif pbv_premium <= 10:
                score += 10
                parts.append('溢价适中')
            elif pbv_premium <= 20:
                score += 6
                parts.append('溢价偏高')
            else:
                score += 2
                parts.append('远离债底')
        else:
            # 无纯债价值数据时，用YTM作为替代
            ytm = bond.get('ytm_rt', 0)
            if ytm >= 3:
                score += 12
                parts.append('高YTM')
            elif ytm >= 0:
                score += 8
                parts.append('正YTM')
            else:
                score += 2
                parts.append('负YTM')

        # 税后YTM（满分10）
        ytm_at = bond.get('ytm_after_tax', bond.get('ytm_rt', 0))
        if ytm_at >= 3:
            score += 10
            parts.append('税后强')
        elif ytm_at >= 1:
            score += 8
            parts.append('税后尚可')
        elif ytm_at >= 0:
            score += 6
            parts.append('税后保本')
        elif ytm_at >= -1:
            score += 3
            parts.append('税后微亏')
        else:
            score += 0
            parts.append('税后亏损')

        return min(score, 25), '+'.join(parts) if parts else '无数据'

    @staticmethod
    def _score_credit_quality(bond: dict) -> Tuple[int, str]:
        """维度3：信用质量（满分20）— 评级 + 正股估值合理性"""
        score = 0
        parts = []

        # 评级分（满分12）
        rating = bond.get('rating_cd', '')
        rating_score_map = {'AAA': 12, 'AA+': 10, 'AA': 8, 'AA-': 5, 'A+': 2, 'A': 0}
        rs = rating_score_map.get(rating, 0)
        score += rs
        parts.append(f'评级{rating}({rs}分)')

        # 正股PE合理性（满分4）
        pe = bond.get('stock_pe', 0)
        if 0 < pe < 30:
            score += 4
            parts.append('PE合理')
        elif 30 <= pe < 60:
            score += 2
            parts.append('PE偏高')
        elif pe < 0:
            score += 0
            parts.append('PE亏损')
        else:
            score += 1
            parts.append('PE过高')

        # 正股PB合理性（满分4）
        pb = bond.get('stock_pb', 0)
        if 0 < pb < 2:
            score += 4
            parts.append('PB合理')
        elif 2 <= pb < 4:
            score += 2
            parts.append('PB偏高')
        else:
            score += 0
            parts.append('PB过高')

        if score >= 17:
            label = '优质'
        elif score >= 13:
            label = '良好'
        elif score >= 8:
            label = '一般'
        else:
            label = '较差'

        return min(score, 20), label

    @staticmethod
    def _score_convert_potential(bond: dict) -> Tuple[int, str]:
        """维度4：转股潜力（满分15）— 转股价值越高、距强赎越近，潜力越大"""
        score = 0
        parts = []

        cv = bond.get('convert_value', 0)

        # 转股价值（满分8）
        if cv >= 120:
            score += 8
            parts.append('深度实值')
        elif cv >= 100:
            score += 7
            parts.append('实值')
        elif cv >= 85:
            score += 5
            parts.append('轻度虚值')
        elif cv >= 70:
            score += 3
            parts.append('虚值')
        elif cv >= 50:
            score += 1
            parts.append('深度虚值')
        else:
            score += 0
            parts.append('极深虚值')

        # 距强赎触发距离（满分4）
        rd = bond.get('redeem_distance', 999)
        if rd <= 0:
            score += 4  # 已满足强赎
            parts.append('已触发强赎')
        elif rd <= 10:
            score += 3
            parts.append('接近强赎')
        elif rd <= 30:
            score += 2
            parts.append('中等距离')
        else:
            score += 0
            parts.append('远离强赎')

        # 是否进入转股期（满分3）
        if bond.get('convert_flag') or bond.get('convert_dt'):
            score += 3
            parts.append('可转股')
        else:
            score += 0
            parts.append('未到转股期')

        if score >= 12:
            label = '高潜力'
        elif score >= 8:
            label = '中等潜力'
        elif score >= 4:
            label = '低潜力'
        else:
            label = '极低潜力'

        return min(score, 15), label

    @staticmethod
    def _score_liquidity(bond: dict) -> Tuple[int, str]:
        """维度5：流动性（满分15）— 规模、成交额、剩余年限"""
        score = 0
        parts = []

        # 剩余规模（满分5）
        amt = bond.get('curr_iss_amt', 0)
        if amt >= 10:
            score += 5
            parts.append('大规模')
        elif amt >= 5:
            score += 4
            parts.append('中大规模')
        elif amt >= 2:
            score += 3
            parts.append('中等规模')
        elif amt >= 1:
            score += 1
            parts.append('小规模')
        else:
            score += 0
            parts.append('极小规模')

        # 成交额（满分5）
        turnover = bond.get('turnover', 0)
        if turnover >= 1000:
            score += 5
            parts.append('活跃')
        elif turnover >= 500:
            score += 4
            parts.append('较活跃')
        elif turnover >= 200:
            score += 3
            parts.append('一般')
        elif turnover >= 100:
            score += 2
            parts.append('较冷')
        else:
            score += 0
            parts.append('冷门')

        # 剩余年限（满分5）— 2-4年最佳
        yl = bond.get('year_left', 0)
        if 2 <= yl <= 4:
            score += 5
            parts.append('期限适中')
        elif 4 < yl <= 6:
            score += 3
            parts.append('期限较长')
        elif 1 <= yl < 2:
            score += 2
            parts.append('期限较短')
        elif yl < 1:
            score += 0
            parts.append('临近到期')
        else:
            score += 1
            parts.append('期限过长')

        if score >= 12:
            label = '高流动性'
        elif score >= 8:
            label = '中等流动性'
        elif score >= 4:
            label = '低流动性'
        else:
            label = '极低流动性'

        return min(score, 15), label

    @staticmethod
    def _detect_risk_tags(bond: dict) -> List[dict]:
        """检测风险标签（增强版：含强赎风险量化）"""
        tags = []

        cv = bond.get('convert_value', 0)
        yl = bond.get('year_left', 0)
        ytm = bond.get('ytm_rt', 0)
        rating = bond.get('rating_cd', '')
        turnover = bond.get('turnover', 0)
        price = bond.get('price', 0)
        amt = bond.get('curr_iss_amt', 0)
        rating_val = CBService.RATING_ORDER.get(rating, 0)

        # 强赎风险（量化）
        redeem_info = bond.get('redeem_risk', {})
        if redeem_info.get('redeem_risk_level') == 'high':
            tags.append({
                'tag': '强赎风险',
                'level': 'high',
                'desc': redeem_info.get('redeem_timeline', '强赎风险'),
            })
        elif redeem_info.get('redeem_risk_level') == 'medium':
            tags.append({
                'tag': '接近强赎',
                'level': 'medium',
                'desc': redeem_info.get('redeem_timeline', ''),
            })

        # 到期赎回风险：转股价值低 + 剩余年限短
        if cv < 70 and yl < 2:
            tags.append({'tag': '到期赎回风险', 'level': 'high', 'desc': f'转股价值{cv:.0f}，仅剩{yl:.1f}年，大概率到期赎回'})

        # 低评级风险
        if rating_val <= 2:  # A+及以下
            tags.append({'tag': '低评级', 'level': 'high', 'desc': f'评级{rating}，信用风险较高'})
        elif rating_val == 3:  # AA-
            tags.append({'tag': '评级偏低', 'level': 'medium', 'desc': f'评级{rating}，需关注信用状况'})

        # 低流动性风险
        if turnover < 50:
            tags.append({'tag': '流动性差', 'level': 'high', 'desc': f'日成交额仅{turnover:.0f}万，难以按预期价格交易'})
        elif turnover < 100:
            tags.append({'tag': '流动性偏低', 'level': 'medium', 'desc': f'日成交额{turnover:.0f}万'})

        # 临近到期
        if yl < 1:
            tags.append({'tag': '临近到期', 'level': 'high', 'desc': f'剩余{yl:.1f}年，需尽快处理'})

        # 深度折价（可能有信用风险）
        if price < 85:
            tags.append({'tag': '深度折价', 'level': 'high', 'desc': f'价格{price:.2f}，市场可能隐含违约预期'})
        elif price < 95:
            tags.append({'tag': '低于面值', 'level': 'medium', 'desc': f'价格{price:.2f}，低于面值'})

        # 规模过小
        if amt < 1:
            tags.append({'tag': '规模过小', 'level': 'medium', 'desc': f'剩余规模仅{amt:.2f}亿，流动性受限'})

        # YTM为负
        if ytm < -2:
            tags.append({'tag': 'YTM深度为负', 'level': 'high', 'desc': f'到期收益率{ytm:.2f}%，持有到期亏损较大'})

        return tags

    @staticmethod
    def _score_cb_quality(bond: dict) -> Tuple[int, dict, List[dict], str]:
        """综合质量评分

        Returns:
            (total_score, scores_dict, risk_tags, verdict)
        """
        s1, l1 = CBService._score_valuation(bond)
        s2, l2 = CBService._score_bond_floor(bond)
        s3, l3 = CBService._score_credit_quality(bond)
        s4, l4 = CBService._score_convert_potential(bond)
        s5, l5 = CBService._score_liquidity(bond)

        total = s1 + s2 + s3 + s4 + s5
        scores = {
            'valuation': {'score': s1, 'max': 25, 'label': l1},
            'bond_floor': {'score': s2, 'max': 25, 'label': l2},
            'credit': {'score': s3, 'max': 20, 'label': l3},
            'convert': {'score': s4, 'max': 15, 'label': l4},
            'liquidity': {'score': s5, 'max': 15, 'label': l5},
        }

        risk_tags = CBService._detect_risk_tags(bond)

        if total >= 80:
            verdict = 'A'
        elif total >= 65:
            verdict = 'B'
        elif total >= 50:
            verdict = 'C'
        else:
            verdict = 'D'

        return total, scores, risk_tags, verdict

    @staticmethod
    def get_double_low_list(
        max_double_low: float = 130.0,
        min_rating: str = 'A',
        min_year_left: float = 1.0,
        min_turnover: float = 100.0,
        min_ytm: float = -999,
        top_n: int = 20,
        sort_by: str = 'double_low',
        exclude_st: bool = True,
        exclude_force_redeem: bool = True,
    ) -> dict:
        """获取双低排名（增强版：支持质量评分排序）

        Args:
            max_double_low: 双低值上限，默认130
            min_rating: 最低信用评级，默认A
            min_year_left: 最低剩余年限，默认1年
            min_turnover: 最低成交额(万)，默认100万
            min_ytm: 最低到期收益率(%)，默认不限
            top_n: 返回前N只，默认20
            sort_by: 排序方式 - double_low(双低值) / quality_score(质量评分) / ytm(到期收益率)
            exclude_st: 排除ST
            exclude_force_redeem: 排除已公告强赎
        """
        cache_key = f"cb_{max_double_low}_{min_rating}_{min_year_left}_{min_turnover}_{min_ytm}_{top_n}_{sort_by}_{exclude_st}_{exclude_force_redeem}"
        cached = _get_cache(cache_key, _get_realtime_ttl())
        if cached:
            return cached

        raw_bonds, data_source = CBService._fetch_cb_data()

        if not raw_bonds:
            return {
                'bonds': [],
                'total': 0,
                'total_before_filter': 0,
                'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'error': '无法获取可转债数据（所有数据源均不可用）',
                'risk_summary': {},
                'data_source': data_source,
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
        if max_double_low > 0 and max_double_low < 999:
            bonds = [b for b in bonds if b['double_low'] <= max_double_low]

        # 筛选: 信用评级
        min_rating_val = CBService.RATING_ORDER.get(min_rating, 0)
        bonds = [b for b in bonds if CBService.RATING_ORDER.get(b['rating_cd'], 0) >= min_rating_val]

        # 筛选: 最低到期收益率
        if min_ytm > -999:
            bonds = [b for b in bonds if b['ytm_rt'] >= min_ytm]

        # 计算质量评分
        risk_counter = {}
        for bond in bonds:
            total, scores, risk_tags, verdict = CBService._score_cb_quality(bond)
            bond['quality_score'] = total
            bond['quality_scores'] = scores
            bond['risk_tags'] = risk_tags
            bond['verdict'] = verdict
            for tag in risk_tags:
                risk_counter[tag['tag']] = risk_counter.get(tag['tag'], 0) + 1

        # 排序
        if sort_by == 'quality_score':
            bonds.sort(key=lambda x: x['quality_score'], reverse=True)
        elif sort_by == 'ytm':
            bonds.sort(key=lambda x: x['ytm_rt'], reverse=True)
        elif sort_by == 'triple_low':
            bonds.sort(key=lambda x: x.get('triple_low', 999))
        elif sort_by == 'ytm_after_tax':
            bonds.sort(key=lambda x: x.get('ytm_after_tax', 0), reverse=True)
        elif sort_by == 'pure_bond_value':
            bonds.sort(key=lambda x: x.get('pure_bond_value', 0))
        else:
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
            'sort_by': sort_by,
            'risk_summary': risk_counter,
            'data_source': data_source,
        }

        _set_cache(cache_key, result)
        return result

    # ===== 大师策略 =====

    # 策略定义
    STRATEGIES = {
        'andaoquan': {
            'name': '安道全面值策略',
            'master': '安道全',
            'source': '《可转债投资魔法书》',
            'philosophy': '下有保底，上不封顶',
            'risk_level': '低',
            'complexity': '简单',
            'min_capital': '1万+',
            'expected_return': '8-15%',
            'description': '面值附近买入，130元卖出。规则极简，适合新手。',
            'rules': [
                '买入：价格 ≤ 105元，到期收益率 > 0',
                '持有：不卖除非触发卖出条件',
                '卖出：价格达到130元或触发强赎',
                '分散：持有多只，不集中',
            ],
            'suitable_for': [
                '完全的新手，第一次接触可转债',
                '不想花时间盯盘、研究',
                '追求"稳稳的幸福"，年化8-15%就满足',
                '本金不多（1万起步就行）',
            ],
            'warnings': [
                '105元不是铁底：市场恐慌时可能跌到95-98元，要扛得住',
                '130元不一定到：有些转债可能在100-110元晃荡好几年',
                '强赎公告后必须卖：不卖就按100+利息赎回，白白损失几十元',
                '评级下调要警惕：公司被降级，债底会下移',
            ],
            'risks': [
                {'name': '正股暴雷/退市', 'probability': '极低', 'impact': '本金损失50%+', 'solution': '分散持有10只以上'},
                {'name': '长期不涨', 'probability': '中等', 'impact': '资金被占用', 'solution': '分批买入，保留现金'},
                {'name': '流动性枯竭', 'probability': '低', 'impact': '想卖卖不掉', 'solution': '只买成交额>50万的'},
            ],
            'pitfalls': [
                '看到130不卖，想等更高 → 130就是卖出点，贪心是最大的敌人',
                '单只重仓 → 万一那家公司出问题，损失惨重',
                '忽略强赎公告 → 不看公告 = 白白亏钱',
            ],
            'filter': lambda b: (
                b['price'] <= 105
                and b['ytm_rt'] > 0
                and CBService.RATING_ORDER.get(b['rating_cd'], 0) >= 3  # AA-及以上
                and b['year_left'] >= 1
                and b['turnover'] >= 50
            ),
            'sort_key': lambda b: b['ytm_rt'],
            'reverse': True,
        },
        'dual_low': {
            'name': '双低策略',
            'master': '集思录社区',
            'source': '集思录量化实践',
            'philosophy': '低价格 + 低溢价率 = 攻守兼备',
            'risk_level': '中',
            'complexity': '中等',
            'min_capital': '5万+',
            'expected_return': '10-20%',
            'description': '经典量化策略，按双低值排序轮动，历史回测长期年化10-15%。',
            'rules': [
                '筛选：双低值 ≤ 130',
                '排除：ST、强赎、剩余年限<1年',
                '排序：双低值升序',
                '轮动：每1-2周调仓一次',
            ],
            'suitable_for': [
                '有一定基础，理解溢价率的含义',
                '能接受每周花1-2小时调仓',
                '本金5万以上（分散需要）',
                '追求年化10-20%',
            ],
            'warnings': [
                '双低值130是动态门槛：市场好时可能140也算便宜，市场差时120才算便宜',
                '轮动有成本：每次调仓都有手续费和滑点，频繁轮动会侵蚀收益',
                '溢价率低≠一定好：溢价率低可能是因为正股涨了，不是转债便宜',
                '要排除"假双低"：有些转债价格低是因为公司有风险',
            ],
            'risks': [
                {'name': '调仓时正好卖在低点', 'probability': '中等', 'impact': '错过反弹', 'solution': '固定周期调仓，不临时操作'},
                {'name': '双低陷阱', 'probability': '中等', 'impact': '买入后继续跌', 'solution': '看质量评分，排除C/D级'},
                {'name': '市场系统性下跌', 'probability': '低', 'impact': '全部持仓下跌', 'solution': '控制仓位，保留现金'},
            ],
            'pitfalls': [
                '只看双低值，不看质量评分 → 双低值120但评级BBB的转债，可能是陷阱',
                '追涨杀跌 → 看到双低值上升就恐慌卖出，违反策略纪律',
                '轮动太频繁 → 每周调仓≠每天调仓，太频繁手续费吃不消',
            ],
            'filter': lambda b: (
                b['double_low'] <= 130
                and b['year_left'] >= 1
                and b['turnover'] >= 100
            ),
            'sort_key': lambda b: b['double_low'],
            'reverse': False,
        },
        'pancake': {
            'name': '摊大饼策略',
            'master': '低风险投资圈',
            'source': '集思录/雪球实践',
            'philosophy': '不选赢家，买一篮子，靠概率取胜',
            'risk_level': '低-中',
            'complexity': '简单',
            'min_capital': '3万+',
            'expected_return': '8-12%',
            'description': '类指数投资，买入所有符合条件的低价转债，等权持有，定期轮动。',
            'rules': [
                '筛选：价格 ≤ 120，溢价率 ≤ 50%',
                '排除：ST、评级<A-、规模<1亿',
                '持有：等权分配，10-50只',
                '轮动：每周五调仓，价格>130卖出',
            ],
            'suitable_for': [
                '不想花时间研究个股',
                '相信"不要把鸡蛋放在一个篮子里"',
                '本金3万以上',
                '追求年化8-12%',
            ],
            'warnings': [
                '10只以上才有分散效果：只买3-5只不算摊大饼',
                '等权分配很重要：不要因为某只涨了就加仓',
                '130元必须卖：这是纪律，不能破',
                '资金利用率不高：持有很多只，每只仓位小，绝对收益有限',
            ],
            'risks': [
                {'name': '集体暴雷（极端行情）', 'probability': '极低', 'impact': '大面积亏损', 'solution': '保持10只以上分散'},
                {'name': '买入后长期横盘', 'probability': '中等', 'impact': '资金效率低', 'solution': '接受这是策略特性'},
                {'name': '轮动时正好踩雷', 'probability': '低', 'impact': '单只亏损', 'solution': '质量评分过滤'},
            ],
            'pitfalls': [
                '只买3-5只就说自己在摊大饼 → 分散不够，风险集中',
                '看到某只涨了就重仓 → 违背等权原则',
                '忘记周五调仓 → 不调仓就不是摊大饼了',
            ],
            'filter': lambda b: (
                b['price'] <= 120
                and b['premium_rt'] <= 50
                and b['year_left'] >= 1
                and b['curr_iss_amt'] >= 1
                and b['turnover'] >= 50
                and CBService.RATING_ORDER.get(b['rating_cd'], 0) >= 1  # A-及以上
            ),
            'sort_key': lambda b: b['double_low'],
            'reverse': False,
        },
        'ytm_defense': {
            'name': 'YTM保本策略',
            'master': '宁稳/低风险派',
            'source': '知乎/集思录',
            'philosophy': '到期不亏是底线，转股收益是惊喜',
            'risk_level': '低',
            'complexity': '简单',
            'min_capital': '1万+',
            'expected_return': '3-6%（保底）',
            'description': '最保守策略，只买到期收益率为正的转债，持有到期保证不亏。',
            'rules': [
                '筛选：到期收益率 > 0，评级 ≥ AA',
                '排序：到期收益率降序',
                '持有：到期获取本息，或中途转股/卖出',
                '止损：评级下调至AA-以下时卖出',
            ],
            'suitable_for': [
                '极度保守的投资者',
                '不能接受任何本金损失',
                '愿意持有到期（可能2-5年）',
                '年化3-6%就满足',
            ],
            'warnings': [
                'YTM>0不代表一定赚：公司可能违约',
                '持有到期很漫长：有些转债剩余期限5年，要有耐心',
                '机会成本高：资金锁定这么久，可能错过其他机会',
                '评级AA是最低要求：AA-的转债风险明显更高',
            ],
            'risks': [
                {'name': '公司违约（极端）', 'probability': '极低', 'impact': '本金损失', 'solution': '只买AA+以上'},
                {'name': '评级下调', 'probability': '低', 'impact': '债底下降，浮亏', 'solution': '监控评级变化'},
                {'name': '长期不涨', 'probability': '高', 'impact': '资金效率低', 'solution': '接受这是策略特性'},
            ],
            'pitfalls': [
                '以为YTM>0就绝对安全 → 公司可能违约，评级可能下调',
                '中途恐慌卖出 → YTM策略就是要持有到期，中途波动是正常的',
                '忽略评级下调信号 → 评级下调是卖出信号，不是死扛',
            ],
            'filter': lambda b: (
                b['ytm_rt'] > 0
                and CBService.RATING_ORDER.get(b['rating_cd'], 0) >= 4  # AA及以上
                and b['year_left'] >= 1
                and b['turnover'] >= 50
            ),
            'sort_key': lambda b: b['ytm_rt'],
            'reverse': True,
        },
        'revision_game': {
            'name': '下修博弈策略',
            'master': '集思录进阶玩家',
            'source': '集思录下修博弈实践',
            'philosophy': '公司有压力促转股，下修转股价是最大催化剂',
            'risk_level': '中-高',
            'complexity': '较高',
            'min_capital': '3万+',
            'expected_return': '15-30%（若成功）',
            'description': '寻找正股价接近下修触发价的转债，博弈公司下修转股价带来的价格跳跃。',
            'rules': [
                '筛选：正股价/转股价在70-95%区间',
                '优先：临近回售期、到期收益率>0',
                '买入：在下修触发前布局',
                '卖出：下修公告后价格跳涨时卖出',
            ],
            'suitable_for': [
                '理解"下修"的逻辑和触发条件',
                '能承受"不下修"的失望',
                '有时间研究公司促转股的动机',
                '本金3万以上',
            ],
            'warnings': [
                '下修不是必然的：公司可能选择不下修，期望落空',
                '下修幅度不确定：可能只下修一点点，价格涨幅有限',
                '需要研究公司动机：临近回售期、未转股比例高的公司更可能下修',
                '博弈失败要认亏：如果不下修，价格可能回落',
            ],
            'risks': [
                {'name': '公司不下修', 'probability': '中等', 'impact': '价格回落，浮亏', 'solution': '设置止损线'},
                {'name': '下修幅度不及预期', 'probability': '中等', 'impact': '涨幅有限', 'solution': '不追高，提前布局'},
                {'name': '正股持续下跌', 'probability': '中等', 'impact': '即使下修也不涨', 'solution': '选基本面尚可的公司'},
            ],
            'pitfalls': [
                '把"可能下修"当成"一定下修" → 这是博弈，不是确定性事件',
                '下修公告后追高 → 消息出来后价格已经反映了，追高容易被套',
                '不研究公司动机 → 盲目买"接近下修线"的转债，可能踩雷',
            ],
            'filter': lambda b: (
                b['convert_value'] >= 50
                and b['convert_value'] <= 95
                and b['ytm_rt'] > -2
                and b['year_left'] >= 0.5
                and b['turnover'] >= 50
            ),
            'sort_key': lambda b: b['convert_value'],  # 转股价值越接近下修触发线越优先
            'reverse': False,
        },
        'redeem_game': {
            'name': '强赎博弈策略',
            'master': '集思录进阶玩家',
            'source': '集思录强赎博弈实践',
            'philosophy': '公司有强烈促转股动机，强赎是终极目标',
            'risk_level': '中',
            'complexity': '中-高',
            'min_capital': '3万+',
            'expected_return': '10-20%',
            'description': '寻找转股价值接近130强赎线的转债，博弈公司促转股行为。',
            'rules': [
                '筛选：转股价值在100-130区间',
                '优先：未转股比例高、剩余期限短',
                '信号：公司有下修历史、正股基本面尚可',
                '卖出：触发强赎公告后卖出',
            ],
            'suitable_for': [
                '理解强赎的触发条件和后果',
                '能判断公司促转股的意愿',
                '有时间跟踪正股走势',
                '本金3万以上',
            ],
            'warnings': [
                '强赎线130是关键：转股价值要连续15/30天≥130才触发',
                '正股可能回调：接近130时正股可能回调，永远不触发',
                '强赎公告后必须卖：不卖就按100+利息赎回，亏大了',
                '溢价率要低：溢价率高说明转债价格虚高，风险大',
            ],
            'risks': [
                {'name': '正股回调，不触发强赎', 'probability': '中等', 'impact': '价格回落', 'solution': '设置止损'},
                {'name': '强赎公告后忘记卖', 'probability': '低', 'impact': '被低价赎回', 'solution': '设置提醒'},
                {'name': '溢价率过高', 'probability': '中等', 'impact': '正股涨但转债不涨', 'solution': '只买溢价率≤30%的'},
            ],
            'pitfalls': [
                '强赎公告后不看公告 → 这是最大的坑，被赎回就亏几十元',
                '溢价率太高还买 → 溢价率30%意味着正股要涨30%转债才不亏',
                '以为接近130就一定触发 → 正股波动，可能永远到不了',
            ],
            'filter': lambda b: (
                b['convert_value'] >= 90
                and b['convert_value'] <= 130
                and b['premium_rt'] <= 30
                and b['year_left'] >= 0.5
                and b['turnover'] >= 50
            ),
            'sort_key': lambda b: b['redeem_distance'],  # 距强赎越近越优先
            'reverse': False,
        },
        'triple_low': {
            'name': '三低策略',
            'master': '集思录进阶玩家',
            'source': '三低策略实践',
            'philosophy': '低价格 + 低溢价率 + 低规模 = 弹性大、资金推动效应强',
            'risk_level': '中',
            'complexity': '中等',
            'min_capital': '5万+',
            'expected_return': '12-25%',
            'description': '在双低基础上加入低剩余规模条件。小规模转债更容易被资金推动上涨，弹性更大。',
            'rules': [
                '筛选：价格 <= 120，溢价率 <= 30%，剩余规模 <= 3亿',
                '排除：ST、已公告强赎、剩余年限<1年',
                '排序：三低值 = 价格 + 溢价率 + 规模*10',
                '轮动：每周调仓，价格>130或规模膨胀后卖出',
            ],
            'suitable_for': [
                '理解"小规模"的弹性和风险',
                '能承受更大的波动',
                '本金5万以上',
                '追求年化12-25%',
            ],
            'warnings': [
                '小规模=高波动：涨得快，跌得也快',
                '流动性风险：小规模转债可能想卖卖不掉',
                '规模会膨胀：转股后规模会变大，失去"低规模"优势',
                '资金推动效应：小规模转债容易被游资炒作，波动更大',
            ],
            'risks': [
                {'name': '流动性枯竭', 'probability': '中等', 'impact': '想卖卖不掉', 'solution': '只买成交额>50万的'},
                {'name': '游资撤离后暴跌', 'probability': '中等', 'impact': '短期大幅亏损', 'solution': '设置止损'},
                {'name': '规模膨胀失去优势', 'probability': '高', 'impact': '策略失效', 'solution': '监控规模变化'},
            ],
            'pitfalls': [
                '只看规模小就买 → 小规模不等于好，还要看基本面',
                '暴跌时恐慌卖出 → 三低策略波动大，要扛得住',
                '忽略流动性 → 成交额太小的转债，想卖卖不掉',
            ],
            'filter': lambda b: (
                b['price'] <= 120
                and b['premium_rt'] <= 30
                and b['curr_iss_amt'] <= 3
                and b['year_left'] >= 1
                and b['turnover'] >= 50
                and CBService.RATING_ORDER.get(b['rating_cd'], 0) >= 1  # A-及以上
            ),
            'sort_key': lambda b: b.get('triple_low', b['price'] + b['premium_rt'] + b['curr_iss_amt'] * 10),
            'reverse': False,
        },
        'negative_premium': {
            'name': '负溢价套利策略',
            'master': '低风险套利派',
            'source': '可转债套利实践',
            'philosophy': '溢价率为负时买入转债并转股，赚取无风险价差',
            'risk_level': '低-中',
            'complexity': '较高',
            'min_capital': '10万+',
            'expected_return': '2-8%（单次）',
            'description': '当转股溢价率为负时，买入转债并申请转股，次日获得正股后卖出，赚取价差。需注意T+1风险和正股波动。',
            'rules': [
                '筛选：溢价率 < -1%（扣除交易成本后仍有利润）',
                '优先：流动性好（成交额>500万）、正股波动小',
                '操作：买入转债 -> 当日转股 -> 次日卖出正股',
                '止损：若正股次日大幅低开，可能亏损',
            ],
            'suitable_for': [
                '理解T+1交割制度',
                '能承受"套利变套牢"',
                '本金10万以上（规模效应）',
                '有时间盯盘操作',
            ],
            'warnings': [
                'T+1是最大的坑：今天转股，明天才能卖，今晚正股可能暴跌',
                '负溢价可能有原因：市场可能知道你不知道的坏消息',
                '交易成本要算清：佣金+印花税+滑点，可能吃掉利润',
                '操作要快：负溢价窗口很短，犹豫就没了',
            ],
            'risks': [
                {'name': '正股次日低开', 'probability': '中等', 'impact': '套利变亏损', 'solution': '只套利正股波动小的'},
                {'name': '负溢价消失', 'probability': '高', 'impact': '买在高点', 'solution': '操作要快'},
                {'name': '转股失败', 'probability': '极低', 'impact': '无法套利', 'solution': '确认转股成功'},
            ],
            'pitfalls': [
                '以为负溢价就是"无风险" → T+1风险是真实存在的',
                '负溢价-0.5%就去套利 → 算上交易成本，可能亏钱',
                '不看正股基本面 → 负溢价可能是因为正股要暴跌',
            ],
            'filter': lambda b: (
                b['premium_rt'] < -1
                and b['convert_value'] > 80
                and b['turnover'] >= 500
                and b['year_left'] >= 0.5
                and CBService.RATING_ORDER.get(b['rating_cd'], 0) >= 2  # A+及以上
            ),
            'sort_key': lambda b: b['premium_rt'],  # 负溢价越深越优先
            'reverse': False,
        },
    }

    @staticmethod
    def get_master_strategy(strategy: str = 'andaoquan', top_n: int = 20) -> dict:
        """获取大师策略筛选结果

        Args:
            strategy: 策略名称（andaoquan/dual_low/pancake/ytm_defense/revision_game/redeem_game）
            top_n: 返回前N只
        """
        cache_key = f"cb_ms_{strategy}_{top_n}"
        cached = _get_cache(cache_key, _get_realtime_ttl())
        if cached:
            return cached

        strat = CBService.STRATEGIES.get(strategy)
        if not strat:
            return {
                'bonds': [],
                'strategy': strategy,
                'error': f'未知策略: {strategy}，可选: {", ".join(CBService.STRATEGIES.keys())}',
            }

        raw_bonds, data_source = CBService._fetch_cb_data()
        if not raw_bonds:
            return {
                'bonds': [],
                'strategy': strategy,
                'strategy_info': strat,
                'total': 0,
                'total_before_filter': 0,
                'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'error': '无法获取可转债数据（所有数据源均不可用）',
                'risk_summary': {},
                'data_source': data_source,
            }

        total_before = len(raw_bonds)

        # 标准化 + 排除ST + 排除强赎
        bonds = []
        for cell in raw_bonds:
            bond = CBService._normalize_cb(cell)
            if bond and 'ST' not in bond['bond_nm'] and 'ST' not in bond['stock_nm'] and not bond['force_redeem']:
                bonds.append(bond)

        # 应用策略专属筛选
        bonds = [b for b in bonds if strat['filter'](b)]

        # 计算质量评分
        risk_counter = {}
        for bond in bonds:
            total, scores, risk_tags, verdict = CBService._score_cb_quality(bond)
            bond['quality_score'] = total
            bond['quality_scores'] = scores
            bond['risk_tags'] = risk_tags
            bond['verdict'] = verdict
            for tag in risk_tags:
                risk_counter[tag['tag']] = risk_counter.get(tag['tag'], 0) + 1

        # 策略排序
        bonds.sort(key=strat['sort_key'], reverse=strat['reverse'])

        # 取前N只
        top_bonds = bonds[:top_n]

        result = {
            'bonds': top_bonds,
            'strategy': strategy,
            'strategy_info': strat,
            'total': len(bonds),
            'total_before_filter': total_before,
            'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'top_n': top_n,
            'risk_summary': risk_counter,
            'data_source': data_source,
        }

        _set_cache(cache_key, result)
        return result

    @staticmethod
    def refresh_data() -> dict:
        _clear_cache("cb_")
        return CBService.get_double_low_list()
