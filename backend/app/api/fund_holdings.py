"""基金持仓分析API — 机构级标准

从东方财富获取LOF/开放式基金的持仓信息，提供五大分析维度：

1. 基金持仓数据（前N大重仓股，支持历史年份）
2. 行业配置分析（申万一级行业分布，集中度指标）
3. 持仓变动追踪（季度环比增减仓，新进/退出股票）
4. 重仓股分析（集中度、HHI、持仓稳定性评分）
5. 指数偏离度（与基准指数的行业/个股偏离）

数据特点：
- 持仓数据按季度披露，更新频率低 -> 缓存1小时
- 行业配置数据同上
- 支持按年份筛选历史持仓
- 返回可用年份列表供前端切换
"""

import logging
import math
import re
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.core.cache import TTL_DAILY, TTL_WEEKLY, get_cache, set_cache
from app.core.rate_limiter import eastmoney_limiter
from app.core.utils import safe_float

logger = logging.getLogger(__name__)

router = APIRouter()

# ==================== HTTP 会话 ====================

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


# ==================== 基准指数映射 ====================

# 常见基金类型 -> 基准指数代码（用于偏离度计算）
_BENCHMARK_MAP = {
    # 沪深300类
    "沪深300": "1.000300",
    "300": "1.000300",
    # 中证500类
    "中证500": "1.000905",
    "500": "1.000905",
    # 中证1000类
    "中证1000": "1.000852",
    "1000": "1.000852",
    # 创业板类
    "创业板": "0.399006",
    "创业板指": "0.399006",
    # 科创50
    "科创50": "1.000688",
    # 上证50
    "上证50": "1.000016",
    # 中证红利
    "中证红利": "1.000922",
    "红利": "1.000922",
    # 恒生指数
    "恒生指数": "100.HSI",
    # 纳斯达克100
    "纳斯达克": "100.NDX",
    "纳指": "100.NDX",
    "纳斯达克100": "100.NDX",
    # 标普500
    "标普500": "100.SPX",
    "标普": "100.SPX",
    # 中证消费
    "消费": "0.399967",
    "中证消费": "0.399967",
    # 医药
    "医药": "0.399933",
    "中证医药": "0.399933",
}


def _guess_benchmark(fund_name: str) -> Optional[str]:
    """根据基金名称猜测基准指数的secid"""
    for keyword, secid in _BENCHMARK_MAP.items():
        if keyword in fund_name:
            return secid
    return None


# ==================== HTML 解析 ====================

def _parse_holdings_html(html: str) -> List[Dict]:
    """解析东方财富基金持仓HTML数据

    从HTML表格中提取重仓股信息：序号、股票代码、股票名称、
    占净值比例、持股数、持仓市值、行业等。

    Args:
        html: 东方财富返回的HTML片段

    Returns:
        [{'rank', 'stock_code', 'stock_name', 'weight', 'shares',
          'market_value', 'market_code', 'report_date'}, ...]
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

            # 提取报告日期（从该行或附近文本）
            report_date = ""
            date_match = re.search(r"(\d{4}-\d{2}-\d{2})", row)
            if date_match:
                report_date = date_match.group(1)

            if rank and stock_code:
                holdings.append({
                    "rank": int(rank) if rank.isdigit() else 0,
                    "stock_code": stock_code,
                    "stock_name": stock_name,
                    "weight": safe_float(weight.replace("%", ""), 0.0) if weight else 0.0,
                    "shares": shares,
                    "market_value": market_value,
                    "market_code": market_code,
                    "report_date": report_date,
                })
        except Exception:
            continue

    return holdings


def _parse_industry_html(html: str) -> List[Dict]:
    """解析东方财富基金行业配置HTML数据

    从HTML表格中提取行业配置信息：行业名称、占净值比例等。

    Args:
        html: 东方财富返回的行业配置HTML片段

    Returns:
        [{'industry', 'weight', 'stock_count'}, ...]
    """
    industries = []
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL)

    for row in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
        if len(cells) < 3:
            continue

        try:
            def clean(text: str) -> str:
                return re.sub(r"<[^>]+>", "", text).strip()

            # 列顺序：行业名称, 占净值比例(%), 股票数
            industry_name = clean(cells[0])
            weight = clean(cells[1])
            stock_count = clean(cells[2]) if len(cells) > 2 else ""

            if industry_name and weight:
                industries.append({
                    "industry": industry_name,
                    "weight": safe_float(weight.replace("%", ""), 0.0) if weight else 0.0,
                    "stock_count": int(stock_count) if stock_count and stock_count.isdigit() else 0,
                })
        except Exception:
            continue

    return industries


# ==================== 数据获取层 ====================

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


def _fetch_fund_industry_allocation(fund_code: str) -> Dict:
    """从东方财富获取基金行业配置数据（带缓存和限流）

    使用 FundArchivesDatas.aspx?type=jjhy 接口。

    Args:
        fund_code: 纯数字基金代码

    Returns:
        {
            'fund_code': str,
            'report_date': str,
            'industries': [{'industry', 'weight', 'stock_count'}, ...],
            'total': int,
            'update_time': str,
        }
    """
    cache_key = f"fund_industry:{fund_code}"
    cached_data = get_cache(cache_key, TTL_DAILY)
    if cached_data is not None:
        return cached_data

    try:
        eastmoney_limiter.wait()

        url = "http://fundf10.eastmoney.com/FundArchivesDatas.aspx"
        params = {
            "type": "jjhy",
            "code": fund_code,
        }

        headers = {
            "Referer": f"http://fundf10.eastmoney.com/ccmx_{fund_code}.html",
        }

        resp = _session.get(url, params=params, headers=headers, timeout=15)
        resp.encoding = "utf-8"
        text = resp.text

        # 解析JavaScript响应
        content_match = re.search(r'content:"(.*?)",arryear', text, re.DOTALL)

        if not content_match:
            # 尝试匹配无arryear的格式
            content_match = re.search(r'content:"(.*?)"(?:,arryear|\})', text, re.DOTALL)

        if not content_match:
            logger.warning(f"基金 {fund_code} 行业配置数据解析失败，响应前200字符: {text[:200]}")
            return {
                "error": "无法解析行业配置数据",
                "fund_code": fund_code,
                "industries": [],
                "total": 0,
                "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

        html_content = content_match.group(1)
        html_content = html_content.replace('\\"', '"').replace("\\/", "/")

        industries = _parse_industry_html(html_content)

        # 提取报告期
        report_date = ""
        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", html_content)
        if date_match:
            report_date = date_match.group(1)

        result = {
            "fund_code": fund_code,
            "report_date": report_date,
            "industries": industries,
            "total": len(industries),
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        set_cache(cache_key, result)
        return result

    except Exception as e:
        logger.error(f"获取基金 {fund_code} 行业配置数据失败: {e}")
        return {
            "error": str(e),
            "fund_code": fund_code,
            "industries": [],
            "total": 0,
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }


def _fetch_fund_all_holdings(fund_code: str) -> Dict:
    """获取基金全部持仓（topline=9999），用于偏离度计算"""
    return _fetch_fund_holdings(fund_code, topline=9999)


def _fetch_index_constituents(secid: str) -> Dict:
    """从东方财富获取指数成分股权重数据

    使用push2行情API获取指数成分股列表和权重。

    Args:
        secid: 指数secid，如 '1.000300' (沪深300)

    Returns:
        {
            'secid': str,
            'name': str,
            'constituents': [{'stock_code', 'stock_name', 'weight'}, ...],
            'total': int,
            'update_time': str,
        }
    """
    cache_key = f"index_constituents:{secid}"
    cached_data = get_cache(cache_key, TTL_WEEKLY)
    if cached_data is not None:
        return cached_data

    try:
        eastmoney_limiter.wait()

        # 使用东方财富数据中心获取指数成分股
        url = "https://push2.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": 1,
            "pz": 500,
            "po": 1,
            "np": 1,
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": 2,
            "invt": 2,
            "fid": "f3",
            "fs": f"b:{secid.split('.')[1]}+f:!50" if '.' in secid else f"b:{secid}",
            "fields": "f12,f14,f2,f3,f20,f21",
        }

        # 尝试使用指数成分股接口
        em_code = secid.split(".")[-1] if "." in secid else secid
        market = secid.split(".")[0] if "." in secid else "1"

        # 东方财富指数成分股API
        url = "https://push2.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": 1,
            "pz": 1000,
            "po": 1,
            "np": 1,
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": 2,
            "invt": 2,
            "fid": "f3",
            "fs": f"ii:{em_code}",
            "fields": "f12,f14,f2,f3,f20,f21",
        }

        resp = _session.get(url, params=params, timeout=15)
        data = resp.json()

        rows = data.get("data", {}).get("diff", []) if data.get("data") else []

        constituents = []
        for row in rows:
            stock_code = row.get("f12", "")
            stock_name = row.get("f14", "")
            # f20 = 总市值, f21 = 流通市值 — 用于计算权重
            circ_cap = row.get("f21", 0) or 0

            if stock_code:
                constituents.append({
                    "stock_code": stock_code,
                    "stock_name": stock_name,
                    "circ_market_cap": circ_cap,
                    "weight": 0.0,  # 后续根据流通市值计算
                })

        # 根据流通市值计算权重占比
        total_circ = sum(c["circ_market_cap"] for c in constituents)
        if total_circ > 0:
            for c in constituents:
                c["weight"] = round(c["circ_market_cap"] / total_circ * 100, 2)

        result = {
            "secid": secid,
            "constituents": constituents,
            "total": len(constituents),
            "total_circ_cap": total_circ,
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        set_cache(cache_key, result)
        return result

    except Exception as e:
        logger.error(f"获取指数 {secid} 成分股失败: {e}")
        return {
            "error": str(e),
            "secid": secid,
            "constituents": [],
            "total": 0,
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }


# ==================== 分析计算层 ====================

def _compute_concentration(holdings: List[Dict]) -> Dict:
    """计算持仓集中度指标

    包括：
    - top5_weight / top10_weight: 前5/10大重仓股合计权重
    - hhi: 赫芬达尔指数 (Herfindahl-Hirschman Index)，衡量集中度
    - effective_n: 有效持仓数 = 1/HHI，等价于"均匀持有N只股票"
    - max_single_weight: 单只股票最大权重
    - concentration_level: 集中度评级 (高/中/低)

    Args:
        holdings: 持仓列表，每项含 'weight' 字段

    Returns:
        集中度指标字典
    """
    if not holdings:
        return {
            "top5_weight": 0,
            "top10_weight": 0,
            "hhi": 0,
            "effective_n": 0,
            "max_single_weight": 0,
            "max_single_stock": "",
            "concentration_level": "无数据",
            "total_stocks": 0,
        }

    weights = [h.get("weight", 0) for h in holdings if h.get("weight", 0) > 0]
    weights.sort(reverse=True)

    top5_weight = round(sum(weights[:5]), 2)
    top10_weight = round(sum(weights[:10]), 2)

    # HHI: 各股票权重的平方和（权重以百分比表示）
    hhi = round(sum((w / 100) ** 2 for w in weights) * 10000, 2)

    # 有效持仓数
    effective_n = round(10000 / hhi, 1) if hhi > 0 else 0

    # 最大单只权重
    max_weight = weights[0] if weights else 0
    max_stock = holdings[0].get("stock_name", "") if holdings else ""

    # 集中度评级
    if top5_weight >= 50:
        level = "高集中"
    elif top5_weight >= 30:
        level = "中等集中"
    else:
        level = "分散"

    return {
        "top5_weight": top5_weight,
        "top10_weight": top10_weight,
        "hhi": hhi,
        "effective_n": effective_n,
        "max_single_weight": max_weight,
        "max_single_stock": max_stock,
        "concentration_level": level,
        "total_stocks": len(weights),
    }


def _compute_holdings_change(
    current_holdings: List[Dict],
    previous_holdings: List[Dict],
) -> Dict:
    """计算持仓变动（季度环比）

    对比当前季度与上一季度的持仓，计算：
    - 增仓股票：权重上升的股票
    - 减仓股票：权重下降的股票
    - 新进股票：本季度新出现的股票
    - 退出股票：上季度有但本季度消失的股票
    - 换手率估算：基于进出股票数量

    Args:
        current_holdings: 当前季度持仓
        previous_holdings: 上一季度持仓

    Returns:
        持仓变动分析结果
    """
    if not current_holdings or not previous_holdings:
        return {
            "increased": [],
            "decreased": [],
            "new_entries": [],
            "exits": [],
            "turnover_estimate": 0,
            "current_report_date": current_holdings[0].get("report_date", "") if current_holdings else "",
            "previous_report_date": previous_holdings[0].get("report_date", "") if previous_holdings else "",
            "note": "缺少对比期间数据" if not previous_holdings else "",
        }

    # 建立代码->持仓映射
    current_map = {h["stock_code"]: h for h in current_holdings}
    previous_map = {h["stock_code"]: h for h in previous_holdings}

    current_codes = set(current_map.keys())
    previous_codes = set(previous_map.keys())

    # 增仓：两期都有，但权重上升
    increased = []
    for code in current_codes & previous_codes:
        cur_w = current_map[code].get("weight", 0)
        prev_w = previous_map[code].get("weight", 0)
        diff = round(cur_w - prev_w, 2)
        if diff > 0.1:  # 阈值0.1%避免噪音
            increased.append({
                "stock_code": code,
                "stock_name": current_map[code].get("stock_name", ""),
                "current_weight": cur_w,
                "previous_weight": prev_w,
                "weight_change": diff,
                "rank": current_map[code].get("rank", 0),
            })

    # 减仓：两期都有，但权重下降
    decreased = []
    for code in current_codes & previous_codes:
        cur_w = current_map[code].get("weight", 0)
        prev_w = previous_map[code].get("weight", 0)
        diff = round(cur_w - prev_w, 2)
        if diff < -0.1:
            decreased.append({
                "stock_code": code,
                "stock_name": current_map[code].get("stock_name", ""),
                "current_weight": cur_w,
                "previous_weight": prev_w,
                "weight_change": diff,
                "rank": current_map[code].get("rank", 0),
            })

    # 新进股票
    new_entries = []
    for code in current_codes - previous_codes:
        h = current_map[code]
        new_entries.append({
            "stock_code": code,
            "stock_name": h.get("stock_name", ""),
            "weight": h.get("weight", 0),
            "rank": h.get("rank", 0),
        })

    # 退出股票
    exits = []
    for code in previous_codes - current_codes:
        h = previous_map[code]
        exits.append({
            "stock_code": code,
            "stock_name": h.get("stock_name", ""),
            "previous_weight": h.get("weight", 0),
            "rank": h.get("rank", 0),
        })

    # 按变动幅度排序
    increased.sort(key=lambda x: x["weight_change"], reverse=True)
    decreased.sort(key=lambda x: x["weight_change"])

    # 换手率估算 = (新进权重 + 退出权重) / 2
    new_weight = sum(e["weight"] for e in new_entries)
    exit_weight = sum(e["previous_weight"] for e in exits)
    turnover_estimate = round((new_weight + exit_weight) / 2, 2)

    return {
        "increased": increased,
        "decreased": decreased,
        "new_entries": new_entries,
        "exits": exits,
        "turnover_estimate": turnover_estimate,
        "current_report_date": current_holdings[0].get("report_date", "") if current_holdings else "",
        "previous_report_date": previous_holdings[0].get("report_date", "") if previous_holdings else "",
    }


def _compute_index_deviation(
    fund_holdings: List[Dict],
    index_constituents: List[Dict],
) -> Dict:
    """计算基金持仓与基准指数的偏离度

    从两个维度衡量偏离：
    1. 个股偏离：基金重仓股在指数中的权重 vs 基金中的权重
    2. 行业偏离：基金整体行业配置 vs 指数行业配置（需要行业映射）

    由于我们没有逐只股票的行业分类数据，这里只做个股层面偏离。
    如果基金持有指数外的股票，标记为"主动偏离"。

    Args:
        fund_holdings: 基金持仓列表
        index_constituents: 指数成分股列表（含weight）

    Returns:
        偏离度分析结果
    """
    if not fund_holdings or not index_constituents:
        return {
            "available": False,
            "reason": "缺少基金持仓或指数成分股数据",
            "overweight": [],
            "underweight": [],
            "active_deviations": [],
            "tracking_error_estimate": 0,
            "index_coverage": 0,
        }

    # 指数成分股映射
    idx_map = {c["stock_code"]: c for c in index_constituents}
    idx_codes = set(idx_map.keys())

    overweight = []    # 超配：基金权重 > 指数权重
    underweight = []   # 低配：基金权重 < 指数权重（但在指数中）
    active_deviations = []  # 主动偏离：基金持有但指数中没有

    total_abs_deviation = 0

    for h in fund_holdings:
        code = h.get("stock_code", "")
        fund_weight = h.get("weight", 0)

        if code in idx_codes:
            idx_weight = idx_map[code].get("weight", 0)
            deviation = round(fund_weight - idx_weight, 2)
            total_abs_deviation += abs(deviation)

            entry = {
                "stock_code": code,
                "stock_name": h.get("stock_name", ""),
                "fund_weight": fund_weight,
                "index_weight": idx_weight,
                "deviation": deviation,
            }

            if deviation > 0.5:
                overweight.append(entry)
            elif deviation < -0.5:
                underweight.append(entry)
        else:
            # 基金持有但不在指数中 -> 主动偏离
            total_abs_deviation += fund_weight
            active_deviations.append({
                "stock_code": code,
                "stock_name": h.get("stock_name", ""),
                "fund_weight": fund_weight,
                "index_weight": 0,
                "deviation": fund_weight,
            })

    # 按偏离幅度排序
    overweight.sort(key=lambda x: x["deviation"], reverse=True)
    underweight.sort(key=lambda x: x["deviation"])
    active_deviations.sort(key=lambda x: x["deviation"], reverse=True)

    # 跟踪误差估算：基于持仓偏离度的标准差
    deviations = [abs(d) for d in
                  [h.get("weight", 0) - (idx_map.get(h.get("stock_code", ""), {}).get("weight", 0))
                   for h in fund_holdings]]
    tracking_error = round(math.sqrt(sum(d**2 for d in deviations) / len(deviations)), 2) if deviations else 0

    # 指数覆盖率：基金持仓中有多少在指数中
    covered = sum(1 for h in fund_holdings if h.get("stock_code", "") in idx_codes)
    coverage = round(covered / len(fund_holdings) * 100, 1) if fund_holdings else 0

    return {
        "available": True,
        "overweight": overweight[:15],   # 限制返回数量
        "underweight": underweight[:15],
        "active_deviations": active_deviations[:15],
        "total_abs_deviation": round(total_abs_deviation, 2),
        "tracking_error_estimate": tracking_error,
        "index_coverage": coverage,
        "fund_stock_count": len(fund_holdings),
        "index_stock_count": len(index_constituents),
    }


def _compute_industry_summary(industries: List[Dict]) -> Dict:
    """计算行业配置汇总指标

    Args:
        industries: 行业配置列表

    Returns:
        汇总指标
    """
    if not industries:
        return {
            "top3_industries": [],
            "top5_industries": [],
            "industry_hhi": 0,
            "industry_count": 0,
            "top3_weight": 0,
            "top5_weight": 0,
        }

    sorted_ind = sorted(industries, key=lambda x: x.get("weight", 0), reverse=True)
    weights = [i.get("weight", 0) for i in sorted_ind]

    top3 = sorted_ind[:3]
    top5 = sorted_ind[:5]

    # 行业HHI
    hhi = round(sum((w / 100) ** 2 for w in weights) * 10000, 2)

    return {
        "top3_industries": [
            {"industry": i["industry"], "weight": i["weight"]}
            for i in top3
        ],
        "top5_industries": [
            {"industry": i["industry"], "weight": i["weight"]}
            for i in top5
        ],
        "industry_hhi": hhi,
        "industry_count": len(industries),
        "top3_weight": round(sum(i["weight"] for i in top3), 2),
        "top5_weight": round(sum(i["weight"] for i in top5), 2),
    }


def _compute_stability_score(
    current_holdings: List[Dict],
    previous_holdings: List[Dict],
) -> Dict:
    """计算持仓稳定性评分

    基于以下维度评估基金经理的持仓稳定性：
    1. 重仓股保留率：前10大重仓股中有多少只保留
    2. 权重变化幅度：平均权重变动幅度
    3. 换手率估算

    评分范围: 0-100，越高越稳定

    Args:
        current_holdings: 当前季度持仓
        previous_holdings: 上一季度持仓

    Returns:
        稳定性评分
    """
    if not current_holdings or not previous_holdings:
        return {
            "score": 0,
            "level": "无数据",
            "top10_retention": 0,
            "avg_weight_change": 0,
        }

    current_map = {h["stock_code"]: h for h in current_holdings}
    previous_map = {h["stock_code"]: h for h in previous_holdings}

    # 前10大重仓股保留率
    current_top10 = {h["stock_code"] for h in current_holdings[:10]}
    previous_top10 = {h["stock_code"] for h in previous_holdings[:10]}
    retained = current_top10 & previous_top10
    retention = len(retained) / max(len(previous_top10), 1) * 100

    # 平均权重变化（仅对两期都有的股票）
    common_codes = set(current_map.keys()) & set(previous_map.keys())
    weight_changes = []
    for code in common_codes:
        cur_w = current_map[code].get("weight", 0)
        prev_w = previous_map[code].get("weight", 0)
        weight_changes.append(abs(cur_w - prev_w))
    avg_change = round(sum(weight_changes) / len(weight_changes), 2) if weight_changes else 0

    # 综合评分
    # 保留率贡献60分，权重稳定贡献40分
    retention_score = retention * 0.6
    stability_score = max(0, (1 - avg_change / 5) * 40)  # 权重变化5%以内满分
    total_score = round(retention_score + stability_score, 1)

    if total_score >= 80:
        level = "非常稳定"
    elif total_score >= 60:
        level = "较稳定"
    elif total_score >= 40:
        level = "一般"
    else:
        level = "高换手"

    return {
        "score": total_score,
        "level": level,
        "top10_retention": round(retention, 1),
        "avg_weight_change": avg_change,
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
    """
    fund_code = fund_code.strip()
    if not fund_code.isdigit() or len(fund_code) != 6:
        raise HTTPException(
            status_code=400,
            detail="基金代码格式无效，应为6位数字（如 161130）",
        )

    result = _fetch_fund_holdings(fund_code, topline, year)

    if result.get("error"):
        error_msg = result["error"]
        if "无法解析" in error_msg:
            raise HTTPException(status_code=404, detail=f"未找到基金 {fund_code} 的持仓数据")
        raise HTTPException(status_code=500, detail=f"获取持仓数据失败: {error_msg}")

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
    """获取基金可查询的年份列表"""
    fund_code = fund_code.strip()
    if not fund_code.isdigit() or len(fund_code) != 6:
        raise HTTPException(
            status_code=400,
            detail="基金代码格式无效，应为6位数字（如 161130）",
        )

    result = _fetch_fund_holdings(fund_code, topline=1)

    return {
        "error": False,
        "fund_code": fund_code,
        "available_years": result.get("available_years", []),
        "current_year": result.get("current_year"),
        "report_date": result.get("report_date", ""),
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


@router.get("/fund-holdings/{fund_code}/industry")
def get_fund_industry_allocation(fund_code: str):
    """获取基金行业配置分析

    返回基金的申万一级行业分布，包括：
    - 各行业权重占比
    - 行业集中度指标（HHI、前3/5行业权重）
    - 行业数量

    数据来源：东方财富 FundArchivesDatas.aspx?type=jjhy
    """
    fund_code = fund_code.strip()
    if not fund_code.isdigit() or len(fund_code) != 6:
        raise HTTPException(
            status_code=400,
            detail="基金代码格式无效，应为6位数字（如 161130）",
        )

    result = _fetch_fund_industry_allocation(fund_code)

    if result.get("error"):
        raise HTTPException(status_code=500, detail=f"获取行业配置数据失败: {result['error']}")

    summary = _compute_industry_summary(result["industries"])

    return {
        "error": False,
        "fund_code": fund_code,
        "report_date": result.get("report_date", ""),
        "industries": result["industries"],
        "total": result["total"],
        "summary": summary,
        "update_time": result["update_time"],
    }


@router.get("/fund-holdings/{fund_code}/changes")
def get_fund_holdings_changes(fund_code: str):
    """获取基金持仓变动分析

    对比当前季度与上一季度的持仓，返回：
    - 增仓股票（权重上升）
    - 减仓股票（权重下降）
    - 新进股票（本季度新出现）
    - 退出股票（上季度有但本季度消失）
    - 换手率估算
    - 持仓稳定性评分

    需要获取两个季度的数据，因此会发起两次请求。
    """
    fund_code = fund_code.strip()
    if not fund_code.isdigit() or len(fund_code) != 6:
        raise HTTPException(
            status_code=400,
            detail="基金代码格式无效，应为6位数字（如 161130）",
        )

    # 获取当前持仓
    current = _fetch_fund_holdings(fund_code, topline=9999)
    if current.get("error"):
        raise HTTPException(status_code=500, detail=f"获取当前持仓失败: {current['error']}")

    # 确定上一季度的年份
    available_years = current.get("available_years", [])
    current_year = current.get("current_year")
    current_report_date = current.get("report_date", "")

    # 从报告日期推断上一季度
    previous_holdings = []
    previous_report_date = ""

    if current_report_date:
        try:
            # 解析报告期，如 2024-12-31 -> 上一期为 2024-09-30
            rd = datetime.strptime(current_report_date, "%Y-%m-%d")
            quarter_ends = [
                (3, 31), (6, 30), (9, 30), (12, 31),
            ]
            # 找到当前报告期所在季度
            current_q = -1
            for i, (m, d) in enumerate(quarter_ends):
                if rd.month == m and rd.day == d:
                    current_q = i
                    break

            if current_q > 0:
                # 同年上一季度
                pm, pd = quarter_ends[current_q - 1]
                prev_year = rd.year
            elif current_q == 0:
                # 当前是Q1，上一季度是去年Q4
                pm, pd = 12, 31
                prev_year = rd.year - 1
            else:
                prev_year = None

            if prev_year is not None:
                # 获取上一年的数据（如果有）
                prev_data = _fetch_fund_holdings(fund_code, topline=9999, year=prev_year)
                if not prev_data.get("error"):
                    prev_holdings = prev_data.get("holdings", [])
                    # 找到报告期匹配的持仓
                    target_date = f"{prev_year}-{pm:02d}-{pd:02d}"
                    matched = [h for h in prev_holdings if h.get("report_date") == target_date]
                    if matched:
                        previous_holdings = matched
                        previous_report_date = target_date
                    elif prev_holdings:
                        # 如果没有精确匹配，使用最近的一期
                        # 按报告期排序，取最后出现的一组
                        dates = set(h.get("report_date", "") for h in prev_holdings)
                        if dates:
                            latest_prev = max(dates)
                            previous_holdings = [h for h in prev_holdings if h.get("report_date") == latest_prev]
                            previous_report_date = latest_prev

        except (ValueError, IndexError) as e:
            logger.warning(f"解析报告期失败: {e}")

    # 计算变动
    changes = _compute_holdings_change(current["holdings"], previous_holdings)

    # 计算稳定性评分
    stability = _compute_stability_score(current["holdings"], previous_holdings)

    return {
        "error": False,
        "fund_code": fund_code,
        "changes": changes,
        "stability": stability,
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


@router.get("/fund-holdings/{fund_code}/concentration")
def get_fund_concentration(fund_code: str):
    """获取基金持仓集中度分析

    返回：
    - 前5/10大重仓股合计权重
    - HHI赫芬达尔指数
    - 有效持仓数 (1/HHI)
    - 最大单只股票权重
    - 集中度评级

    使用全部持仓数据（topline=9999）计算。
    """
    fund_code = fund_code.strip()
    if not fund_code.isdigit() or len(fund_code) != 6:
        raise HTTPException(
            status_code=400,
            detail="基金代码格式无效，应为6位数字（如 161130）",
        )

    # 获取全部持仓
    result = _fetch_fund_holdings(fund_code, topline=9999)
    if result.get("error"):
        raise HTTPException(status_code=500, detail=f"获取持仓数据失败: {result['error']}")

    holdings = result.get("holdings", [])
    concentration = _compute_concentration(holdings)

    return {
        "error": False,
        "fund_code": fund_code,
        "report_date": result.get("report_date", ""),
        "concentration": concentration,
        "holdings": holdings[:20],  # 返回前20大供展示
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


@router.get("/fund-holdings/{fund_code}/deviation")
def get_fund_index_deviation(
    fund_code: str,
    benchmark: Optional[str] = Query(
        None,
        description="基准指数secid，如 1.000300(沪深300)。不填则自动根据基金名称推断。",
    ),
):
    """获取基金与基准指数的偏离度分析

    对比基金持仓与基准指数成分股，返回：
    - 超配股票（基金权重 > 指数权重）
    - 低配股票（基金权重 < 指数权重）
    - 主动偏离（基金持有但指数中没有）
    - 跟踪误差估算
    - 指数覆盖率

    Args:
        path fund_code: 基金代码
        query benchmark: 基准指数secid（可选，自动推断）
    """
    fund_code = fund_code.strip()
    if not fund_code.isdigit() or len(fund_code) != 6:
        raise HTTPException(
            status_code=400,
            detail="基金代码格式无效，应为6位数字（如 161130）",
        )

    # 获取基金全部持仓
    holdings_result = _fetch_fund_holdings(fund_code, topline=9999)
    if holdings_result.get("error"):
        raise HTTPException(status_code=500, detail=f"获取持仓数据失败: {holdings_result['error']}")

    fund_holdings = holdings_result.get("holdings", [])
    if not fund_holdings:
        raise HTTPException(status_code=404, detail=f"基金 {fund_code} 无持仓数据")

    # 确定基准指数
    if not benchmark:
        # 从基金名称推断
        fund_name = ""
        if fund_holdings:
            # 尝试从持仓数据中获取基金名称
            pass
        # 使用基金代码尝试获取基金名称
        try:
            eastmoney_limiter.wait()
            info_url = f"https://fundf10.eastmoney.com/jbgk_{fund_code}.html"
            resp = _session.get(info_url, timeout=10)
            resp.encoding = "utf-8"
            title_match = re.search(r"<title>(.*?)</title>", resp.text)
            if title_match:
                fund_name = title_match.group(1).split("-")[0].strip()
        except Exception:
            pass

        benchmark = _guess_benchmark(fund_name)
        if not benchmark:
            return {
                "error": False,
                "fund_code": fund_code,
                "deviation": {
                    "available": False,
                    "reason": f"无法自动推断基金 {fund_code} 的基准指数，请手动指定 benchmark 参数",
                    "fund_name": fund_name,
                },
                "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

    # 获取指数成分股
    index_result = _fetch_index_constituents(benchmark)
    if index_result.get("error"):
        return {
            "error": False,
            "fund_code": fund_code,
            "benchmark": benchmark,
            "deviation": {
                "available": False,
                "reason": f"获取指数 {benchmark} 成分股失败: {index_result['error']}",
            },
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    # 计算偏离度
    deviation = _compute_index_deviation(
        fund_holdings,
        index_result.get("constituents", []),
    )

    return {
        "error": False,
        "fund_code": fund_code,
        "benchmark": benchmark,
        "report_date": holdings_result.get("report_date", ""),
        "deviation": deviation,
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


@router.get("/fund-holdings/{fund_code}/full-analysis")
def get_fund_full_analysis(fund_code: str):
    """获取基金持仓全景分析（一次性返回所有维度）

    综合返回：
    1. 持仓数据（前10大重仓股）
    2. 行业配置分析
    3. 持仓集中度
    4. 持仓变动（如有历史数据）
    5. 稳定性评分

    注意：此接口会发起多次HTTP请求，响应时间较长。
    建议前端按需调用单独的子接口。
    """
    fund_code = fund_code.strip()
    if not fund_code.isdigit() or len(fund_code) != 6:
        raise HTTPException(
            status_code=400,
            detail="基金代码格式无效，应为6位数字（如 161130）",
        )

    # 并行获取数据
    holdings_result = _fetch_fund_holdings(fund_code, topline=9999)
    industry_result = _fetch_fund_industry_allocation(fund_code)

    holdings = holdings_result.get("holdings", [])
    top10 = holdings[:10] if holdings else []

    # 集中度
    concentration = _compute_concentration(holdings)

    # 行业汇总
    industry_summary = _compute_industry_summary(industry_result.get("industries", []))

    return {
        "error": False,
        "fund_code": fund_code,
        "report_date": holdings_result.get("report_date", ""),
        "holdings": {
            "top10": top10,
            "total_count": len(holdings),
            "available_years": holdings_result.get("available_years", []),
        },
        "industry": {
            "industries": industry_result.get("industries", []),
            "summary": industry_summary,
            "report_date": industry_result.get("report_date", ""),
        },
        "concentration": concentration,
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
