"""数据服务 - 使用新浪财经和东方财富获取A股数据，腾讯财经获取港股数据"""

import requests
import json
import logging
from typing import Optional
from datetime import datetime
from urllib.parse import quote
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.core.cache import cached, TTL_STATIC, TTL_WEEKLY, get_realtime_ttl
from app.core.utils import safe_float as _safe_float
from app.services.multi_source_quote import multi_source_service

logger = logging.getLogger(__name__)

# 共享HTTP会话（带连接池和重试）
_session = requests.Session()
_adapter = HTTPAdapter(
    pool_connections=10,
    pool_maxsize=20,
    max_retries=Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504]),
)
_session.mount("https://", _adapter)
_session.mount("http://", _adapter)
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
})


class DataService:
    """金融数据服务"""

    @staticmethod
    def _is_hk_code(code: str) -> bool:
        """判断是否为港股代码（5位数字）"""
        return len(code) == 5 and code.isdigit()

    @staticmethod
    def _is_b_share(code: str) -> bool:
        """判断是否为B股代码（深圳200开头，上海900开头）"""
        return len(code) == 6 and code.isdigit() and (code.startswith('200') or code.startswith('900'))

    @staticmethod
    def _get_a_share_code(b_code: str) -> str:
        """将B股代码转换为对应的A股代码
        深圳B股 200xxx -> A股 000xxx
        上海B股 900xxx -> A股 600xxx
        """
        if b_code.startswith('200'):
            return '000' + b_code[3:]
        elif b_code.startswith('900'):
            return '600' + b_code[3:]
        return b_code

    @staticmethod
    @cached(ttl_seconds=30, key_prefix="stock_basic")
    def get_stock_basic(stock_code: str) -> dict:
        """获取股票基本信息和实时行情

        使用多数据源自动切换：通达信 -> 新浪 -> 东方财富
        """
        # 港股
        if DataService._is_hk_code(stock_code):
            return DataService._get_hk_stock_basic(stock_code)

        try:
            # 使用多数据源服务获取行情
            quote = multi_source_service.get_quote(stock_code, market='A')

            if quote:
                # 获取总股本和PE/PB（从东方财富获取补充数据）
                market = "1" if stock_code.startswith('6') else "0"
                total_shares, pe, pb = DataService._get_valuation_data(stock_code, market, quote.price)

                # 如果多数据源返回了PE/PB，优先使用
                if quote.pe:
                    pe = quote.pe
                if quote.pb:
                    pb = quote.pb

                market_cap = quote.price * total_shares if total_shares else None
                if quote.total_market_cap:
                    market_cap = quote.total_market_cap / 1e8  # 转换为亿元

                return {
                    "code": stock_code,
                    "name": quote.name,
                    "price": quote.price,
                    "open": quote.open,
                    "high": quote.high,
                    "low": quote.low,
                    "pre_close": quote.pre_close,
                    "change_pct": quote.change_pct,
                    "change_amount": quote.change_amount,
                    "volume": int(quote.volume),
                    "amount": quote.amount,
                    "turnover_rate": quote.turnover_rate,
                    "pe": pe,
                    "pe_type": "TTM",
                    "pb": pb,
                    "market_cap": round(market_cap, 2) if market_cap else None,
                    "trade_date": quote.trade_date,
                    "trade_time": quote.timestamp,
                    "data_source": quote.source,
                    "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }

            # 多数据源失败，降级到原有逻辑
            logger.warning(f"多数据源获取失败，降级到新浪: {stock_code}")
            return DataService._get_stock_basic_fallback(stock_code)

        except Exception as e:
            logger.error(f"get_stock_basic failed for {stock_code}: {e}")
            return {"code": stock_code, "error": "获取行情数据失败，请稍后重试"}

    @staticmethod
    def _get_stock_basic_fallback(stock_code: str) -> dict:
        """降级方案：使用原有新浪接口"""
        try:
            # 判断市场
            if stock_code.startswith('6'):
                symbol = f"sh{stock_code}"
                market = "1"
            else:
                symbol = f"sz{stock_code}"
                market = "0"

            # 新浪实时行情
            url = f"https://hq.sinajs.cn/list={symbol}"
            headers = {"Referer": "https://finance.sina.com.cn"}
            r = _session.get(url, headers=headers, timeout=10)
            r.encoding = 'gbk'

            # 解析数据
            data = r.text.split('"')[1].split(',')
            if len(data) < 32:
                return {"code": stock_code, "error": "未找到行情数据"}

            name = data[0]
            if not name:
                return {"code": stock_code, "error": "未找到行情数据"}

            open_price = float(data[1]) if data[1] else 0
            pre_close = float(data[2]) if data[2] else 0
            price = float(data[3]) if data[3] else 0
            high = float(data[4]) if data[4] else 0
            low = float(data[5]) if data[5] else 0

            # 校验价格合理性
            if price <= 0:
                return {"code": stock_code, "error": "行情数据异常：价格为0或负数"}
            volume = int(float(data[8])) if data[8] else 0
            amount = float(data[9]) if data[9] else 0
            trade_date = data[30]  # 交易日期
            trade_time = data[31]  # 交易时间

            change_pct = ((price - pre_close) / pre_close * 100) if pre_close > 0 else 0

            # 获取总股本和PE/PB
            total_shares, pe, pb = DataService._get_valuation_data(stock_code, market, price)

            market_cap = price * total_shares  # total_shares already in 亿股, result in 亿元

            return {
                "code": stock_code,
                "name": name,
                "price": price,
                "open": open_price,
                "high": high,
                "low": low,
                "pre_close": pre_close,
                "change_pct": round(change_pct, 2),
                "volume": volume,
                "amount": amount,
                "pe": pe,
                "pe_type": "TTM",
                "pb": pb,
                "market_cap": round(market_cap, 2),
                "trade_date": trade_date,
                "trade_time": trade_time,
                "data_source": "新浪(降级)",
                "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        except Exception as e:
            logger.error(f"_get_stock_basic_fallback failed for {stock_code}: {e}")
            return {"code": stock_code, "error": "获取行情数据失败，请稍后重试"}

    @staticmethod
    def _fetch_eastmoney_report(stock_code: str, columns: str, page_size: str = "20") -> list:
        """从东方财富获取财报数据的共享方法

        Args:
            stock_code: 股票代码
            columns: 需要的列名，逗号分隔
            page_size: 返回条数，默认20

        Returns:
            报告数据列表，失败时返回空列表
        """
        try:
            url = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
            params = {
                "reportName": "RPT_F10_FINANCE_MAINFINADATA",
                "columns": columns,
                "filter": f"(SECURITY_CODE=\"{stock_code}\")",
                "pageNumber": "1",
                "pageSize": page_size,
                "sortTypes": "-1",
                "sortColumns": "REPORT_DATE",
                "source": "HSF10",
                "client": "PC"
            }
            r = _session.get(url, params=params, timeout=15)
            data = r.json()

            if data.get("result") and data["result"].get("data"):
                return data["result"]["data"]
            return []
        except Exception as e:
            logger.warning(f"_fetch_eastmoney_report failed for {stock_code}: {e}")
            return []

    @staticmethod
    def _get_valuation_data(stock_code: str, market: str, price: float) -> tuple:
        """获取估值数据：总股本、PE(TTM)、PB"""
        try:
            items = DataService._fetch_eastmoney_report(
                stock_code,
                columns="REPORT_DATE,TOTAL_SHARE,EPSJB,BPS",
                page_size="6",
            )

            if items:
                latest = items[0]
                total_share = latest.get("TOTAL_SHARE", 0) / 1e8  # 转换为亿股
                bps = latest.get("BPS", 0)

                # 计算TTM EPS
                eps = DataService._calc_ttm_eps(items)

                pe = round(price / eps, 2) if eps and eps > 0 else None
                pb = round(price / bps, 2) if bps and bps > 0 else None

                return total_share, pe, pb

            return 0, None, None
        except Exception as e:
            logger.warning(f"_get_valuation_data failed for {stock_code}: {e}")
            return 0, None, None

    @staticmethod
    def _calc_ttm_eps(items: list) -> float:
        """根据报告列表计算滚动12个月EPS(TTM)

        东方财富的EPSJB是年初至今累计值：
        - 年报(12-31): 全年EPS
        - 三季报(09-30): 前9个月EPS
        - 中报(06-30): 前6个月EPS
        - 一季报(03-31): 前3个月EPS

        TTM计算：
        - 最新为年报 → 直接使用
        - 最新为季报 → 当期累计 + 上年全年 - 上年同期累计
        """
        if not items:
            return 0

        latest = items[0]
        latest_date = latest.get("REPORT_DATE", "")[:10]
        latest_eps = _safe_float(latest.get("EPSJB")) or 0
        month_day = latest_date[5:] if len(latest_date) >= 10 else ""

        # 年报：EPS就是全年值，直接用
        if month_day == "12-31":
            return latest_eps

        # 季报/中报/三季报：需要上年同期和上年年报数据
        # 找上年年报和上年同期
        prev_annual_eps = None
        prev_same_period_eps = None
        latest_year = latest_date[:4] if len(latest_date) >= 4 else ""

        for item in items[1:]:
            d = item.get("REPORT_DATE", "")[:10]
            if not d:
                continue
            eps_val = _safe_float(item.get("EPSJB")) or 0
            # 上年年报
            if d[:4] < latest_year and d[5:] == "12-31" and prev_annual_eps is None:
                prev_annual_eps = eps_val
            # 上年同期
            if d[:4] < latest_year and d[5:] == month_day and prev_same_period_eps is None:
                prev_same_period_eps = eps_val

        if prev_annual_eps is not None:
            # TTM = 本期累计 + 上年全年 - 上年同期累计
            ttm = latest_eps + prev_annual_eps - (prev_same_period_eps or 0)
            return ttm if ttm > 0 else 0

        # 找不到上年年报，降级处理：用最新EPS（可能是年化不准的值）
        return latest_eps

    @staticmethod
    def _get_hk_stock_basic(stock_code: str) -> dict:
        """通过腾讯财经获取港股基本信息和实时行情"""
        try:
            url = f'https://qt.gtimg.cn/q=r_hk{stock_code}'
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://stockapp.finance.qq.com/'
            }
            r = _session.get(url, headers=headers, timeout=10)
            r.encoding = 'gbk'

            text = r.text
            if '="' not in text:
                return {"code": stock_code, "error": "未找到港股行情数据"}

            data = text.split('"')[1].split('~')
            if len(data) < 50:
                return {"code": stock_code, "error": "港股数据格式异常"}

            name = data[1]
            price = float(data[3]) if data[3] else 0
            pre_close = float(data[4]) if data[4] else 0
            open_price = float(data[5]) if data[5] else 0
            high = float(data[33]) if data[33] else 0
            low = float(data[34]) if data[34] else 0
            volume = int(float(data[6])) if data[6] else 0
            amount = float(data[37]) if data[37] else 0
            change_pct = float(data[32]) if data[32] else 0
            # 注意：腾讯API的PE/PB数据不可靠，统一改用财报计算
            # pe = float(data[39]) if data[39] else 0
            # pb = float(data[51]) if len(data) > 51 and data[51] else 0
            market_cap = float(data[44]) if data[44] else 0
            dividend_yield = float(data[43]) if data[43] else 0
            total_shares = float(data[69]) if len(data) > 69 and data[69] else 0  # 总股本（股）

            if price <= 0:
                return {"code": stock_code, "error": "港股价格数据异常"}

            trade_time = data[30] if len(data) > 30 else ""

            # 通过最新财报计算PE和PB（腾讯API的数据不可靠）
            pe, pb = DataService._calc_hk_valuation(stock_code, price, total_shares)

            return {
                "code": stock_code,
                "name": name,
                "market": "HK",
                "price": price,
                "open": open_price,
                "high": high,
                "low": low,
                "pre_close": pre_close,
                "change_pct": round(change_pct, 2),
                "volume": volume,
                "amount": amount,
                "pe": pe,
                "pe_type": "TTM",
                "pb": pb,
                "market_cap": round(market_cap, 2),
                "dividend_yield": round(dividend_yield, 2) if dividend_yield > 0 else None,
                "trade_date": trade_time[:10] if trade_time else "",
                "trade_time": trade_time,
                "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        except Exception as e:
            logger.error(f"_get_hk_stock_basic failed for {stock_code}: {e}")
            return {"code": stock_code, "error": "获取港股行情失败，请稍后重试"}

    @staticmethod
    def _calc_hk_valuation(stock_code: str, price: float, total_shares: float) -> tuple:
        """通过最新财报计算港股PE(TTM)和PB

        腾讯财经API返回的PE/PB数据不可靠，统一用akshare获取财报数据计算。
        支持一般公司(004开头)和保险公司(002开头)的会计科目。

        Args:
            stock_code: 港股代码
            price: 当前股价（港币）
            total_shares: 总股本（股）

        Returns:
            (pe, pb) 元组，计算失败时返回None
        """
        try:
            import akshare as ak

            # 获取利润表（全部报告期）- 计算TTM EPS
            df_income = ak.stock_financial_hk_report_em(stock=stock_code, symbol='利润表', indicator='报告期')
            # 获取资产负债表（全部报告期）- 计算BPS
            df_bs = ak.stock_financial_hk_report_em(stock=stock_code, symbol='资产负债表', indicator='报告期')

            if df_income.empty or df_bs.empty:
                return None, None

            # 判断是保险公司还是一般公司
            # 保险公司使用002开头的科目，一般公司使用004开头
            is_insurance = not df_income[df_income['STD_ITEM_CODE'].str.startswith('004')].empty == False
            # 尝试获取净利润数据
            np_codes = ['004025002', '002030999']  # 一般公司/保险公司
            np_rows = None
            for code in np_codes:
                rows = df_income[df_income['STD_ITEM_CODE'] == code]
                if not rows.empty:
                    np_rows = rows
                    break

            if np_rows is None or np_rows.empty:
                return None, None

            # 构建净利润数据表
            np_data = {}
            for _, row in np_rows.iterrows():
                d = str(row['REPORT_DATE'])[:10]
                np_val = _safe_float(row['AMOUNT'])
                if np_val is not None:
                    np_data[d] = np_val

            sorted_dates = sorted(np_data.keys(), reverse=True)
            if not sorted_dates:
                return None, None

            # 计算TTM净利润
            latest_date = sorted_dates[0]
            latest_np = np_data[latest_date]
            month_day = latest_date[5:]

            ttm_np = latest_np
            if month_day != "12-31":
                # 季报：需要上年年报和上年同期数据
                year = latest_date[:4]
                prev_annual_np = None
                prev_same_period_np = None

                for d in sorted_dates[1:]:
                    if d[:4] < year and d[5:] == "12-31":
                        prev_annual_np = np_data[d]
                    if d[:4] < year and d[5:] == month_day:
                        prev_same_period_np = np_data[d]
                    if prev_annual_np is not None and prev_same_period_np is not None:
                        break

                if prev_annual_np is not None:
                    ttm_np = latest_np + prev_annual_np - (prev_same_period_np or 0)

            # 获取总股本
            shares = total_shares
            if not shares or shares <= 0:
                # 从资产负债表获取
                shares_rows = df_bs[df_bs['STD_ITEM_CODE'] == '004008000']
                if not shares_rows.empty:
                    shares = _safe_float(shares_rows.iloc[0]['AMOUNT'])

            if not shares or shares <= 0:
                return None, None

            # 计算TTM EPS
            ttm_eps = ttm_np / shares if ttm_np and shares > 0 else None

            # 获取最新归属母公司股东权益（支持保险公司和一般公司）
            # 一般公司: 004030999, 保险公司: 002011999(归属于母公司) 或 002009999(股东权益合计)
            equity_codes = ['004030999', '002011999', '002009999']
            equity = None
            for code in equity_codes:
                equity_rows = df_bs[df_bs['STD_ITEM_CODE'] == code]
                if not equity_rows.empty:
                    # 使用最新报告期的数据
                    bs_dates = sorted(df_bs['REPORT_DATE'].unique(), reverse=True)
                    for bs_date in bs_dates:
                        eq_rows = df_bs[(df_bs['REPORT_DATE'] == bs_date) & (df_bs['STD_ITEM_CODE'] == code)]
                        if not eq_rows.empty:
                            equity = _safe_float(eq_rows.iloc[0]['AMOUNT'])
                            if equity:
                                break
                if equity:
                    break

            # 计算BPS
            bps_rmb = equity / shares if equity and shares > 0 else None

            # 获取汇率转换
            try:
                exchange_rate = DataService._get_hkd_exchange_rate()
            except Exception:
                exchange_rate = 1.08

            # 计算PE和PB
            pe = None
            pb = None

            if ttm_eps and ttm_eps > 0:
                # EPS是人民币，股价是港币，需要转换
                ttm_eps_hkd = ttm_eps / exchange_rate
                pe = round(price / ttm_eps_hkd, 2)

            if bps_rmb and bps_rmb > 0:
                bps_hkd = bps_rmb / exchange_rate
                pb = round(price / bps_hkd, 2)

            return pe, pb
        except Exception as e:
            logger.warning(f"_calc_hk_valuation failed for {stock_code}: {e}")
            return None, None

    @staticmethod
    def _get_hkd_exchange_rate() -> float:
        """获取港币兑人民币汇率"""
        try:
            url = "https://qt.gtimg.cn/q=HKDCNY"
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Referer': 'https://stockapp.finance.qq.com/'
            }
            r = _session.get(url, headers=headers, timeout=5)
            r.encoding = 'gbk'
            # 解析汇率数据
            data = r.text.split('"')[1].split('~')
            if len(data) > 3:
                return float(data[3])
            return 1.08  # 默认值
        except Exception:
            return 1.08

    @staticmethod
    def _get_hk_financial_indicators(stock_code: str) -> dict:
        """获取港股财务指标 - ROE/增长率取年报，BPS取最新财报"""
        try:
            import akshare as ak

            reports = []
            latest_date = None

            # 获取利润表（年度）- 计算增长率和利润率
            df_income = ak.stock_financial_hk_report_em(stock=stock_code, symbol='利润表', indicator='年度')
            income_periods = sorted(df_income['REPORT_DATE'].unique(), reverse=True)[:3]

            # 获取资产负债表（年度）- 计算负债率和ROE
            df_bs_annual = ak.stock_financial_hk_report_em(stock=stock_code, symbol='资产负债表', indicator='年度')

            # 获取资产负债表（全部）- 取最新BPS
            df_bs_all = ak.stock_financial_hk_report_em(stock=stock_code, symbol='资产负债表', indicator='报告期')
            latest_bps = None
            latest_bps_date = None
            if not df_bs_all.empty:
                latest_bs_periods = sorted(df_bs_all['REPORT_DATE'].unique(), reverse=True)
                if latest_bs_periods:
                    latest_bs = df_bs_all[df_bs_all['REPORT_DATE'] == latest_bs_periods[0]]
                    equity_rows = latest_bs[latest_bs['STD_ITEM_CODE'] == '004030999']
                    shares_rows = latest_bs[latest_bs['STD_ITEM_CODE'] == '004008000']  # 总股本
                    if len(equity_rows) > 0:
                        equity = _safe_float(equity_rows['AMOUNT'].values[0])
                        # 尝试获取总股本计算BPS
                        if len(shares_rows) > 0:
                            shares = _safe_float(shares_rows['AMOUNT'].values[0])
                            if equity and shares and shares > 0:
                                latest_bps = round(equity / shares, 2)
                        latest_bps_date = str(latest_bs_periods[0])[:10]

            # 先提取所有期间的关键数据
            period_data = []
            for period in income_periods:
                p_data = df_income[df_income['REPORT_DATE'] == period]
                report_date = str(period)[:10]

                rev = _safe_float(p_data[p_data['STD_ITEM_CODE'] == '004001001']['AMOUNT'].values[0]) if len(p_data[p_data['STD_ITEM_CODE'] == '004001001']) > 0 else None
                gross = _safe_float(p_data[p_data['STD_ITEM_CODE'] == '004007999']['AMOUNT'].values[0]) if len(p_data[p_data['STD_ITEM_CODE'] == '004007999']) > 0 else None
                np_val = _safe_float(p_data[p_data['STD_ITEM_CODE'] == '004025002']['AMOUNT'].values[0]) if len(p_data[p_data['STD_ITEM_CODE'] == '004025002']) > 0 else None
                eps_val = _safe_float(p_data[p_data['STD_ITEM_CODE'] == '004027002']['AMOUNT'].values[0]) if len(p_data[p_data['STD_ITEM_CODE'] == '004027002']) > 0 else None

                # 资产负债率和ROE
                debt_ratio = None
                roe = None
                bps = None
                try:
                    bs_data = df_bs_annual[df_bs_annual['REPORT_DATE'] == period]
                    total_liab = _safe_float(bs_data[bs_data['STD_ITEM_CODE'] == '004025999']['AMOUNT'].values[0]) if len(bs_data[bs_data['STD_ITEM_CODE'] == '004025999']) > 0 else None
                    total_equity = _safe_float(bs_data[bs_data['STD_ITEM_CODE'] == '004036999']['AMOUNT'].values[0]) if len(bs_data[bs_data['STD_ITEM_CODE'] == '004036999']) > 0 else None
                    equity = _safe_float(bs_data[bs_data['STD_ITEM_CODE'] == '004030999']['AMOUNT'].values[0]) if len(bs_data[bs_data['STD_ITEM_CODE'] == '004030999']) > 0 else None
                    if total_liab and total_equity:
                        total_assets = total_liab + total_equity
                        debt_ratio = round(total_liab / total_assets * 100, 2) if total_assets > 0 else None
                    if np_val and equity and equity > 0:
                        roe = round(np_val / equity * 100, 2)
                except Exception:
                    pass

                period_data.append({
                    "date": report_date, "rev": rev, "gross": gross,
                    "np": np_val, "eps": eps_val, "debt_ratio": debt_ratio, "roe": roe,
                })

            # 构建报告（含增长率：当期 vs 上期）
            latest_date = period_data[0]["date"] if period_data else None
            for i, pd in enumerate(period_data):
                revenue_growth = None
                profit_growth = None
                if i + 1 < len(period_data):
                    prev = period_data[i + 1]
                    if pd["rev"] and prev["rev"] and prev["rev"] > 0:
                        revenue_growth = round((pd["rev"] - prev["rev"]) / prev["rev"] * 100, 2)
                    if pd["np"] and prev["np"] and prev["np"] > 0:
                        profit_growth = round((pd["np"] - prev["np"]) / prev["np"] * 100, 2)

                gross_margin = round(pd["gross"] / pd["rev"] * 100, 2) if pd["gross"] and pd["rev"] and pd["rev"] > 0 else None
                net_margin = round(pd["np"] / pd["rev"] * 100, 2) if pd["np"] and pd["rev"] and pd["rev"] > 0 else None

                reports.append({
                    "date": pd["date"],
                    "report_name": f"{pd['date'][:4]}年报",
                    "eps": pd["eps"],
                    "bps": None,
                    "roe": pd["roe"],
                    "revenue": pd["rev"],
                    "net_profit": pd["np"],
                    "revenue_growth": revenue_growth,
                    "profit_growth": profit_growth,
                    "gross_margin": gross_margin,
                    "net_margin": net_margin,
                    "debt_ratio": pd["debt_ratio"],
                    "report_period": f"{pd['date'][:4]}年报",
                    "is_annual": True,
                })

            # 最新财报BPS替换到第一份年报
            if latest_bps and reports:
                reports[0]["bps"] = latest_bps
                reports[0]["bps_date"] = latest_bps_date

            return {
                "code": stock_code,
                "reports": reports,
                "latest_report_date": latest_date,
                "latest_bps": latest_bps,
                "latest_bps_date": latest_bps_date,
                "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        except Exception as e:
            logger.error(f"_get_hk_financial_indicators failed for {stock_code}: {e}")
            return {"code": stock_code, "error": "获取港股财务数据失败，请稍后重试", "reports": []}

    @staticmethod
    @cached(ttl_seconds=300, key_prefix="financial_indicators")
    def get_financial_indicators(stock_code: str) -> dict:
        """获取财务指标 - ROE/增长率取年报，BPS取最新财报"""
        if DataService._is_hk_code(stock_code):
            return DataService._get_hk_financial_indicators(stock_code)
        try:
            items = DataService._fetch_eastmoney_report(
                stock_code,
                columns="REPORT_DATE,REPORT_DATE_NAME,EPSJB,BPS,ROEJQ,TOTALOPERATEREVE,PARENTNETPROFIT,TOTALOPERATEREVETZ,PARENTNETPROFITTZ,XSMLL,XSJLL,ZCFZL",
                page_size="20",
            )

            if not items:
                return {"code": stock_code, "error": "未找到财务数据", "reports": []}

            all_reports = []
            for item in items:
                report_date = item.get("REPORT_DATE", "")[:10]
                report = {
                    "date": report_date,
                    "report_name": item.get("REPORT_DATE_NAME", ""),
                    "eps": _safe_float(item.get("EPSJB")),
                    "bps": _safe_float(item.get("BPS")),
                    "roe": _safe_float(item.get("ROEJQ")),
                    "revenue": _safe_float(item.get("TOTALOPERATEREVE")),
                    "net_profit": _safe_float(item.get("PARENTNETPROFIT")),
                    "revenue_growth": _safe_float(item.get("TOTALOPERATEREVETZ")),
                    "profit_growth": _safe_float(item.get("PARENTNETPROFITTZ")),
                    "gross_margin": _safe_float(item.get("XSMLL")),
                    "net_margin": _safe_float(item.get("XSJLL")),
                    "debt_ratio": _safe_float(item.get("ZCFZL")),
                }
                # 数据合理性校验
                report = _validate_report(report)
                all_reports.append(_classify_report(report))

            # 最新财报的BPS（市净率用最新数据）
            latest_bps = all_reports[0]["bps"] if all_reports else None
            latest_bps_date = all_reports[0]["date"] if all_reports else None

            # ROE、增长率等取年报数据
            annual_reports = [r for r in all_reports if r.get("is_annual")]
            reports = annual_reports[:5] if annual_reports else all_reports[:5]

            # 年报的BPS替换为最新财报BPS（市净率用最新数据）
            if latest_bps and reports:
                reports[0]["bps"] = latest_bps
                reports[0]["bps_date"] = latest_bps_date

            latest_date = reports[0]["date"] if reports else None

            return {
                "code": stock_code,
                "reports": reports,
                "latest_report_date": latest_date,
                "latest_bps": latest_bps,
                "latest_bps_date": latest_bps_date,
                "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            # 用现金流量表补充FCF数据
            try:
                cashflow = DataService._fetch_cashflow_statement(stock_code)
                cf_by_date = {}
                for cf in cashflow:
                    cf_date = cf.get("report_date", "")[:10]
                    fcf = cf.get("free_cashflow")
                    if cf_date and fcf is not None:
                        cf_by_date[cf_date] = fcf
                # 将FCF补充到对应的report中
                for report in all_reports:
                    rdate = report.get("date", "")
                    if rdate in cf_by_date:
                        report["fcf"] = round(cf_by_date[rdate] / 1e8, 2)  # 转为亿
            except Exception as e2:
                logger.debug(f"补充FCF数据失败: {e2}")

        except Exception as e:
            logger.error(f"get_financial_indicators failed for {stock_code}: {e}")
            return {"code": stock_code, "error": "获取财务数据失败，请稍后重试", "reports": []}

    # ========== 三大报表（F12功能）==========

    @staticmethod
    def _fetch_eastmoney_report_v2(report_name: str, columns: str, stock_code: str,
                                     page_size: int = 30) -> list:
        """通用东方财富财务报表API调用"""
        try:
            from app.core.rate_limiter import eastmoney_limiter
            eastmoney_limiter.wait()
            url = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
            params = {
                "reportName": report_name,
                "columns": columns,
                "filter": f'(SECURITY_CODE="{stock_code}")',
                "pageNumber": "1",
                "pageSize": str(page_size),
                "sortTypes": "-1",
                "sortColumns": "REPORT_DATE",
                "source": "HSF10",
                "client": "PC",
            }
            r = _session.get(url, params=params, timeout=15)
            data = r.json()
            if data.get("result") and data["result"].get("data"):
                return data["result"]["data"]
            return []
        except Exception as e:
            logger.error(f"_fetch_eastmoney_report_v2({report_name}) failed for {stock_code}: {e}")
            return []

    @staticmethod
    def _classify_report_type(report_date: str) -> str:
        """根据报告日期判断报告类型"""
        month_day = report_date[5:] if len(report_date) >= 10 else ""
        if month_day == "12-31":
            return "annual"
        elif month_day == "09-30":
            return "q3"
        elif month_day == "06-30":
            return "semi"
        elif month_day == "03-31":
            return "q1"
        return "other"

    @staticmethod
    def _fetch_income_statement(stock_code: str) -> list:
        """获取利润表数据"""
        columns = (
            "REPORT_DATE,REPORT_DATE_NAME,OPERATE_INCOME,OPERATE_COST,"
            "SALE_EXPENSE,MANAGE_EXPENSE,RESEARCH_EXPENSE,FINANCE_EXPENSE,"
            "OPERATE_PROFIT,TOTAL_PROFIT,INCOME_TAX,NETPROFIT,PARENT_NETPROFIT"
        )
        raw_data = DataService._fetch_eastmoney_report_v2(
            "RPT_F10_FINANCE_GINCOME", columns, stock_code
        )
        result = []
        for item in raw_data:
            report_date = item.get("REPORT_DATE", "")[:10]
            total_revenue = _safe_float(item.get("OPERATE_INCOME"))
            operating_cost = _safe_float(item.get("OPERATE_COST"))
            sell_expense = _safe_float(item.get("SALE_EXPENSE"))
            manage_expense = _safe_float(item.get("MANAGE_EXPENSE"))
            research_expense = _safe_float(item.get("RESEARCH_EXPENSE"))
            finance_expense = _safe_float(item.get("FINANCE_EXPENSE"))
            operate_profit = _safe_float(item.get("OPERATE_PROFIT"))
            parent_net_profit = _safe_float(item.get("PARENT_NETPROFIT"))

            # 计算衍生比率
            def _ratio(val):
                if val is not None and total_revenue and total_revenue != 0:
                    return round(val / total_revenue * 100, 2)
                return None

            gross_margin = None
            if total_revenue and total_revenue != 0 and operating_cost is not None:
                gross_margin = round((total_revenue - operating_cost) / total_revenue * 100, 2)

            report = {
                "report_date": report_date,
                "report_name": item.get("REPORT_DATE_NAME", ""),
                "report_type": DataService._classify_report_type(report_date),
                "total_revenue": total_revenue,
                "operating_cost": operating_cost,
                "sell_expense": sell_expense,
                "manage_expense": manage_expense,
                "research_expense": research_expense,
                "finance_expense": finance_expense,
                "operate_profit": operate_profit,
                "total_profit": _safe_float(item.get("TOTAL_PROFIT")),
                "income_tax": _safe_float(item.get("INCOME_TAX")),
                "net_profit": _safe_float(item.get("NETPROFIT")),
                "parent_net_profit": parent_net_profit,
                "sell_expense_ratio": _ratio(sell_expense),
                "manage_expense_ratio": _ratio(manage_expense),
                "research_expense_ratio": _ratio(research_expense),
                "finance_expense_ratio": _ratio(finance_expense),
                "gross_margin": gross_margin,
                "net_margin": _ratio(parent_net_profit),
                "operating_margin": _ratio(operate_profit),
            }
            result.append(report)
        return result

    @staticmethod
    def _fetch_balance_sheet(stock_code: str) -> list:
        """获取资产负债表数据"""
        columns = (
            "REPORT_DATE,REPORT_DATE_NAME,MONETARYFUNDS,ACCOUNTS_RECE,INVENTORY,"
            "TOTAL_CURRENT_ASSETS,TOTAL_NONCURRENT_ASSETS,TOTAL_ASSETS,"
            "SHORT_LOAN,LONG_LOAN,TOTAL_CURRENT_LIAB,TOTAL_NONCURRENT_LIAB,"
            "TOTAL_LIABILITIES,TOTAL_EQUITY,TOTAL_PARENT_EQUITY"
        )
        raw_data = DataService._fetch_eastmoney_report_v2(
            "RPT_F10_FINANCE_GBALANCE", columns, stock_code
        )
        result = []
        for item in raw_data:
            report_date = item.get("REPORT_DATE", "")[:10]
            total_assets = _safe_float(item.get("TOTAL_ASSETS"))
            total_liabilities = _safe_float(item.get("TOTAL_LIABILITIES"))
            total_current_assets = _safe_float(item.get("TOTAL_CURRENT_ASSETS"))
            total_current_liabilities = _safe_float(item.get("TOTAL_CURRENT_LIAB"))
            inventory = _safe_float(item.get("INVENTORY"))

            # 计算衍生比率
            debt_ratio = None
            if total_assets and total_assets != 0 and total_liabilities is not None:
                debt_ratio = round(total_liabilities / total_assets * 100, 2)

            current_ratio = None
            if total_current_liabilities and total_current_liabilities != 0 and total_current_assets is not None:
                current_ratio = round(total_current_assets / total_current_liabilities, 2)

            quick_ratio = None
            if total_current_liabilities and total_current_liabilities != 0:
                if total_current_assets is not None and inventory is not None:
                    quick_ratio = round((total_current_assets - inventory) / total_current_liabilities, 2)

            total_non_current_assets = _safe_float(item.get("TOTAL_NONCURRENT_ASSETS"))
            # 如果API没有直接返回非流动资产，用总资产减去流动资产
            if total_non_current_assets is None and total_assets and total_current_assets:
                total_non_current_assets = round(total_assets - total_current_assets, 2)

            total_non_current_liabilities = _safe_float(item.get("TOTAL_NONCURRENT_LIAB"))
            if total_non_current_liabilities is None and total_liabilities and total_current_liabilities:
                total_non_current_liabilities = round(total_liabilities - total_current_liabilities, 2)

            report = {
                "report_date": report_date,
                "report_name": item.get("REPORT_DATE_NAME", ""),
                "report_type": DataService._classify_report_type(report_date),
                "monetary_funds": _safe_float(item.get("MONETARYFUNDS")),
                "accounts_receivable": _safe_float(item.get("ACCOUNTS_RECE")),
                "inventory": inventory,
                "total_current_assets": total_current_assets,
                "total_non_current_assets": total_non_current_assets,
                "total_assets": total_assets,
                "short_term_borrowing": _safe_float(item.get("SHORT_LOAN")),
                "long_term_borrowing": _safe_float(item.get("LONG_LOAN")),
                "total_current_liabilities": total_current_liabilities,
                "total_non_current_liabilities": total_non_current_liabilities,
                "total_liabilities": total_liabilities,
                "total_equity": _safe_float(item.get("TOTAL_EQUITY")),
                "parent_equity": _safe_float(item.get("TOTAL_PARENT_EQUITY")),
                "debt_ratio": debt_ratio,
                "current_ratio": current_ratio,
                "quick_ratio": quick_ratio,
            }
            result.append(report)
        return result

    @staticmethod
    def _fetch_cashflow_statement(stock_code: str) -> list:
        """获取现金流量表数据

        东方财富RPT_F10_FINANCE_GCASHFLOW关键列：
        - NETCASH_OPERATE: 经营活动现金流净额
        - NETCASH_INVEST: 投资活动现金流净额
        - NETCASH_FINANCE: 筹资活动现金流净额
        - CCE_ADD: 现金及等价物净增加额
        - END_CCE: 期末现金及等价物余额
        - FIX_ASSET_DEPR: 固定资产折旧
        - INTANGIBLE_ASSET_AMORT: 无形资产摊销
        - LTD_EXPENSE_AMORT: 长期待摊费用摊销
        """
        columns = (
            "REPORT_DATE,REPORT_DATE_NAME,NETCASH_OPERATE,NETCASH_INVEST,"
            "NETCASH_FINANCE,CCE_ADD,END_CCE,"
            "FIX_ASSET_DEPR,INTANGIBLE_ASSET_AMORT,LTD_EXPENSE_AMORT"
        )
        raw_data = DataService._fetch_eastmoney_report_v2(
            "RPT_F10_FINANCE_GCASHFLOW", columns, stock_code
        )
        result = []
        for item in raw_data:
            report_date = item.get("REPORT_DATE", "")[:10]
            netcash_operate = _safe_float(item.get("NETCASH_OPERATE"))
            netcash_invest = _safe_float(item.get("NETCASH_INVEST"))

            # 折旧摊销（用于EBITDA计算）
            fix_depr = _safe_float(item.get("FIX_ASSET_DEPR")) or 0
            intangible_amort = _safe_float(item.get("INTANGIBLE_ASSET_AMORT")) or 0
            ltd_amort = _safe_float(item.get("LTD_EXPENSE_AMORT")) or 0
            depreciation_amortization = round(fix_depr + intangible_amort + ltd_amort, 2) if (fix_depr or intangible_amort or ltd_amort) else None

            # 资本开支估算：投资活动现金流为负通常意味着资本开支
            # 真实CAPEX = |投资活动现金流| - 股权/债权投资收益 + 资产处置收益
            # 简化：当投资现金流为负时，取其绝对值作为CAPEX的近似
            capex = abs(netcash_invest) if netcash_invest is not None and netcash_invest < 0 else 0

            # 自由现金流 = 经营现金流 - 资本开支
            # 使用投资现金流负值部分作为CAPEX近似（比原逻辑更准确）
            free_cashflow = None
            if netcash_operate is not None and netcash_invest is not None:
                if netcash_invest < 0:
                    free_cashflow = round(netcash_operate + netcash_invest, 2)
                else:
                    # 投资活动为正（收回投资），CAPEX为0，FCF=经营现金流
                    free_cashflow = round(netcash_operate, 2)

            report = {
                "report_date": report_date,
                "report_name": item.get("REPORT_DATE_NAME", ""),
                "report_type": DataService._classify_report_type(report_date),
                "netcash_operate": netcash_operate,
                "netcash_invest": netcash_invest,
                "netcash_finance": _safe_float(item.get("NETCASH_FINANCE")),
                "cash_begin": None,
                "cash_end": _safe_float(item.get("END_CCE")),
                "capex": round(capex, 2) if capex else None,
                "free_cashflow": free_cashflow,
                "depreciation_amortization": depreciation_amortization,
                "operating_to_profit_ratio": None,  # 后续用利润表数据补充
            }
            result.append(report)
        return result

    @staticmethod
    @cached(ttl_seconds=300, key_prefix="financial_statements")
    def get_financial_statements(stock_code: str) -> dict:
        """获取三大报表（利润表/资产负债表/现金流量表）"""
        if DataService._is_hk_code(stock_code):
            return {"code": stock_code, "error": "港股暂不支持三大报表查询", "income": [], "balance": [], "cashflow": []}
        try:
            income = DataService._fetch_income_statement(stock_code)
            balance = DataService._fetch_balance_sheet(stock_code)
            cashflow = DataService._fetch_cashflow_statement(stock_code)

            # 用利润表数据补充现金流的经营现金流/净利润比率
            income_by_date = {item["report_date"]: item for item in income}
            for cf in cashflow:
                inc = income_by_date.get(cf["report_date"])
                if inc and inc.get("parent_net_profit") and inc["parent_net_profit"] != 0:
                    if cf.get("netcash_operate") is not None:
                        cf["operating_to_profit_ratio"] = round(
                            cf["netcash_operate"] / inc["parent_net_profit"] * 100, 2
                        )

            return {
                "code": stock_code,
                "income": income,
                "balance": balance,
                "cashflow": cashflow,
                "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        except Exception as e:
            logger.error(f"get_financial_statements failed for {stock_code}: {e}")
            return {"code": stock_code, "error": "获取三大报表失败", "income": [], "balance": [], "cashflow": []}

    @staticmethod
    @cached(ttl_seconds=TTL_WEEKLY, key_prefix="search_stock")
    def search_stock(keyword: str) -> list:
        """搜索股票（A股 + 港股）- 使用腾讯财经搜索API"""
        try:
            url = f'https://smartbox.gtimg.cn/s3/?v=2&q={quote(keyword)}&t=all&c=1'
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://stockapp.finance.qq.com/'
            }
            r = _session.get(url, headers=headers, timeout=10)
            r.encoding = 'utf-8'

            text = r.text
            if 'v_hint="' not in text and "v_hint='" not in text:
                return []

            raw = text.split('"')[1]
            items = raw.split('^')
            results = []

            def decode_name(s):
                """解码 \\uXXXX 转义序列为中文"""
                result = []
                i = 0
                while i < len(s):
                    if s[i] == '\\' and i + 5 < len(s) and s[i+1] == 'u':
                        hex_str = s[i+2:i+6]
                        try:
                            result.append(chr(int(hex_str, 16)))
                            i += 6
                            continue
                        except ValueError:
                            pass
                    result.append(s[i])
                    i += 1
                return ''.join(result)

            for item in items:
                parts = item.split('~')
                if len(parts) < 4:
                    continue

                market = parts[0]
                code = parts[1].split('.')[0]  # 去除 .ps 等后缀
                name = decode_name(parts[2])

                # A股（沪深）
                if market in ('sh', 'sz') and len(code) == 6 and code.isdigit():
                    results.append({"code": code, "name": name, "market": "A"})
                # 港股（5位数字，排除8开头的重复代码）
                elif market == 'hk' and len(code) == 5 and code.isdigit() and not code.startswith('8'):
                    results.append({"code": code, "name": name, "market": "HK"})

                if len(results) >= 10:
                    break

            return results
        except Exception as e:
            return []

    @staticmethod
    def get_dividend_stocks() -> list:
        """获取高股息股票数据 - 用于王文和散户乙筛选器"""
        try:
            # 使用东方财富API获取A股股票数据
            # 先获取沪深300成分股 + 中证红利成分股
            stocks = []

            # 预设的高股息蓝筹股列表（银行、能源、公用事业等）
            blue_chip_codes = [
                # 银行
                "601398", "601288", "601988", "601939", "600036",
                "601166", "600016", "601818", "600000", "601328",
                # 能源
                "601088", "600188", "601857", "600028", "601898",
                "601225", "600395", "601001", "600971", "601666",
                # 电力/公用事业
                "600900", "600886", "600795", "600023", "601985",
                "600025", "600674", "600236", "601991", "600098",
                # 交通运输
                "601006", "600029", "601111", "600115", "601872",
                "600009", "600018", "601598", "600897", "600026",
                # 钢铁/基建
                "600019", "601003", "600507", "601186", "601668",
                "601390", "601800", "601169", "600170", "600820",
                # 白酒/消费
                "600519", "000858", "000568", "600809", "002304",
                "000799", "603369", "600779", "000596", "600702",
                # 家电/制造
                "000333", "000651", "600690", "002032", "002508",
                # 医药
                "600196", "600276", "000538", "002001", "600867",
            ]

            # 去重
            unique_codes = list(set(blue_chip_codes))

            # 批量获取数据
            for code in unique_codes[:50]:  # 限制数量避免请求过多
                try:
                    stock_data = DataService._get_stock_dividend_data(code)
                    if stock_data and stock_data.get("dividend_yield") and stock_data["dividend_yield"] > 0:
                        stocks.append(stock_data)
                except Exception:
                    continue

            # 按股息率排序
            stocks.sort(key=lambda x: x.get("dividend_yield", 0), reverse=True)

            return stocks
        except Exception as e:
            logger.error(f"获取高股息股票数据失败: {e}")
            return []

    @staticmethod
    def _get_stock_dividend_data(stock_code: str) -> dict:
        """获取单只股票的分红数据"""
        try:
            # 获取实时行情
            basic = DataService.get_stock_basic(stock_code)
            if "error" in basic:
                return None

            # 获取财务数据
            financials = DataService.get_financial_indicators(stock_code)
            if "error" in financials:
                return None

            reports = financials.get("reports", [])
            if not reports:
                return None

            latest = _get_annual_report(reports)

            # 获取实际分红数据（含CAGR、可持续性等高级指标）
            div_data = DataService._get_actual_dividend(stock_code)
            dividend_per_share = div_data["dividend_per_share"]
            consecutive_years = div_data["consecutive_years"]
            dividend_ratio = div_data["dividend_ratio"]

            # 计算股息率（使用实际分红数据）
            if dividend_per_share > 0 and basic["price"] > 0:
                dividend_yield = (dividend_per_share / basic["price"]) * 100
            else:
                dividend_yield = 0

            return {
                "code": stock_code,
                "name": basic["name"],
                "price": basic["price"],
                "pe": basic.get("pe"),
                "pb": basic.get("pb"),
                "roe": latest.get("roe"),
                "dividend_yield": round(dividend_yield, 2),
                "dividend_per_share": dividend_per_share,
                "dividend_ratio": dividend_ratio,
                "debt_ratio": latest.get("debt_ratio"),
                "gross_margin": latest.get("gross_margin"),
                "net_margin": latest.get("net_margin"),
                "revenue_growth": latest.get("revenue_growth"),
                "profit_growth": latest.get("profit_growth"),
                "market_cap": basic.get("market_cap"),
                "consecutive_years": consecutive_years,
                "operating_cashflow": 1,
                "report_period": latest.get("report_period", ""),
                # 新增：机构级股息分析指标
                "dividend_cagr_3y": div_data["dividend_cagr_3y"],
                "dividend_cagr_5y": div_data["dividend_cagr_5y"],
                "payout_sustainability": div_data["payout_sustainability"],
                "has_special_dividend": div_data["has_special_dividend"],
            }
        except Exception as e:
            logger.warning(f"获取{stock_code}数据失败: {e}")
            return None

    @staticmethod
    @cached(ttl_seconds=TTL_STATIC, key_prefix="dividend_history", persist=True)
    def get_dividend_history(stock_code: str) -> dict:
        """获取历史分红明细（用于攒股收息计算）"""
        if DataService._is_hk_code(stock_code):
            return DataService._get_hk_dividend_history(stock_code)
        try:
            # B股需要转换为对应的A股代码来查询分红（东方财富API不支持B股代码）
            query_code = DataService._get_a_share_code(stock_code) if DataService._is_b_share(stock_code) else stock_code

            # 东方财富分红数据API
            url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
            params = {
                "reportName": "RPT_SHAREBONUS_DET",
                "columns": "SECURITY_CODE,REPORT_DATE,PRETAX_BONUS_RMB,BASIC_EPS,ASSIGN_PROGRESS,EX_DIVIDEND_DATE",
                "filter": f"(SECURITY_CODE=\"{query_code}\")",
                "pageNumber": "1",
                "pageSize": "30",
                "sortTypes": "-1",
                "sortColumns": "REPORT_DATE",
                "source": "HSF10",
                "client": "PC"
            }

            r = _session.get(url, params=params, timeout=15)
            data = r.json()

            if not data.get("result") or not data["result"].get("data"):
                return {"code": stock_code, "dividends": [], "message": "暂无分红数据"}

            # 按年度汇总分红（中期+年终）
            year_dividends = {}
            for div in data["result"]["data"]:
                bonus_per_10 = _safe_float(div.get("PRETAX_BONUS_RMB"))
                if bonus_per_10 and bonus_per_10 > 0:
                    report_date = div.get("REPORT_DATE", "")[:10]
                    year = report_date[:4]
                    ex_date = div.get("EX_DIVIDEND_DATE", "")[:10] if div.get("EX_DIVIDEND_DATE") else ""
                    progress = div.get("ASSIGN_PROGRESS", "")
                    eps = _safe_float(div.get("BASIC_EPS"))
                    dps = round(bonus_per_10 / 10, 4)

                    if year not in year_dividends:
                        year_dividends[year] = {
                            "year": year,
                            "total_dps": 0,
                            "eps": eps,
                            "ex_date": ex_date,
                            "progress": progress,
                            "details": [],
                        }
                    year_dividends[year]["total_dps"] = round(year_dividends[year]["total_dps"] + dps, 4)
                    year_dividends[year]["details"].append({
                        "report_date": report_date,
                        "dividend_per_share": dps,
                        "ex_date": ex_date,
                        "progress": progress,
                    })
                    # 用年报的EPS
                    if report_date.endswith("12-31") and eps:
                        year_dividends[year]["eps"] = eps
                    # 取最新的实施进度
                    if progress == "实施分配":
                        year_dividends[year]["progress"] = progress

            # 按年度降序排列
            dividends = sorted(year_dividends.values(), key=lambda x: x["year"], reverse=True)

            return {
                "code": stock_code,
                "dividends": dividends,
                "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        except Exception as e:
            logger.warning(f"get_dividend_history failed for {stock_code}: {e}")
            return {"code": stock_code, "dividends": [], "error": "获取分红数据失败"}

    @staticmethod
    def _get_hk_dividend_history(stock_code: str) -> dict:
        """获取港股历史分红明细"""
        try:
            import akshare as ak
            import re

            df_div = ak.stock_hk_dividend_payout_em(symbol=stock_code)
            if df_div.empty:
                return {"code": stock_code, "dividends": [], "message": "暂无分红数据"}

            dividends = []
            for _, row in df_div.iterrows():
                ex_date = row.iloc[4]  # 除净日
                scheme = str(row.iloc[2])  # 分红方案
                if not ex_date or not scheme:
                    continue
                m = re.search(r'[\d.]+', scheme)
                if m:
                    dps = float(m.group())
                    if dps > 0:
                        dividends.append({
                            "report_date": str(row.iloc[1])[:10] if row.iloc[1] else "",
                            "ex_date": str(ex_date)[:10],
                            "dividend_per_share": dps,
                            "eps": None,
                            "progress": str(row.iloc[3]) if row.iloc[3] else "",
                        })

            return {
                "code": stock_code,
                "dividends": dividends,
                "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        except Exception as e:
            logger.warning(f"_get_hk_dividend_history failed for {stock_code}: {e}")
            return {"code": stock_code, "dividends": [], "error": "获取港股分红数据失败"}

    @staticmethod
    def _get_actual_dividend(stock_code: str) -> dict:
        """获取实际分红数据：每股股息、连续分红年数、分红比例、增长率等

        Returns:
            {
                "dividend_per_share": float,  # 最近12个月每股股息
                "consecutive_years": int,     # 连续分红年数
                "dividend_ratio": float,      # 分红比例(%)
                "dividend_cagr_3y": float|None,  # 3年股息CAGR(%)
                "dividend_cagr_5y": float|None,  # 5年股息CAGR(%)
                "payout_sustainability": str,    # sustainable/high/unsustainable
                "has_special_dividend": bool,    # 是否有特别股息
                "year_dividends": dict,          # 各年度分红明细
            }
        """
        empty = {
            "dividend_per_share": 0, "consecutive_years": 0, "dividend_ratio": 0,
            "dividend_cagr_3y": None, "dividend_cagr_5y": None,
            "payout_sustainability": "unknown", "has_special_dividend": False,
            "year_dividends": {},
        }
        try:
            from datetime import datetime, timedelta

            # B股需要转换为对应的A股代码来查询分红（东方财富API不支持B股代码）
            query_code = DataService._get_a_share_code(stock_code) if DataService._is_b_share(stock_code) else stock_code

            # 东方财富分红数据API
            url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
            params = {
                "reportName": "RPT_SHAREBONUS_DET",
                "columns": "SECURITY_CODE,REPORT_DATE,PRETAX_BONUS_RMB,BASIC_EPS,ASSIGN_PROGRESS",
                "filter": f"(SECURITY_CODE=\"{query_code}\")",
                "pageNumber": "1",
                "pageSize": "30",
                "sortTypes": "-1",
                "sortColumns": "REPORT_DATE",
                "source": "HSF10",
                "client": "PC"
            }

            r = _session.get(url, params=params, timeout=15)
            data = r.json()

            if not data.get("result") or not data["result"].get("data"):
                return empty

            raw_dividends = data["result"]["data"]

            # === 按财政年度分组，合并中期+年终分红 ===
            year_dividends = {}  # {year_str: {"total_dps": float, "eps": float, "progress": str}}
            for div in raw_dividends:
                bonus_per_10 = _safe_float(div.get("PRETAX_BONUS_RMB"))
                if not bonus_per_10 or bonus_per_10 <= 0:
                    # bonus为0表示该年度不分红，记录为0
                    report_date_str = div.get("REPORT_DATE", "")[:10]
                    if report_date_str:
                        y = report_date_str[:4]
                        if y not in year_dividends:
                            year_dividends[y] = {"total_dps": 0, "eps": 0, "progress": ""}
                    continue

                report_date_str = div.get("REPORT_DATE", "")[:10]
                if not report_date_str:
                    continue
                year = report_date_str[:4]
                dps = round(bonus_per_10 / 10, 4)
                eps = _safe_float(div.get("BASIC_EPS")) or 0
                progress = div.get("ASSIGN_PROGRESS", "")

                if year not in year_dividends:
                    year_dividends[year] = {"total_dps": 0, "eps": 0, "progress": ""}
                year_dividends[year]["total_dps"] = round(year_dividends[year]["total_dps"] + dps, 4)
                # 年报的EPS更准确
                if report_date_str.endswith("12-31") and eps > 0:
                    year_dividends[year]["eps"] = eps
                elif eps > 0 and year_dividends[year]["eps"] == 0:
                    year_dividends[year]["eps"] = eps
                # 取最新的实施进度
                if progress:
                    year_dividends[year]["progress"] = progress

            if not year_dividends:
                return empty

            # === 按年度排序 ===
            sorted_years = sorted(year_dividends.keys(), reverse=True)
            annual_dps = [(y, year_dividends[y]["total_dps"]) for y in sorted_years]

            # === 最近12个月的股息（累计同年中期+年终） ===
            now = datetime.now()
            one_year_ago = now - timedelta(days=365)
            ttm_dividend = 0
            latest_eps = 0
            has_recent = False

            for div in raw_dividends:
                report_date_str = div.get("REPORT_DATE", "")[:10]
                if not report_date_str:
                    continue
                try:
                    report_date = datetime.strptime(report_date_str, "%Y-%m-%d")
                except ValueError:
                    continue
                bonus_per_10 = _safe_float(div.get("PRETAX_BONUS_RMB"))
                if bonus_per_10 and bonus_per_10 > 0 and report_date >= one_year_ago:
                    ttm_dividend += bonus_per_10 / 10
                    has_recent = True
                    if latest_eps == 0:
                        latest_eps = _safe_float(div.get("BASIC_EPS")) or 0

            # 如果过去12个月没有分红，取最近一年的年度分红
            if not has_recent and annual_dps:
                latest_year, latest_dps = annual_dps[0]
                ttm_dividend = latest_dps
                latest_eps = year_dividends[latest_year].get("eps", 0)

            # === 连续分红年数（按年度分组统计） ===
            consecutive_years = 0
            for y, dps in annual_dps:
                if dps > 0:
                    consecutive_years += 1
                else:
                    break  # 遇到不分红的年份则中断

            # === 特别股息检测 ===
            # 如果某一年的分红显著高于其他年份（>2倍中位数），标记为特别股息
            has_special_dividend = False
            positive_dps = [d for _, d in annual_dps if d > 0]
            if len(positive_dps) >= 3:
                median_dps = sorted(positive_dps)[len(positive_dps) // 2]
                for _, dps in annual_dps:
                    if dps > median_dps * 2.5 and median_dps > 0:
                        has_special_dividend = True
                        break

            # === 分红比例 ===
            dividend_ratio = 0
            if latest_eps > 0 and ttm_dividend > 0:
                dividend_ratio = round((ttm_dividend / latest_eps) * 100, 2)

            # 派息率可持续性评估
            if dividend_ratio > 100:
                payout_sustainability = "unsustainable"
            elif dividend_ratio > 80:
                payout_sustainability = "high"
            elif dividend_ratio > 0:
                payout_sustainability = "sustainable"
            else:
                payout_sustainability = "unknown"

            # === 股息增长率 CAGR ===
            def _calc_cagr(years_back: int):
                """计算N年股息CAGR"""
                if len(annual_dps) < years_back + 1:
                    return None
                # 找years_back年前和最近一年都有分红的数据
                recent = annual_dps[0]
                target = annual_dps[years_back]
                if recent[1] <= 0 or target[1] <= 0:
                    return None
                try:
                    cagr = (pow(recent[1] / target[1], 1.0 / years_back) - 1) * 100
                    return round(cagr, 2)
                except (ZeroDivisionError, ValueError):
                    return None

            dividend_cagr_3y = _calc_cagr(3)
            dividend_cagr_5y = _calc_cagr(5)

            return {
                "dividend_per_share": round(ttm_dividend, 4),
                "consecutive_years": consecutive_years,
                "dividend_ratio": dividend_ratio,
                "dividend_cagr_3y": dividend_cagr_3y,
                "dividend_cagr_5y": dividend_cagr_5y,
                "payout_sustainability": payout_sustainability,
                "has_special_dividend": has_special_dividend,
                "year_dividends": year_dividends,
            }

        except Exception as e:
            logger.warning(f"获取{stock_code}分红数据失败: {e}")
            return empty

    @staticmethod
    @cached(ttl_seconds=TTL_STATIC, key_prefix="valuation_history", persist=True)
    def get_valuation_history(stock_code: str) -> dict:
        """获取个股历史PE(TTM)/PB/股息率估值数据和统计指标"""
        if DataService._is_hk_code(stock_code):
            return DataService._get_hk_valuation_history(stock_code)

        try:
            import akshare as ak

            # 获取PE(TTM)历史
            df_pe = ak.stock_zh_valuation_baidu(symbol=stock_code, indicator='市盈率(TTM)', period='全部')
            pe_history = [{"date": str(row["date"])[:10], "value": round(float(row["value"]), 2)} for _, row in df_pe.iterrows()]

            # 获取PB历史
            df_pb = ak.stock_zh_valuation_baidu(symbol=stock_code, indicator='市净率', period='全部')
            pb_history = [{"date": str(row["date"])[:10], "value": round(float(row["value"]), 2)} for _, row in df_pb.iterrows()]

            # 获取股息率历史（通过价格+分红数据计算）
            div_history = DataService._calc_a_dividend_yield(stock_code)

            return {
                "pe_history": pe_history,
                "pb_history": pb_history,
                "div_history": div_history,
                "stats": DataService._calc_valuation_stats(pe_history, pb_history, div_history),
            }
        except Exception as e:
            logger.error(f"get_valuation_history failed for {stock_code}: {e}")
            return {"pe_history": [], "pb_history": [], "div_history": [], "stats": None, "error": "获取估值历史失败，请稍后重试"}

    @staticmethod
    def _calc_valuation_stats(pe_history: list, pb_history: list, div_history: list = None) -> dict:
        """计算估值统计指标（含异常值过滤）"""
        import numpy as np

        def calc_stats(history, upper_limit=None):
            if not history:
                return None
            values = [h["value"] for h in history if h["value"] and h["value"] > 0]
            if not values:
                return None
            # 过滤极端异常值（如PE>500的亏损边缘股票）
            if upper_limit is not None:
                values = [v for v in values if v < upper_limit]
            if not values:
                return None
            current = values[-1]
            arr = np.array(values)
            count_below = int(np.sum(arr <= current))
            return {
                "current": round(current, 2),
                "min": round(float(np.min(arr)), 2),
                "max": round(float(np.max(arr)), 2),
                "median": round(float(np.median(arr)), 2),
                "p25": round(float(np.percentile(arr, 25)), 2),
                "p75": round(float(np.percentile(arr, 75)), 2),
                "percentile": round(count_below / len(values) * 100, 1),
                "count": len(values),
            }

        result = {
            "pe": calc_stats(pe_history, upper_limit=500),
            "pb": calc_stats(pb_history, upper_limit=100),
        }
        if div_history is not None:
            result["div"] = calc_stats(div_history, upper_limit=30)
        return result

    @staticmethod
    def _calc_a_dividend_yield(stock_code: str) -> list:
        """计算A股历史股息率 = 过去12个月分红 / 股价"""
        try:
            import akshare as ak

            # 获取分红记录
            df_div = ak.stock_history_dividend_detail(symbol=stock_code, indicator='分红')
            # 只取已实施的分红
            df_done = df_div[df_div['进度'] == '实施'].copy()
            if df_done.empty:
                return []

            # 解析分红数据：(除权除息日, 每股分红)
            div_records = []
            for _, row in df_done.iterrows():
                ex_date = row.get('除权除息日')
                bonus = _safe_float(row.get('派息'))
                if ex_date and bonus and bonus > 0:
                    try:
                        ex_date_str = str(ex_date)[:10]
                        dps = bonus / 10  # 每10股派息 → 每股
                        div_records.append((ex_date_str, dps))
                    except Exception:
                        continue

            if not div_records:
                return []

            div_records.sort(key=lambda x: x[0])

            # 获取历史价格（新浪财经K线）
            price_data = DataService._fetch_a_kline(stock_code)
            if not price_data:
                return []

            # 对每个交易日，计算过去12个月的股息率
            from datetime import datetime, timedelta
            result = []
            for date_str, price in price_data:
                try:
                    d = datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    continue
                one_year_ago = (d - timedelta(days=365)).strftime("%Y-%m-%d")
                ttm_div = sum(dps for ex, dps in div_records if one_year_ago < ex <= date_str)
                if ttm_div > 0 and price > 0:
                    div_yield = round(ttm_div / price * 100, 2)
                    if 0 < div_yield < 30:
                        result.append({"date": date_str, "value": div_yield})

            return result
        except Exception:
            return []

    @staticmethod
    def _fetch_a_kline(stock_code: str) -> list:
        """从新浪财经获取A股历史日K线数据，返回[(date, close_price), ...]"""
        try:
            if stock_code.startswith('6'):
                symbol = f"sh{stock_code}"
            else:
                symbol = f"sz{stock_code}"

            url = 'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData'
            params = {'symbol': symbol, 'scale': '240', 'ma': 'no', 'datalen': '1500'}
            headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.sina.com.cn'}
            r = _session.get(url, params=params, headers=headers, timeout=15)
            data = r.json()

            result = []
            for item in data:
                date = item.get('day', '')
                close = float(item.get('close', 0))
                if date and close > 0:
                    result.append((date, close))
            return result
        except Exception:
            return []

    @staticmethod
    def _calc_hk_dividend_yield(stock_code: str, price_data: list) -> list:
        """计算港股历史股息率 = 过去12个月分红 / 股价"""
        try:
            import akshare as ak
            import re
            from datetime import datetime, timedelta

            # 获取港股分红记录（参数名是symbol）
            df_div = ak.stock_hk_dividend_payout_em(symbol=stock_code)
            if df_div.empty:
                return []

            # 按列索引访问（列名有编码问题）：
            # col[0]=公告日期, col[1]=报告期, col[2]=分红方案, col[3]=进度, col[4]=除净日
            div_records = []
            for _, row in df_div.iterrows():
                ex_date = row.iloc[4]  # 除净日
                scheme = str(row.iloc[2])  # 分红方案
                if not ex_date or not scheme:
                    continue
                # 解析"每股派港币X.XX元"或"每股派X.XX港元"
                m = re.search(r'[\d.]+', scheme)
                if m:
                    dps = float(m.group())
                    if dps > 0:
                        ex_date_str = str(ex_date)[:10]
                        div_records.append((ex_date_str, dps))

            if not div_records:
                return []

            div_records.sort(key=lambda x: x[0])

            # 对每个交易日，计算过去12个月的股息率
            result = []
            for date_str, price in price_data:
                try:
                    d = datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    continue
                one_year_ago = (d - timedelta(days=365)).strftime("%Y-%m-%d")
                ttm_div = sum(dps for ex, dps in div_records if one_year_ago < ex <= date_str)
                if ttm_div > 0 and price > 0:
                    div_yield = round(ttm_div / price * 100, 2)
                    if 0 < div_yield < 30:
                        result.append({"date": date_str, "value": div_yield})

            return result
        except Exception:
            return []

    @staticmethod
    def _get_hk_valuation_history(stock_code: str) -> dict:
        """获取港股历史PE(TTM)/PB - 通过腾讯K线+akshare财务数据计算"""
        try:
            import akshare as ak

            # 1. 获取历史日K线数据（腾讯财经）
            price_data = DataService._fetch_hk_kline(stock_code)
            if not price_data:
                return {"pe_history": [], "pb_history": [], "stats": None, "message": "无法获取港股历史价格数据"}

            # 2. 获取财务数据（EPS和净资产）
            df_income = ak.stock_financial_hk_report_em(stock=stock_code, symbol='利润表', indicator='报告期')
            df_bs = ak.stock_financial_hk_report_em(stock=stock_code, symbol='资产负债表', indicator='报告期')

            # 提取EPS数据
            eps_rows = df_income[df_income['STD_ITEM_CODE'] == '004027002']
            np_rows = df_income[df_income['STD_ITEM_CODE'] == '004025002']
            equity_rows = df_bs[df_bs['STD_ITEM_CODE'] == '004030999']

            # 构建财务数据表：{report_date: {eps, np, equity}}
            fin_data = {}
            for _, row in eps_rows.iterrows():
                d = str(row['REPORT_DATE'])[:10]
                eps_val = _safe_float(row['AMOUNT'])
                if eps_val and eps_val > 0:
                    fin_data.setdefault(d, {})['eps'] = eps_val

            for _, row in np_rows.iterrows():
                d = str(row['REPORT_DATE'])[:10]
                np_val = _safe_float(row['AMOUNT'])
                if np_val:
                    fin_data.setdefault(d, {})['np'] = np_val

            for _, row in equity_rows.iterrows():
                d = str(row['REPORT_DATE'])[:10]
                eq_val = _safe_float(row['AMOUNT'])
                if eq_val:
                    fin_data.setdefault(d, {})['equity'] = eq_val

            # 计算每个报告期的TTM EPS和BPS
            sorted_dates = sorted(fin_data.keys(), reverse=True)
            report_metrics = []  # [(date, ttm_eps, bps)]

            for i, d in enumerate(sorted_dates):
                fd = fin_data[d]
                eps = fd.get('eps', 0)
                np_val = fd.get('np')
                equity = fd.get('equity')

                if not eps or eps <= 0:
                    continue

                # 计算TTM EPS
                month_day = d[5:]
                ttm_eps = eps
                if month_day != "12-31":
                    # 季报：找上年年报和上年同期
                    year = d[:4]
                    for d2 in sorted_dates[i+1:]:
                        fd2 = fin_data[d2]
                        if d2[:4] < year and d2[5:] == "12-31" and fd2.get('eps'):
                            prev_annual = fd2['eps']
                            prev_same = 0
                            for d3 in sorted_dates:
                                if d3[:4] < year and d3[5:] == month_day:
                                    prev_same = fin_data[d3].get('eps', 0)
                                    break
                            ttm_eps = eps + prev_annual - prev_same
                            break

                # 计算BPS = 净资产 / 股份数
                bps = None
                if equity and np_val and eps > 0:
                    shares = np_val / eps  # 股份数 = 净利润 / EPS
                    if shares > 0:
                        bps = equity / shares

                report_metrics.append((d, ttm_eps, bps))

            # 3. 对每个交易日匹配最近的财务数据，计算PE/PB
            report_metrics.sort(key=lambda x: x[0])
            pe_history = []
            pb_history = []
            ri = 0  # report index

            for date, price in price_data:
                # 找到该日期之前最近的财报
                while ri + 1 < len(report_metrics) and report_metrics[ri + 1][0] <= date:
                    ri += 1

                if ri < len(report_metrics) and report_metrics[ri][0] <= date:
                    _, ttm_eps, bps = report_metrics[ri]
                    if ttm_eps and ttm_eps > 0:
                        pe_val = round(price / ttm_eps, 2)
                        if 0 < pe_val < 500:  # 过滤异常值
                            pe_history.append({"date": date, "value": pe_val})
                    if bps and bps > 0:
                        pb_val = round(price / bps, 2)
                        if 0 < pb_val < 100:
                            pb_history.append({"date": date, "value": pb_val})

            # 4. 计算股息率历史
            div_history = DataService._calc_hk_dividend_yield(stock_code, price_data)

            return {
                "pe_history": pe_history,
                "pb_history": pb_history,
                "div_history": div_history,
                "stats": DataService._calc_valuation_stats(pe_history, pb_history, div_history),
            }
        except Exception as e:
            logger.error(f"_get_hk_valuation_history failed for {stock_code}: {e}")
            return {"pe_history": [], "pb_history": [], "div_history": [], "stats": None, "error": "获取港股估值历史失败，请稍后重试"}

    @staticmethod
    def _fetch_hk_kline(stock_code: str) -> list:
        """从腾讯财经获取港股历史日K线数据，返回[(date, close_price), ...]"""
        try:
            from datetime import datetime
            end_date = datetime.now().strftime("%Y-%m-%d")
            url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get'
            params = {'param': f'hk{stock_code},day,2010-01-01,{end_date},1500,qfq'}
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://stockapp.finance.qq.com/'
            }
            r = _session.get(url, params=params, headers=headers, timeout=15)
            data = r.json()

            key = f'hk{stock_code}'
            if 'data' not in data or key not in data['data']:
                return []

            klines = data['data'][key].get('day', [])
            result = []
            for k in klines:
                if len(k) >= 3:
                    date = k[0]
                    close = float(k[2])
                    if close > 0:
                        result.append((date, close))
            return result
        except Exception:
            return []


# _safe_float is now imported from app.core.utils (see top of file)


def _validate_report(report: dict) -> dict:
    """校验财务数据合理性，标记异常值"""
    warnings = []

    # 毛利率/净利率范围校验
    gm = report.get("gross_margin")
    if gm is not None and (gm < -50 or gm > 100):
        warnings.append(f"毛利率异常({gm:.1f}%)")
        report["gross_margin"] = None  # 置为None，避免误导

    nm = report.get("net_margin")
    if nm is not None and (nm < -100 or nm > 100):
        warnings.append(f"净利率异常({nm:.1f}%)")
        report["net_margin"] = None

    # ROE范围校验
    roe = report.get("roe")
    if roe is not None and (roe < -100 or roe > 200):
        warnings.append(f"ROE异常({roe:.1f}%)")
        report["roe"] = None

    # 资产负债率范围校验
    dr = report.get("debt_ratio")
    if dr is not None and (dr < 0 or dr > 100):
        warnings.append(f"资产负债率异常({dr:.1f}%)")
        report["debt_ratio"] = None

    # 增长率异常检测（超过1000%通常有特殊原因，标记但不置None）
    rg = report.get("revenue_growth")
    if rg is not None and abs(rg) > 1000:
        warnings.append(f"营收增长率异常({rg:.1f}%)")

    pg = report.get("profit_growth")
    if pg is not None and abs(pg) > 5000:
        warnings.append(f"利润增长率异常({pg:.1f}%)")

    if warnings:
        report["_warnings"] = warnings

    return report


def _classify_report(report: dict) -> dict:
    """给报告添加报告期分类信息"""
    date = report.get("date", "")
    month_day = date[5:] if len(date) >= 10 else ""

    if month_day == "12-31":
        report["report_period"] = f"{date[:4]}年报"
        report["is_annual"] = True
    elif month_day == "09-30":
        report["report_period"] = f"{date[:4]}三季报"
        report["is_annual"] = False
    elif month_day == "06-30":
        report["report_period"] = f"{date[:4]}中报"
        report["is_annual"] = False
    elif month_day == "03-31":
        report["report_period"] = f"{date[:4]}一季报"
        report["is_annual"] = False
    else:
        report["report_period"] = date
        report["is_annual"] = False

    return report


def _get_annual_report(reports: list) -> dict:
    """从报告列表中选取最新一份年报，找不到则回退到最新报告"""
    for r in reports:
        if r.get("is_annual"):
            return r
    return reports[0] if reports else {}
