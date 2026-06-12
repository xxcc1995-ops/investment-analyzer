"""LOF基金EST净值估算API

基于Palmmicro技术方案，使用校准值法计算LOF基金的实时估算净值。
支持美股QDII、港股QDII等LOF基金。

数据流：
  新浪实时行情（基金价格 + 底层资产价格）
    + 东方财富基金净值（T-1日官方净值）
    + 美元人民币中间价
    -> 校准值法计算EST净值 -> 溢价率
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.api.fund_utils import (
    determine_market_status,
    get_fund_nav_from_eastmoney,
    get_sina_fund_code,
    get_sina_realtime,
    get_usdcny_rate,
    make_error_response,
    make_success_response,
    normalize_fund_code,
    parse_underlying_price,
)
from app.core.cache import TTL_REALTIME, cached, get_realtime_ttl
from app.core.utils import safe_float

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== LOF基金配置 ====================
# 基金代码 -> 底层资产代码、仓位比例、校准值
# 校准值 = 基金官方净值 / (底层资产价格 x 汇率 x 仓位比例)
# 港股基金：校准值 = 基金官方净值 / (指数价格 x 港币汇率 x 仓位比例)
# 底层资产说明：gb_xxx = 美股ETF（美元），hf_xxx = 期货（点数），rt_hkxxx = 港股指数（点数）

LOF_FUND_CONFIG = {
    # === 美股QDII LOF ===
    "SZ161130": {"name": "纳斯达克100LOF", "underlying": "gb_qqq", "position": 0.95, "calibration": 0.001012},
    "SZ161125": {"name": "标普500LOF", "underlying": "gb_spy", "position": 0.95, "calibration": 0.000660},
    "SZ162415": {"name": "美国消费LOF", "underlying": "gb_xly", "position": 0.95, "calibration": 0.003913},
    "SZ161126": {"name": "标普医疗保健LOF", "underlying": "gb_xlv", "position": 0.95, "calibration": 0.001888},
    "SZ161128": {"name": "标普信息科技LOF", "underlying": "gb_xlk", "position": 0.95, "calibration": 0.005944},
    "SZ161127": {"name": "标普生物科技LOF", "underlying": "gb_xbi", "position": 0.95, "calibration": 0.002163},
    "SZ162411": {"name": "华宝油气LOF", "underlying": "gb_xop", "position": 0.95, "calibration": 0.000846},
    "SZ160416": {"name": "石油基金LOF", "underlying": "gb_uso", "position": 0.95, "calibration": 0.002474},
    "SZ162719": {"name": "石油LOF", "underlying": "gb_uso", "position": 0.95, "calibration": 0.003201},
    "SZ164906": {"name": "中概互联网LOF", "underlying": "gb_kweb", "position": 0.95, "calibration": 0.005742},
    "SH501300": {"name": "美元债LOF", "underlying": "gb_agg", "position": 0.95, "calibration": 0.001492},
    "SZ160140": {"name": "美国REIT精选LOF", "underlying": "gb_vnq", "position": 0.95, "calibration": 0.002249},
    "SZ164824": {"name": "印度基金LOF", "underlying": "gb_inda", "position": 0.95, "calibration": 0.004203},
    "SZ163208": {"name": "全球油气能源LOF", "underlying": "gb_xle", "position": 0.95, "calibration": 0.003575},
    "SH501018": {"name": "南方原油LOF", "underlying": "gb_uso", "position": 0.95, "calibration": 0.002159},
    "SZ160723": {"name": "嘉实原油LOF", "underlying": "gb_uso", "position": 0.95, "calibration": 0.002458},
    "SZ161129": {"name": "原油LOF易方达", "underlying": "gb_uso", "position": 0.95, "calibration": 0.002060},
    "SZ160216": {"name": "国泰商品LOF", "underlying": "gb_gsg", "position": 0.95, "calibration": 0.003553},
    "SZ161815": {"name": "抗通胀LOF", "underlying": "gb_tip", "position": 0.95, "calibration": 0.001585},
    "SZ160719": {"name": "嘉实黄金LOF", "underlying": "gb_gld", "position": 0.95, "calibration": 0.000787},
    "SZ161116": {"name": "黄金主题LOF", "underlying": "gb_gld", "position": 0.95, "calibration": 0.000654},
    "SZ164701": {"name": "黄金LOF", "underlying": "gb_gld", "position": 0.95, "calibration": 0.000690},
    "SZ165513": {"name": "中信保诚商品LOF", "underlying": "gb_djp", "position": 0.95, "calibration": 0.003499},
    "SH501225": {"name": "全球芯片LOF", "underlying": "gb_soxx", "position": 0.95, "calibration": 0.000969},
    "SH501312": {"name": "海外科技LOF", "underlying": "gb_arkk", "position": 0.95, "calibration": 0.005036},
    "SZ160644": {"name": "港美互联网LOF", "underlying": "gb_kweb", "position": 0.95, "calibration": 0.012235},
    "SZ161226": {"name": "国投白银LOF", "underlying": "gb_slv", "position": 0.95, "calibration": 0.005081},
    # === 港股QDII LOF ===
    "SH501025": {"name": "香港银行LOF", "underlying": "rt_hkHSCEI", "position": 0.95, "calibration": 0.000245},
    "SZ161124": {"name": "港股小盘LOF", "underlying": "rt_hkHSCCI", "position": 0.95, "calibration": 0.000265},
    "SZ160717": {"name": "H股LOF", "underlying": "rt_hkHSCEI", "position": 0.95, "calibration": 0.000101},
    "SZ161831": {"name": "恒生国企LOF", "underlying": "rt_hkHSCEI", "position": 0.95, "calibration": 0.000102},
    "SH501302": {"name": "恒生指数基金LOF", "underlying": "rt_hkHSI", "position": 0.95, "calibration": 0.000054},
    "SZ160924": {"name": "恒生指数LOF", "underlying": "rt_hkHSI", "position": 0.95, "calibration": 0.000047},
    "SZ164705": {"name": "恒生LOF", "underlying": "rt_hkHSI", "position": 0.95, "calibration": 0.000053},
}

# 合法代码集合（用于标准化）
_VALID_FUND_CODES = set(LOF_FUND_CONFIG.keys())

# HKD/CNY 近似汇率（用于港股资产）
_HKD_TO_CNY = 0.9


def _calc_est_nav(
    underlying_code: str,
    underlying_price: float,
    usdcny_rate: float,
    position: float,
    calibration: float,
) -> float:
    """使用校准值法计算EST净值

    Args:
        underlying_code: 底层资产代码
        underlying_price: 底层资产当前价格
        usdcny_rate: USD/CNY 汇率
        position: 仓位比例
        calibration: 校准值

    Returns:
        估算净值
    """
    if underlying_code.startswith("gb_") or underlying_code.startswith("hf_"):
        return underlying_price * usdcny_rate * position * calibration
    else:
        # 港股资产
        return underlying_price * _HKD_TO_CNY * position * calibration


def _process_single_fund(
    fund_code: str,
    config: dict,
    fund_data: dict,
    underlying_data: dict,
    usdcny_rate: float,
) -> Optional[dict]:
    """处理单只基金的EST净值计算

    Args:
        fund_code: 基金代码（带SH/SZ前缀）
        config: 基金配置
        fund_data: 新浪基金行情数据
        underlying_data: 新浪底层资产行情数据
        usdcny_rate: USD/CNY 汇率

    Returns:
        基金EST数据字典，处理失败返回 None
    """
    try:
        # 基金实时价格
        sina_fund_code = get_sina_fund_code(fund_code)
        fund_info = fund_data.get(sina_fund_code, [])
        if len(fund_info) < 10:
            return None

        fund_price = safe_float(fund_info[3], 0)
        fund_change_pct = safe_float(fund_info[32], 0) if len(fund_info) > 32 else 0
        fund_name = fund_info[1] if len(fund_info) > 1 else config["name"]

        if fund_price <= 0:
            return None

        # 底层资产价格
        underlying_code = config["underlying"]
        underlying_info = underlying_data.get(underlying_code, [])

        # 尝试备用底层资产
        if not underlying_info and "underlying_alt" in config:
            underlying_code = config["underlying_alt"]
            underlying_info = underlying_data.get(underlying_code, [])

        if not underlying_info:
            return None

        parsed = parse_underlying_price(underlying_code, underlying_info)
        if not parsed or parsed["price"] <= 0:
            return None

        underlying_price = parsed["price"]

        # 获取基金净值（T-1日）
        fund_nav_code = fund_code[2:]  # 去掉SH/SZ前缀
        nav_info = get_fund_nav_from_eastmoney(fund_nav_code)

        # 计算EST净值
        position = config["position"]
        calibration = config["calibration"]
        est_nav = _calc_est_nav(
            underlying_code, underlying_price, usdcny_rate, position, calibration
        )

        # 溢价率
        premium = (
            round((fund_price - est_nav) / est_nav * 100, 2) if est_nav > 0 else 0
        )

        return {
            "fund_code": fund_code,
            "fund_name": fund_name,
            "fund_price": fund_price,
            "fund_change_pct": round(fund_change_pct, 2),
            "underlying_code": underlying_code,
            "underlying_price": underlying_price,
            "underlying_change_pct": parsed["change_pct"],
            "est_nav": round(est_nav, 4),
            "premium": premium,
            "official_nav": nav_info.get("nav", 0),
            "official_nav_date": nav_info.get("nav_date", ""),
            "position": position,
            "usdcny_rate": usdcny_rate,
        }
    except Exception as e:
        logger.warning(f"处理基金 {fund_code} 失败: {e}")
        return None


# ==================== API 端点 ====================


@router.get("/est-list")
def get_fund_est_list():
    """获取所有LOF基金的EST净值估算列表

    批量获取底层资产价格，减少HTTP请求数。
    结果按溢价率降序排列。

    Returns:
        {
            'error': False,
            'funds': [...],
            'total': int,
            'usdcny_rate': float,
            'market_status': str,
            'update_time': str,
        }
    """
    try:
        # 批量收集所有底层资产代码
        underlying_symbols = set()
        for config in LOF_FUND_CONFIG.values():
            underlying_symbols.add(config["underlying"])
            if "underlying_alt" in config:
                underlying_symbols.add(config["underlying_alt"])

        # 批量获取基金实时价格
        fund_symbols = [get_sina_fund_code(s) for s in LOF_FUND_CONFIG.keys()]
        fund_data = get_sina_realtime(fund_symbols)

        # 批量获取底层资产价格
        underlying_data = get_sina_realtime(list(underlying_symbols))

        # 获取汇率
        usdcny_rate = get_usdcny_rate()

        # 市场状态
        market_status = determine_market_status()

        # 逐个处理基金
        results = []
        for fund_code, config in LOF_FUND_CONFIG.items():
            item = _process_single_fund(
                fund_code, config, fund_data, underlying_data, usdcny_rate
            )
            if item:
                results.append(item)

        # 按溢价率降序排序
        results.sort(key=lambda x: x["premium"], reverse=True)

        return make_success_response(
            {
                "funds": results,
                "total": len(results),
                "usdcny_rate": usdcny_rate,
                "market_status": market_status,
            }
        )
    except Exception as e:
        logger.error(f"获取LOF基金EST列表失败: {e}")
        raise HTTPException(status_code=500, detail="获取基金EST列表失败，请稍后重试")


@router.get("/est/{fund_code}")
def get_fund_est(fund_code: str):
    """获取单只LOF基金的EST净值估算

    Args:
        path fund_code: 基金代码（支持带/不带SH/SZ前缀）

    Returns:
        {
            'error': False,
            'fund_code': str,
            'fund_name': str,
            'fund_price': float,
            'est_nav': float,
            'premium': float,
            ...
        }

    Raises:
        400: 基金代码无效或不支持
        404: 未找到基金数据
    """
    # 标准化基金代码
    normalized = normalize_fund_code(fund_code, _VALID_FUND_CODES)
    if not normalized:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的基金代码: {fund_code}。支持的代码: {', '.join(sorted(_VALID_FUND_CODES)[:10])}...",
        )

    config = LOF_FUND_CONFIG[normalized]

    try:
        # 获取基金实时价格
        sina_fund_code = get_sina_fund_code(normalized)
        fund_data = get_sina_realtime([sina_fund_code])
        fund_info = fund_data.get(sina_fund_code, [])

        if len(fund_info) < 10:
            raise HTTPException(status_code=404, detail="获取基金价格失败，请稍后重试")

        fund_price = safe_float(fund_info[3], 0)
        fund_change_pct = safe_float(fund_info[32], 0) if len(fund_info) > 32 else 0

        if fund_price <= 0:
            raise HTTPException(status_code=404, detail="基金价格数据异常")

        # 获取底层资产价格
        underlying_code = config["underlying"]
        underlying_data = get_sina_realtime([underlying_code])
        underlying_info = underlying_data.get(underlying_code, [])

        # 尝试备用底层资产
        if not underlying_info and "underlying_alt" in config:
            underlying_code = config["underlying_alt"]
            underlying_data = get_sina_realtime([underlying_code])
            underlying_info = underlying_data.get(underlying_code, [])

        if not underlying_info:
            raise HTTPException(
                status_code=404,
                detail=f"获取底层资产 {underlying_code} 价格失败",
            )

        parsed = parse_underlying_price(underlying_code, underlying_info)
        if not parsed or parsed["price"] <= 0:
            raise HTTPException(
                status_code=404,
                detail=f"底层资产 {underlying_code} 价格数据异常",
            )

        underlying_price = parsed["price"]

        # 获取汇率
        usdcny_rate = get_usdcny_rate()

        # 计算EST净值
        position = config["position"]
        calibration = config["calibration"]
        est_nav = _calc_est_nav(
            underlying_code, underlying_price, usdcny_rate, position, calibration
        )

        # 溢价率
        premium = (
            round((fund_price - est_nav) / est_nav * 100, 2) if est_nav > 0 else 0
        )

        # 获取基金净值（T-1日）
        fund_nav_code = normalized[2:]
        nav_info = get_fund_nav_from_eastmoney(fund_nav_code)

        return make_success_response(
            {
                "fund_code": normalized,
                "fund_name": config["name"],
                "fund_price": fund_price,
                "fund_change_pct": round(fund_change_pct, 2),
                "underlying_code": underlying_code,
                "underlying_price": underlying_price,
                "underlying_change_pct": parsed["change_pct"],
                "est_nav": round(est_nav, 4),
                "premium": premium,
                "official_nav": nav_info.get("nav", 0),
                "official_nav_date": nav_info.get("nav_date", ""),
                "position": position,
                "usdcny_rate": usdcny_rate,
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取基金 {fund_code} EST失败: {e}")
        raise HTTPException(status_code=500, detail="获取基金EST数据失败，请稍后重试")
