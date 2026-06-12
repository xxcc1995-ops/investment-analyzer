"""基金持仓数据API

从东方财富获取LOF/开放式基金的持仓信息（前N大重仓股）。

数据特点：
- 持仓数据按季度披露，更新频率低 -> 缓存1小时
- 支持按年份筛选历史持仓
- 返回可用年份列表供前端切换
"""

import logging
import re
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.core.cache import TTL_DAILY, cached, get_cache, set_cache
from app.core.rate_limiter import eastmoney_limiter
from app.core.utils import safe_float

logger = logging.getLogger(__name__)

router = APIRouter()

# 共享HTTP会话
_session = requests.Session()
_adapter = HTTPAdapter(
    pool_connections=10,
    pool_maxsize=20,
    max_retries=Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
    ),
)
_session.mount("https://", _adapter)
_session.mount("http://", _adapter)
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
})


def _parse_holdings_html(html: str) -> List[Dict]:
    """解析东方财富基金持仓HTML数据

    从HTML表格中提取重仓股信息：序号、股票代码、股票名称、
    占净值比例、持股数、持仓市值等。

    Args:
        html: 东方财富返回的HTML片段

    Returns:
        [{'rank', 'stock_code', 'stock_name', 'weight', 'shares', 'market_value', 'market_code'}, ...]
    """
    holdings = []
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL)

    for row in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
        if len(cells) < 8:
            continue

        try:
            def clean(text: str) -> str:
                return re.sub(r"<[^>]+>", "", text).strip()

            rank = clean(cells[0])
            stock_code_raw = clean(cells[1])
            stock_name = clean(cells[2])
            weight = clean(cells[6])   # 占净值比例
            shares = clean(cells[7])   # 持股数
            market_value = clean(cells[8]) if len(cells) > 8 else ""

            # 从链接中提取股票代码
            code_match = re.search(r">([A-Z0-9]+)<", cells[1])
            stock_code = code_match.group(1) if code_match else stock_code_raw

            # 解析市场代码
            market_code = ""
            market_match = re.search(r"market=(\d+)", cells[1])
            if market_match:
                market_code = market_match.group(1)

            if rank and stock_code:
                holdings.append({
                    "rank": int(rank) if rank.isdigit() else 0,
                    "stock_code": stock_code,
                    "stock_name": stock_name,
                    "weight": weight.replace("%", "") if weight else "0",
                    "shares": shares,
                    "market_value": market_value,
                    "market_code": market_code,
                })
        except Exception:
            continue

    return holdings


def _fetch_fund_holdings(
    fund_code: str,
    topline: int = 10,
    year: Optional[int] = None,
) -> Dict:
    """从东方财富获取基金持仓数据（带缓存和限流）

    Args:
        fund_code: 纯数字基金代码，如 '161130'
        topline: 持仓数量限制，10=前十大，9999=全部
        year: 指定年份，None=最新

    Returns:
        {
            'fund_code': str,
            'report_date': str,
            'current_year': int,
            'available_years': [int, ...],
            'holdings': [...],
            'total': int,
            'update_time': str,
        }
        失败返回 {'error': str, 'holdings': [], 'available_years': []}
    """
    # 缓存键：基金代码 + 数量限制 + 年份
    cache_key = f"fund_holdings:{fund_code}:{topline}:{year or 'latest'}"
    cached_data = get_cache(cache_key, TTL_DAILY)
    if cached_data is not None:
        return cached_data

    try:
        eastmoney_limiter.wait()

        url = "http://fundf10.eastmoney.com/FundArchivesDatas.aspx"
        params = {
            "type": "jjcc",
            "code": fund_code,
            "topline": str(topline),
        }
        if year:
            params["year"] = str(year)

        headers = {
            "Referer": f"http://fundf10.eastmoney.com/ccmx_{fund_code}.html",
        }

        resp = _session.get(url, params=params, headers=headers, timeout=15)
        resp.encoding = "utf-8"
        text = resp.text

        # 解析JavaScript响应
        content_match = re.search(r'content:"(.*?)",arryear', text, re.DOTALL)
        years_match = re.search(r"arryear:\[(.*?)\]", text)
        curyear_match = re.search(r"curyear:(\d+)", text)

        if not content_match:
            error_result = {
                "error": "无法解析持仓数据",
                "fund_code": fund_code,
                "holdings": [],
                "available_years": [],
                "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            return error_result

        html_content = content_match.group(1)
        # 反转义HTML
        html_content = html_content.replace('\\"', '"').replace("\\/", "/")

        # 解析可用年份
        available_years: List[int] = []
        if years_match:
            years_str = years_match.group(1)
            available_years = [
                int(y.strip()) for y in years_str.split(",") if y.strip().isdigit()
            ]

        current_year = int(curyear_match.group(1)) if curyear_match else None

        # 解析持仓数据
        holdings = _parse_holdings_html(html_content)

        # 提取报告期
        report_date = ""
        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", html_content)
        if date_match:
            report_date = date_match.group(1)

        result = {
            "fund_code": fund_code,
            "report_date": report_date,
            "current_year": current_year,
            "available_years": available_years,
            "holdings": holdings,
            "total": len(holdings),
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        set_cache(cache_key, result)
        return result

    except Exception as e:
        logger.error(f"获取基金 {fund_code} 持仓数据失败: {e}")
        return {
            "error": str(e),
            "fund_code": fund_code,
            "holdings": [],
            "available_years": [],
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }


# ==================== API 端点 ====================


@router.get("/fund-holdings/{fund_code}")
def get_fund_holdings_api(
    fund_code: str,
    topline: int = Query(
        10,
        description="持仓数量，10=前十大，20=前二十，9999=全部",
        ge=1,
        le=9999,
    ),
    year: Optional[int] = Query(
        None,
        description="指定年份查询历史持仓，不填返回最新报告期",
        ge=2000,
        le=2030,
    ),
):
    """获取基金持仓数据

    从东方财富获取指定基金的重仓股持仓信息。
    数据按季度更新，缓存1小时。

    Args:
        path fund_code: 基金代码（纯数字，如 161130）
        query topline: 持仓数量限制，默认前10大
        query year: 指定年份（可选）

    Returns:
        {
            'error': False,
            'fund_code': str,
            'report_date': str,
            'available_years': [int, ...],
            'holdings': [...],
            'total': int,
            'update_time': str,
        }

    Raises:
        400: 基金代码格式无效
        500: 数据获取失败
    """
    # 参数验证
    fund_code = fund_code.strip()
    if not fund_code.isdigit() or len(fund_code) != 6:
        raise HTTPException(
            status_code=400,
            detail="基金代码格式无效，应为6位数字（如 161130）",
        )

    result = _fetch_fund_holdings(fund_code, topline, year)

    # 检查错误
    if result.get("error"):
        error_msg = result["error"]
        if "无法解析" in error_msg:
            raise HTTPException(status_code=404, detail=f"未找到基金 {fund_code} 的持仓数据")
        raise HTTPException(status_code=500, detail=f"获取持仓数据失败: {error_msg}")

    # 统一响应格式
    return {
        "error": False,
        "fund_code": result["fund_code"],
        "report_date": result["report_date"],
        "current_year": result.get("current_year"),
        "available_years": result["available_years"],
        "holdings": result["holdings"],
        "total": result["total"],
        "update_time": result["update_time"],
    }


@router.get("/fund-holdings/{fund_code}/years")
def get_fund_available_years(fund_code: str):
    """获取基金可查询的年份列表

    返回该基金在东方财富有持仓数据的所有年份，
    以及当前默认展示的年份（最新报告期所在年）。

    Args:
        path fund_code: 基金代码（纯数字）

    Returns:
        {
            'error': False,
            'fund_code': str,
            'available_years': [int, ...],
            'current_year': int,
            'report_date': str,
        }

    Raises:
        400: 基金代码格式无效
    """
    # 参数验证
    fund_code = fund_code.strip()
    if not fund_code.isdigit() or len(fund_code) != 6:
        raise HTTPException(
            status_code=400,
            detail="基金代码格式无效，应为6位数字（如 161130）",
        )

    # 只获取少量数据来提取年份信息
    result = _fetch_fund_holdings(fund_code, topline=1)

    return {
        "error": False,
        "fund_code": fund_code,
        "available_years": result.get("available_years", []),
        "current_year": result.get("current_year"),
        "report_date": result.get("report_date", ""),
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
