"""国债收益率 & 股债比 API 路由"""

from fastapi import APIRouter
from typing import Dict, Optional
import akshare as ak
import requests
import re
import logging

router = APIRouter()
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


@router.get("/yields")
def get_bond_yields():
    """获取中美十年期国债收益率及股债比"""
    result = {"cn": None, "us": None, "error": None}

    # 中国十年期国债
    try:
        cn_df = ak.bond_gb_zh_sina()
        cn_bond = _get_latest_yield(cn_df)
        cn_pe = _get_cn_pe()
        if cn_bond:
            cn_bond["pe"] = round(cn_pe, 2) if cn_pe else None
            # 股债比 = (1/PE) / 国债收益率 × 100
            if cn_pe and cn_bond["yield"] > 0:
                earnings_yield = (1 / cn_pe) * 100
                cn_bond["stock_bond_ratio"] = round(earnings_yield / cn_bond["yield"], 2)
                cn_bond["earnings_yield"] = round(earnings_yield, 2)
            else:
                cn_bond["stock_bond_ratio"] = None
                cn_bond["earnings_yield"] = None
        result["cn"] = cn_bond
    except Exception as e:
        logger.warning(f"获取中国国债收益率失败: {e}")
        result["error"] = f"中国: {e}"

    # 美国十年期国债
    try:
        us_df = ak.bond_gb_us_sina()
        us_bond = _get_latest_yield(us_df)
        us_pe = _get_us_pe()
        if us_bond:
            us_bond["pe"] = round(us_pe, 2) if us_pe else None
            if us_pe and us_bond["yield"] > 0:
                earnings_yield = (1 / us_pe) * 100
                us_bond["stock_bond_ratio"] = round(earnings_yield / us_bond["yield"], 2)
                us_bond["earnings_yield"] = round(earnings_yield, 2)
            else:
                us_bond["stock_bond_ratio"] = None
                us_bond["earnings_yield"] = None
        result["us"] = us_bond
    except Exception as e:
        logger.warning(f"获取美国国债收益率失败: {e}")
        result["error"] = (result["error"] or "") + f" 美国: {e}"

    return result
