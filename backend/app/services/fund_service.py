"""基金套利数据服务 - 从集思录获取LOF/ETF折溢价数据"""

import requests
import logging
import time
import os
import json
import re
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

# 登录状态持久化文件
_LOGIN_STATE_FILE = os.path.join(os.path.dirname(__file__), '..', '..', '.jisilu_login.json')


def _get_cache(key: str) -> Optional[dict]:
    if key in _cache:
        data, ts = _cache[key]
        if time.time() - ts < CACHE_TTL:
            return data
        del _cache[key]
    return None


def _set_cache(key: str, data: dict):
    _cache[key] = (data, time.time())


def _save_login_state(cookies: dict):
    """保存登录状态到文件"""
    try:
        state = {
            'cookies': cookies,
            'timestamp': time.time(),
        }
        with open(_LOGIN_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f)
    except Exception as e:
        logger.warning(f"保存登录状态失败: {e}")


def _load_login_state() -> Optional[dict]:
    """从文件加载登录状态"""
    try:
        if not os.path.exists(_LOGIN_STATE_FILE):
            return None
        with open(_LOGIN_STATE_FILE, 'r', encoding='utf-8') as f:
            state = json.load(f)
        # 检查是否过期（24小时）
        if time.time() - state.get('timestamp', 0) > 86400:
            return None
        return state
    except Exception as e:
        logger.warning(f"加载登录状态失败: {e}")
        return None


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


# ============================================================
# EST估算净值 - 底层资产映射
# ============================================================

_UNDERLYING_MAP = {
    # 纳指100类
    '161130': {'code': 'gb_qqq', 'type': 'us_etf', 'name': '纳指100'},
    '513100': {'code': 'gb_qqq', 'type': 'us_etf', 'name': '纳指100'},
    '513110': {'code': 'gb_qqq', 'type': 'us_etf', 'name': '纳指100'},
    '513300': {'code': 'gb_qqq', 'type': 'us_etf', 'name': '纳指100'},
    '513390': {'code': 'gb_qqq', 'type': 'us_etf', 'name': '纳指100'},
    '513870': {'code': 'gb_qqq', 'type': 'us_etf', 'name': '纳指100'},
    '159501': {'code': 'gb_qqq', 'type': 'us_etf', 'name': '纳指100'},
    '159513': {'code': 'gb_qqq', 'type': 'us_etf', 'name': '纳指100'},
    '159632': {'code': 'gb_qqq', 'type': 'us_etf', 'name': '纳指100'},
    '159659': {'code': 'gb_qqq', 'type': 'us_etf', 'name': '纳指100'},
    '159660': {'code': 'gb_qqq', 'type': 'us_etf', 'name': '纳指100'},
    '159696': {'code': 'gb_qqq', 'type': 'us_etf', 'name': '纳指100'},
    '159941': {'code': 'gb_qqq', 'type': 'us_etf', 'name': '纳指100'},
    # 标普500类
    '513500': {'code': 'gb_spy', 'type': 'us_etf', 'name': '标普500'},
    '513650': {'code': 'gb_spy', 'type': 'us_etf', 'name': '标普500'},
    '161125': {'code': 'gb_spy', 'type': 'us_etf', 'name': '标普500'},
    '159612': {'code': 'gb_spy', 'type': 'us_etf', 'name': '标普500'},
    '159655': {'code': 'gb_spy', 'type': 'us_etf', 'name': '标普500'},
    # 标普信息科技
    '161128': {'code': 'gb_xlk', 'type': 'us_etf', 'name': '标普信息科技'},
    # 标普医疗保健
    '161126': {'code': 'gb_xlv', 'type': 'us_etf', 'name': '标普医疗'},
    # 生物科技类
    '513290': {'code': 'gb_ibb', 'type': 'us_etf', 'name': '纳指生物科技'},
    '161127': {'code': 'gb_ibb', 'type': 'us_etf', 'name': '纳指生物科技'},
    '159502': {'code': 'gb_ibb', 'type': 'us_etf', 'name': '纳指生物科技'},
    # 美国消费
    '162415': {'code': 'gb_xly', 'type': 'us_etf', 'name': '美国消费'},
    # 美国REIT
    '160140': {'code': 'gb_vnq', 'type': 'us_etf', 'name': '美国REIT'},
    # 道琼斯
    '513400': {'code': 'gb_dia', 'type': 'us_etf', 'name': '道琼斯'},
    # 原油类
    '162411': {'code': 'hf_CL', 'type': 'futures', 'name': '原油'},
    '162719': {'code': 'hf_CL', 'type': 'futures', 'name': '原油'},
    '160416': {'code': 'hf_CL', 'type': 'futures', 'name': '原油'},
    '513350': {'code': 'hf_CL', 'type': 'futures', 'name': '标普油气'},
    '159518': {'code': 'hf_CL', 'type': 'futures', 'name': '标普油气'},
    # 黄金类
    '518880': {'code': 'hf_GC', 'type': 'futures', 'name': '黄金'},
    '518800': {'code': 'hf_GC', 'type': 'futures', 'name': '黄金'},
    '159934': {'code': 'hf_GC', 'type': 'futures', 'name': '黄金'},
    '159937': {'code': 'hf_GC', 'type': 'futures', 'name': '黄金'},
    # 白银
    '161226': {'code': 'hf_SI', 'type': 'futures', 'name': '白银'},
    # 豆粕
    '159985': {'code': 'hf_SM', 'type': 'futures', 'name': '豆粕'},
    # A股宽基指数
    '160706': {'code': 'sh000300', 'type': 'a_index', 'name': '沪深300'},
    '510300': {'code': 'sh000300', 'type': 'a_index', 'name': '沪深300'},
    '510310': {'code': 'sh000300', 'type': 'a_index', 'name': '沪深300'},
    '510330': {'code': 'sh000300', 'type': 'a_index', 'name': '沪深300'},
    '159919': {'code': 'sh000300', 'type': 'a_index', 'name': '沪深300'},
    '501043': {'code': 'sh000300', 'type': 'a_index', 'name': '沪深300'},
    '163407': {'code': 'sh000300', 'type': 'a_index', 'name': '沪深300'},
    '160119': {'code': 'sh000905', 'type': 'a_index', 'name': '中证500'},
    '502000': {'code': 'sh000905', 'type': 'a_index', 'name': '中证500'},
    '161812': {'code': 'sz399006', 'type': 'a_index', 'name': '创业板'},
    '163109': {'code': 'sz399006', 'type': 'a_index', 'name': '创业板'},
    '161227': {'code': 'sz399001', 'type': 'a_index', 'name': '深证成指'},
    # Jisilu A股行业LOF
    '160615': {'code': 'sh000300', 'type': 'a_index', 'name': '沪深300'},
    '160616': {'code': 'sh000905', 'type': 'a_index', 'name': '中证500'},
    '160223': {'code': 'sz399006', 'type': 'a_index', 'name': '创业板'},
    '160219': {'code': 'sh000037', 'type': 'a_index', 'name': '上证医药'},
    '160635': {'code': 'sh000037', 'type': 'a_index', 'name': '上证医药'},
    '160221': {'code': 'sh000033', 'type': 'a_index', 'name': '上证材料'},
    '160222': {'code': 'sh000036', 'type': 'a_index', 'name': '上证消费'},
    '160632': {'code': 'sh000036', 'type': 'a_index', 'name': '上证消费'},
    '160225': {'code': 'sz399808', 'type': 'a_index', 'name': '中证新能'},
    '160620': {'code': 'sh000032', 'type': 'a_index', 'name': '上证能源'},
    '160625': {'code': 'sh000038', 'type': 'a_index', 'name': '上证金融'},
    '160631': {'code': 'sh000038', 'type': 'a_index', 'name': '上证金融'},
    '160633': {'code': 'sh000038', 'type': 'a_index', 'name': '上证金融'},
    '160218': {'code': 'sh000006', 'type': 'a_index', 'name': '上证地产'},
    '160628': {'code': 'sh000006', 'type': 'a_index', 'name': '上证地产'},
}

_underlying_cache = {}
_UNDERLYING_CACHE_TTL = 300  # 5分钟


def _fetch_single_est_nav(fid: str) -> tuple:
    """获取单只基金的EST估算净值"""
    try:
        import json
        url = f"https://fundgz.1234567.com.cn/js/{fid}.js"
        resp = requests.get(url, timeout=5)
        text = resp.text
        if 'fundcode' not in text:
            return fid, None
        json_str = text[text.index('{'):text.rindex('}') + 1]
        data = json.loads(json_str)
        dwjz = float(data.get('dwjz', 0))
        gsz = float(data.get('gsz', 0))
        gszzl = float(data.get('gszzl', 0))
        if dwjz > 0 and gsz > 0:
            return fid, {
                'nav': dwjz,
                'est_nav': gsz,
                'est_change': gszzl,
                'name': data.get('name', ''),
                'gztime': data.get('gztime', ''),
            }
    except Exception:
        pass
    return fid, None


def _fetch_est_nav_batch(fund_ids: list) -> dict:
    """从天天基金API并行获取EST估算净值，返回 {fund_id: {nav, est_nav, est_change, name}} """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    result = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_fetch_single_est_nav, fid): fid for fid in fund_ids}
        for f in as_completed(futures):
            fid, data = f.result()
            if data:
                result[fid] = data
    return result


def _fetch_underlying_prices() -> dict:
    """批量获取底层资产实时价格，返回 {api_code: {current, prev_close}} """
    global _underlying_cache
    if _underlying_cache:
        data, ts = _underlying_cache
        if time.time() - ts < _UNDERLYING_CACHE_TTL:
            return data

    # 去重，分类
    all_codes = list(set(m['code'] for m in _UNDERLYING_MAP.values()))
    sina_codes = [c for c in all_codes if c.startswith('gb_') or c.startswith('hf_')]
    a_index_codes = [c for c in all_codes if c.startswith('sh') or c.startswith('sz')]

    result = {}
    try:
        # 新浪API支持批量查询 - 美股ETF和期货
        if sina_codes:
            url = f"https://hq.sinajs.cn/list={','.join(sina_codes)}"
            headers = {'Referer': 'https://finance.sina.com.cn'}
            resp = requests.get(url, headers=headers, timeout=10)
            resp.encoding = 'gbk'
            text = resp.text

            for line in text.strip().split('\n'):
                if '=' not in line:
                    continue
                var_part, _, val_part = line.partition('=')
                code = var_part.split('_str_')[-1]
                val_part = val_part.strip(';').strip('"')
                if not val_part:
                    continue
                fields = val_part.split(',')

                if code.startswith('gb_'):
                    # 美股ETF格式: 名称,当前价,涨跌幅,时间,涨跌额,开盘,最高,最低,昨收,...
                    if len(fields) >= 9:
                        try:
                            current = float(fields[1])
                            prev_close = float(fields[8])
                            if current > 0 and prev_close > 0:
                                result[code] = {
                                    'current': current,
                                    'prev_close': prev_close,
                                    'change_pct': round((current - prev_close) / prev_close * 100, 2),
                                }
                        except (ValueError, IndexError):
                            pass
                elif code.startswith('hf_'):
                    # 期货格式: 当前价,,昨结,开盘,最高,最低,时间,昨收,...
                    if len(fields) >= 7:
                        try:
                            current = float(fields[0])
                            prev_close = float(fields[7]) if len(fields) > 7 and fields[7] else float(fields[2])
                            if current > 0 and prev_close > 0:
                                result[code] = {
                                    'current': current,
                                    'prev_close': prev_close,
                                    'change_pct': round((current - prev_close) / prev_close * 100, 2),
                                }
                        except (ValueError, IndexError):
                            pass

        # A股指数数据
        if a_index_codes:
            url = f"https://hq.sinajs.cn/list={','.join(a_index_codes)}"
            headers = {'Referer': 'https://finance.sina.com.cn'}
            resp = requests.get(url, headers=headers, timeout=10)
            resp.encoding = 'gbk'
            text = resp.text

            for line in text.strip().split('\n'):
                if '=' not in line:
                    continue
                var_part, _, val_part = line.partition('=')
                code = var_part.split('_str_')[-1]
                val_part = val_part.strip(';').strip('"')
                if not val_part:
                    continue
                fields = val_part.split(',')
                # A股指数格式: 名称,今开,昨收,当前,最高,最低,...
                if len(fields) >= 4:
                    try:
                        current = float(fields[3])
                        prev_close = float(fields[2])
                        if current > 0 and prev_close > 0:
                            result[code] = {
                                'current': current,
                                'prev_close': prev_close,
                                'change_pct': round((current - prev_close) / prev_close * 100, 2),
                            }
                    except (ValueError, IndexError):
                        pass

        # 获取汇率
        try:
            fx_resp = requests.get(
                "https://hq.sinajs.cn/list=fx_susdcny",
                headers={'Referer': 'https://finance.sina.com.cn'},
                timeout=10,
            )
            fx_resp.encoding = 'gbk'
            fx_text = fx_resp.text.strip()
            if '=' in fx_text:
                fx_val = fx_text.partition('=')[2].strip(';').strip('"')
                fx_fields = fx_val.split(',')
                if len(fx_fields) >= 2:
                    result['_usdcny'] = float(fx_fields[1])
        except Exception:
            result['_usdcny'] = 7.25  # fallback

    except Exception as e:
        logger.warning(f"获取底层资产价格失败: {e}")

    _underlying_cache = (result, time.time())
    return result


def _estimate_nav(fund: dict, prices: dict) -> dict:
    """为单只基金添加EST估算净值字段"""
    fund_id = fund.get('fund_id', '')
    mapping = _UNDERLYING_MAP.get(fund_id)

    if not mapping:
        fund['est_nav'] = None
        fund['est_discount_rt'] = None
        fund['underlying_name'] = None
        fund['underlying_change'] = None
        return fund

    api_code = mapping['code']
    price_data = prices.get(api_code)

    if not price_data or price_data['prev_close'] <= 0:
        fund['est_nav'] = None
        fund['est_discount_rt'] = None
        fund['underlying_name'] = mapping['name']
        fund['underlying_change'] = None
        return fund

    nav = fund.get('fund_nav', 0)
    if nav <= 0:
        fund['est_nav'] = None
        fund['est_discount_rt'] = None
        fund['underlying_name'] = mapping['name']
        fund['underlying_change'] = price_data['change_pct']
        return fund

    change_pct = price_data['change_pct']
    fund['underlying_name'] = mapping['name']
    fund['underlying_change'] = change_pct

    # 对于美股类ETF，需要考虑汇率变动
    if mapping['type'] == 'us_etf':
        usdcny = prices.get('_usdcny', 7.25)
        # 简化处理：假设昨收净值对应的汇率也是当前汇率（因为净值公布时汇率已确定）
        # EST NAV = 昨收净值 * (1 + 底层资产涨跌幅%)
        est_nav = round(nav * (1 + change_pct / 100), 4)
    else:
        # 商品期货类，直接用涨跌幅
        est_nav = round(nav * (1 + change_pct / 100), 4)

    fund['est_nav'] = est_nav

    # 计算EST溢价率
    price = fund.get('price', 0)
    if est_nav > 0:
        fund['est_discount_rt'] = round((price - est_nav) / est_nav * 100, 2)
    else:
        fund['est_discount_rt'] = None

    return fund


class FundService:
    """基金套利数据服务"""

    JISILU_LOF_URLS = [
        'https://www.jisilu.cn/data/lof/stock_lof_list/',
        'https://www.jisilu.cn/data/lof/index_lof_list/',
    ]

    JISILU_QDII_URL = 'https://www.jisilu.cn/data/qdii/qdii_list/'

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
            # 直接POST登录，跳过访问登录页（减少一次请求）
            resp = session.post(login_url, data=login_data, timeout=10)
            result = resp.json()

            if result.get('code') == 200:
                _jisilu_session = session
                _jisilu_logged_in = True
                _cache.clear()
                # 保存登录状态
                _save_login_state(dict(session.cookies))
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
    def restore_login() -> bool:
        """从文件恢复登录状态"""
        global _jisilu_session, _jisilu_logged_in

        state = _load_login_state()
        if not state:
            return False

        try:
            session = requests.Session()
            session.headers.update({
                'User-Agent': FundService.HEADERS['User-Agent'],
                'Referer': 'https://www.jisilu.cn/data/lof/',
            })
            # 恢复 cookies
            for name, value in state.get('cookies', {}).items():
                session.cookies.set(name, value)

            # 验证登录状态
            resp = session.get('https://www.jisilu.cn/data/lof/stock_lof_list/', timeout=10)
            data = resp.json()
            if 'rows' in data:
                _jisilu_session = session
                _jisilu_logged_in = True
                logger.info("从文件恢复集思录登录状态成功")
                return True
        except Exception as e:
            logger.warning(f"恢复登录状态失败: {e}")

        return False

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

        # 获取 stock_lof_list 和 index_lof_list
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

        # 获取 QDII 列表中的 LOF 基金
        try:
            headers = dict(FundService.HEADERS)
            headers['Referer'] = 'https://www.jisilu.cn/data/qdii/'
            resp = session.get(FundService.JISILU_QDII_URL, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            for row in data.get('rows', []):
                cell = row.get('cell', {})
                if cell:
                    # 筛选 LOF 类型的基金 (lof_type 为 QDII 或名称包含 LOF)
                    lof_type = cell.get('lof_type', '')
                    fund_nm = cell.get('fund_nm', '')
                    if lof_type == 'QDII' or 'LOF' in fund_nm:
                        all_funds.append(cell)
        except Exception as e:
            logger.warning(f"获取集思录QDII数据失败 [{FundService.JISILU_QDII_URL}]: {e}")

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
    def _fetch_eastmoney_lof_list() -> List[dict]:
        """从东方财富获取LOF数据(备用)"""
        try:
            url = 'https://push2.eastmoney.com/api/qt/clist/get'
            params = {
                'pn': 1,
                'pz': 1000,
                'po': 1,
                'np': 1,
                'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
                'fltt': 2,
                'invt': 2,
                'fid': 'f3',
                'fs': 'b:MK0404,b:MK0405,b:MK0406,b:MK0407',
                'fields': 'f12,f14,f2,f3,f5,f6,f15,f16,f17,f18',
            }

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://quote.eastmoney.com/',
            }

            resp = requests.get(url, headers=headers, params=params, timeout=15)
            data = resp.json()
            rows = data.get('data', {}).get('diff', [])

            funds = []
            for row in rows:
                fund_id = row.get('f12', '')
                price = row.get('f2', 0) / 100 if row.get('f2') else 0
                volume = row.get('f5', 0)  # 成交量
                amount = row.get('f6', 0)  # 成交额

                funds.append({
                    'fund_id': fund_id,
                    'fund_nm': row.get('f14', ''),
                    'price': str(price),
                    'fund_nav': '0',  # 净值需要从其他来源获取
                    'nav_discount_rt': '0',
                    'increase_rt': str(row.get('f3', 0) / 100 if row.get('f3') else 0),
                    'volume': str(volume),
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
            logger.warning(f"东方财富获取LOF数据失败: {e}")
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

            if price <= 0:
                return None

            # 允许净值为 0 的基金通过，后续会从天天基金获取净值
            if nav <= 0:
                nav = 0

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

            # 申购限额 - 优先从 min_amt 提取，回退到 apply_status
            apply_limit = ''
            min_amt = cell.get('min_amt', '') or ''
            apply_status = cell.get('apply_status', '') or ''

            # 1) 从 min_amt 中提取日累计申购限额
            if '限额' in min_amt:
                for line in min_amt.split('\r\n'):
                    if '限额' in line:
                        val = line.strip()
                        if '无限额' not in val:
                            apply_limit = val
                        break

            # 2) 从 apply_status 中提取限大额信息 (如 "限1万", "限20万", "限1千")
            if not apply_limit and apply_status.startswith('限') and apply_status != '开放申购':
                raw = apply_status  # e.g. "限1万", "限20万", "限1千", "限0"
                if raw == '限0':
                    apply_limit = '暂停申购'
                else:
                    # 解析 "限X万" / "限X千" 格式为具体金额
                    m = re.match(r'限(\d+(?:\.\d+)?)(万|千)', raw)
                    if m:
                        num = float(m.group(1))
                        unit = m.group(2)
                        if unit == '万':
                            amount = int(num * 10000)
                        else:
                            amount = int(num * 1000)
                        apply_limit = f'日限额{amount:,}元'
                    else:
                        apply_limit = raw

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

        # 获取集思录数据
        jisilu_funds = FundService._fetch_jisilu_lof()
        data_source = "集思录"

        # 获取备用数据源
        backup_funds = FundService._fetch_akshare_lof()
        if not backup_funds:
            backup_funds = FundService._fetch_eastmoney_lof_list()
            if backup_funds:
                data_source = "集思录+东方财富"
        else:
            data_source = "集思录+AKShare"

        # 合并数据：集思录为主，备用数据源补充
        if jisilu_funds:
            # 已存在的基金 ID
            existing_ids = {f.get('fund_id') for f in jisilu_funds}
            # 从备用数据源中补充集思录没有的基金
            for fund in backup_funds:
                fund_id = fund.get('fund_id', '')
                if fund_id and fund_id not in existing_ids:
                    jisilu_funds.append(fund)
            raw_funds = jisilu_funds
        else:
            raw_funds = backup_funds
            data_source = "AKShare" if backup_funds else "无数据"

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

        # EST估算净值 - 优先使用天天基金API，回退到底层资产计算
        fund_ids = [f['fund_id'] for f in funds]
        try:
            est_data = _fetch_est_nav_batch(fund_ids)
            for fund in funds:
                fid = fund['fund_id']
                if fid in est_data:
                    ed = est_data[fid]
                    fund['est_nav'] = round(ed['est_nav'], 4)
                    fund['underlying_change'] = ed['est_change']
                    fund['underlying_name'] = ed.get('name', '')
                    price = fund.get('price', 0)
                    if ed['est_nav'] > 0:
                        fund['est_discount_rt'] = round((price - ed['est_nav']) / ed['est_nav'] * 100, 2)
                    # 如果原始净值为 0，使用天天基金的净值
                    if fund['fund_nav'] <= 0 and ed.get('nav', 0) > 0:
                        fund['fund_nav'] = round(ed['nav'], 4)
                        # 重新计算折溢价率
                        if fund['fund_nav'] > 0:
                            fund['nav_discount_rt'] = round((price - fund['fund_nav']) / fund['fund_nav'] * 100, 2)
                            fund['direction'] = "溢价" if fund['nav_discount_rt'] > 0 else "折价"
                            fund['estimated_profit'] = _estimate_profit(price, fund['fund_nav'], fund['apply_fee'], fund['redeem_fee'], fund['direction'])
                else:
                    fund['est_nav'] = None
                    fund['est_discount_rt'] = None
                    fund['underlying_name'] = None
                    fund['underlying_change'] = None
        except Exception as e:
            logger.warning(f"天天基金EST获取失败，回退到底层资产计算: {e}")
            try:
                underlying_prices = _fetch_underlying_prices()
                for fund in funds:
                    _estimate_nav(fund, underlying_prices)
            except Exception as e2:
                logger.warning(f"EST估算完全失败: {e2}")

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

    @staticmethod
    def _fetch_eastmoney_fund(fund_id: str) -> Optional[dict]:
        """从东方财富API获取单只基金数据"""
        try:
            # 东方财富单只基金行情 API
            url = 'https://push2.eastmoney.com/api/qt/stock/get'
            params = {
                'secid': f'0.{fund_id}',  # 0 表示深圳，1 表示上海
                'fields': 'f43,f44,f45,f46,f47,f48,f57,f58,f60,f170',
                'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
            }

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://quote.eastmoney.com/',
            }

            resp = requests.get(url, headers=headers, params=params, timeout=10)
            data = resp.json()

            if data.get('data'):
                d = data['data']
                price = d.get('f43', 0) / 1000  # 最新价
                volume = d.get('f47', 0)  # 成交量
                amount = d.get('f48', 0)  # 成交额

                return {
                    'fund_id': d.get('f57', fund_id),
                    'fund_nm': d.get('f58', ''),
                    'price': str(price),
                    'fund_nav': '0',  # 净值需要从其他来源获取
                    'nav_discount_rt': '0',
                    'increase_rt': str(d.get('f170', 0) / 100),
                    'volume': str(volume),
                    'amount': 0,
                    'apply_fee': '',
                    'redeem_fee': '',
                    'apply_status': '',
                    'redeem_status': '',
                    'nav_dt': '',
                    'price_dt': datetime.now().strftime('%Y-%m-%d'),
                    'issuer_nm': '',
                }
        except Exception as e:
            logger.warning(f"从东方财富获取基金 {fund_id} 数据失败: {e}")
        return None
