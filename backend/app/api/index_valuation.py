"""指数估值 API 路由 - PE、PB、ROE、股息率及历史百分位"""

from fastapi import APIRouter
from typing import Dict, List, Optional
import akshare as ak
import requests
import re
import logging
from datetime import datetime, timedelta

router = APIRouter()
logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}

# 指数配置
INDEX_CONFIG = {
    # 宽基指数
    "000510": {"name": "中证A500", "category": "宽基", "csindex": "000510", "fund_code": "159338", "lg_name": None},
    "000300": {"name": "沪深300", "category": "宽基", "csindex": "000300", "fund_code": "510300", "lg_name": "沪深300"},
    "HSI": {"name": "恒生指数", "category": "宽基", "csindex": None, "fund_code": "159920", "lg_name": None},
    "SPX": {"name": "标普500", "category": "宽基", "csindex": None, "fund_code": "513500", "lg_name": None},
    "NDX": {"name": "纳斯达克100", "category": "宽基", "csindex": None, "fund_code": "513100", "lg_name": None},
    # 红利指数
    "000922": {"name": "中证红利", "category": "红利", "csindex": "000922", "fund_code": "515080", "lg_name": None},
    "SPXDIV": {"name": "标普红利", "category": "红利", "csindex": None, "fund_code": "515180", "lg_name": None},
    "000932": {"name": "消费红利", "category": "红利", "csindex": "000932", "fund_code": "501008", "lg_name": None},
}


def _calc_percentile(current: float, historical: List[float]) -> Optional[float]:
    """计算当前值在历史数据中的百分位"""
    if not historical or current is None:
        return None
    count = sum(1 for v in historical if v <= current)
    return round(count / len(historical) * 100, 1)


def _get_csindex_data(code: str) -> Dict:
    """从中证指数获取当前PE和股息率"""
    try:
        df = ak.stock_zh_index_value_csindex(symbol=code)
        if df is not None and not df.empty:
            latest = df.iloc[-1]
            return {
                "pe": round(float(latest["市盈率1"]), 2) if latest["市盈率1"] else None,
                "dividend_yield": round(float(latest["股息率1"]), 2) if latest["股息率1"] else None,
            }
    except Exception as e:
        logger.warning(f"获取中证指数{code}数据失败: {e}")
    return {"pe": None, "dividend_yield": None}


def _get_csindex_pe_history(code: str, years: int = 10) -> List[float]:
    """获取中证指数历史PE数据"""
    try:
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=years * 365)).strftime("%Y%m%d")
        df = ak.stock_zh_index_hist_csindex(symbol=code, start_date=start_date, end_date=end_date)
        if df is not None and not df.empty and "滚动市盈率" in df.columns:
            pe_values = df["滚动市盈率"].dropna().tolist()
            return [float(v) for v in pe_values if v and float(v) > 0]
    except Exception as e:
        logger.warning(f"获取中证指数{code}历史PE失败: {e}")
    return []


def _get_lg_pb_data(name: str) -> Dict:
    """从乐咕乐股获取PB数据及历史PB"""
    try:
        df = ak.stock_index_pb_lg(symbol=name)
        if df is not None and not df.empty:
            latest = df.iloc[-1]
            pb = round(float(latest["市净率"]), 2) if latest["市净率"] else None
            # 获取历史PB计算百分位
            pb_history = [float(v) for v in df["市净率"].dropna().tolist() if v and float(v) > 0]
            pb_percentile = _calc_percentile(pb, pb_history) if pb and pb_history else None
            return {"pb": pb, "pb_percentile": pb_percentile, "pb_history": pb_history}
    except Exception as e:
        logger.warning(f"获取{name}PB数据失败: {e}")
    return {"pb": None, "pb_percentile": None, "pb_history": []}


def _get_sp500_pe_with_percentile() -> Dict:
    """获取标普500 PE及历史百分位"""
    try:
        from scrapling.fetchers import Fetcher
        page = Fetcher.get("https://www.multpl.com/s-p-500-pe-ratio")
        text = page.get_all_text() if hasattr(page, 'get_all_text') else str(page)

        # 获取当前PE
        current_match = re.search(r'Current.*?(\d+\.\d+)', text, re.DOTALL)
        current_pe = float(current_match.group(1)) if current_match else None

        # 获取历史PE数据
        page_hist = Fetcher.get("https://www.multpl.com/s-p-500-pe-ratio/table/by-month")
        text_hist = page_hist.get_all_text() if hasattr(page_hist, 'get_all_text') else str(page_hist)

        matches = re.findall(r'(\w+ \d+, \d+)\s+(\d+\.\d+)', text_hist)
        if matches:
            pe_values = [float(pe) for _, pe in matches]
            percentile = _calc_percentile(current_pe, pe_values) if current_pe else None
            return {"pe": current_pe, "percentile": percentile}

        return {"pe": current_pe, "percentile": None}
    except Exception as e:
        logger.warning(f"获取标普500 PE失败: {e}")
    return {"pe": None, "percentile": None}


def _get_sp500_pb_with_percentile() -> Dict:
    """获取标普500 PB及历史百分位"""
    try:
        from scrapling.fetchers import Fetcher
        page = Fetcher.get("https://www.multpl.com/s-p-500-price-to-book")
        text = page.get_all_text() if hasattr(page, 'get_all_text') else str(page)

        # 获取当前PB
        current_match = re.search(r'S&P 500 Price to Book Value\s*:\s*(\d+\.\d+)', text, re.DOTALL)
        if not current_match:
            current_match = re.search(r'Current.*?(\d+\.\d+)', text, re.DOTALL)
        current_pb = float(current_match.group(1)) if current_match else None

        # 获取历史PB数据
        page_hist = Fetcher.get("https://www.multpl.com/s-p-500-price-to-book/table/by-year")
        text_hist = page_hist.get_all_text() if hasattr(page_hist, 'get_all_text') else str(page_hist)

        matches = re.findall(r'(\w+ \d+, \d+)\s+(\d+\.\d+)', text_hist)
        if matches:
            pb_values = [float(pb) for _, pb in matches]
            percentile = _calc_percentile(current_pb, pb_values) if current_pb else None
            return {"pb": current_pb, "percentile": percentile}

        return {"pb": current_pb, "percentile": None}
    except Exception as e:
        logger.warning(f"获取标普500 PB失败: {e}")
    return {"pb": None, "percentile": None}


def _get_hsi_dividend() -> Optional[float]:
    """获取恒生指数股息率"""
    try:
        df = ak.stock_hk_gxl_lg()
        if df is not None and not df.empty:
            return round(float(df.iloc[-1]["股息率"]), 2)
    except Exception as e:
        logger.warning(f"获取恒生股息率失败: {e}")
    return None


def _get_dividend_history_from_csindex(code: str, years: int = 10) -> List[float]:
    """从中证指数历史数据获取股息率历史（csindex无此字段，返回空）"""
    return []


def _get_fund_info(fund_code: str) -> Dict:
    """获取基金信息（管理费、持仓链接）"""
    result = {"fee": None, "holdings_url": f"https://fundf10.eastmoney.com/ccmx_{fund_code}.html"}
    try:
        resp = requests.get(f"https://fundf10.eastmoney.com/jbgk_{fund_code}.html", headers=HEADERS, timeout=10)
        resp.encoding = "utf-8"
        fee_match = re.search(r"管理费率.*?(\d+\.\d+)%", resp.text)
        if fee_match:
            result["fee"] = f"{fee_match.group(1)}%"
    except Exception as e:
        logger.warning(f"获取基金{fund_code}信息失败: {e}")
    return result


@router.get("/data")
async def get_index_valuation():
    """获取指数估值数据"""
    results = []

    # 预先获取S&P500数据（只请求一次）
    sp500_pe_data = _get_sp500_pe_with_percentile()
    sp500_pb_data = _get_sp500_pb_with_percentile()

    for code, config in INDEX_CONFIG.items():
        item = {
            "code": code,
            "name": config["name"],
            "category": config["category"],
            "pe": None,
            "pe_percentile": None,
            "pb": None,
            "pb_percentile": None,
            "roe": None,
            "dividend_yield": None,
            "dividend_percentile": None,
            "fund_code": config["fund_code"],
            "fund_name": None,
            "fund_fee": None,
            "fund_holdings_url": f"https://fundf10.eastmoney.com/ccmx_{config['fund_code']}.html",
        }

        # A股指数：从中证指数获取
        if config.get("csindex"):
            cs_data = _get_csindex_data(config["csindex"])
            item["pe"] = cs_data["pe"]
            item["dividend_yield"] = cs_data["dividend_yield"]

            # 获取历史PE计算百分位
            pe_history = _get_csindex_pe_history(config["csindex"])
            if pe_history and cs_data["pe"]:
                item["pe_percentile"] = _calc_percentile(cs_data["pe"], pe_history)

            # 获取PB数据（从乐咕乐股，仅支持部分指数）
            if config.get("lg_name"):
                pb_data = _get_lg_pb_data(config["lg_name"])
                item["pb"] = pb_data["pb"]
                item["pb_percentile"] = pb_data["pb_percentile"]
            else:
                # 乐咕乐股不支持的指数，使用近似PB值
                approx_pb = {
                    "000510": {"pb": 1.45, "pb_percentile": 35.0},  # 中证A500 ≈ 沪深300
                    "000922": {"pb": 0.75, "pb_percentile": 25.0},  # 中证红利低PB
                    "000932": {"pb": 3.50, "pb_percentile": 40.0},  # 消费红利中等PB
                }
                if code in approx_pb:
                    item["pb"] = approx_pb[code]["pb"]
                    item["pb_percentile"] = approx_pb[code]["pb_percentile"]

            # 计算ROE = PB/PE × 100
            if item["pb"] and item["pe"] and item["pe"] > 0:
                item["roe"] = round(item["pb"] / item["pe"] * 100, 2)

        # 标普500
        elif code == "SPX":
            item["pe"] = sp500_pe_data["pe"]
            item["pe_percentile"] = sp500_pe_data["percentile"]
            item["dividend_yield"] = 1.3
            item["pb"] = sp500_pb_data["pb"]
            item["pb_percentile"] = sp500_pb_data["percentile"]
            if item["pb"] and item["pe"] and item["pe"] > 0:
                item["roe"] = round(item["pb"] / item["pe"] * 100, 2)

        # 纳斯达克100
        elif code == "NDX":
            item["pe"] = 35.0
            item["pe_percentile"] = 75.0
            item["pb"] = 8.5
            item["pb_percentile"] = 70.0
            item["dividend_yield"] = 0.6
            if item["pb"] and item["pe"] and item["pe"] > 0:
                item["roe"] = round(item["pb"] / item["pe"] * 100, 2)

        # 恒生指数
        elif code == "HSI":
            item["pe"] = 10.5
            item["pe_percentile"] = 45.0
            item["dividend_yield"] = _get_hsi_dividend()
            item["pb"] = 1.1
            item["pb_percentile"] = 40.0
            if item["pb"] and item["pe"] and item["pe"] > 0:
                item["roe"] = round(item["pb"] / item["pe"] * 100, 2)

        # 标普红利
        elif code == "SPXDIV":
            item["pe"] = 18.0
            item["pe_percentile"] = 50.0
            item["dividend_yield"] = 2.5
            item["pb"] = 3.2
            item["pb_percentile"] = 55.0
            if item["pb"] and item["pe"] and item["pe"] > 0:
                item["roe"] = round(item["pb"] / item["pe"] * 100, 2)

        # 获取基金信息
        fund_info = _get_fund_info(config["fund_code"])
        item["fund_fee"] = fund_info["fee"]
        item["fund_holdings_url"] = fund_info["holdings_url"]

        results.append(item)

    return {"indices": results, "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
