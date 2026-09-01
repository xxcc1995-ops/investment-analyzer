"""国债收益率服务 - 获取中美十年期国债收益率及股债比"""

import logging
import re
from typing import Dict, Optional

import akshare as ak
import requests

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}


def _get_latest_yield(df) -> Optional[Dict]:
    """从 DataFrame 提取最新收益率"""
    if df is None or df.empty:
        return None
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest
    return {
        "date": str(latest["date"]),
        "yield": round(float(latest["close"]), 3),
        "change": round(float(latest["close"]) - float(prev["close"]), 3),
        "open": round(float(latest["open"]), 3),
        "high": round(float(latest["high"]), 3),
        "low": round(float(latest["low"]), 3),
    }


def _get_cn_pe() -> Optional[float]:
    """获取沪深300市盈率"""
    try:
        df = ak.stock_zh_index_value_csindex(symbol='000300')
        if df is not None and not df.empty:
            return float(df.iloc[-1]['市盈率1'])
    except Exception as e:
        logger.warning(f"获取沪深300 PE失败: {e}")
    return None


def _get_us_pe() -> Optional[float]:
    """获取标普500市盈率"""
    try:
        resp = requests.get('https://www.multpl.com/s-p-500-pe-ratio', headers=HEADERS, timeout=15)
        match = re.search(r'id="current"[^>]*>(\d+\.\d+)', resp.text)
        if match:
            return float(match.group(1))
        match = re.search(r'Current S&P 500 PE Ratio.*?(\d+\.\d+)', resp.text, re.DOTALL)
        if match:
            return float(match.group(1))
    except Exception as e:
        logger.warning(f"获取标普500 PE失败: {e}")
    return None


def _enrich_bond_data(bond: Dict, pe: Optional[float]) -> Dict:
    """为债券数据添加PE、盈利收益率、股债比，以及「美债10Y − 盈利收益率」差值。

    差值 = 10年期国债收益率 − 标的指数盈利收益率(1/PE)。
    缩窄（长债降得快）→ 股权风险溢价上升 → 债市资金挤出流入股市 → 股市涨；
    走阔（盈利跌得更快）→ 长债降幅被盈利恶化抵消 → 高开低走 / 债涨股跌背离。
    """
    if bond is None:
        return None
    bond["pe"] = round(pe, 2) if pe else None
    if pe and bond["yield"] > 0:
        earnings_yield = (1 / pe) * 100
        bond["stock_bond_ratio"] = round(earnings_yield / bond["yield"], 2)
        bond["earnings_yield"] = round(earnings_yield, 2)
        # 差值 = 美债10年期收益率 − 标普500盈利收益率
        bond["spread"] = round(bond["yield"] - earnings_yield, 2)
    else:
        bond["stock_bond_ratio"] = None
        bond["earnings_yield"] = None
        bond["spread"] = None
    return bond


def get_bond_yields() -> Dict:
    """获取中美十年期国债收益率及股债比

    Returns:
        {
            "cn": { "date", "yield", "change", "pe", "stock_bond_ratio", ... } | None,
            "us": { "date", "yield", "change", "pe", "stock_bond_ratio", ... } | None,
            "error": str | None
        }
    """
    result = {"cn": None, "us": None, "error": None}

    # 中国十年期国债
    try:
        cn_df = ak.bond_gb_zh_sina()
        cn_bond = _get_latest_yield(cn_df)
        cn_pe = _get_cn_pe()
        result["cn"] = _enrich_bond_data(cn_bond, cn_pe)
    except Exception as e:
        logger.warning(f"获取中国国债收益率失败: {e}")
        result["error"] = f"中国: {e}"

    # 美国十年期国债
    try:
        us_df = ak.bond_gb_us_sina()
        us_bond = _get_latest_yield(us_df)
        us_pe = _get_us_pe()
        result["us"] = _enrich_bond_data(us_bond, us_pe)
    except Exception as e:
        logger.warning(f"获取美国国债收益率失败: {e}")
        result["error"] = (result["error"] or "") + f" 美国: {e}"

    return result
