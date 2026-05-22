"""
Tushare数据服务 - 高质量A股财务数据
数据源：Tushare Pro（需要API Token）
配置：通过环境变量 TUSHARE_TOKEN 设置Token
"""
import os
import time
import logging
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

# 缓存配置
CACHE_TTL = 600  # 10分钟缓存（Tushare有调用限制）
_cache: Dict[str, tuple] = {}


def _get_cached(key: str) -> Optional[Any]:
    if key in _cache:
        data, timestamp = _cache[key]
        if time.time() - timestamp < CACHE_TTL:
            return data
    return None


def _set_cache(key: str, data: Any):
    _cache[key] = (data, time.time())


class TushareService:
    """Tushare财务数据服务"""

    def __init__(self):
        self._pro = None
        self._token = os.environ.get("TUSHARE_TOKEN", "")
        self._initialized = False

    def _get_pro(self):
        """懒加载Tushare Pro接口"""
        if not self._initialized:
            self._initialized = True
            if not self._token:
                logger.warning("未配置TUSHARE_TOKEN环境变量，Tushare服务不可用")
                return None
            try:
                import tushare as ts
                ts.set_token(self._token)
                self._pro = ts.pro_api()
                logger.info("Tushare Pro接口初始化成功")
            except Exception as e:
                logger.warning(f"Tushare初始化失败: {e}")
        return self._pro

    @property
    def available(self) -> bool:
        """检查Tushare是否可用"""
        return self._get_pro() is not None

    def get_stock_basic(self, ts_code: Optional[str] = None) -> Optional[List[Dict]]:
        """获取股票基本信息"""
        cache_key = f"tushare_stock_basic_{ts_code}"
        cached = _get_cached(cache_key)
        if cached:
            return cached

        pro = self._get_pro()
        if not pro:
            return None

        try:
            kwargs = {"exchange": "", "list_status": "L"}
            if ts_code:
                kwargs["ts_code"] = ts_code
            df = pro.stock_basic(**kwargs)
            if df is None or df.empty:
                return None

            result = []
            for _, row in df.iterrows():
                result.append({
                    "ts_code": str(row.get("ts_code", "")),
                    "symbol": str(row.get("symbol", "")),
                    "name": str(row.get("name", "")),
                    "area": str(row.get("area", "")),
                    "industry": str(row.get("industry", "")),
                    "market": str(row.get("market", "")),
                    "list_date": str(row.get("list_date", "")),
                })
            _set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取股票基本信息失败: {e}")
            return None

    def get_fina_indicator(self, ts_code: str) -> Optional[List[Dict]]:
        """获取财务指标"""
        cache_key = f"tushare_fina_{ts_code}"
        cached = _get_cached(cache_key)
        if cached:
            return cached

        pro = self._get_pro()
        if not pro:
            return None

        try:
            df = pro.fina_indicator(ts_code=ts_code, limit=8)
            if df is None or df.empty:
                return None

            result = []
            for _, row in df.iterrows():
                result.append({
                    "ts_code": str(row.get("ts_code", "")),
                    "ann_date": str(row.get("ann_date", "")),
                    "end_date": str(row.get("end_date", "")),
                    "roe": float(row.get("roe", 0)) if row.get("roe") else None,
                    "roe_waa": float(row.get("roe_waa", 0)) if row.get("roe_waa") else None,
                    "roa": float(row.get("roa", 0)) if row.get("roa") else None,
                    "grossprofit_margin": float(row.get("grossprofit_margin", 0)) if row.get("grossprofit_margin") else None,
                    "netprofit_margin": float(row.get("netprofit_margin", 0)) if row.get("netprofit_margin") else None,
                    "debt_to_assets": float(row.get("debt_to_assets", 0)) if row.get("debt_to_assets") else None,
                    "current_ratio": float(row.get("current_ratio", 0)) if row.get("current_ratio") else None,
                    "revenue_ps": float(row.get("revenue_ps", 0)) if row.get("revenue_ps") else None,
                    "profit_dedt_ps": float(row.get("profit_dedt_ps", 0)) if row.get("profit_dedt_ps") else None,
                    "cfps": float(row.get("cfps", 0)) if row.get("cfps") else None,
                    "ocfps": float(row.get("ocfps", 0)) if row.get("ocfps") else None,
                    "eps": float(row.get("eps", 0)) if row.get("eps") else None,
                    "bps": float(row.get("bps", 0)) if row.get("bps") else None,
                })
            _set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取财务指标失败 ({ts_code}): {e}")
            return None

    def get_income(self, ts_code: str) -> Optional[List[Dict]]:
        """获取利润表"""
        cache_key = f"tushare_income_{ts_code}"
        cached = _get_cached(cache_key)
        if cached:
            return cached

        pro = self._get_pro()
        if not pro:
            return None

        try:
            df = pro.income(ts_code=ts_code, limit=8)
            if df is None or df.empty:
                return None

            result = []
            for _, row in df.iterrows():
                result.append({
                    "ts_code": str(row.get("ts_code", "")),
                    "ann_date": str(row.get("ann_date", "")),
                    "end_date": str(row.get("end_date", "")),
                    "revenue": float(row.get("revenue", 0)) if row.get("revenue") else None,
                    "operate_profit": float(row.get("operate_profit", 0)) if row.get("operate_profit") else None,
                    "total_profit": float(row.get("total_profit", 0)) if row.get("total_profit") else None,
                    "n_income": float(row.get("n_income", 0)) if row.get("n_income") else None,
                    "n_income_attr_p": float(row.get("n_income_attr_p", 0)) if row.get("n_income_attr_p") else None,
                })
            _set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取利润表失败 ({ts_code}): {e}")
            return None

    def get_balance_sheet(self, ts_code: str) -> Optional[List[Dict]]:
        """获取资产负债表"""
        cache_key = f"tushare_balance_{ts_code}"
        cached = _get_cached(cache_key)
        if cached:
            return cached

        pro = self._get_pro()
        if not pro:
            return None

        try:
            df = pro.balancesheet(ts_code=ts_code, limit=8)
            if df is None or df.empty:
                return None

            result = []
            for _, row in df.iterrows():
                result.append({
                    "ts_code": str(row.get("ts_code", "")),
                    "ann_date": str(row.get("ann_date", "")),
                    "end_date": str(row.get("end_date", "")),
                    "total_assets": float(row.get("total_assets", 0)) if row.get("total_assets") else None,
                    "total_liab": float(row.get("total_liab", 0)) if row.get("total_liab") else None,
                    "total_hldr_eqy_exc_min_int": float(row.get("total_hldr_eqy_exc_min_int", 0)) if row.get("total_hldr_eqy_exc_min_int") else None,
                    "total_cur_assets": float(row.get("total_cur_assets", 0)) if row.get("total_cur_assets") else None,
                    "total_cur_liab": float(row.get("total_cur_liab", 0)) if row.get("total_cur_liab") else None,
                    "money_cap": float(row.get("money_cap", 0)) if row.get("money_cap") else None,
                })
            _set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取资产负债表失败 ({ts_code}): {e}")
            return None

    def get_cashflow(self, ts_code: str) -> Optional[List[Dict]]:
        """获取现金流量表"""
        cache_key = f"tushare_cashflow_{ts_code}"
        cached = _get_cached(cache_key)
        if cached:
            return cached

        pro = self._get_pro()
        if not pro:
            return None

        try:
            df = pro.cashflow(ts_code=ts_code, limit=8)
            if df is None or df.empty:
                return None

            result = []
            for _, row in df.iterrows():
                result.append({
                    "ts_code": str(row.get("ts_code", "")),
                    "ann_date": str(row.get("ann_date", "")),
                    "end_date": str(row.get("end_date", "")),
                    "n_cashflow_act": float(row.get("n_cashflow_act", 0)) if row.get("n_cashflow_act") else None,
                    "n_cashflow_inv_act": float(row.get("n_cashflow_inv_act", 0)) if row.get("n_cashflow_inv_act") else None,
                    "n_cash_flows_fnc_act": float(row.get("n_cash_flows_fnc_act", 0)) if row.get("n_cash_flows_fnc_act") else None,
                    "free_cashflow": float(row.get("free_cashflow", 0)) if row.get("free_cashflow") else None,
                })
            _set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取现金流量表失败 ({ts_code}): {e}")
            return None

    def get_dividend(self, ts_code: str) -> Optional[List[Dict]]:
        """获取分红历史"""
        cache_key = f"tushare_dividend_{ts_code}"
        cached = _get_cached(cache_key)
        if cached:
            return cached

        pro = self._get_pro()
        if not pro:
            return None

        try:
            df = pro.dividend(ts_code=ts_code)
            if df is None or df.empty:
                return None

            result = []
            for _, row in df.iterrows():
                result.append({
                    "ts_code": str(row.get("ts_code", "")),
                    "end_date": str(row.get("end_date", "")),
                    "ann_date": str(row.get("ann_date", "")),
                    "div_proc": str(row.get("div_proc", "")),
                    "stk_div": float(row.get("stk_div", 0)) if row.get("stk_div") else None,
                    "stk_bo_rate": float(row.get("stk_bo_rate", 0)) if row.get("stk_bo_rate") else None,
                    "stk_co_rate": float(row.get("stk_co_rate", 0)) if row.get("stk_co_rate") else None,
                    "cash_div": float(row.get("cash_div", 0)) if row.get("cash_div") else None,
                    "cash_div_tax": float(row.get("cash_div_tax", 0)) if row.get("cash_div_tax") else None,
                    "record_date": str(row.get("record_date", "")),
                    "ex_date": str(row.get("ex_date", "")),
                    "pay_date": str(row.get("pay_date", "")),
                })
            _set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取分红历史失败 ({ts_code}): {e}")
            return None

    def get_daily(self, ts_code: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Optional[List[Dict]]:
        """获取日线行情"""
        cache_key = f"tushare_daily_{ts_code}_{start_date}_{end_date}"
        cached = _get_cached(cache_key)
        if cached:
            return cached

        pro = self._get_pro()
        if not pro:
            return None

        try:
            kwargs = {"ts_code": ts_code}
            if start_date:
                kwargs["start_date"] = start_date
            if end_date:
                kwargs["end_date"] = end_date
            df = pro.daily(**kwargs)
            if df is None or df.empty:
                return None

            result = []
            for _, row in df.iterrows():
                result.append({
                    "ts_code": str(row.get("ts_code", "")),
                    "trade_date": str(row.get("trade_date", "")),
                    "open": float(row.get("open", 0)) if row.get("open") else None,
                    "high": float(row.get("high", 0)) if row.get("high") else None,
                    "low": float(row.get("low", 0)) if row.get("low") else None,
                    "close": float(row.get("close", 0)) if row.get("close") else None,
                    "vol": float(row.get("vol", 0)) if row.get("vol") else None,
                    "amount": float(row.get("amount", 0)) if row.get("amount") else None,
                    "pct_chg": float(row.get("pct_chg", 0)) if row.get("pct_chg") else None,
                })
            _set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取日线行情失败 ({ts_code}): {e}")
            return None

    def get_index_weight(self, index_code: str) -> Optional[List[Dict]]:
        """获取指数成分权重"""
        cache_key = f"tushare_index_weight_{index_code}"
        cached = _get_cached(cache_key)
        if cached:
            return cached

        pro = self._get_pro()
        if not pro:
            return None

        try:
            df = pro.index_weight(index_code=index_code)
            if df is None or df.empty:
                return None

            result = []
            for _, row in df.iterrows():
                result.append({
                    "index_code": str(row.get("index_code", "")),
                    "con_code": str(row.get("con_code", "")),
                    "trade_date": str(row.get("trade_date", "")),
                    "weight": float(row.get("weight", 0)) if row.get("weight") else None,
                })
            _set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取指数成分权重失败 ({index_code}): {e}")
            return None


# 单例
tushare_service = TushareService()
