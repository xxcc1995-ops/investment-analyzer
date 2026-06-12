"""QDII LOF基金EST净值估算API - 动态比率法

使用动态比率法（Dynamic Ratio Method）计算QDII LOF基金的实时估算净值：
  est_nav = official_nav x (underlying_current / underlying_prev_close)

相比传统校准值法，动态比率法无需维护校准值，自动适应基金净值变化。
同时提供传统方法结果用于对比。

数据流：
  新浪实时行情（基金A股价格 + 底层资产价格）
    + 东方财富基金净值（T-1日官方净值）
    + 美元人民币中间价
    -> 动态比率法计算EST净值 -> 溢价率
"""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.api.fund_est import LOF_FUND_CONFIG, _calc_est_nav
from app.api.fund_utils import (
    determine_market_status,
    get_fund_nav_batch,
    get_fund_nav_from_eastmoney,
    get_sina_fund_code,
    get_sina_realtime,
    get_usdcny_rate,
    make_success_response,
    normalize_fund_code,
    parse_underlying_price,
)
from app.core.cache import get_cache, set_cache
from app.core.utils import safe_float

logger = logging.getLogger(__name__)

router = APIRouter()

# 合法代码集合
_VALID_FUND_CODES = set(LOF_FUND_CONFIG.keys())

# HKD/CNY 近似汇率
_HKD_TO_CNY = 0.9


def _calc_est_nav_dynamic(
    official_nav: float,
    underlying_price: float,
    underlying_prev_close: float,
) -> float:
    """动态比率法计算EST净值

    est_nav = official_nav x (underlying_current / underlying_prev_close)

    Args:
        official_nav: T-1日官方净值
        underlying_price: 底层资产当前价格
        underlying_prev_close: 底层资产前收盘价

    Returns:
        估算净值
    """
    if underlying_prev_close <= 0:
        return official_nav
    price_ratio = underlying_price / underlying_prev_close
    return official_nav * price_ratio


def _get_underlying_detail(underlying_code: str, raw_data: list) -> Optional[dict]:
    """解析底层资产详细行情数据（比parse_underlying_price多返回字段）

    Args:
        underlying_code: 底层资产代码
        raw_data: 新浪返回的原始字段列表

    Returns:
        详细行情字典，解析失败返回 None
    """
    parsed = parse_underlying_price(underlying_code, raw_data)
    if not parsed:
        return None

    return {
        "price": parsed["price"],
        "prev_close": parsed["prev_close"],
        "open": parsed["open"],
        "high": parsed["high"],
        "low": parsed["low"],
        "name": parsed["name"],
        "change_pct": parsed["change_pct"],
    }


@router.get("/list")
def get_fund_est_detail_list():
    """获取所有QDII LOF基金的EST净值估算列表（动态比率法）

    批量获取所有底层资产价格，减少HTTP请求数。
    同时返回动态比率法和传统校准值法的结果用于对比。

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

        # 批量获取基金实时价格
        fund_symbols = [get_sina_fund_code(s) for s in LOF_FUND_CONFIG.keys()]
        fund_data = get_sina_realtime(fund_symbols)

        # 批量获取底层资产价格
        underlying_data = get_sina_realtime(list(underlying_symbols))

        # 获取汇率和市场状态
        usdcny_rate = get_usdcny_rate()
        market_status = determine_market_status()

        # 批量获取所有基金净值（并发请求，比串行快5-10倍）
        fund_nav_codes = [fund_code[2:] for fund_code in LOF_FUND_CONFIG.keys()]
        nav_data_batch = get_fund_nav_batch(fund_nav_codes)

        results = []

        for fund_code, config in LOF_FUND_CONFIG.items():
            try:
                # 基金实时价格
                sina_fund_code = get_sina_fund_code(fund_code)
                fund_info = fund_data.get(sina_fund_code, [])
                if len(fund_info) < 10:
                    continue

                fund_price = safe_float(fund_info[3], 0)
                fund_change_pct = safe_float(fund_info[32], 0) if len(fund_info) > 32 else 0

                if fund_price <= 0:
                    continue

                # 底层资产价格
                underlying_code = config["underlying"]
                underlying_info = underlying_data.get(underlying_code, [])
                if not underlying_info:
                    continue

                parsed = parse_underlying_price(underlying_code, underlying_info)
                if not parsed or parsed["price"] <= 0 or parsed["prev_close"] <= 0:
                    continue

                underlying_price = parsed["price"]
                underlying_prev_close = parsed["prev_close"]

                # 从批量结果中获取基金净值（T-1日）
                fund_nav_code = fund_code[2:]
                nav_info = nav_data_batch.get(fund_nav_code, {})
                official_nav = safe_float(nav_info.get("nav"), 0)
                nav_date = nav_info.get("nav_date", "")

                if official_nav <= 0:
                    continue

                # 动态比率法
                position = config["position"]
                price_ratio = underlying_price / underlying_prev_close
                est_nav_dynamic = _calc_est_nav_dynamic(
                    official_nav, underlying_price, underlying_prev_close
                )

                # 传统校准值法（用于对比）
                calibration = config.get("calibration", 0)
                est_nav_traditional = _calc_est_nav(
                    underlying_code, underlying_price, usdcny_rate, position, calibration
                )

                # 溢价率（基于动态比率法）
                premium = (
                    round((fund_price - est_nav_dynamic) / est_nav_dynamic * 100, 2)
                    if est_nav_dynamic > 0
                    else 0
                )

                results.append(
                    {
                        "fund_code": fund_code,
                        "fund_name": config["name"],
                        "fund_price": fund_price,
                        "fund_change_pct": round(fund_change_pct, 2),
                        "underlying_code": underlying_code,
                        "underlying_price": underlying_price,
                        "underlying_prev_close": underlying_prev_close,
                        "underlying_change_pct": parsed["change_pct"],
                        "est_nav": round(est_nav_dynamic, 4),
                        "est_nav_traditional": round(est_nav_traditional, 4),
                        "premium": premium,
                        "official_nav": official_nav,
                        "official_nav_date": nav_date,
                        "position": position,
                        "usdcny_rate": usdcny_rate,
                        "price_ratio": round(price_ratio, 6),
                        "calculation_method": "dynamic_ratio",
                    }
                )

            except Exception as e:
                logger.warning(f"处理基金 {fund_code} 失败: {e}")
                continue

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
        logger.error(f"获取QDII基金EST列表失败: {e}")
        raise HTTPException(status_code=500, detail="获取基金EST列表失败，请稍后重试")


@router.get("/detail/{fund_code}")
def get_fund_est_detail(fund_code: str):
    """获取单只QDII LOF基金的详细EST净值估算（动态比率法）

    返回详细的底层资产行情、两种计算方法的对比、市场状态等信息。

    Args:
        path fund_code: 基金代码（支持带/不带SH/SZ前缀）

    Returns:
        {
            'error': False,
            'fund_code': str,
            'fund_name': str,
            'est_nav': float,                # 动态比率法
            'est_nav_traditional': float,    # 传统校准值法
            'a_share_price': float,          # A股实时价格
            'a_share_change_pct': float,
            'underlying_price': float,
            'underlying_change_pct': float,
            'premium_pct': float,
            'market_status': str,
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
            detail=f"不支持的基金代码: {fund_code}",
        )

    config = LOF_FUND_CONFIG[normalized]

    try:
        # 1. 获取基金最新官方净值
        fund_nav_code = normalized[2:]
        nav_info = get_fund_nav_from_eastmoney(fund_nav_code)
        official_nav = safe_float(nav_info.get("nav"), 0)
        nav_date = nav_info.get("nav_date", "")

        if official_nav <= 0:
            raise HTTPException(status_code=404, detail="获取基金官方净值失败")

        # 2. 获取底层资产实时价格
        underlying_code = config["underlying"]
        underlying_raw = get_sina_realtime([underlying_code])
        underlying_info = underlying_raw.get(underlying_code, [])

        if not underlying_info or len(underlying_info) < 2:
            raise HTTPException(
                status_code=404,
                detail=f"获取 {underlying_code} 价格失败，请检查网络连接",
            )

        underlying = _get_underlying_detail(underlying_code, underlying_info)
        if not underlying or underlying["price"] <= 0:
            raise HTTPException(
                status_code=404,
                detail=f"{underlying_code} 价格数据异常",
            )

        # 3. 获取美元人民币汇率
        usdcny_rate = get_usdcny_rate()

        # 4. 获取A股市场实时价格
        sina_fund_code = get_sina_fund_code(normalized)
        fund_data_raw = get_sina_realtime([sina_fund_code])
        fund_info = fund_data_raw.get(sina_fund_code, [])

        a_share_price = 0.0
        a_share_change_pct = 0.0
        a_share_volume = 0
        a_share_amount = 0.0

        if fund_info and len(fund_info) > 10:
            a_share_price = safe_float(fund_info[3], 0)
            a_share_change_pct = safe_float(fund_info[32], 0) if len(fund_info) > 32 else 0
            a_share_volume = int(safe_float(fund_info[8], 0))
            a_share_amount = safe_float(fund_info[9], 0)

        # 5. 计算EST净值
        position = config["position"]
        underlying_price = underlying["price"]
        underlying_prev_close = underlying["prev_close"]

        # 动态比率法
        if underlying_prev_close > 0:
            price_ratio = underlying_price / underlying_prev_close
            est_nav_dynamic = official_nav * price_ratio
        else:
            price_ratio = 1.0
            est_nav_dynamic = official_nav

        # 传统校准值法（用于对比）
        calibration = config.get("calibration", 0)
        est_nav_traditional = _calc_est_nav(
            underlying_code, underlying_price, usdcny_rate, position, calibration
        )

        est_nav = est_nav_dynamic

        # 6. 溢价率
        premium_pct = (
            round((a_share_price - est_nav) / est_nav * 100, 2)
            if a_share_price > 0 and est_nav > 0
            else 0
        )

        # 7. 市场状态
        market_status = determine_market_status()

        return make_success_response(
            {
                "fund_code": normalized,
                "fund_name": config["name"],
                "est_nav": round(est_nav, 4),
                "est_nav_traditional": round(est_nav_traditional, 4),
                "a_share_price": a_share_price,
                "a_share_change_pct": round(a_share_change_pct, 2),
                "a_share_volume": a_share_volume,
                "a_share_amount": round(a_share_amount, 2),
                "premium_pct": premium_pct,
                "official_nav": official_nav,
                "official_nav_date": nav_date,
                "underlying_code": underlying_code,
                "underlying_name": underlying["name"],
                "underlying_price": underlying_price,
                "underlying_prev_close": underlying_prev_close,
                "underlying_change_pct": underlying["change_pct"],
                "underlying_open": underlying["open"],
                "underlying_high": underlying["high"],
                "underlying_low": underlying["low"],
                "usdcny_rate": usdcny_rate,
                "position_ratio": position,
                "calibration": round(calibration, 6),
                "price_ratio": round(price_ratio, 6),
                "calculation_method": "dynamic_ratio",
                "market_status": market_status,
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取基金 {fund_code} 详细EST失败: {e}")
        raise HTTPException(status_code=500, detail="获取基金EST数据失败，请稍后重试")


@router.get("/stock-quotes")
def get_stock_quotes(codes: str = Query(..., description="逗号分隔的股票代码，如 sh600519,sz000858")):
    """批量获取A股股票实时行情（用于基金持仓股票价格查询）

    使用新浪API批量获取，单次请求最多处理50个代码。
    结果缓存30秒，避免频繁请求。

    Args:
        query codes: 逗号分隔的股票代码（新浪格式：sh600xxx, sz000xxx）

    Returns:
        {
            'error': False,
            'quotes': {
                'sh600519': {'price': 1800.0, 'change_pct': 1.23, 'name': '贵州茅台'},
                ...
            }
        }
    """
    if not codes or not codes.strip():
        raise HTTPException(status_code=400, detail="codes参数不能为空")

    code_list = [c.strip().lower() for c in codes.split(",") if c.strip()]

    if not code_list:
        raise HTTPException(status_code=400, detail="未提供有效的股票代码")

    if len(code_list) > 50:
        raise HTTPException(status_code=400, detail="单次最多查询50个股票代码")

    # 检查缓存
    cache_key = f"stock_quotes:{','.join(sorted(code_list))}"
    cached_data = get_cache(cache_key, 30)
    if cached_data is not None:
        return make_success_response({"quotes": cached_data})

    try:
        # 批量获取新浪实时数据
        raw_data = get_sina_realtime(code_list)

        quotes = {}
        for code in code_list:
            fields = raw_data.get(code, [])
            if not fields or len(fields) < 32:
                continue

            name = fields[0] if fields[0] else code
            price = safe_float(fields[3], 0)
            prev_close = safe_float(fields[2], 0)

            if price <= 0 or prev_close <= 0:
                continue

            change_pct = round((price - prev_close) / prev_close * 100, 2)

            quotes[code] = {
                "code": code,
                "name": name,
                "price": price,
                "change_pct": change_pct,
                "prev_close": prev_close,
                "open": safe_float(fields[1], 0),
                "high": safe_float(fields[4], 0),
                "low": safe_float(fields[5], 0),
                "volume": int(safe_float(fields[8], 0)),
                "amount": safe_float(fields[9], 0),
            }

        # 缓存结果
        if quotes:
            set_cache(cache_key, quotes)

        return make_success_response({"quotes": quotes})

    except Exception as e:
        logger.error(f"批量获取股票行情失败 ({len(code_list)}个代码): {e}")
        raise HTTPException(status_code=500, detail="获取股票行情失败，请稍后重试")
