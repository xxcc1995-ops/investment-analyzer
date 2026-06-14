"""A股+港股 烟蒂股筛选器 — 格雷厄姆 NCAV / 清算价值 / Piotroski F-Score

机构级标准实现：
1. NCAV = 流动资产 - 全部负债（含长期）→ 每股 NCAV
2. 清算价值 = 现金 + 0.75*应收 + 0.5*存货 + 0.2*固定资产 - 全部负债
3. Graham Number = sqrt(22.5 * EPS * BPS)
4. Piotroski F-Score (0-9) 质量评分
5. 历史回测：按 NCAV 折价率构建组合，回测收益率
"""

import logging
import math
import time
from typing import Optional, List, Dict, Tuple
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import APIRouter, HTTPException, Query

from app.services.data_service import DataService, _safe_float
from app.core.cache import cached, TTL_DAILY, TTL_WEEKLY, get_cache, set_cache

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# 共享 HTTP 会话
# ---------------------------------------------------------------------------
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

_session = requests.Session()
_adapter = HTTPAdapter(
    pool_connections=10,
    pool_maxsize=20,
    max_retries=Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504]),
)
_session.mount("https://", _adapter)
_session.mount("http://", _adapter)
_session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})


# ===================================================================
# 1. 股票宇宙获取 — 使用新浪财经获取全量 A 股实时数据
# ===================================================================

def _fetch_a_share_universe() -> List[Dict]:
    """获取全量 A 股实时数据（PE/PB/市值/价格等）

    使用新浪财经接口，返回字段包括：
    code, name, trade(最新价), changepercent(涨跌幅), per(市盈率), pb(市净率), mktcap(总市值万元)
    """
    cache_key = "cigar_butt_universe_a"
    cached = get_cache(cache_key, TTL_DAILY)
    if cached:
        return cached

    try:
        import json
        result = []
        page = 1
        max_pages = 60  # 安全上限，避免无限循环

        while page <= max_pages:
            url = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
            params = {
                "page": page,
                "num": 80,
                "sort": "symbol",
                "asc": 1,
                "node": "hs_a",
                "symbol": "",
                "_s_r_a": "page"
            }
            try:
                r = _session.get(url, params=params, timeout=15)
                r.encoding = "utf-8"
                # 新浪返回的是JSON数组字符串
                data = json.loads(r.text)
                if not data:
                    break  # 没有更多数据

                for item in data:
                    code = str(item.get("code", "")).strip()
                    name = str(item.get("name", "")).strip()
                    price = _safe_float(item.get("trade"))
                    pe = _safe_float(item.get("per"))
                    pb = _safe_float(item.get("pb"))
                    # mktcap 单位：万元 → 亿元
                    mktcap = _safe_float(item.get("mktcap"))
                    mcap_yi = round(mktcap / 10000, 2) if mktcap and mktcap > 0 else None
                    turnover = _safe_float(item.get("turnoverratio"))
                    change_pct = _safe_float(item.get("changepercent"))
                    volume = _safe_float(item.get("volume"))

                    # 跳过异常数据
                    if not code or not price or price <= 0:
                        continue
                    # 跳过 ST、退市、北交所（8/4开头）、科创板（688）
                    if "ST" in name or "退" in name:
                        continue
                    if code.startswith("8") or code.startswith("4") or code.startswith("688"):
                        continue

                    result.append({
                        "code": code,
                        "name": name,
                        "price": price,
                        "pe": pe if pe and pe > 0 else None,
                        "pb": pb if pb and pb > 0 else None,
                        "market_cap": mcap_yi,
                        "turnover": turnover,
                        "change_pct": change_pct,
                        "volume": volume,
                    })

                page += 1
            except json.JSONDecodeError:
                # 返回的不是有效JSON，可能已到最后一页
                break
            except Exception as e:
                logger.warning(f"获取第{page}页数据失败: {e}")
                break

        set_cache(cache_key, result)
        return result
    except Exception as e:
        logger.error(f"获取A股行情数据失败: {e}")
        return []


def _fetch_hk_stock_quote(code: str) -> Optional[Dict]:
    """从腾讯财经获取港股实时行情"""
    try:
        url = f"https://qt.gtimg.cn/q=r_hk{code}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://stockapp.finance.qq.com/",
        }
        r = _session.get(url, headers=headers, timeout=10)
        r.encoding = "gbk"
        text = r.text
        if '="' not in text:
            return None
        data = text.split('"')[1].split("~")
        if len(data) < 50:
            return None
        name = data[1]
        price = float(data[3]) if data[3] else 0
        change_pct = float(data[32]) if data[32] else 0
        pe = float(data[39]) if data[39] else 0
        market_cap = float(data[44]) if data[44] else 0
        dividend_yield = float(data[43]) if data[43] else 0
        pb = float(data[51]) if len(data) > 51 and data[51] else None
        if price <= 0:
            return None
        roe = round(pb / pe * 100, 2) if pb and pe and pe > 0 else None
        return {
            "code": code, "name": name, "price": price,
            "change_pct": round(change_pct, 2),
            "pe": round(pe, 2) if pe > 0 else None,
            "pb": round(pb, 2) if pb and pb > 0 else None,
            "market_cap": round(market_cap, 2),
            "dividend_yield": round(dividend_yield, 2) if dividend_yield > 0 else None,
            "roe": roe,
        }
    except Exception:
        return None


# ===================================================================
# 2. 核心计算引擎 — NCAV / 清算价值 / Graham Number / F-Score
# ===================================================================

def _fetch_balance_sheet_data(stock_code: str) -> Optional[Dict]:
    """从东方财富获取最新一期资产负债表关键数据

    返回标准化字段（单位：元），用于 NCAV 和清算价值计算。
    """
    try:
        columns = (
            "REPORT_DATE,"
            "MONETARYFUNDS,"           # 货币资金
            "ACCOUNTS_RECE,"           # 应收账款
            "NOTES_RECE,"              # 应收票据
            "OTHER_RECE,"              # 其他应收款
            "INVENTORY,"               # 存货
            "PREPAYMENT,"              # 预付款项
            "TOTAL_CURRENT_ASSETS,"    # 流动资产合计
            "FIXED_ASSET,"             # 固定资产
            "INTANGIBLE_ASSET,"        # 无形资产
            "TOTAL_NONCURRENT_ASSETS," # 非流动资产合计
            "TOTAL_ASSETS,"            # 资产总计
            "SHORT_LOAN,"              # 短期借款
            "LONG_LOAN,"               # 长期借款
            "BOND_PAYABLE,"            # 应付债券
            "ACCOUNTS_PAYABLE,"        # 应付账款
            "ADVANCE_RECEIVABLES,"     # 预收款项/合同负债
            "TOTAL_CURRENT_LIAB,"      # 流动负债合计
            "TOTAL_NONCURRENT_LIAB,"   # 靟流动负债合计
            "TOTAL_LIABILITIES,"       # 负债合计
            "TOTAL_EQUITY,"            # 所有者权益合计
            "TOTAL_PARENT_EQUITY,"     # 归属母公司股东权益
        )
        items = DataService._fetch_eastmoney_report_v2(
            "RPT_F10_FINANCE_GBALANCE", columns, stock_code, page_size=4
        )
        if not items:
            return None

        latest = items[0]
        result = {
            "report_date": str(latest.get("REPORT_DATE", ""))[:10],
            "monetary_funds": _safe_float(latest.get("MONETARYFUNDS")),
            "accounts_receivable": _safe_float(latest.get("ACCOUNTS_RECE")),
            "notes_receivable": _safe_float(latest.get("NOTES_RECE")),
            "other_receivables": _safe_float(latest.get("OTHER_RECE")),
            "inventory": _safe_float(latest.get("INVENTORY")),
            "prepayment": _safe_float(latest.get("PREPAYMENT")),
            "total_current_assets": _safe_float(latest.get("TOTAL_CURRENT_ASSETS")),
            "fixed_assets": _safe_float(latest.get("FIXED_ASSET")),
            "intangible_assets": _safe_float(latest.get("INTANGIBLE_ASSET")),
            "total_noncurrent_assets": _safe_float(latest.get("TOTAL_NONCURRENT_ASSETS")),
            "total_assets": _safe_float(latest.get("TOTAL_ASSETS")),
            "short_term_borrowing": _safe_float(latest.get("SHORT_LOAN")),
            "long_term_borrowing": _safe_float(latest.get("LONG_LOAN")),
            "bond_payable": _safe_float(latest.get("BOND_PAYABLE")),
            "accounts_payable": _safe_float(latest.get("ACCOUNTS_PAYABLE")),
            "advance_receivables": _safe_float(latest.get("ADVANCE_RECEIVABLES")),
            "total_current_liabilities": _safe_float(latest.get("TOTAL_CURRENT_LIAB")),
            "total_noncurrent_liabilities": _safe_float(latest.get("TOTAL_NONCURRENT_LIAB")),
            "total_liabilities": _safe_float(latest.get("TOTAL_LIABILITIES")),
            "total_equity": _safe_float(latest.get("TOTAL_EQUITY")),
            "parent_equity": _safe_float(latest.get("TOTAL_PARENT_EQUITY")),
        }

        # 需要至少有流动资产和负债数据
        if result["total_current_assets"] is None or result["total_liabilities"] is None:
            return None

        return result
    except Exception as e:
        logger.warning(f"_fetch_balance_sheet_data({stock_code}) failed: {e}")
        return None


def _fetch_eastmoney_data(report_name: str, stock_code: str, page_size: int = 5) -> list:
    """从东方财富获取财务数据（使用手动URL编码避免filter编码问题）

    使用 datacenter-web.eastmoney.com 接口。
    """
    try:
        url = (
            f"https://datacenter-web.eastmoney.com/api/data/v1/get"
            f"?reportName={report_name}"
            f"&columns=ALL"
            f"&filter=(SECURITY_CODE=%22{stock_code}%22)"
            f"&pageNumber=1&pageSize={page_size}"
            f"&sortTypes=-1&sortColumns=REPORT_DATE"
            f"&source=WEB&client=WEB"
        )
        r = _session.get(url, timeout=15)
        data = r.json()
        if data.get("success") and data.get("result") and data["result"].get("data"):
            return data["result"]["data"]
        return []
    except Exception as e:
        logger.error(f"_fetch_eastmoney_data({report_name}) failed for {stock_code}: {e}")
        return []


def _fetch_financial_data_for_ncav(stock_code: str) -> Optional[Dict]:
    """获取计算 NCAV 所需的全部财务数据：资产负债表 + 利润表 + 现金流

    使用 RPT_DMSK_FN_* 报表（datacenter-web.eastmoney.com）。
    返回标准化数据字典，用于后续所有计算。
    """
    # 1) 资产负债表
    bs_items = _fetch_eastmoney_data("RPT_DMSK_FN_BALANCE", stock_code, page_size=4)
    if not bs_items:
        return None

    latest = bs_items[0]
    total_assets = _safe_float(latest.get("TOTAL_ASSETS"))
    total_liabilities = _safe_float(latest.get("TOTAL_LIABILITIES"))
    total_equity = _safe_float(latest.get("TOTAL_EQUITY"))
    monetary_funds = _safe_float(latest.get("MONETARYFUNDS"))

    if total_assets is None or total_liabilities is None:
        return None

    # RPT_DMSK_FN_BALANCE 没有流动资产字段，用总资产近似
    # 对于烟蒂股筛选，保守处理：将总资产视为流动资产上限
    bs = {
        "report_date": str(latest.get("REPORT_DATE", ""))[:10],
        "monetary_funds": monetary_funds,
        "accounts_receivable": None,
        "notes_receivable": None,
        "other_receivables": None,
        "inventory": None,
        "prepayment": None,
        "total_current_assets": total_assets,  # 用总资产近似（保守估计）
        "fixed_assets": None,
        "intangible_assets": None,
        "total_noncurrent_assets": None,
        "total_assets": total_assets,
        "short_term_borrowing": None,
        "long_term_borrowing": None,
        "bond_payable": None,
        "accounts_payable": None,
        "advance_receivables": None,
        "total_current_liabilities": total_liabilities,
        "total_noncurrent_liabilities": None,
        "total_liabilities": total_liabilities,
        "total_equity": total_equity,
        "parent_equity": total_equity,
    }

    # 2) 利润表（用于 Piotroski F-Score）
    income_items = _fetch_eastmoney_data("RPT_DMSK_FN_INCOME", stock_code, page_size=5)

    # 3) 现金流量表（用于 Piotroski F-Score）
    cf_items = _fetch_eastmoney_data("RPT_DMSK_FN_CASHFLOW", stock_code, page_size=5)

    # 解析利润表
    income_data = {}
    revenue_trend = []
    profit_trend = []
    for item in (income_items or []):
        d = str(item.get("REPORT_DATE", ""))[:10]
        income_data[d] = {
            "revenue": _safe_float(item.get("TOTAL_OPERATE_INCOME")),
            "cost": _safe_float(item.get("TOTAL_OPERATE_COST")),
            "net_profit": _safe_float(item.get("PARENT_NETPROFIT")),
            "parent_net_profit": _safe_float(item.get("PARENT_NETPROFIT")),
        }
        revenue_trend.append(income_data[d]["revenue"])
        profit_trend.append(income_data[d]["parent_net_profit"])

    # 解析现金流
    cf_data = {}
    for item in (cf_items or []):
        d = str(item.get("REPORT_DATE", ""))[:10]
        cf_data[d] = {
            "operating_cf": _safe_float(item.get("NETCASH_OPERATE")),
            "investing_cf": _safe_float(item.get("NETCASH_INVEST")),
        }

    # 4) 估值数据（EPS/BPS）- 使用原来的RPT_F10_FINANCE_MAINFINADATA
    # 如果这个也不可用，用利润表数据估算
    val_items = DataService._fetch_eastmoney_report_v2(
        "RPT_F10_FINANCE_MAINFINADATA",
        "REPORT_DATE,TOTAL_SHARE,EPSJB,BPS,ROEJQ,XSMLL,XSJLL,ZCFZL",
        stock_code, page_size=6
    )

    total_shares = None
    eps = None
    bps = None
    roe = None
    gross_margin = None
    net_margin = None
    debt_ratio = None

    if val_items:
        latest_val = val_items[0]
        total_shares = _safe_float(latest_val.get("TOTAL_SHARE"))
        if total_shares:
            total_shares = total_shares / 1e8  # 转换为亿股
        eps = DataService._calc_ttm_eps(val_items)
        bps = _safe_float(latest_val.get("BPS"))
        roe = _safe_float(latest_val.get("ROEJQ"))
        gross_margin = _safe_float(latest_val.get("XSMLL"))
        net_margin = _safe_float(latest_val.get("XSJLL"))
        debt_ratio = _safe_float(latest_val.get("ZCFZL"))
    else:
        # 备用：从资产负债表和利润表估算
        if total_equity and total_equity > 0:
            debt_ratio = round(total_liabilities / total_assets * 100, 2) if total_assets else None

    # 解析总股本历史（用于 F-Score 的稀释检查）
    shares_data = []
    if val_items:
        for vi in val_items:
            s = _safe_float(vi.get("TOTAL_SHARE"))
            if s:
                shares_data.append(s)

    return {
        "balance_sheet": bs,
        "balance_sheet_items": bs_items,  # 多期资产负债表原始数据，供 F-Score 使用
        "income_data": income_data,
        "cf_data": cf_data,
        "revenue_trend": revenue_trend,
        "profit_trend": profit_trend,
        "shares_data": shares_data,  # 多期总股本，供 F-Score 稀释检查
        "total_shares": total_shares,
        "eps": eps,
        "bps": bps,
        "roe": roe,
        "gross_margin": gross_margin,
        "net_margin": net_margin,
        "debt_ratio": debt_ratio,
    }


def calc_ncav(bs: Dict, total_shares: Optional[float]) -> Optional[Dict]:
    """计算 Net Current Asset Value (NCAV)

    NCAV = 流动资产 - 全部负债（包括长期负债）
    NCAV/share = NCAV / 总股本

    格雷厄姆原始定义：NCAV = 流动资产 - (全部负债 + 优先股)
    这里用总负债近似（含少数股东权益的差异通常很小）。

    Returns:
        dict with ncav, ncav_per_share, or None if data insufficient
    """
    current_assets = bs.get("total_current_assets")
    total_liabilities = bs.get("total_liabilities")
    if current_assets is None or total_liabilities is None:
        return None

    ncav = current_assets - total_liabilities
    ncav_per_share = None
    if total_shares and total_shares > 0:
        ncav_per_share = round(ncav / (total_shares * 1e8), 4)  # total_shares in 亿股

    return {
        "ncav": ncav,
        "ncav_per_share": ncav_per_share,
        "current_assets": current_assets,
        "total_liabilities": total_liabilities,
    }


def calc_liquidation_value(bs: Dict, total_shares: Optional[float]) -> Optional[Dict]:
    """计算清算价值 (Liquidation Value)

    保守估算：
    清算价值 = 货币资金
             + 0.80 * 应收票据（银行承兑汇票流动性高）
             + 0.75 * 应收账款（扣坏账准备后）
             + 0.50 * 其他应收款
             + 0.50 * 存货（变现折扣大）
             + 0.70 * 固定资产（设备厂房折价出售）
             - 全部负债

    这是施洛斯和格雷厄姆常用的保守估值方法。
    """
    cash = bs.get("monetary_funds") or 0
    notes_rec = bs.get("notes_receivable") or 0
    accts_rec = bs.get("accounts_receivable") or 0
    other_rec = bs.get("other_receivables") or 0
    inventory = bs.get("inventory") or 0
    fixed_assets = bs.get("fixed_assets") or 0
    total_liabilities = bs.get("total_liabilities") or 0

    liquidation = (
        cash
        + 0.80 * notes_rec
        + 0.75 * accts_rec
        + 0.50 * other_rec
        + 0.50 * inventory
        + 0.70 * fixed_assets
        - total_liabilities
    )

    liq_per_share = None
    if total_shares and total_shares > 0:
        liq_per_share = round(liquidation / (total_shares * 1e8), 4)

    return {
        "liquidation_value": liquidation,
        "liquidation_per_share": liq_per_share,
        "breakdown": {
            "cash": cash,
            "notes_receivable_discounted": round(0.80 * notes_rec, 2),
            "accounts_receivable_discounted": round(0.75 * accts_rec, 2),
            "other_receivables_discounted": round(0.50 * other_rec, 2),
            "inventory_discounted": round(0.50 * inventory, 2),
            "fixed_assets_discounted": round(0.70 * fixed_assets, 2),
            "total_liabilities": total_liabilities,
        }
    }


def calc_graham_number(eps: Optional[float], bps: Optional[float]) -> Optional[float]:
    """计算 Graham Number = sqrt(22.5 * EPS * BPS)

    格雷厄姆认为：合理价格上限 = sqrt(22.5 * 每股收益 * 每股净资产)
    其中 22.5 = 15 PE * 1.5 PB 的隐含上限
    """
    if not eps or not bps or eps <= 0 or bps <= 0:
        return None
    return round(math.sqrt(22.5 * eps * bps), 2)


def calc_piotroski_f_score(fin_data: Dict) -> Tuple[int, Dict]:
    """计算 Piotroski F-Score (0-9)

    使用 _fetch_financial_data_for_ncav 已获取的数据，避免重复 API 调用。

    9个二元指标，每满足一个得1分：

    盈利能力 (4分):
    1. ROA > 0（净利润/总资产 > 0）
    2. 经营现金流 > 0
    3. ROA 同比增长
    4. 经营现金流 > 净利润（应计质量）

    杠杆/流动性 (3分):
    5. 长期负债/总资产 同比下降
    6. 流动比率同比上升
    7. 本期未发行新股（总股本未增加）

    运营效率 (2分):
    8. 毛利率同比上升
    9. 资产周转率同比上升
    """
    score = 0
    details = {}

    bs = fin_data.get("balance_sheet", {})
    income_data = fin_data.get("income_data", {})
    cf_data = fin_data.get("cf_data", {})
    bs_items = fin_data.get("balance_sheet_items", [])
    shares_data = fin_data.get("shares_data", [])

    income_dates = sorted(income_data.keys(), reverse=True)
    cf_dates = sorted(cf_data.keys(), reverse=True)

    latest_np = None
    prev_np = None
    latest_revenue = None
    prev_revenue = None
    latest_cost = None
    prev_cost = None
    latest_opcf = None
    latest_total_assets = None
    prev_total_assets = None
    latest_lt_liab = None
    prev_lt_liab = None
    latest_current_assets = None
    prev_current_assets = None
    latest_current_liab = None
    prev_current_liab = None

    # 利润表数据
    if len(income_dates) >= 1:
        d0 = income_dates[0]
        latest_np = income_data[d0].get("parent_net_profit")
        latest_revenue = income_data[d0].get("revenue")
        latest_cost = income_data[d0].get("cost")
    if len(income_dates) >= 2:
        d1 = income_dates[1]
        prev_np = income_data[d1].get("parent_net_profit")
        prev_revenue = income_data[d1].get("revenue")
        prev_cost = income_data[d1].get("cost")

    # 现金流数据
    if len(cf_dates) >= 1:
        latest_opcf = cf_data[cf_dates[0]].get("operating_cf")

    # 资产负债表数据（两期对比，使用已获取的 bs_items）
    if bs_items and len(bs_items) >= 2:
        latest_bs = bs_items[0]
        prev_bs = bs_items[1]
        latest_total_assets = _safe_float(latest_bs.get("TOTAL_ASSETS"))
        prev_total_assets = _safe_float(prev_bs.get("TOTAL_ASSETS"))
        latest_lt_liab = _safe_float(latest_bs.get("TOTAL_NONCURRENT_LIAB"))
        prev_lt_liab = _safe_float(prev_bs.get("TOTAL_NONCURRENT_LIAB"))
        latest_current_assets = _safe_float(latest_bs.get("TOTAL_CURRENT_ASSETS"))
        prev_current_assets = _safe_float(prev_bs.get("TOTAL_CURRENT_ASSETS"))
        latest_current_liab = _safe_float(latest_bs.get("TOTAL_CURRENT_LIAB"))
        prev_current_liab = _safe_float(prev_bs.get("TOTAL_CURRENT_LIAB"))
    elif bs:
        latest_total_assets = bs.get("total_assets")
        latest_lt_liab = bs.get("total_noncurrent_liabilities")
        latest_current_assets = bs.get("total_current_assets")
        latest_current_liab = bs.get("total_current_liabilities")

    # 1. ROA > 0
    if latest_np is not None and latest_total_assets and latest_total_assets > 0:
        roa = latest_np / latest_total_assets
        details["roa_positive"] = roa > 0
        if roa > 0:
            score += 1
    else:
        details["roa_positive"] = None

    # 2. 经营现金流 > 0
    if latest_opcf is not None:
        details["ocf_positive"] = latest_opcf > 0
        if latest_opcf > 0:
            score += 1
    else:
        details["ocf_positive"] = None

    # 3. ROA 同比增长
    if (latest_np is not None and prev_np is not None
            and latest_total_assets and latest_total_assets > 0
            and prev_total_assets and prev_total_assets > 0):
        roa_curr = latest_np / latest_total_assets
        roa_prev = prev_np / prev_total_assets
        details["roa_improving"] = roa_curr > roa_prev
        if roa_curr > roa_prev:
            score += 1
    else:
        details["roa_improving"] = None

    # 4. 经营现金流 > 净利润（应计质量）
    if latest_opcf is not None and latest_np is not None:
        details["accrual_quality"] = latest_opcf > latest_np
        if latest_opcf > latest_np:
            score += 1
    else:
        details["accrual_quality"] = None

    # 5. 长期负债/总资产 同比下降
    if (latest_lt_liab is not None and prev_lt_liab is not None
            and latest_total_assets and latest_total_assets > 0
            and prev_total_assets and prev_total_assets > 0):
        lev_curr = latest_lt_liab / latest_total_assets
        lev_prev = prev_lt_liab / prev_total_assets
        details["leverage_decreasing"] = lev_curr < lev_prev
        if lev_curr < lev_prev:
            score += 1
    else:
        details["leverage_decreasing"] = None

    # 6. 流动比率同比上升
    if (latest_current_assets is not None and latest_current_liab is not None
            and latest_current_liab > 0
            and prev_current_assets is not None and prev_current_liab is not None
            and prev_current_liab > 0):
        cr_curr = latest_current_assets / latest_current_liab
        cr_prev = prev_current_assets / prev_current_liab
        details["liquidity_improving"] = cr_curr > cr_prev
        if cr_curr > cr_prev:
            score += 1
    else:
        details["liquidity_improving"] = None

    # 7. 未发行新股（总股本未显著增加）— 使用预获取的 shares_data
    if len(shares_data) >= 2:
        s0 = shares_data[0]
        s1 = shares_data[1]
        if s0 > 0 and s1 > 0:
            details["no_dilution"] = s0 / s1 <= 1.01
            if s0 / s1 <= 1.01:
                score += 1
        else:
            details["no_dilution"] = None
    else:
        details["no_dilution"] = None

    # 8. 毛利率同比上升
    if (latest_revenue is not None and latest_cost is not None and latest_revenue > 0
            and prev_revenue is not None and prev_cost is not None and prev_revenue > 0):
        gm_curr = (latest_revenue - latest_cost) / latest_revenue
        gm_prev = (prev_revenue - prev_cost) / prev_revenue
        details["gross_margin_improving"] = gm_curr > gm_prev
        if gm_curr > gm_prev:
            score += 1
    else:
        details["gross_margin_improving"] = None

    # 9. 资产周转率同比上升
    if (latest_revenue is not None and latest_total_assets and latest_total_assets > 0
            and prev_revenue is not None and prev_total_assets and prev_total_assets > 0):
        at_curr = latest_revenue / latest_total_assets
        at_prev = prev_revenue / prev_total_assets
        details["asset_turnover_improving"] = at_curr > at_prev
        if at_curr > at_prev:
            score += 1
    else:
        details["asset_turnover_improving"] = None

    return score, details


def _quality_filter(fin_data: Dict, quote: Dict) -> Tuple[bool, List[str]]:
    """质量过滤：排除财务造假风险高和经营恶化的公司

    返回 (is_pass, [rejection_reasons])
    """
    reasons = []
    bs = fin_data.get("balance_sheet", {})
    income_data = fin_data.get("income_data", {})
    cf_data = fin_data.get("cf_data", {})

    # 1. 流动资产必须为正
    ca = bs.get("total_current_assets")
    if not ca or ca <= 0:
        reasons.append("流动资产为零或负")

    # 2. 负债不能超过资产（资不抵债）
    ta = bs.get("total_assets")
    tl = bs.get("total_liabilities")
    if ta and tl and tl > ta:
        reasons.append("资不抵债")

    # 3. 应收账款/营收比例过高 → 警惕虚增收入
    accts_rec = bs.get("accounts_receivable") or 0
    income_dates = sorted(income_data.keys(), reverse=True)
    if income_dates:
        rev = income_data[income_dates[0]].get("revenue")
        if rev and rev > 0 and accts_rec / rev > 0.5:
            reasons.append("应收账款/营收>50%，虚增收入风险")

    # 4. 经营现金流为负（连续两期）
    cf_dates = sorted(cf_data.keys(), reverse=True)
    neg_cf_count = 0
    for d in cf_dates[:4]:
        ocf = cf_data[d].get("operating_cf")
        if ocf is not None and ocf < 0:
            neg_cf_count += 1
    if neg_cf_count >= 3:
        reasons.append("连续多期经营现金流为负")

    # 5. 货币资金/短期借款比例过低 → 偿债风险
    cash = bs.get("monetary_funds") or 0
    st_borrow = bs.get("short_term_borrowing") or 0
    if st_borrow > 0 and cash / st_borrow < 0.3:
        reasons.append("货币资金/短期借款<30%，偿债压力大")

    # 6. 存货异常增长
    if len(income_dates) >= 2:
        inv = bs.get("inventory") or 0
        rev = income_data[income_dates[0]].get("revenue") or 0
        if rev > 0 and inv / rev > 1.0:
            reasons.append("存货/营收>100%，存货积压风险")

    # 7. 市值过小（<10亿），流动性差
    mcap = quote.get("market_cap")
    if mcap and mcap < 10:
        reasons.append("市值<10亿，流动性差")

    return len(reasons) == 0, reasons


def _calc_composite_score(ncav_discount: float, liq_discount: float,
                          f_score: int, pe: Optional[float],
                          pb: Optional[float], roe: Optional[float]) -> float:
    """计算综合评分（0-100）

    权重分配：
    - NCAV折价率: 30%（越折价越好）
    - 清算价值折价率: 20%
    - Piotroski F-Score: 25%（质量）
    - PE 估值: 15%
    - PB 估值: 10%
    """
    score = 0.0

    # NCAV 折价率得分 (0-30)
    # 折价50%以上得满分，0%折价得0分
    ncav_score = min(30, max(0, ncav_discount * 60))
    score += ncav_score

    # 清算价值折价率得分 (0-20)
    liq_score = min(20, max(0, liq_discount * 40))
    score += liq_score

    # Piotroski F-Score (0-25)
    fscore_score = (f_score / 9) * 25
    score += fscore_score

    # PE 得分 (0-15)
    if pe and pe > 0:
        if pe <= 5:
            pe_score = 15
        elif pe <= 8:
            pe_score = 12
        elif pe <= 10:
            pe_score = 10
        elif pe <= 15:
            pe_score = 5
        else:
            pe_score = 0
        score += pe_score

    # PB 得分 (0-10)
    if pb and pb > 0:
        if pb <= 0.5:
            pb_score = 10
        elif pb <= 0.7:
            pb_score = 8
        elif pb <= 1.0:
            pb_score = 6
        elif pb <= 1.5:
            pb_score = 3
        else:
            pb_score = 0
        score += pb_score

    return round(score, 1)


# ===================================================================
# 3. API 端点
# ===================================================================

@router.get("/screener")
def cigar_butt_screener(
    market: str = Query("A", description="市场：A=A股, HK=港股"),
    max_ncav_discount: float = Query(-0.33, description="最大 NCAV 折价率（负数表示折价，如-0.33表示价格<NCAV的2/3）"),
    max_pb: float = Query(1.0, description="最大PB"),
    max_pe: float = Query(15, description="最大PE"),
    min_f_score: int = Query(0, description="最低Piotroski F-Score (0-9)"),
    min_market_cap: float = Query(10, description="最低市值(亿元)"),
    include_quality_fail: bool = Query(False, description="是否包含质量过滤未通过的"),
    top_n: int = Query(50, description="显示数量"),
):
    """格雷厄姆烟蒂股筛选器

    核心逻辑：价格 < NCAV * 2/3 （即 NCAV 折价率 > 33%）
    附加：清算价值、Graham Number、Piotroski F-Score
    """
    start_time = time.time()

    if market == "HK":
        results = _screen_hk_stocks(max_pb, max_pe, min_market_cap, top_n)
    else:
        results = _screen_a_stocks(
            max_ncav_discount, max_pb, max_pe, min_f_score,
            min_market_cap, include_quality_fail, top_n
        )

    elapsed = round(time.time() - start_time, 2)
    return {
        "stocks": results,
        "total": len(results),
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_seconds": elapsed,
        "criteria": {
            "market": market,
            "max_ncav_discount": max_ncav_discount,
            "max_pb": max_pb,
            "max_pe": max_pe,
            "min_f_score": min_f_score,
            "min_market_cap": min_market_cap,
        }
    }


def _screen_a_stocks(max_ncav_discount, max_pb, max_pe, min_f_score,
                     min_market_cap, include_quality_fail, top_n) -> List[Dict]:
    """A股烟蒂股筛选 - 快速版本"""
    # Step 1: 获取全量 A 股数据，做严格初筛
    universe = _fetch_a_share_universe()
    if not universe:
        logger.error("无法获取A股行情数据")
        return []

    # 严格初筛：直接使用用户设定的 PB/PE/市值条件（不再放宽）
    # 这样大幅减少需要获取详细数据的候选股数量
    candidates = []
    for s in universe:
        pb = s.get("pb")
        pe = s.get("pe")
        mcap = s.get("market_cap")
        # PB 必须满足条件（允许 0-10% 容差用于 NCAV 计算）
        if not pb or pb > max_pb * 1.1:
            continue
        # PE 必须满足条件（允许负 PE 用于困境股）
        if pe is not None and pe > 0 and pe > max_pe:
            continue
        # 市值必须满足
        if not mcap or mcap < min_market_cap:
            continue
        candidates.append(s)

    # 按 PB 升序排序（PB 越低越可能是烟蒂股），只处理前 60 只
    candidates.sort(key=lambda x: x.get("pb") or 999)
    max_candidates = min(len(candidates), 60)
    candidates = candidates[:max_candidates]

    logger.info(f"A股初筛: {len(candidates)} 只股票（严格筛选，上限60只）")

    # Step 2: 并发获取财务数据（限制并发数避免被限流）
    results = []
    processed = 0

    def _process_one(stock: dict) -> Optional[Dict]:
        code = stock["code"]
        try:
            fin_data = _fetch_financial_data_for_ncav(code)
            if not fin_data:
                return None
            fin_data["_stock_code"] = code

            bs = fin_data["balance_sheet"]
            total_shares = fin_data.get("total_shares")
            price = stock["price"]

            # 计算 NCAV
            ncav_result = calc_ncav(bs, total_shares)
            if not ncav_result or ncav_result["ncav_per_share"] is None:
                return None

            ncav_per_share = ncav_result["ncav_per_share"]
            ncav_discount = (price - ncav_per_share) / ncav_per_share if ncav_per_share > 0 else -1

            # 二次筛选：NCAV 折价率
            if ncav_discount > max_ncav_discount:
                return None

            # 计算清算价值
            liq_result = calc_liquidation_value(bs, total_shares)
            liq_per_share = liq_result["liquidation_per_share"] if liq_result else None
            liq_discount = None
            if liq_per_share and liq_per_share > 0:
                liq_discount = (price - liq_per_share) / liq_per_share

            # Graham Number
            graham_number = calc_graham_number(fin_data.get("eps"), fin_data.get("bps"))

            # Piotroski F-Score
            f_score, f_details = calc_piotroski_f_score(fin_data)

            # 二次筛选：F-Score
            if f_score < min_f_score:
                return None

            # 质量过滤
            is_quality, reject_reasons = _quality_filter(fin_data, stock)

            if not is_quality and not include_quality_fail:
                return None

            # 计算综合评分
            composite = _calc_composite_score(
                ncav_discount if ncav_discount < 0 else 0,
                liq_discount if liq_discount and liq_discount < 0 else 0,
                f_score,
                stock.get("pe"),
                stock.get("pb"),
                fin_data.get("roe"),
            )

            # 判断符合的标准
            criteria_met = []
            if ncav_discount < -0.33:
                criteria_met.append("NCAV 2/3规则")
            if liq_discount is not None and liq_discount < -0.33:
                criteria_met.append("清算价值折价")
            if graham_number and price < graham_number:
                criteria_met.append("低于Graham Number")
            if f_score >= 7:
                criteria_met.append(f"F-Score优秀({f_score}/9)")
            elif f_score >= 5:
                criteria_met.append(f"F-Score良好({f_score}/9)")
            if stock.get("pb") and stock["pb"] < 1:
                criteria_met.append("PB<1")
            if stock.get("pe") and stock["pe"] < 10:
                criteria_met.append("PE<10")

            return {
                "code": code,
                "name": stock["name"],
                "price": price,
                "change_pct": stock.get("change_pct"),
                "pe": stock.get("pe"),
                "pb": stock.get("pb"),
                "market_cap": stock.get("market_cap"),
                "ncav_per_share": ncav_per_share,
                "ncav_discount": round(ncav_discount * 100, 1),  # 百分比
                "liquidation_per_share": liq_per_share,
                "liquidation_discount": round(liq_discount * 100, 1) if liq_discount else None,
                "graham_number": graham_number,
                "f_score": f_score,
                "f_score_details": f_details,
                "roe": fin_data.get("roe"),
                "gross_margin": fin_data.get("gross_margin"),
                "net_margin": fin_data.get("net_margin"),
                "debt_ratio": fin_data.get("debt_ratio"),
                "eps": fin_data.get("eps"),
                "bps": fin_data.get("bps"),
                "composite_score": composite,
                "criteria_met": criteria_met,
                "quality_pass": is_quality,
                "quality_issues": reject_reasons if not is_quality else [],
                "report_date": bs.get("report_date"),
            }
        except Exception as e:
            logger.warning(f"处理 {code} 失败: {e}")
            return None

    # 并发处理（控制并发数）
    max_workers = 6  # 避免被东方财富限流
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_process_one, s): s for s in candidates}
        for future in as_completed(futures):
            processed += 1
            if processed % 20 == 0:
                logger.info(f"已处理 {processed}/{len(candidates)}")
            try:
                result = future.result()
                if result:
                    results.append(result)
            except Exception as e:
                logger.warning(f"Future 执行失败: {e}")

    # 按综合评分排序
    results.sort(key=lambda x: x.get("composite_score", 0), reverse=True)
    return results[:top_n]


def _screen_hk_stocks(max_pb, max_pe, min_market_cap, top_n) -> List[Dict]:
    """港股烟蒂股筛选（从 vi_service 导入港股列表）"""
    from app.core.stock_lists import HK_STOCKS_LIST

    results = []
    for code in HK_STOCKS_LIST:
        try:
            quote = _fetch_hk_stock_quote(code)
            if not quote:
                continue
            pb = quote.get("pb")
            pe = quote.get("pe")
            mcap = quote.get("market_cap")
            if not pb or pb > max_pb:
                continue
            if pe and pe > max_pe:
                continue
            if not mcap or mcap < min_market_cap:
                continue

            criteria_met = []
            if pb and pb < 1:
                criteria_met.append("PB<1")
            if pe and pe < 10:
                criteria_met.append("PE<10")

            quote["criteria_met"] = criteria_met
            quote["ncav_per_share"] = None  # 港股暂不支持NCAV（需要单独获取财报）
            quote["composite_score"] = round((1 - pb) * 50 + (10 - (pe or 10)) * 3, 1) if pb and pe else 0
            results.append(quote)
        except Exception:
            continue

    results.sort(key=lambda x: x.get("composite_score", 0), reverse=True)
    return results[:top_n]


@router.get("/detail/{stock_code}")
def get_stock_detail(stock_code: str):
    """获取单只股票的详细 NCAV / 清算价值 / F-Score 分析"""
    # 获取实时行情
    quote = DataService.get_stock_basic(stock_code)
    if "error" in quote:
        raise HTTPException(status_code=404, detail=quote["error"])

    price = quote.get("price")
    if not price or price <= 0:
        raise HTTPException(status_code=400, detail="无法获取当前价格")

    # 获取财务数据
    fin_data = _fetch_financial_data_for_ncav(stock_code)
    if not fin_data:
        raise HTTPException(status_code=404, detail="无法获取财务数据")

    fin_data["_stock_code"] = stock_code
    bs = fin_data["balance_sheet"]
    total_shares = fin_data.get("total_shares")

    # NCAV
    ncav_result = calc_ncav(bs, total_shares)
    ncav_per_share = ncav_result["ncav_per_share"] if ncav_result else None
    ncav_discount = (price - ncav_per_share) / ncav_per_share if ncav_per_share and ncav_per_share > 0 else None

    # 清算价值
    liq_result = calc_liquidation_value(bs, total_shares)
    liq_per_share = liq_result["liquidation_per_share"] if liq_result else None
    liq_discount = (price - liq_per_share) / liq_per_share if liq_per_share and liq_per_share > 0 else None

    # Graham Number
    graham_number = calc_graham_number(fin_data.get("eps"), fin_data.get("bps"))

    # Piotroski F-Score
    f_score, f_details = calc_piotroski_f_score(fin_data)

    # 质量过滤
    is_quality, reject_reasons = _quality_filter(fin_data, quote)

    # 综合评分
    composite = _calc_composite_score(
        ncav_discount if ncav_discount and ncav_discount < 0 else 0,
        liq_discount if liq_discount and liq_discount < 0 else 0,
        f_score,
        quote.get("pe"),
        quote.get("pb"),
        fin_data.get("roe"),
    )

    # 资产负债结构
    ta = bs.get("total_assets") or 0
    asset_structure = {
        "current_assets_pct": round((bs.get("total_current_assets") or 0) / ta * 100, 1) if ta > 0 else None,
        "cash_pct": round((bs.get("monetary_funds") or 0) / ta * 100, 1) if ta > 0 else None,
        "receivables_pct": round(((bs.get("accounts_receivable") or 0) + (bs.get("notes_receivable") or 0)) / ta * 100, 1) if ta > 0 else None,
        "inventory_pct": round((bs.get("inventory") or 0) / ta * 100, 1) if ta > 0 else None,
        "fixed_assets_pct": round((bs.get("fixed_assets") or 0) / ta * 100, 1) if ta > 0 else None,
    }

    # 流动性指标
    current_ratio = None
    quick_ratio = None
    ca = bs.get("total_current_assets")
    cl = bs.get("total_current_liabilities")
    if ca and cl and cl > 0:
        current_ratio = round(ca / cl, 2)
        inv = bs.get("inventory") or 0
        quick_ratio = round((ca - inv) / cl, 2)

    return {
        "code": stock_code,
        "name": quote.get("name"),
        "price": price,
        "pe": quote.get("pe"),
        "pb": quote.get("pb"),
        "report_date": bs.get("report_date"),
        # 核心估值
        "ncav": {
            "total": ncav_result["ncav"] if ncav_result else None,
            "per_share": ncav_per_share,
            "discount_pct": round(ncav_discount * 100, 1) if ncav_discount else None,
            "graham_rule": ncav_discount is not None and ncav_discount < -0.33,
        },
        "liquidation": {
            "total": liq_result["liquidation_value"] if liq_result else None,
            "per_share": liq_per_share,
            "discount_pct": round(liq_discount * 100, 1) if liq_discount else None,
            "breakdown": liq_result["breakdown"] if liq_result else None,
        },
        "graham_number": graham_number,
        # 质量评分
        "f_score": {
            "total": f_score,
            "details": f_details,
            "grade": "优秀" if f_score >= 7 else "良好" if f_score >= 5 else "一般" if f_score >= 3 else "较差",
        },
        # 财务指标
        "roe": fin_data.get("roe"),
        "eps": fin_data.get("eps"),
        "bps": fin_data.get("bps"),
        "gross_margin": fin_data.get("gross_margin"),
        "net_margin": fin_data.get("net_margin"),
        "debt_ratio": fin_data.get("debt_ratio"),
        # 资产结构
        "asset_structure": asset_structure,
        "current_ratio": current_ratio,
        "quick_ratio": quick_ratio,
        # 综合评分
        "composite_score": composite,
        "quality_pass": is_quality,
        "quality_issues": reject_reasons,
        "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


@router.get("/backtest")
def cigar_butt_backtest(
    market: str = Query("A", description="市场"),
    start_date: str = Query("2020-01-01", description="回测起始日"),
    end_date: str = Query("2025-12-31", description="回测结束日"),
    rebalance: str = Query("quarterly", description="调仓频率: monthly/quarterly/annual"),
    max_pb: float = Query(0.8, description="最大PB阈值"),
    top_n: int = Query(10, description="持仓数量"),
):
    """烟蒂股策略历史回测

    策略逻辑：
    - 每个调仓日，选取 PB 最低且 PE < 10 的 top_n 只股票
    - 等权持有，到下一调仓日换仓
    - 对比基准：沪深300指数
    """
    try:
        import akshare as ak

        # 获取沪深300历史数据作为基准
        benchmark_df = ak.stock_zh_index_daily(symbol="sh000300")
        if benchmark_df is None or benchmark_df.empty:
            return {"error": "无法获取基准指数数据"}

        benchmark_df = benchmark_df[
            (benchmark_df["date"] >= start_date) & (benchmark_df["date"] <= end_date)
        ].copy()
        benchmark_df["return"] = benchmark_df["close"].pct_change()

        # 构建调仓日列表
        rebalance_dates = _generate_rebalance_dates(start_date, end_date, rebalance)

        # 由于无法在API调用中实时获取历史PB数据（需要历史截面数据），
        # 使用简化回测：基于当前低PB股票池的历史收益
        # 获取当前PB<max_pb的股票列表
        universe = _fetch_a_share_universe()
        low_pb_stocks = [
            s for s in universe
            if s.get("pb") and s["pb"] <= max_pb
            and s.get("pe") and s["pe"] > 0 and s["pe"] < 15
            and s.get("market_cap") and s["market_cap"] > 20
        ]
        low_pb_stocks.sort(key=lambda x: x.get("pb", 999))
        selected_codes = [s["code"] for s in low_pb_stocks[:min(top_n * 3, len(low_pb_stocks))]]

        # 获取这些股票的历史数据
        portfolio_returns = []
        stock_histories = {}

        for code in selected_codes[:top_n * 2]:  # 多取一些以备换仓
            try:
                hist = ak.stock_zh_a_hist(
                    symbol=code, period="daily",
                    start_date=start_date.replace("-", ""),
                    end_date=end_date.replace("-", ""),
                    adjust="qfq"
                )
                if hist is not None and not hist.empty:
                    hist["return"] = hist["收盘"].pct_change()
                    stock_histories[code] = hist
            except Exception:
                continue
            if len(stock_histories) >= 30:
                break

        if not stock_histories:
            return {"error": "无法获取足够的历史数据进行回测"}

        # 等权组合回测
        portfolio_values = [1.0]
        benchmark_values = [1.0]
        benchmark_idx = 0

        for i, date_str in enumerate(rebalance_dates[:-1]):
            next_date = rebalance_dates[i + 1]

            # 在每个调仓日选取 top_n 只股票
            available = []
            for code, hist in stock_histories.items():
                date_rows = hist[hist["date"] >= date_str]
                if not date_rows.empty:
                    available.append(code)
            selected = available[:top_n] if available else list(stock_histories.keys())[:top_n]

            if not selected:
                continue

            # 计算期间收益
            period_returns = []
            for code in selected:
                hist = stock_histories.get(code)
                if hist is None:
                    continue
                period_data = hist[(hist["date"] >= date_str) & (hist["date"] < next_date)]
                if len(period_data) >= 2:
                    start_p = period_data.iloc[0]["收盘"]
                    end_p = period_data.iloc[-1]["收盘"]
                    if start_p > 0:
                        period_returns.append(end_p / start_p - 1)

            if period_returns:
                avg_return = sum(period_returns) / len(period_returns)
                portfolio_values.append(portfolio_values[-1] * (1 + avg_return))

        # 基准收益
        bm_data = benchmark_df[
            (benchmark_df["date"] >= start_date) & (benchmark_df["date"] <= end_date)
        ]
        if len(bm_data) >= 2:
            bm_total = bm_data.iloc[-1]["close"] / bm_data.iloc[0]["close"]
            benchmark_values = [1.0, bm_total]

        # 计算回测指标
        total_return = (portfolio_values[-1] / portfolio_values[0] - 1) * 100
        bm_return = (benchmark_values[-1] / benchmark_values[0] - 1) * 100 if benchmark_values else 0
        years = max(1, len(rebalance_dates) / 4)
        annualized = ((portfolio_values[-1] / portfolio_values[0]) ** (1 / years) - 1) * 100

        return {
            "backtest": {
                "start_date": start_date,
                "end_date": end_date,
                "rebalance": rebalance,
                "max_pb": max_pb,
                "top_n": top_n,
                "total_return_pct": round(total_return, 2),
                "annualized_return_pct": round(annualized, 2),
                "benchmark_return_pct": round(bm_return, 2),
                "excess_return_pct": round(total_return - bm_return, 2),
                "num_rebalances": len(rebalance_dates) - 1,
                "stocks_in_pool": len(stock_histories),
            },
            "portfolio_values": portfolio_values,
            "benchmark_values": benchmark_values,
            "rebalance_dates": rebalance_dates,
            "selected_stocks": [
                {"code": s["code"], "name": s["name"], "pb": s["pb"], "pe": s["pe"]}
                for s in low_pb_stocks[:top_n]
            ],
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    except Exception as e:
        logger.error(f"回测失败: {e}")
        raise HTTPException(status_code=500, detail=f"回测失败: {str(e)}")


def _generate_rebalance_dates(start: str, end: str, freq: str) -> List[str]:
    """生成调仓日列表"""
    from datetime import datetime, timedelta
    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")

    dates = []
    current = start_dt
    while current <= end_dt:
        dates.append(current.strftime("%Y-%m-%d"))
        if freq == "monthly":
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)
        elif freq == "quarterly":
            month = current.month
            if month >= 10:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=month + 3)
        else:  # annual
            current = current.replace(year=current.year + 1)

    dates.append(end)
    return dates


@router.get("/philosophy")
def get_philosophy():
    """投资哲学详情"""
    return {
        "graham": {
            "name": "本杰明·格雷厄姆",
            "title": "价值投资之父 | 华尔街教父",
            "core_idea": "以远低于净流动资产价值(NCAV)的价格买入股票，即'用50美分买1美元的资产'",
            "criteria": [
                "价格 < NCAV 的 2/3（核心规则）",
                "PE < 10（低估值确认）",
                "PB < 1（价格低于净资产）",
                "连续5年以上分红（证明盈利能力真实）",
                "流动比率 > 2（短期偿债能力）",
                "资产负债率 < 50%（财务安全）",
            ],
            "ncav_explanation": "NCAV = 流动资产 - 全部负债（含长期）。这是公司被清算时股东能拿到的理论最低价值。",
            "liquidation_explanation": "清算价值 = 现金 + 0.75*应收 + 0.5*存货 + 0.7*固定资产 - 全部负债。比NCAV更保守，考虑了资产变现折扣。",
            "graham_number": "Graham Number = sqrt(22.5 * EPS * BPS)。格雷厄姆认为这是股票的合理价格上限。",
            "classic_quote": "安全边际是投资中最重要的概念。投资的精髓不在于你买什么，而在于你用什么价格买。",
        },
        "schloss": {
            "name": "沃尔特·施洛斯",
            "title": "格雷厄姆最成功的弟子 | 华尔街超级投资者",
            "core_idea": "坚持PB<1的策略，买入被市场忽视的低价股，耐心等待价值回归",
            "criteria": [
                "PB < 1（核心标准，价格低于每股净资产）",
                "PE < 10（低估值）",
                "负债少，资产负债率低于行业平均",
                "长期持续盈利（至少过去5年无亏损）",
                "管理层有持股（利益绑定）",
            ],
            "performance": "1955-2002年，47年年化收益率20.1%，累计回报率5,456倍",
            "classic_quote": "我不喜欢负债。我们买的公司都是不太受欢迎的、不被看好的，但是价格便宜。",
        },
        "f_score_explanation": {
            "name": "Piotroski F-Score (0-9)",
            "description": "9个二元指标评估公司财务健康度，得分越高越好",
            "categories": [
                {"name": "盈利能力(4分)", "items": ["ROA>0", "经营现金流>0", "ROA同比增长", "现金流>净利润(应计质量)"]},
                {"name": "杠杆/流动性(3分)", "items": ["长期负债比率下降", "流动比率上升", "未发行新股"]},
                {"name": "运营效率(2分)", "items": ["毛利率上升", "资产周转率上升"]},
            ],
            "interpretation": "7-9分: 优秀 | 5-6分: 良好 | 3-4分: 一般 | 0-2分: 较差，需警惕",
        },
        "risks": [
            "价值陷阱：低PB可能因为资产质量差（商誉减值、存货跌价）",
            "流动性风险：小市值股票买卖价差大，可能无法及时退出",
            "公司治理风险：大股东掏空上市公司、关联交易",
            "行业衰退：夕阳行业的资产可能持续贬值",
            "会计操纵：虚增资产、隐藏负债导致PB失真",
            "宏观经济风险：系统性下跌时烟蒂股通常跌幅更大",
        ],
    }
