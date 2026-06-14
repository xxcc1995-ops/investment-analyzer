"""QDII LOF基金EST净值估算 - 动态比率法（纯函数库）

API端点已迁移到 fund_arb.py，本文件仅保留辅助函数。
"""

import logging
from typing import Optional

from app.api.fund_utils import parse_underlying_price

logger = logging.getLogger(__name__)


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


# 注意：API端点已迁移到 fund_arb.py，本文件仅保留纯函数供 import
