"""
AKShare数据服务 - 统一的金融数据接口
数据源：AKShare（聚合多个国内财经数据源）
"""
import time
import math
import logging
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

from app.core.cache import get_cache as _get_cached, set_cache as _set_cache, TTL_WEEKLY, TTL_DAILY
from app.core.utils import safe_float as _safe_float


class AKShareService:
    """AKShare数据服务"""

    # ==================== 宏观数据 ====================

    def get_gdp_data(self) -> Optional[List[Dict]]:
        """获取中国GDP数据"""
        cache_key = "macro_china_gdp"
        cached = _get_cached(cache_key, TTL_WEEKLY)
        if cached:
            return cached
        try:
            import akshare as ak
            df = ak.macro_china_gdp()
            if df is None or df.empty:
                return None
            result = []
            for _, row in df.iterrows():
                result.append({
                    "date": str(row.iloc[0]),               # 季度
                    "gdp": _safe_float(row.iloc[1]),         # GDP绝对值
                    "gdp_growth": _safe_float(row.iloc[2]),  # GDP同比
                    "primary": _safe_float(row.iloc[3]),     # 第一产业绝对值
                    "primary_growth": _safe_float(row.iloc[4]),  # 第一产业同比
                    "secondary": _safe_float(row.iloc[5]),   # 第二产业绝对值
                    "secondary_growth": _safe_float(row.iloc[6]),  # 第二产业同比
                    "tertiary": _safe_float(row.iloc[7]),    # 第三产业绝对值
                    "tertiary_growth": _safe_float(row.iloc[8]),  # 第三产业同比
                })
            _set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取GDP数据失败: {e}")
            return None

    def get_cpi_data(self) -> Optional[List[Dict]]:
        """获取中国CPI数据（全国/城市/农村当月同比）"""
        cache_key = "macro_china_cpi"
        cached = _get_cached(cache_key, TTL_WEEKLY)
        if cached:
            return cached
        try:
            import akshare as ak
            df = ak.macro_china_cpi()
            if df is None or df.empty:
                return None
            result = []
            for _, row in df.iterrows():
                result.append({
                    "date": str(row.iloc[0]),                       # 月份
                    "cpi": _safe_float(row.iloc[1]),                # 全国-当月
                    "cpi_yoy": _safe_float(row.iloc[2]),            # 全国-同比增长
                    "city": _safe_float(row.iloc[5]),               # 城市-当月
                    "city_yoy": _safe_float(row.iloc[6]),           # 城市-同比增长
                    "rural": _safe_float(row.iloc[9]),              # 农村-当月
                    "rural_yoy": _safe_float(row.iloc[10]),         # 农村-同比增长
                })
            _set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取CPI数据失败: {e}")
            return None

    def get_pmi_data(self) -> Optional[List[Dict]]:
        """获取中国PMI数据"""
        cache_key = "macro_china_pmi"
        cached = _get_cached(cache_key, TTL_WEEKLY)
        if cached:
            return cached
        try:
            import akshare as ak
            df = ak.macro_china_pmi()
            if df is None or df.empty:
                return None
            result = []
            for _, row in df.iterrows():
                result.append({
                    "date": str(row.iloc[0]),                       # 月份
                    "manufacturing": _safe_float(row.iloc[1]),      # 制造业-指数
                    "mfg_yoy": _safe_float(row.iloc[2]),            # 制造业-同比
                    "non_manufacturing": _safe_float(row.iloc[3]),  # 非制造业-指数
                    "non_mfg_yoy": _safe_float(row.iloc[4]),        # 非制造业-同比
                })
            _set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取PMI数据失败: {e}")
            return None

    def get_money_supply(self) -> Optional[List[Dict]]:
        """获取货币供应量数据(M0/M1/M2)"""
        cache_key = "macro_china_money"
        cached = _get_cached(cache_key, TTL_WEEKLY)
        if cached:
            return cached
        try:
            import akshare as ak
            df = ak.macro_china_money_supply()
            if df is None or df.empty:
                return None
            result = []
            for _, row in df.iterrows():
                result.append({
                    "date": str(row.iloc[0]),                       # 月份
                    "m2": _safe_float(row.iloc[1]),                 # M2-数量(亿元)
                    "m2_growth": _safe_float(row.iloc[2]),          # M2-同比增长
                    "m1": _safe_float(row.iloc[4]),                 # M1-数量(亿元)
                    "m1_growth": _safe_float(row.iloc[5]),          # M1-同比增长
                    "m0": _safe_float(row.iloc[7]),                 # M0-数量(亿元)
                    "m0_growth": _safe_float(row.iloc[8]),          # M0-同比增长
                })
            _set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取货币供应量数据失败: {e}")
            return None

    def get_social_financing(self) -> Optional[List[Dict]]:
        """获取社会融资规模数据"""
        cache_key = "macro_china_shrz"
        cached = _get_cached(cache_key, TTL_WEEKLY)
        if cached:
            return cached
        try:
            import akshare as ak
            df = ak.macro_china_shrzgm()
            if df is None or df.empty:
                return None
            result = []
            for _, row in df.iterrows():
                result.append({
                    "date": str(row.iloc[0]),                       # 月份
                    "value": _safe_float(row.iloc[1]),              # 社会融资规模增量
                    "rmb_loan": _safe_float(row.iloc[2]) if len(row) > 2 else None,  # 人民币贷款
                })
            _set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取社融数据失败: {e}")
            return None

    def get_lpr_data(self) -> Optional[List[Dict]]:
        """获取LPR利率数据（仅返回有效LPR数据，过滤2019年前的NaN）"""
        cache_key = "macro_china_lpr"
        cached = _get_cached(cache_key, TTL_WEEKLY)
        if cached:
            return cached
        try:
            import akshare as ak
            df = ak.macro_china_lpr()
            if df is None or df.empty:
                return None
            # 过滤掉LPR1Y为NaN的行（2019年前无LPR数据）
            df_valid = df[df["LPR1Y"].notna()]
            result = []
            for _, row in df_valid.iterrows():
                result.append({
                    "date": str(row["TRADE_DATE"]),
                    "lpr_1y": _safe_float(row["LPR1Y"]),
                    "lpr_5y": _safe_float(row["LPR5Y"]),
                })
            _set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取LPR数据失败: {e}")
            return None

    def get_us_cpi(self) -> Optional[List[Dict]]:
        """获取美国CPI数据"""
        cache_key = "macro_us_cpi"
        cached = _get_cached(cache_key)
        if cached:
            return cached
        try:
            import akshare as ak
            df = ak.macro_usa_cpi_monthly()
            if df is None or df.empty:
                return None
            result = []
            for _, row in df.iterrows():
                result.append({
                    "date": str(row.iloc[0]),
                    "value": _safe_float(row.iloc[1]),
                })
            result.sort(key=lambda x: x['date'], reverse=True)
            _set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取美国CPI数据失败: {e}")
            return None

    def get_us_unemployment(self) -> Optional[List[Dict]]:
        """获取美国失业率数据"""
        cache_key = "macro_us_unemployment"
        cached = _get_cached(cache_key)
        if cached:
            return cached
        try:
            import akshare as ak
            df = ak.macro_usa_unemployment_rate()
            if df is None or df.empty:
                return None
            result = []
            for _, row in df.iterrows():
                result.append({
                    "date": str(row.iloc[0]),
                    "value": _safe_float(row.iloc[1]),
                })
            result.sort(key=lambda x: x['date'], reverse=True)
            _set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取美国失业率数据失败: {e}")
            return None

    # ==================== 消费拐点指标 ====================

    def get_consumer_confidence(self) -> Optional[List[Dict]]:
        """获取消费者信心指数（总指数/满意指数/预期指数）"""
        cache_key = "macro_china_consumer_confidence"
        cached = _get_cached(cache_key)
        if cached:
            return cached
        try:
            import akshare as ak
            df = ak.macro_china_xfzxx()
            if df is None or df.empty:
                return None
            result = []
            for _, row in df.iterrows():
                result.append({
                    "date": str(row.iloc[0]),
                    "confidence": _safe_float(row.iloc[1]),       # 消费者信心指数
                    "confidence_yoy": _safe_float(row.iloc[2]),   # 同比
                    "satisfaction": _safe_float(row.iloc[4]),     # 满意指数
                    "expectation": _safe_float(row.iloc[7]),      # 预期指数
                })
            _set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取消费者信心指数失败: {e}")
            return None

    def get_ppi_data(self) -> Optional[List[Dict]]:
        """获取PPI数据（工业品出厂价格指数）"""
        cache_key = "macro_china_ppi"
        cached = _get_cached(cache_key)
        if cached:
            return cached
        try:
            import akshare as ak
            df = ak.macro_china_ppi()
            if df is None or df.empty:
                return None
            result = []
            for _, row in df.iterrows():
                result.append({
                    "date": str(row.iloc[0]),
                    "value": _safe_float(row.iloc[1]),       # 当月指数
                    "yoy": _safe_float(row.iloc[2]),         # 同比
                    "cumulative": _safe_float(row.iloc[3]),  # 累计
                })
            _set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取PPI数据失败: {e}")
            return None

    def get_retail_sales(self) -> Optional[List[Dict]]:
        """获取社会消费品零售总额"""
        cache_key = "macro_china_retail_sales"
        cached = _get_cached(cache_key)
        if cached:
            return cached
        try:
            import akshare as ak
            df = ak.macro_china_consumer_goods_retail()
            if df is None or df.empty:
                return None
            result = []
            for _, row in df.iterrows():
                result.append({
                    "date": str(row.iloc[0]),
                    "value": _safe_float(row.iloc[1]),         # 当月值（亿元）
                    "yoy": _safe_float(row.iloc[2]),           # 同比增长
                    "cumulative": _safe_float(row.iloc[4]),    # 累计
                    "cumulative_yoy": _safe_float(row.iloc[5]),  # 累计同比
                })
            _set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取社零数据失败: {e}")
            return None

    def get_housing_price(self) -> Optional[List[Dict]]:
        """获取一线城市新建住宅价格指数（北京/上海）"""
        cache_key = "macro_china_housing_price"
        cached = _get_cached(cache_key)
        if cached:
            return cached
        try:
            import akshare as ak
            df = ak.macro_china_new_house_price()
            if df is None or df.empty:
                return None
            # 按日期聚合一线城市同比均值
            # 同比指数: 100=持平, 101.5=+1.5%, 96.5=-3.5%
            date_groups = {}
            for _, row in df.iterrows():
                date = str(row.iloc[0])
                yoy = _safe_float(row.iloc[2])  # 新建商品住宅价格指数-同比
                if yoy is not None:
                    if date not in date_groups:
                        date_groups[date] = []
                    date_groups[date].append(yoy)

            result = []
            for date in sorted(date_groups.keys(), reverse=True):
                vals = date_groups[date]
                avg_idx = round(sum(vals) / len(vals), 2) if vals else None
                # 转换为百分比变动: 100.7 -> +0.7%, 96.5 -> -3.5%
                avg_pct = round(avg_idx - 100, 2) if avg_idx is not None else None
                result.append({
                    "date": date,
                    "avg_index": avg_idx,          # 原始指数值
                    "avg_yoy": avg_pct,            # 同比变动百分比
                    "cities": len(vals),           # 城市数量
                })
            _set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取房价数据失败: {e}")
            return None

    def get_unemployment_rate(self) -> Optional[List[Dict]]:
        """获取全国城镇调查失业率"""
        cache_key = "macro_china_unemployment"
        cached = _get_cached(cache_key)
        if cached:
            return cached
        try:
            import akshare as ak
            df = ak.macro_china_urban_unemployment()
            if df is None or df.empty:
                return None
            # 筛选"全国城镇调查失业率"
            mask = df['item'].str.contains('全国城镇调查失业率')
            df_filtered = df[mask].copy()
            result = []
            for _, row in df_filtered.iterrows():
                date_str = str(row['date'])
                # 格式化日期: 201801 -> 2018-01
                if len(date_str) == 6:
                    date_str = f"{date_str[:4]}-{date_str[4:]}"
                result.append({
                    "date": date_str,
                    "value": _safe_float(row['value']),
                })
            # 按日期降序排列
            result.sort(key=lambda x: x['date'], reverse=True)
            _set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取失业率数据失败: {e}")
            return None

    # ==================== 美国宏观数据 ====================

    def _fetch_us_macro_generic(self, ak_func_name: str, cache_key: str) -> Optional[List[Dict]]:
        """通用美国宏观数据获取（东方财富经济日历格式：商品/日期/今值/预测值/前值）"""
        cached = _get_cached(cache_key, TTL_WEEKLY)
        if cached:
            return cached
        try:
            import akshare as ak
            func = getattr(ak, ak_func_name)
            df = func()
            if df is None or df.empty:
                return None
            result = []
            for _, row in df.iterrows():
                result.append({
                    "date": str(row.iloc[1]),              # 日期
                    "value": _safe_float(row.iloc[2]),     # 今值
                    "forecast": _safe_float(row.iloc[3]),  # 预测值
                    "previous": _safe_float(row.iloc[4]),  # 前值
                })
            # 按日期降序排列（最新在前）
            result.sort(key=lambda x: x['date'], reverse=True)
            _set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取{ak_func_name}数据失败: {e}")
            return None

    def get_us_gdp(self) -> Optional[List[Dict]]:
        """获取美国GDP数据"""
        return self._fetch_us_macro_generic("macro_usa_gdp_monthly", "macro_us_gdp")

    def get_us_ism_pmi(self) -> Optional[List[Dict]]:
        """获取美国ISM制造业PMI"""
        return self._fetch_us_macro_generic("macro_usa_ism_pmi", "macro_us_ism_pmi")

    def get_us_ism_services_pmi(self) -> Optional[List[Dict]]:
        """获取美国ISM非制造业PMI"""
        return self._fetch_us_macro_generic("macro_usa_ism_non_pmi", "macro_us_ism_services_pmi")

    def get_us_fed_rate(self) -> Optional[List[Dict]]:
        """获取美联储利率决议"""
        return self._fetch_us_macro_generic("macro_bank_usa_interest_rate", "macro_us_fed_rate")

    def get_us_non_farm(self) -> Optional[List[Dict]]:
        """获取美国非农就业数据"""
        return self._fetch_us_macro_generic("macro_usa_non_farm", "macro_us_non_farm")

    def get_us_ppi(self) -> Optional[List[Dict]]:
        """获取美国PPI数据"""
        return self._fetch_us_macro_generic("macro_usa_ppi", "macro_us_ppi")

    def get_us_retail_sales(self) -> Optional[List[Dict]]:
        """获取美国零售销售数据"""
        return self._fetch_us_macro_generic("macro_usa_retail_sales", "macro_us_retail_sales")

    # ==================== 收益率曲线 ====================

    def get_yield_curve(self) -> Optional[Dict]:
        """获取中美收益率曲线（2Y/5Y/10Y/30Y）及2Y-10Y利差"""
        cache_key = "macro_yield_curve"
        cached = _get_cached(cache_key, TTL_DAILY)
        if cached:
            return cached
        try:
            import akshare as ak
            df = ak.bond_zh_us_rate(start_date="20200101")
            if df is None or df.empty:
                return None

            cn_series = []
            us_series = []
            for _, row in df.iterrows():
                date_str = str(row.iloc[0])
                cn_y2 = _safe_float(row.iloc[1])
                cn_y5 = _safe_float(row.iloc[2])
                cn_y10 = _safe_float(row.iloc[3])
                cn_y30 = _safe_float(row.iloc[4])
                cn_spread = _safe_float(row.iloc[5])
                us_y2 = _safe_float(row.iloc[7])
                us_y5 = _safe_float(row.iloc[8])
                us_y10 = _safe_float(row.iloc[9])
                us_y30 = _safe_float(row.iloc[10])
                us_spread = _safe_float(row.iloc[11])

                cn_series.append({
                    "date": date_str,
                    "y2": cn_y2, "y5": cn_y5, "y10": cn_y10, "y30": cn_y30,
                    "spread_10y_2y": cn_spread,
                })
                us_series.append({
                    "date": date_str,
                    "y2": us_y2, "y5": us_y5, "y10": us_y10, "y30": us_y30,
                    "spread_10y_2y": us_spread,
                })

            result = {
                "cn": cn_series,
                "us": us_series,
            }
            _set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取收益率曲线数据失败: {e}")
            return None

    # ==================== 中国补充指标 ====================

    def get_industrial_production(self) -> Optional[List[Dict]]:
        """获取中国规模以上工业增加值年率"""
        return self._fetch_us_macro_generic("macro_china_industrial_production_yoy", "macro_china_industrial_production")

    def get_trade_balance(self) -> Optional[List[Dict]]:
        """获取中国贸易差额（美元计）"""
        return self._fetch_us_macro_generic("macro_china_trade_balance", "macro_china_trade_balance")

    def get_caixin_mfg_pmi(self) -> Optional[List[Dict]]:
        """获取财新制造业PMI（东方财富经济日历格式）"""
        return self._fetch_us_macro_generic("macro_china_cx_pmi_yearly", "macro_china_caixin_mfg_pmi")

    def get_caixin_services_pmi(self) -> Optional[List[Dict]]:
        """获取财新服务业PMI（东方财富经济日历格式）"""
        return self._fetch_us_macro_generic("macro_china_cx_services_pmi_yearly", "macro_china_caixin_services_pmi")

    def get_fx_gold_reserves(self) -> Optional[List[Dict]]:
        """获取中国外汇储备和黄金储备"""
        cache_key = "macro_china_fx_gold"
        cached = _get_cached(cache_key, TTL_WEEKLY)
        if cached:
            return cached
        try:
            import akshare as ak
            df = ak.macro_china_fx_gold()
            if df is None or df.empty:
                return None
            result = []
            for _, row in df.iterrows():
                result.append({
                    "date": str(row.iloc[0]),
                    "gold_reserves": _safe_float(row.iloc[1]),       # 黄金储备(万盎司)
                    "gold_yoy": _safe_float(row.iloc[2]),            # 黄金储备同比
                    "forex_reserves": _safe_float(row.iloc[4]),      # 外汇储备(亿美元)
                    "forex_yoy": _safe_float(row.iloc[5]),           # 外汇储备同比
                })
            result.sort(key=lambda x: x['date'], reverse=True)
            _set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取外储黄金数据失败: {e}")
            return None

    def get_new_financial_credit(self) -> Optional[List[Dict]]:
        """获取新增人民币贷款"""
        cache_key = "macro_china_new_credit"
        cached = _get_cached(cache_key, TTL_WEEKLY)
        if cached:
            return cached
        try:
            import akshare as ak
            df = ak.macro_china_new_financial_credit()
            if df is None or df.empty:
                return None
            result = []
            for _, row in df.iterrows():
                result.append({
                    "date": str(row.iloc[0]),
                    "value": _safe_float(row.iloc[1]),         # 当月新增(亿)
                    "yoy": _safe_float(row.iloc[2]),           # 同比增长
                    "mom": _safe_float(row.iloc[3]),           # 环比增长
                    "cumulative": _safe_float(row.iloc[4]),    # 累计
                    "cumulative_yoy": _safe_float(row.iloc[5]),  # 累计同比
                })
            result.sort(key=lambda x: x['date'], reverse=True)
            _set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取新增信贷数据失败: {e}")
            return None

    # ==================== 期货数据 ====================

    # 关键商品配置：中文名 → (英文代码, 单位)
    COMMODITY_MAP = [
        {"cn_name": "黄金", "symbol": "AU0", "name": "沪金", "unit": "元/克"},
        {"cn_name": "白银", "symbol": "AG0", "name": "沪银", "unit": "元/千克"},
        {"cn_name": "沪铜", "symbol": "CU0", "name": "沪铜", "unit": "元/吨"},
        {"cn_name": "沪铝", "symbol": "AL0", "name": "沪铝", "unit": "元/吨"},
        {"cn_name": "沪锌", "symbol": "ZN0", "name": "沪锌", "unit": "元/吨"},
        {"cn_name": "螺纹钢", "symbol": "RB0", "name": "螺纹钢", "unit": "元/吨"},
        {"cn_name": "铁矿石", "symbol": "I0", "name": "铁矿石", "unit": "元/吨"},
        {"cn_name": "原油", "symbol": "SC0", "name": "原油", "unit": "元/桶"},
    ]

    def get_commodity_snapshot(self) -> List[Dict]:
        """获取关键商品快照（逐个品种调用API取连续合约）"""
        cache_key = "commodity_snapshot"
        cached = _get_cached(cache_key)
        if cached:
            return cached

        result = []
        import akshare as ak
        for comm in self.COMMODITY_MAP:
            try:
                df = ak.futures_zh_realtime(symbol=comm["cn_name"])
                if df is not None and not df.empty:
                    # 找连续合约（symbol以0结尾，如AU0）
                    continuous = df[df["symbol"].str.endswith("0")]
                    if continuous.empty:
                        continuous = df.head(1)
                    row = continuous.iloc[0]
                    result.append({
                        "symbol": comm["symbol"],
                        "name": comm["name"],
                        "unit": comm["unit"],
                        "price": _safe_float(row.get("trade")),
                        "change_pct": _safe_float(row.get("changepercent")),
                        "volume": _safe_float(row.get("volume")),
                        "open_interest": _safe_float(row.get("position")),
                    })
                else:
                    result.append({"symbol": comm["symbol"], "name": comm["name"], "unit": comm["unit"]})
            except Exception as e:
                logger.warning(f"获取{comm['name']}行情失败: {e}")
                result.append({"symbol": comm["symbol"], "name": comm["name"], "unit": comm["unit"]})

        _set_cache(cache_key, result)
        return result

    def get_futures_list(self) -> Optional[List[Dict]]:
        """获取期货实时行情（通过品种列表批量获取）"""
        cache_key = "futures_list"
        cached = _get_cached(cache_key)
        if cached:
            return cached
        try:
            import akshare as ak
            # 获取品种列表
            symbols_df = ak.futures_symbol_mark()
            result = []
            # 只取前20个主要品种，避免请求过多
            main_symbols = ['黄金', '白银', '沪铜', '沪铝', '沪锌', '螺纹钢', '铁矿石', '原油',
                            'PTA', '甲醇', '豆粕', '棕榈油', '白糖', '棉花', '橡胶', '沥青',
                            '燃料油', '液化石油气', '纯碱', '玻璃']
            for sym_name in main_symbols:
                try:
                    df = ak.futures_zh_realtime(symbol=sym_name)
                    if df is not None and not df.empty:
                        continuous = df[df["symbol"].str.endswith("0")]
                        if continuous.empty:
                            continuous = df.head(1)
                        row = continuous.iloc[0]
                        result.append({
                            "symbol": str(row.get("symbol", "")),
                            "name": str(row.get("name", sym_name)),
                            "price": _safe_float(row.get("trade")),
                            "change_pct": _safe_float(row.get("changepercent")),
                            "volume": _safe_float(row.get("volume")),
                            "open_interest": _safe_float(row.get("position")),
                            "exchange": str(row.get("exchange", "")),
                        })
                except Exception:
                    pass
            _set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取期货行情失败: {e}")
            return None

    def get_futures_hist(self, symbol: str = "AU0") -> Optional[List[Dict]]:
        """获取期货历史行情"""
        cache_key = f"futures_hist_{symbol}"
        cached = _get_cached(cache_key)
        if cached:
            return cached
        try:
            import akshare as ak
            df = ak.futures_main_sina(symbol=symbol)
            if df is None or df.empty:
                return None
            result = []
            for _, row in df.iterrows():
                result.append({
                    "date": str(row.iloc[0]),
                    "open": _safe_float(row.iloc[1]),
                    "high": _safe_float(row.iloc[2]),
                    "low": _safe_float(row.iloc[3]),
                    "close": _safe_float(row.iloc[4]),
                    "volume": _safe_float(row.iloc[5]) if len(row) > 5 else None,
                })
            _set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取期货历史数据失败 {symbol}: {e}")
            return None

    # ==================== 行业数据 ====================

    def get_industry_rank(self) -> Optional[List[Dict]]:
        """获取行业板块排名（同花顺）"""
        cache_key = "industry_rank"
        cached = _get_cached(cache_key, TTL_DAILY)
        if cached:
            return cached
        try:
            import akshare as ak
            df = ak.stock_board_industry_summary_ths()
            if df is None or df.empty:
                return None
            result = []
            for _, row in df.iterrows():
                result.append({
                    "rank": _safe_float(row.iloc[0]),
                    "name": str(row.iloc[1]),
                    "change_pct": _safe_float(row.iloc[2]),
                    "amount": _safe_float(row.iloc[3]),
                    "volume": _safe_float(row.iloc[4]),
                    "turnover": _safe_float(row.iloc[5]),
                    "up_count": _safe_float(row.iloc[6]),
                    "down_count": _safe_float(row.iloc[7]),
                    "leader": str(row.iloc[8]) if len(row) > 8 else "",
                    "leader_price": _safe_float(row.iloc[9]) if len(row) > 9 else None,
                    "leader_change": _safe_float(row.iloc[10]) if len(row) > 10 else None,
                })
            _set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取行业排名失败: {e}")
            return None

    def get_sector_fund_flow(self) -> Optional[List[Dict]]:
        """获取行业资金流向"""
        cache_key = "sector_fund_flow"
        cached = _get_cached(cache_key, TTL_DAILY)
        if cached:
            return cached
        try:
            import akshare as ak
            df = ak.stock_sector_fund_flow_rank(indicator="今日")
            if df is None or df.empty:
                return None
            result = []
            for _, row in df.iterrows():
                result.append({
                    "name": str(row.iloc[1]) if len(row) > 1 else "",
                    "change_pct": _safe_float(row.iloc[2]) if len(row) > 2 else None,
                    "main_net_inflow": _safe_float(row.iloc[3]) if len(row) > 3 else None,
                    "main_net_pct": _safe_float(row.iloc[4]) if len(row) > 4 else None,
                })
            _set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取行业资金流向失败: {e}")
            return None

    def get_north_flow(self) -> Optional[List[Dict]]:
        """获取北向资金数据"""
        cache_key = "north_flow"
        cached = _get_cached(cache_key, TTL_DAILY)
        if cached:
            return cached
        try:
            import akshare as ak
            df = ak.stock_hsgt_fund_flow_summary_em()
            if df is None or df.empty:
                return None
            # 筛选北向数据
            df_north = df[df["资金方向"] == "北向"]
            result = []
            for _, row in df_north.iterrows():
                result.append({
                    "date": str(row.get("交易日", "")),
                    "type": str(row.get("板块", "")),
                    "net_buy": _safe_float(row.get("成交净买额")),
                    "net_flow": _safe_float(row.get("资金净流入")),
                    "balance": _safe_float(row.get("当日资金余额")),
                })
            _set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取北向资金数据失败: {e}")
            return None

    # ==================== 期货洞察（新增） ====================

    # 全球商品分类配置
    GLOBAL_COMMODITY_CATEGORIES = {
        "贵金属": {
            "items": [
                {"symbol": "AU0", "name": "沪金", "unit": "元/克", "exchange": "SHFE"},
                {"symbol": "AG0", "name": "沪银", "unit": "元/千克", "exchange": "SHFE"},
            ],
            "driver": "受美元走势、通胀预期和避险情绪驱动",
            "color": "#FFD700",
        },
        "基本金属": {
            "items": [
                {"symbol": "CU0", "name": "沪铜", "unit": "元/吨", "exchange": "SHFE"},
                {"symbol": "AL0", "name": "沪铝", "unit": "元/吨", "exchange": "SHFE"},
                {"symbol": "ZN0", "name": "沪锌", "unit": "元/吨", "exchange": "SHFE"},
                {"symbol": "NI0", "name": "沪镍", "unit": "元/吨", "exchange": "SHFE"},
            ],
            "driver": "经济晴雨表，铜被称为'铜博士'，反映制造业景气度",
            "color": "#B87333",
        },
        "黑色系": {
            "items": [
                {"symbol": "RB0", "name": "螺纹钢", "unit": "元/吨", "exchange": "SHFE"},
                {"symbol": "HC0", "name": "热卷", "unit": "元/吨", "exchange": "SHFE"},
                {"symbol": "I0", "name": "铁矿石", "unit": "元/吨", "exchange": "DCE"},
                {"symbol": "J0", "name": "焦炭", "unit": "元/吨", "exchange": "DCE"},
                {"symbol": "JM0", "name": "焦煤", "unit": "元/吨", "exchange": "DCE"},
            ],
            "driver": "受房地产基建投资、钢厂开工率、环保限产政策影响",
            "color": "#4A4A4A",
        },
        "能源化工": {
            "items": [
                {"symbol": "SC0", "name": "原油", "unit": "元/桶", "exchange": "INE"},
                {"symbol": "FU0", "name": "燃料油", "unit": "元/吨", "exchange": "SHFE"},
                {"symbol": "MA0", "name": "甲醇", "unit": "元/吨", "exchange": "CZCE"},
                {"symbol": "TA0", "name": "PTA", "unit": "元/吨", "exchange": "CZCE"},
                {"symbol": "PP0", "name": "聚丙烯", "unit": "元/吨", "exchange": "DCE"},
            ],
            "driver": "受OPEC产量决策、地缘政治、全球经济增长预期影响",
            "color": "#1E90FF",
        },
        "农产品": {
            "items": [
                {"symbol": "M0", "name": "豆粕", "unit": "元/吨", "exchange": "DCE"},
                {"symbol": "Y0", "name": "豆油", "unit": "元/吨", "exchange": "DCE"},
                {"symbol": "P0", "name": "棕榈油", "unit": "元/吨", "exchange": "DCE"},
                {"symbol": "CF0", "name": "棉花", "unit": "元/吨", "exchange": "CZCE"},
                {"symbol": "SR0", "name": "白糖", "unit": "元/吨", "exchange": "CZCE"},
                {"symbol": "AP0", "name": "苹果", "unit": "元/吨", "exchange": "CZCE"},
            ],
            "driver": "受天气、种植面积、消费季节性、进出口政策影响",
            "color": "#32CD32",
        },
    }

    def get_global_commodities(self) -> Optional[Dict]:
        """获取全球商品分类数据（按类别分组）"""
        cache_key = "futures_global_commodities"
        cached = _get_cached(cache_key)
        if cached:
            return cached
        try:
            import akshare as ak
            categories = {}
            for cat_name, cat_info in self.GLOBAL_COMMODITY_CATEGORIES.items():
                items = []
                for item in cat_info["items"]:
                    try:
                        df = ak.futures_zh_realtime(symbol=item["name"])
                        if df is not None and not df.empty:
                            continuous = df[df["symbol"].str.endswith("0")]
                            if continuous.empty:
                                continuous = df.head(1)
                            row = continuous.iloc[0]
                            price = _safe_float(row.get("trade"))
                            change_pct = _safe_float(row.get("changepercent"))
                            items.append({
                                "symbol": item["symbol"],
                                "name": item["name"],
                                "unit": item["unit"],
                                "exchange": item["exchange"],
                                "price": price,
                                "change_pct": change_pct,
                                "volume": _safe_float(row.get("volume")),
                                "open_interest": _safe_float(row.get("position")),
                            })
                    except Exception as e:
                        logger.warning(f"获取{item['name']}行情失败: {e}")
                        items.append({
                            "symbol": item["symbol"],
                            "name": item["name"],
                            "unit": item["unit"],
                            "exchange": item["exchange"],
                        })
                categories[cat_name] = {
                    "items": items,
                    "driver": cat_info["driver"],
                    "color": cat_info["color"],
                }
            _set_cache(cache_key, categories)
            return categories
        except Exception as e:
            logger.warning(f"获取全球商品数据失败: {e}")
            return None

    def get_cot_ranking(self, vars_list: List[str] = None, date: str = None) -> Optional[List[Dict]]:
        """获取COT持仓排名数据（多空对比）

        COT (Commitments of Traders) 是期货交易所发布的持仓报告。
        返回每个品种的前5/10/20名多空持仓及变化。
        """
        if vars_list is None:
            vars_list = ['AU', 'AG', 'CU', 'AL', 'RB', 'I', 'SC', 'M', 'Y', 'CF']
        if date is None:
            from datetime import datetime, timedelta
            date = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
        cache_key = f"futures_cot_ranking_{date}_{','.join(vars_list)}"
        cached = _get_cached(cache_key, TTL_DAILY)
        if cached:
            return cached
        try:
            import akshare as ak
            df = ak.get_rank_sum(date=date, vars_list=vars_list)
            if df is None or df.empty:
                return None
            # 取每个品种的汇总行（variety列等于品种代码）
            result = []
            for _, row in df.iterrows():
                symbol = str(row.get('symbol', ''))
                variety = str(row.get('variety', ''))
                # 只取汇总行（symbol == variety 或 symbol长度<=3）
                if symbol != variety and len(symbol) > 3:
                    continue
                entry = {
                    "symbol": symbol,
                    "variety": variety,
                    "date": str(row.get('date', '')),
                    # Top5
                    "long_oi_top5": _safe_float(row.get('long_open_interest_top5')),
                    "short_oi_top5": _safe_float(row.get('short_open_interest_top5')),
                    "long_oi_chg_top5": _safe_float(row.get('long_open_interest_chg_top5')),
                    "short_oi_chg_top5": _safe_float(row.get('short_open_interest_chg_top5')),
                    "vol_top5": _safe_float(row.get('vol_top5')),
                    # Top10
                    "long_oi_top10": _safe_float(row.get('long_open_interest_top10')),
                    "short_oi_top10": _safe_float(row.get('short_open_interest_top10')),
                    "long_oi_chg_top10": _safe_float(row.get('long_open_interest_chg_top10')),
                    "short_oi_chg_top10": _safe_float(row.get('short_open_interest_chg_top10')),
                    # Top20
                    "long_oi_top20": _safe_float(row.get('long_open_interest_top20')),
                    "short_oi_top20": _safe_float(row.get('short_open_interest_top20')),
                    "long_oi_chg_top20": _safe_float(row.get('long_open_interest_chg_top20')),
                    "short_oi_chg_top20": _safe_float(row.get('short_open_interest_chg_top20')),
                }
                # 计算净持仓
                if entry["long_oi_top20"] is not None and entry["short_oi_top20"] is not None:
                    entry["net_oi_top20"] = entry["long_oi_top20"] - entry["short_oi_top20"]
                    entry["net_oi_chg_top20"] = (entry["long_oi_chg_top20"] or 0) - (entry["short_oi_chg_top20"] or 0)
                result.append(entry)
            _set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取COT持仓数据失败: {e}")
            return None

    def get_basis_data(self, vars_list: List[str] = None) -> Optional[List[Dict]]:
        """获取基差分析数据（现货vs期货）

        基差 = 期货价格 - 现货价格
        正值为升水（Contango），负值为贴水（Backwardation）
        """
        if vars_list is None:
            vars_list = ['AU', 'CU', 'RB', 'I', 'SC', 'M', 'AL', 'ZN']
        cache_key = f"futures_basis_{','.join(vars_list)}"
        cached = _get_cached(cache_key, TTL_DAILY)
        if cached:
            return cached
        try:
            import akshare as ak
            df = ak.futures_spot_price(date=None, vars_list=vars_list)
            if df is None or df.empty:
                return None
            result = []
            for _, row in df.iterrows():
                spot = _safe_float(row.get('spot_price'))
                near_price = _safe_float(row.get('near_contract_price'))
                dom_price = _safe_float(row.get('dominant_contract_price'))
                near_basis = _safe_float(row.get('near_basis'))
                dom_basis = _safe_float(row.get('dom_basis'))
                near_basis_rate = _safe_float(row.get('near_basis_rate'))
                dom_basis_rate = _safe_float(row.get('dom_basis_rate'))
                # 判断升贴水状态
                state = "flat"
                if dom_basis is not None:
                    if dom_basis > 0:
                        state = "contango"  # 升水
                    elif dom_basis < 0:
                        state = "backwardation"  # 贴水
                result.append({
                    "symbol": str(row.get('symbol', '')),
                    "date": str(row.get('date', '')),
                    "spot_price": spot,
                    "near_contract": str(row.get('near_contract', '')),
                    "near_contract_price": near_price,
                    "dominant_contract": str(row.get('dominant_contract', '')),
                    "dominant_contract_price": dom_price,
                    "near_month": str(row.get('near_month', '')),
                    "dominant_month": str(row.get('dominant_month', '')),
                    "near_basis": near_basis,
                    "dom_basis": dom_basis,
                    "near_basis_rate": near_basis_rate,
                    "dom_basis_rate": dom_basis_rate,
                    "state": state,
                    "state_label": "升水(Contango)" if state == "contango" else ("贴水(Backwardation)" if state == "backwardation" else "平水"),
                })
            _set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取基差数据失败: {e}")
            return None

    def get_roll_yield(self, var: str = 'AU', start_day: str = None, end_day: str = None) -> Optional[List[Dict]]:
        """获取展期收益率数据

        展期收益率：持有近月合约到期后换仓到远月的年化收益/损失。
        正值表示持有近月换远月可获利（Backwardation有利于多头）。
        """
        if end_day is None:
            from datetime import datetime
            end_day = datetime.now().strftime('%Y%m%d')
        if start_day is None:
            from datetime import datetime, timedelta
            start_day = (datetime.now() - timedelta(days=60)).strftime('%Y%m%d')
        cache_key = f"futures_roll_yield_{var}_{start_day}_{end_day}"
        cached = _get_cached(cache_key, TTL_DAILY)
        if cached:
            return cached
        try:
            import akshare as ak
            df = ak.get_roll_yield_bar(type_method='date', var=var, start_day=start_day, end_day=end_day)
            if df is None or df.empty:
                return None
            result = []
            for _, row in df.iterrows():
                result.append({
                    "roll_yield": _safe_float(row.get('roll_yield')),
                    "near_by": str(row.get('near_by', '')),
                    "deferred": str(row.get('deferred', '')),
                })
            _set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取展期收益率失败 {var}: {e}")
            return None

    def get_inventory_data(self, symbols: List[str] = None) -> Optional[Dict]:
        """获取商品库存数据

        库存变化是判断供需关系的重要指标。
        库存下降 + 贴水结构 → 供应紧张。
        """
        # 期货品种中文名到英文代码的映射
        INVENTORY_SYMBOL_MAP = {
            'CU': '铜', 'AL': '铝', 'ZN': '锌', 'NI': '镍', 'PB': '铅',
            'AU': '黄金', 'AG': '白银', 'RB': '螺纹钢', 'HC': '热卷',
            'I': '铁矿石', 'J': '焦炭', 'JM': '焦煤', 'SC': '原油',
            'M': '豆粕', 'Y': '豆油', 'P': '棕榈油', 'CF': '棉花',
            'SR': '白糖', 'TA': 'PTA', 'MA': '甲醇', 'PP': '聚丙烯',
        }
        if symbols is None:
            symbols = ['CU', 'AL', 'RB', 'I', 'AU']
        cache_key = f"futures_inventory_{','.join(symbols)}"
        cached = _get_cached(cache_key, TTL_DAILY)
        if cached:
            return cached
        try:
            import akshare as ak
            result = {}
            for sym in symbols:
                cn_name = INVENTORY_SYMBOL_MAP.get(sym, sym)
                try:
                    df = ak.futures_inventory_em(symbol=cn_name)
                    if df is not None and not df.empty:
                        # 取最近30条数据
                        df = df.tail(30)
                        history = []
                        for _, row in df.iterrows():
                            history.append({
                                "date": str(row.iloc[0]) if len(row) > 0 else "",
                                "inventory": _safe_float(row.iloc[1]) if len(row) > 1 else None,
                                "change": _safe_float(row.iloc[2]) if len(row) > 2 else None,
                            })
                        latest = history[-1] if history else {}
                        result[sym] = {
                            "symbol": sym,
                            "name": cn_name,
                            "latest_inventory": latest.get("inventory"),
                            "latest_change": latest.get("change"),
                            "latest_date": latest.get("date"),
                            "history": history,
                        }
                except Exception as e:
                    logger.warning(f"获取{cn_name}库存数据失败: {e}")
            if result:
                _set_cache(cache_key, result)
            return result if result else None
        except Exception as e:
            logger.warning(f"获取库存数据失败: {e}")
            return None

    def get_commodity_indices(self) -> Optional[List[Dict]]:
        """获取中证商品期货指数数据

        中证商品期货指数跟踪国内一篮子商品期货的表现，
        是衡量商品市场整体走势的重要基准。
        """
        cache_key = "futures_commodity_indices"
        cached = _get_cached(cache_key, TTL_DAILY)
        if cached:
            return cached
        try:
            import akshare as ak
            result = []
            for idx_name in ['中证商品期货指数', '中证商品期货价格指数']:
                try:
                    df = ak.futures_index_ccidx(symbol=idx_name)
                    if df is not None and not df.empty:
                        # 取最近250个交易日
                        df = df.tail(250)
                        history = []
                        for _, row in df.iterrows():
                            create_time = row.get('createTime')
                            date_str = ""
                            if isinstance(create_time, dict):
                                d = create_time.get('date', {})
                                date_str = f"{d.get('year','')}-{d.get('month',''):02d}-{d.get('day',''):02d}"
                            else:
                                date_str = str(create_time)
                            history.append({
                                "date": date_str,
                                "close": _safe_float(row.get('closingPriceNorm')),
                                "change_pct": _safe_float(row.get('dailyIncreaseAndDecreasePercentageClose')),
                                "ytd_return": _safe_float(row.get('yearToDateChangePercentage')),
                                "1m_return": _safe_float(row.get('oneMonthChangePercentage')),
                                "3m_return": _safe_float(row.get('threeMonthChangePercentage')),
                                "1y_return": _safe_float(row.get('oneYearAnnualizedReturnPercentage')),
                            })
                        latest = history[-1] if history else {}
                        result.append({
                            "name": idx_name,
                            "latest_close": latest.get("close"),
                            "latest_change_pct": latest.get("change_pct"),
                            "ytd_return": latest.get("ytd_return"),
                            "1y_return": latest.get("1y_return"),
                            "history": history,
                        })
                except Exception as e:
                    logger.warning(f"获取{idx_name}指数失败: {e}")
            _set_cache(cache_key, result)
            return result if result else None
        except Exception as e:
            logger.warning(f"获取商品指数失败: {e}")
            return None

    def get_institutional_allocation(self) -> Dict:
        """获取机构配置参考模型（静态数据）

        基于桥水、Citadel等顶级机构和CTA基金的公开配置比例。
        这是参考数据，实际配置因策略而异。
        """
        return {
            "title": "顶级机构期货配置参考",
            "description": "基于桥水全天候策略、CTA基金公开数据整理",
            "categories": [
                {
                    "name": "贵金属",
                    "allocation": "15-25%",
                    "reason": "抗通胀、避险、与股债低相关",
                    "examples": "黄金、白银",
                    "icon": "🥇",
                },
                {
                    "name": "能源",
                    "allocation": "20-30%",
                    "reason": "全球经济增长核心驱动，地缘政治溢价",
                    "examples": "原油、天然气、燃料油",
                    "icon": "⛽",
                },
                {
                    "name": "基本金属",
                    "allocation": "10-15%",
                    "reason": "经济晴雨表，新能源转型受益",
                    "examples": "铜、铝、锌、镍",
                    "icon": "🔶",
                },
                {
                    "name": "黑色系",
                    "allocation": "10-15%",
                    "reason": "中国基建/房地产周期，政策敏感",
                    "examples": "螺纹钢、铁矿石、焦炭",
                    "icon": "🏗️",
                },
                {
                    "name": "农产品",
                    "allocation": "5-10%",
                    "reason": "通胀对冲，天气/季节性驱动",
                    "examples": "豆粕、棕榈油、棉花",
                    "icon": "🌾",
                },
                {
                    "name": "股指期货",
                    "allocation": "15-25%",
                    "reason": "股票Beta暴露，对冲工具",
                    "examples": "沪深300、中证500股指期货",
                    "icon": "📈",
                },
                {
                    "name": "国债期货",
                    "allocation": "10-15%",
                    "reason": "利率风险管理，久期配置",
                    "examples": "10年期、5年期国债期货",
                    "icon": "📊",
                },
            ],
            "strategies": [
                {
                    "name": "趋势跟踪（CTA）",
                    "description": "约60%的CTA收益来自趋势跟踪。通过移动平均线、突破等信号捕捉中长期趋势。",
                    "allocation": "30-50%",
                },
                {
                    "name": "套利策略",
                    "description": "期现套利、跨期套利、跨品种套利。风险较低，收益稳定。",
                    "allocation": "20-30%",
                },
                {
                    "name": "宏观配置",
                    "description": "基于宏观经济判断进行大类商品配置。桥水全天候策略的核心。",
                    "allocation": "20-40%",
                },
            ],
        }

    # ==================== 期限结构与套利分析 ====================

    # 品种代码到中文名映射
    SYMBOL_TO_CN_MAP = {
        'AU': '黄金', 'AG': '白银', 'CU': '沪铜', 'AL': '沪铝', 'ZN': '沪锌',
        'NI': '沪镍', 'PB': '沪铅', 'RB': '螺纹钢', 'HC': '热卷',
        'I': '铁矿石', 'J': '焦炭', 'JM': '焦煤', 'SC': '原油',
        'FU': '燃料油', 'BU': '沥青', 'RU': '橡胶', 'SP': '纸浆',
        'SS': '不锈钢', 'LU': '液化石油气', 'SA': '纯碱', 'FG': '玻璃',
        'M': '豆粕', 'Y': '豆油', 'P': '棕榈油', 'CF': '棉花',
        'SR': '白糖', 'TA': 'PTA', 'MA': '甲醇', 'PP': '聚丙烯',
    }

    # 金融期货配置
    FINANCIAL_FUTURES_CATEGORIES = {
        "股指期货": {
            "items": [
                {"symbol": "IF0", "name": "沪深300", "unit": "点", "exchange": "CFFEX", "cn_name": "沪深300"},
                {"symbol": "IC0", "name": "中证500", "unit": "点", "exchange": "CFFEX", "cn_name": "中证500"},
                {"symbol": "IH0", "name": "上证50", "unit": "点", "exchange": "CFFEX", "cn_name": "上证50"},
                {"symbol": "IM0", "name": "中证1000", "unit": "点", "exchange": "CFFEX", "cn_name": "中证1000"},
            ],
            "driver": "与对应指数高度相关，可用于对冲或杠杆化暴露。基差反映市场情绪：升水看多、贴水看空。",
            "color": "#FF6347",
        },
        "国债期货": {
            "items": [
                {"symbol": "T0", "name": "十年国债", "unit": "元", "exchange": "CFFEX", "cn_name": "十年期国债"},
                {"symbol": "TF0", "name": "五年国债", "unit": "元", "exchange": "CFFEX", "cn_name": "五年期国债"},
                {"symbol": "TS0", "name": "二年国债", "unit": "元", "exchange": "CFFEX", "cn_name": "二年期国债"},
            ],
            "driver": "利率下行时价格上涨，久期越长弹性越大。可用于利率风险管理。",
            "color": "#9370DB",
        },
    }

    def get_financial_futures_snapshot(self) -> Dict:
        """获取金融期货快照（股指期货+国债期货）

        返回股指期货(IF/IC/IH/IM)和国债期货(T/TF/TS)的实时行情数据。
        """
        cache_key = "financial_futures_snapshot"
        cached = _get_cached(cache_key)
        if cached:
            return cached
        try:
            import akshare as ak
            categories = {}
            for cat_name, cat_info in self.FINANCIAL_FUTURES_CATEGORIES.items():
                items = []
                for item in cat_info["items"]:
                    try:
                        df = ak.futures_zh_realtime(symbol=item["cn_name"])
                        if df is not None and not df.empty:
                            continuous = df[df["symbol"].str.endswith("0")]
                            if continuous.empty:
                                continuous = df.head(1)
                            row = continuous.iloc[0]
                            items.append({
                                "symbol": item["symbol"],
                                "name": item["name"],
                                "unit": item["unit"],
                                "exchange": item["exchange"],
                                "price": _safe_float(row.get("trade")),
                                "change_pct": _safe_float(row.get("changepercent")),
                                "volume": _safe_float(row.get("volume")),
                                "open_interest": _safe_float(row.get("position")),
                            })
                        else:
                            items.append({
                                "symbol": item["symbol"], "name": item["name"],
                                "unit": item["unit"], "exchange": item["exchange"],
                            })
                    except Exception as e:
                        logger.warning(f"获取{item['name']}行情失败: {e}")
                        items.append({
                            "symbol": item["symbol"], "name": item["name"],
                            "unit": item["unit"], "exchange": item["exchange"],
                        })
                categories[cat_name] = {
                    "items": items,
                    "driver": cat_info["driver"],
                    "color": cat_info["color"],
                }
            _set_cache(cache_key, categories)
            return categories
        except Exception as e:
            logger.warning(f"获取金融期货数据失败: {e}")
            return {}

    def get_term_structure(self, var: str = 'AU') -> Optional[Dict]:
        """获取期限结构数据（近月到远月价格曲线）

        从同一品种不同到期月份合约的价格构建期限结构曲线。
        - 升水(Contango): 远月>近月，通常表示供应充足
        - 贴水(Backwardation): 近月>远月，通常表示供应紧张

        返回:
            contracts: 各月份合约价格列表
            spread: 近月-远月价差
            annualized_spread: 年化价差百分比
            structure: contango/backwardation/flat
        """
        cn_name = self.SYMBOL_TO_CN_MAP.get(var.upper(), var)
        cache_key = f"futures_term_structure_{var}"
        cached = _get_cached(cache_key)
        if cached:
            return cached
        try:
            import akshare as ak
            df = ak.futures_zh_realtime(symbol=cn_name)
            if df is None or df.empty:
                return None
            # Filter for non-continuous contracts (symbol not ending in "0")
            contracts = []
            for _, row in df.iterrows():
                sym = str(row.get("symbol", ""))
                price = _safe_float(row.get("trade"))
                if price is not None and not sym.endswith("0"):
                    # Extract delivery month from symbol: XXYYMM
                    code_len = len(var)
                    delivery = sym[code_len:] if len(sym) > code_len else ""
                    if delivery:  # Only include if we can parse delivery month
                        contracts.append({
                            "symbol": sym,
                            "delivery_month": delivery,
                            "price": price,
                            "open_interest": _safe_float(row.get("position")),
                            "volume": _safe_float(row.get("volume")),
                            "change_pct": _safe_float(row.get("changepercent")),
                        })
            # Sort by delivery month
            contracts.sort(key=lambda x: x["delivery_month"])
            # Take first 6 contracts to avoid noise
            contracts = contracts[:6]
            # Calculate term structure metrics
            if len(contracts) >= 2:
                near = contracts[0]
                far = contracts[-1]
                spread = near["price"] - far["price"]
                months_diff = max(1, len(contracts) - 1)
                annualized_spread = (spread / far["price"]) * (12 / months_diff) * 100 if far["price"] else 0
                structure = "backwardation" if spread > 0 else "contango" if spread < 0 else "flat"
            else:
                spread = 0
                annualized_spread = 0
                structure = "flat"
            result = {
                "var": var,
                "cn_name": cn_name,
                "contracts": contracts,
                "near_price": contracts[0]["price"] if contracts else None,
                "far_price": contracts[-1]["price"] if contracts else None,
                "spread": round(spread, 2) if contracts else 0,
                "annualized_spread": round(annualized_spread, 4),
                "structure": structure,
                "structure_label": "贴水(Backwardation)" if structure == "backwardation"
                    else "升水(Contango)" if structure == "contango" else "平水",
                "contract_count": len(contracts),
            }
            _set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取期限结构失败 {var}: {e}")
            return None

    def get_spread_signals(self) -> List[Dict]:
        """获取跨期套利信号检测

        检测以下信号:
        1. 极端价差: 年化价差超过阈值的品种
        2. 换月压力: 近月持仓量远高于远月
        3. 结构异常: 与常见结构不同的异常状态
        """
        cache_key = "futures_spread_signals"
        cached = _get_cached(cache_key)
        if cached:
            return cached
        try:
            signals = []
            check_vars = ['AU', 'CU', 'RB', 'I', 'SC', 'M', 'AL', 'ZN', 'AG', 'HC', 'TA', 'MA', 'PP', 'SA']
            for var in check_vars:
                try:
                    ts = self.get_term_structure(var)
                    if not ts or not ts.get("contracts") or len(ts["contracts"]) < 2:
                        continue
                    contracts = ts["contracts"]
                    near = contracts[0]
                    far = contracts[-1]
                    spread_pct = ((near["price"] - far["price"]) / far["price"] * 100) if far["price"] else 0
                    # Signal 1: extreme spread (> 5% annualized)
                    if abs(ts.get("annualized_spread", 0)) > 5:
                        signals.append({
                            "var": var,
                            "cn_name": ts.get("cn_name", var),
                            "type": "inter_delivery",
                            "signal": "backwardation_spread" if ts["spread"] > 0 else "contango_spread",
                            "signal_label": f"{'贴水' if ts['spread'] > 0 else '升水'}套利机会",
                            "near_month": near["delivery_month"],
                            "far_month": far["delivery_month"],
                            "near_price": near["price"],
                            "far_price": far["price"],
                            "spread": ts["spread"],
                            "spread_pct": round(spread_pct, 2),
                            "annualized_spread": ts["annualized_spread"],
                            "strength": "strong" if abs(ts["annualized_spread"]) > 10 else "moderate",
                            "description": f"{near['delivery_month']}vs{far['delivery_month']}年化价差{ts['annualized_spread']:.1f}%",
                        })
                    # Signal 2: OI concentration (rollover pressure)
                    if near.get("open_interest") and far.get("open_interest") and far["open_interest"] > 0:
                        oi_ratio = near["open_interest"] / far["open_interest"]
                        if oi_ratio > 3:
                            signals.append({
                                "var": var,
                                "cn_name": ts.get("cn_name", var),
                                "type": "oi_concentration",
                                "signal": "rollover_pressure",
                                "signal_label": "换月压力信号",
                                "near_month": near["delivery_month"],
                                "near_oi": near["open_interest"],
                                "far_oi": far["open_interest"],
                                "oi_ratio": round(oi_ratio, 1),
                                "description": f"近月持仓量是远月的{oi_ratio:.1f}倍，注意换月风险",
                            })
                    # Signal 3: cross-month spread between adjacent contracts
                    if len(contracts) >= 3:
                        mid = contracts[len(contracts) // 2]
                        near_mid_spread = near["price"] - mid["price"]
                        mid_far_spread = mid["price"] - far["price"]
                        # Butterfly spread: near - 2*mid + far
                        butterfly = near["price"] - 2 * mid["price"] + far["price"]
                        if abs(butterfly) / far["price"] > 0.01:  # > 1% butterfly
                            signals.append({
                                "var": var,
                                "cn_name": ts.get("cn_name", var),
                                "type": "butterfly",
                                "signal": "butterfly_spread",
                                "signal_label": "蝶式套利机会",
                                "near_month": near["delivery_month"],
                                "mid_month": mid["delivery_month"],
                                "far_month": far["delivery_month"],
                                "butterfly": round(butterfly, 2),
                                "description": f"蝶式价差异常: {near['delivery_month']}-{mid['delivery_month']}-{far['delivery_month']}",
                            })
                except Exception:
                    pass
            _set_cache(cache_key, signals)
            return signals
        except Exception as e:
            logger.warning(f"获取套利信号失败: {e}")
            return []

    def get_oi_price_analysis(self, vars_list: List[str] = None) -> List[Dict]:
        """获取持仓量-价格分析

        分析主力合约的持仓量和价格关系:
        - 价格上涨+持仓量增加: 多方入场，看涨
        - 价格下跌+持仓量增加: 空方入场，看跌
        - 价格上涨+持仓量减少: 空头平仓反弹，弱
        - 价格下跌+持仓量减少: 多头平仓下跌，弱
        """
        if vars_list is None:
            vars_list = ['AU', 'CU', 'RB', 'I', 'SC', 'M', 'AL', 'ZN', 'AG', 'HC']
        cache_key = f"futures_oi_analysis_{','.join(vars_list)}"
        cached = _get_cached(cache_key)
        if cached:
            return cached
        try:
            result = []
            for var in vars_list:
                try:
                    ts = self.get_term_structure(var)
                    if not ts or not ts.get("contracts"):
                        continue
                    # Get dominant contract (highest OI)
                    dominant = None
                    max_oi = 0
                    for c in ts["contracts"]:
                        oi = c.get("open_interest") or 0
                        if oi > max_oi:
                            max_oi = oi
                            dominant = c
                    if not dominant:
                        continue
                    price = dominant["price"]
                    oi = dominant["open_interest"]
                    change_pct = dominant.get("change_pct", 0) or 0
                    vol = dominant.get("volume") or 0
                    # Interpret OI-price signal
                    if change_pct > 0 and oi and max_oi > 0:
                        signal = "bullish_entry"
                        signal_label = "多方入场"
                        interpretation = "价格上涨+持仓量高，多方力量强"
                    elif change_pct < 0 and oi and max_oi > 0:
                        signal = "bearish_entry"
                        signal_label = "空方入场"
                        interpretation = "价格下跌+持仓量高，空方力量强"
                    elif change_pct > 0:
                        signal = "short_covering"
                        signal_label = "空头回补"
                        interpretation = "价格上涨但持仓不高，可能是空头平仓"
                    elif change_pct < 0:
                        signal = "long_liquidation"
                        signal_label = "多头离场"
                        interpretation = "价格下跌但持仓不高，可能是多头平仓"
                    else:
                        signal = "neutral"
                        signal_label = "中性"
                        interpretation = "价格持平，多空均衡"
                    # OI/Volume ratio for conviction check
                    oi_vol_ratio = (oi / vol) if vol and vol > 0 else None
                    result.append({
                        "var": var,
                        "cn_name": ts.get("cn_name", var),
                        "symbol": dominant["symbol"],
                        "price": price,
                        "change_pct": change_pct,
                        "open_interest": oi,
                        "volume": vol,
                        "oi_vol_ratio": round(oi_vol_ratio, 2) if oi_vol_ratio else None,
                        "signal": signal,
                        "signal_label": signal_label,
                        "interpretation": interpretation,
                        "structure": ts.get("structure"),
                        "structure_label": ts.get("structure_label"),
                        "spread": ts.get("spread"),
                        "annualized_spread": ts.get("annualized_spread"),
                    })
                except Exception:
                    pass
            _set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取OI分析失败: {e}")
            return []


akshare_service = AKShareService()
