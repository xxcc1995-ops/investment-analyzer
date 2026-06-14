"""
FRED (Federal Reserve Economic Data) API 服务
美国官方权威宏观数据源 — 800,000+ 时间序列
https://fred.stlouisfed.org/docs/api/fred/
"""
import os
import logging
import requests
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from app.core.cache import get_cache, set_cache, TTL_DAILY, TTL_WEEKLY

logger = logging.getLogger(__name__)

FRED_BASE = "https://api.stlouisfed.org/fred"
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")

# 关键宏观指标 Series ID
FRED_SERIES = {
    # 通胀
    "cpi": "CPIAUCSL",           # CPI (All Urban Consumers)
    "core_cpi": "CPILFESL",      # Core CPI (Food & Energy excluded)
    "ppi": "PPIACO",             # PPI (All Commodities)
    "pce": "PCEPI",              # PCE Price Index (Fed首选通胀指标)

    # 就业
    "unemployment": "UNRATE",    # Unemployment Rate
    "nonfarm_payroll": "PAYEMS", # Nonfarm Payrolls (thousands)
    "initial_claims": "ICSA",    # Initial Jobless Claims (weekly)

    # 经济增长
    "gdp_real": "GDPC1",         # Real GDP (quarterly)
    "gdp_nominal": "GDP",        # Nominal GDP
    "industrial_production": "INDPRO",  # Industrial Production Index
    "retail_sales": "RSAFS",     # Retail Sales

    # 利率
    "fed_rate": "DFF",           # Fed Funds Rate (daily)
    "fed_rate_monthly": "FEDFUNDS",  # Fed Funds Rate (monthly)
    "treasury_10y": "DGS10",    # 10-Year Treasury (daily)
    "treasury_2y": "DGS2",      # 2-Year Treasury (daily)
    "treasury_30y": "DGS30",    # 30-Year Treasury (daily)
    "yield_spread_10y2y": "T10Y2Y",  # 10Y-2Y Spread (recession predictor)

    # 消费信心
    "consumer_sentiment": "UMCSENT",  # Michigan Consumer Sentiment
    "consumer_confidence": "CSCICP01USM665S",  # OECD Consumer Confidence

    # 货币供应
    "m2": "M2SL",               # M2 Money Supply

    # 房地产
    "housing_starts": "HOUST",   # Housing Starts
    "case_shiller": "CSUSHPINSA",  # Case-Shiller Home Price Index
}


class FREDService:
    """FRED API 数据服务"""

    def __init__(self):
        self.api_key = FRED_API_KEY
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'InvestmentAnalyzer/1.0'
        })

    def _is_available(self) -> bool:
        """检查FRED API是否可用（需要API Key）"""
        return bool(self.api_key)

    def get_series(self, series_id: str, start_date: str = "2020-01-01",
                   limit: int = 100) -> Optional[List[Dict]]:
        """
        获取FRED时间序列数据

        Args:
            series_id: FRED Series ID (如 CPIAUCSL, DFF)
            start_date: 起始日期 YYYY-MM-DD
            limit: 最大返回条数

        Returns:
            [{"date": "2024-01-01", "value": 308.417}, ...] 按日期降序
        """
        if not self._is_available():
            return None

        cache_key = f"fred_{series_id}_{start_date}"
        cached = get_cache(cache_key, TTL_DAILY)
        if cached:
            return cached

        try:
            resp = self.session.get(f"{FRED_BASE}/series/observations", params={
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "observation_start": start_date,
                "sort_order": "desc",
                "limit": limit,
            }, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            observations = data.get("observations", [])
            result = []
            for obs in observations:
                val = obs.get("value", ".")
                if val == ".":
                    continue
                result.append({
                    "date": obs.get("date", ""),
                    "value": float(val),
                })

            set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"FRED API获取 {series_id} 失败: {e}")
            return None

    def get_indicator(self, key: str, start_date: str = "2020-01-01") -> Optional[Dict]:
        """
        获取单个指标的最新值 + 近期序列

        Returns:
            {"latest": {"date": "...", "value": ...}, "series": [...], "source": "FRED", "quality": "official"}
        """
        series_id = FRED_SERIES.get(key)
        if not series_id:
            logger.warning(f"未知FRED指标: {key}")
            return None

        series = self.get_series(series_id, start_date)
        if not series:
            return None

        return {
            "latest": series[0] if series else None,
            "series": series[:60],  # 最近60条
            "source": "FRED",
            "series_id": series_id,
            "quality": "official",  # 官方权威数据
            "fetched_at": datetime.now().isoformat(),
        }

    def get_batch(self, keys: List[str], start_date: str = "2020-01-01") -> Dict:
        """批量获取多个指标"""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results = {}
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {
                pool.submit(self.get_indicator, key, start_date): key
                for key in keys
            }
            for f in as_completed(futures):
                key = futures[f]
                try:
                    results[key] = f.result()
                except Exception:
                    results[key] = None
        return results

    def get_data_quality_report(self) -> Dict:
        """获取数据质量报告：检查各指标的时效性"""
        if not self._is_available():
            return {"available": False, "reason": "FRED_API_KEY未设置"}

        report = {"available": True, "indicators": {}}
        for key, series_id in FRED_SERIES.items():
            try:
                series = self.get_series(series_id, limit=1)
                if series:
                    latest_date = series[0]["date"]
                    days_old = (datetime.now() - datetime.strptime(latest_date, "%Y-%m-%d")).days
                    report["indicators"][key] = {
                        "series_id": series_id,
                        "latest_date": latest_date,
                        "days_old": days_old,
                        "fresh": days_old < 90,  # 90天内算新鲜
                    }
            except Exception:
                report["indicators"][key] = {"series_id": series_id, "error": True}
        return report


fred_service = FREDService()
