"""
AKShare数据服务 - 统一的金融数据接口
数据源：AKShare（聚合多个国内财经数据源）
"""
import time
import math
import logging
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

from app.core.cache import get_cache as _get_cached, set_cache as _set_cache
from app.core.utils import safe_float as _safe_float


class AKShareService:
    """AKShare数据服务"""

    # ==================== 宏观数据 ====================

    def get_gdp_data(self) -> Optional[List[Dict]]:
        """获取中国GDP数据"""
        cache_key = "macro_china_gdp"
        cached = _get_cached(cache_key)
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
        cached = _get_cached(cache_key)
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
        cached = _get_cached(cache_key)
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
        cached = _get_cached(cache_key)
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
        cached = _get_cached(cache_key)
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
        cached = _get_cached(cache_key)
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
        cached = _get_cached(cache_key)
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
        cached = _get_cached(cache_key)
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
        cached = _get_cached(cache_key)
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


akshare_service = AKShareService()
