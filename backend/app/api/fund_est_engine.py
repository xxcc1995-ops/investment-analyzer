"""LOF基金统一EST净值计算引擎

提供三种EST计算方法（参考Palmmicro）：
1. 官方EST - 从天天基金API获取（基金公司披露的估值）
2. 参考EST - 使用校准值法计算（精度高但需定期更新校准值）
   EST = 底层价格 * 汇率 * 仓位 * 校准值
3. 实时EST - 使用动态比率法计算（无需维护校准值，自适应净值变化）
   EST = 官方净值 * (底层当前价 / 底层昨收)

多标的基金使用加权法：
   EST = 官方净值 * (1 + 加权涨跌幅%)
"""

import logging
import json
import re
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.api.fund_config import FUND_CONFIG, get_fund_config
from app.api.fund_utils import (
    get_fund_nav_from_eastmoney,
    get_hkdcny_rate,
    get_sina_realtime,
    get_usdcny_rate,
    parse_underlying_price,
    record_est_accuracy,
)
from app.core.utils import safe_float

logger = logging.getLogger(__name__)

# 共享HTTP会话
_session = requests.Session()
_adapter = HTTPAdapter(
    pool_connections=10,
    pool_maxsize=20,
    max_retries=Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504]),
)
_session.mount("https://", _adapter)
_session.mount("http://", _adapter)
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
})


def get_official_est(fund_code: str) -> Optional[dict]:
    """从天天基金API获取官方EST（基金公司披露的估值）

    Args:
        fund_code: 纯数字基金代码，如 '161130'

    Returns:
        {
            "est_nav": float,       # 官方EST净值
            "est_change": str,      # 估算涨跌幅%
            "est_time": str,        # 估算时间
            "official_nav": float,  # 官方净值
            "nav_date": str,        # 净值日期
        }
        失败返回 None
    """
    try:
        headers = {"Referer": "https://fund.eastmoney.com/"}
        url = f"https://fundgz.1234567.com.cn/js/{fund_code}.js"
        r = _session.get(url, headers=headers, timeout=10)
        match = re.search(r"jsonpgz\((.*)\)", r.text)
        if match:
            data = json.loads(match.group(1))
            nav = safe_float(data.get("dwjz"), 0)
            est_nav = safe_float(data.get("gsz"), 0)
            if nav > 0 and est_nav > 0:
                return {
                    "est_nav": est_nav,
                    "est_change": data.get("gszzl", "0"),
                    "est_time": data.get("gztime", ""),
                    "official_nav": nav,
                    "nav_date": data.get("jzrq", ""),
                }
    except Exception as e:
        logger.debug(f"获取天天基金官方EST失败 {fund_code}: {e}")
    return None


def get_official_est_batch(fund_codes: List[str], max_workers: int = 8) -> Dict[str, dict]:
    """批量获取天天基金官方EST

    Args:
        fund_codes: 纯数字基金代码列表
        max_workers: 最大并发数

    Returns:
        {fund_code: est_info} 字典
    """
    if not fund_codes:
        return {}

    results: Dict[str, dict] = {}

    def _fetch_one(code: str) -> tuple:
        try:
            est = get_official_est(code)
            return (code, est)
        except Exception:
            return (code, None)

    with ThreadPoolExecutor(max_workers=min(max_workers, len(fund_codes))) as executor:
        futures = {executor.submit(_fetch_one, code): code for code in fund_codes}
        for future in as_completed(futures):
            try:
                code, est = future.result(timeout=15)
                if est:
                    results[code] = est
            except Exception:
                pass

    return results


def calc_est_nav_dynamic(
    official_nav: float,
    current_price: float,
    prev_close: float,
) -> Optional[float]:
    """动态比率法计算EST净值（主方法）

    无需维护校准值，自适应净值变化。
    公式: EST = 官方净值 * (底层当前价 / 底层昨收)

    Args:
        official_nav: 官方净值 (T-1日)
        current_price: 底层资产当前价格
        prev_close: 底层资产昨收价

    Returns:
        EST净值，计算失败返回 None
    """
    if not official_nav or not prev_close or prev_close <= 0:
        return None
    return official_nav * (current_price / prev_close)


def calc_est_nav_calibration(
    underlying_code: str,
    underlying_price: float,
    usdcny_rate: float,
    position: float,
    calibration: float,
    hkdcny_rate: float = 0.0,
) -> float:
    """校准值法计算EST净值（验证方法）

    公式: EST = 底层价格 * 汇率 * 仓位 * 校准值

    Args:
        underlying_code: 底层资产代码
        underlying_price: 底层资产当前价格
        usdcny_rate: USD/CNY 汇率
        position: 仓位比例
        calibration: 校准值
        hkdcny_rate: HKD/CNY 汇率（0则自动获取）

    Returns:
        EST净值
    """
    if underlying_code.startswith("gb_") or underlying_code.startswith("hf_"):
        return underlying_price * usdcny_rate * position * calibration
    else:
        # 港股资产 - 使用动态汇率
        rate = hkdcny_rate if hkdcny_rate > 0 else get_hkdcny_rate()
        return underlying_price * rate * position * calibration


def calc_est_nav_multi(
    official_nav: float,
    holdings_data: List[dict],
    underlying_data: Dict[str, List[str]],
) -> Optional[dict]:
    """多标的加权法计算EST净值

    公式: EST = 官方净值 * (1 + 加权涨跌幅% / 100)

    Args:
        official_nav: 官方净值 (T-1日)
        holdings_data: 持仓配置列表 [{"code", "name", "weight"}, ...]
        underlying_data: 底层资产行情数据

    Returns:
        {"est_nav", "change_pct", "holdings_detail"} 或 None
    """
    if not official_nav or not holdings_data:
        return None

    total_weight = 0
    weighted_change = 0
    holdings_detail = []

    for holding in holdings_data:
        sina_code = holding["code"]
        underlying_info = underlying_data.get(sina_code, [])
        if not underlying_info:
            continue

        parsed = parse_underlying_price(sina_code, underlying_info)
        if not parsed or parsed["price"] <= 0:
            continue

        change_pct = parsed["change_pct"]
        weight = holding["weight"]
        weighted_change += change_pct * weight
        total_weight += weight

        holdings_detail.append({
            "code": sina_code,
            "name": holding["name"],
            "weight": weight,
            "price": parsed["price"],
            "change_pct": change_pct,
        })

    if total_weight <= 0:
        return None

    avg_change_pct = weighted_change / total_weight
    est_nav = official_nav * (1 + avg_change_pct / 100)

    return {
        "est_nav": est_nav,
        "change_pct": round(avg_change_pct, 2),
        "holdings_detail": holdings_detail,
    }


def calc_fund_est(
    fund_code: str,
    fund_price: float,
    underlying_data: Dict[str, List[str]],
    usdcny_rate: float,
    official_nav: float,
    official_nav_date: str,
    official_est: Optional[dict] = None,
) -> Optional[dict]:
    """统一EST计算入口（参考Palmmicro三种EST对比）

    根据基金配置自动选择计算方法：
    - 官方EST: 从天天基金API获取（基金公司披露的估值）
    - 参考EST: 校准值法计算（精度高但需定期更新校准值）
    - 实时EST: 动态比率法计算（无需维护校准值，自适应净值变化）

    Args:
        fund_code: 纯数字基金代码
        fund_price: 基金场内价格
        underlying_data: 底层资产行情数据
        usdcny_rate: USD/CNY 汇率
        official_nav: 官方净值 (T-1日)
        official_nav_date: 官方净值日期
        official_est: 天天基金官方EST数据（可选）

    Returns:
        {
            "fund_code": str,
            "fund_name": str,
            "fund_price": float,
            "underlying_code": str,
            "underlying_name": str,
            "underlying_type": str,
            "underlying_price": float,
            "underlying_change_pct": float,
            "est_nav_official": float,  # 官方EST (天天基金)
            "est_nav_cal": float,       # 参考EST (校准值法)
            "est_nav": float,           # 实时EST (动态比率法)
            "est_confidence": str,      # "high" / "low"
            "official_nav": float,
            "official_nav_date": str,
            "premium_pct": float,       # 基于实时EST的溢价率%
            "premium_official": float,  # 基于官方EST的溢价率%
            "premium_cal": float,       # 基于参考EST的溢价率%
            "is_multi_underlying": bool,
            "holdings_detail": list,
        }
    """
    config = get_fund_config(fund_code)
    if not config:
        return None

    fund_name = config["name"]
    underlying_type = config["underlying_type"]
    position = config.get("position", 0.95)

    # 获取官方EST
    est_nav_official = official_est.get("est_nav", 0) if official_est else 0
    est_change_official = official_est.get("est_change", "0") if official_est else "0"
    est_time_official = official_est.get("est_time", "") if official_est else ""

    # 多标的基金
    if underlying_type == "multi":
        holdings = config.get("multi_holdings", [])
        multi_result = calc_est_nav_multi(official_nav, holdings, underlying_data)
        if not multi_result:
            return None

        est_nav = multi_result["est_nav"]
        underlying_change_pct = multi_result["change_pct"]

        # 计算三种溢价率
        premium_pct = round((fund_price - est_nav) / est_nav * 100, 2) if est_nav > 0 else 0
        premium_official = round((fund_price - est_nav_official) / est_nav_official * 100, 2) if est_nav_official > 0 else 0

        return {
            "fund_code": fund_code,
            "fund_name": fund_name,
            "fund_price": fund_price,
            "underlying_code": "multi",
            "underlying_name": config.get("underlying_name", "多标的"),
            "underlying_type": underlying_type,
            "underlying_price": 0,
            "underlying_change_pct": underlying_change_pct,
            "est_nav_official": round(est_nav_official, 4),
            "est_nav_cal": 0,
            "est_nav": round(est_nav, 4),
            "est_confidence": "high",
            "est_change_official": est_change_official,
            "est_time_official": est_time_official,
            "official_nav": official_nav,
            "official_nav_date": official_nav_date,
            "premium_pct": premium_pct,
            "premium_official": premium_official,
            "premium_cal": 0,
            "is_multi_underlying": True,
            "holdings_detail": multi_result["holdings_detail"],
        }

    # 单标的基金
    underlying_code = config.get("underlying", "")
    if not underlying_code:
        return None

    underlying_info = underlying_data.get(underlying_code, [])
    if not underlying_info:
        return None

    parsed = parse_underlying_price(underlying_code, underlying_info)
    if not parsed or parsed["price"] <= 0:
        return None

    current_price = parsed["price"]
    prev_close = parsed["prev_close"]
    underlying_change_pct = parsed["change_pct"]

    # 方法1: 动态比率法（实时EST）
    est_nav_dynamic = calc_est_nav_dynamic(official_nav, current_price, prev_close)

    # 方法2: 校准值法（参考EST）
    calibration = config.get("calibration")
    if calibration:
        # 获取动态HKD/CNY汇率（港股资产需要）
        hkdcny_rate = get_hkdcny_rate() if underlying_code.startswith("rt_hk") else 0.0
        est_nav_cal = calc_est_nav_calibration(
            underlying_code, current_price, usdcny_rate, position, calibration, hkdcny_rate
        )
    else:
        est_nav_cal = None

    # 选择最终EST（优先动态比率法）
    if est_nav_dynamic and est_nav_dynamic > 0:
        est_nav = est_nav_dynamic
    elif est_nav_cal and est_nav_cal > 0:
        est_nav = est_nav_cal
    else:
        return None

    # 评估可信度：增强版四级评估
    # 考虑因素：两种方法偏差 + 底层资产流动性 + 官方EST一致性
    if est_nav_dynamic and est_nav_cal and est_nav_cal > 0:
        deviation = abs(est_nav_dynamic - est_nav_cal) / est_nav_cal
        # 与官方EST对比（如有）
        official_deviation = 0
        if est_nav_official and est_nav_official > 0:
            official_deviation = abs(est_nav_dynamic - est_nav_official) / est_nav_official

        if deviation < 0.005 and official_deviation < 0.01:
            confidence = "high"      # 三种EST高度一致
        elif deviation < 0.01 and official_deviation < 0.02:
            confidence = "medium"    # 偏差可接受
        elif deviation < 0.02:
            confidence = "low"       # 偏差较大，需谨慎
        else:
            confidence = "very_low"  # 偏差过大，不可信
    elif est_nav_official and est_nav_official > 0 and est_nav_dynamic:
        # 仅与官方EST对比
        official_deviation = abs(est_nav_dynamic - est_nav_official) / est_nav_official
        confidence = "high" if official_deviation < 0.01 else "medium" if official_deviation < 0.02 else "low"
    else:
        confidence = "medium"

    # 记录EST准确度（用于回测）
    if est_nav and official_nav and official_nav > 0:
        record_est_accuracy(fund_code, est_nav, official_nav, official_nav_date)

    # 计算三种溢价率
    premium_pct = round((fund_price - est_nav) / est_nav * 100, 2) if est_nav > 0 else 0
    premium_official = round((fund_price - est_nav_official) / est_nav_official * 100, 2) if est_nav_official > 0 else 0
    premium_cal = round((fund_price - est_nav_cal) / est_nav_cal * 100, 2) if est_nav_cal and est_nav_cal > 0 else 0

    return {
        "fund_code": fund_code,
        "fund_name": fund_name,
        "fund_price": fund_price,
        "underlying_code": underlying_code,
        "underlying_name": config.get("underlying_name", underlying_code),
        "underlying_type": underlying_type,
        "underlying_price": current_price,
        "underlying_change_pct": underlying_change_pct,
        "est_nav_official": round(est_nav_official, 4),
        "est_nav_cal": round(est_nav_cal, 4) if est_nav_cal else 0,
        "est_nav": round(est_nav, 4),
        "est_confidence": confidence,
        "est_change_official": est_change_official,
        "est_time_official": est_time_official,
        "official_nav": official_nav,
        "official_nav_date": official_nav_date,
        "premium_pct": premium_pct,
        "premium_official": premium_official,
        "premium_cal": premium_cal,
        "is_multi_underlying": False,
        "holdings_detail": [],
    }
