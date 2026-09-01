"""相对估值法服务 — 同行业 A股/港股 跨市场相对估值对比

设计原则（遵循 CLAUDE.md「宁可空着不要不可靠数据」）：
- 同业分组使用**人工精选**列表（仅含 stock_lists 中已核实的标的），不做不可靠的自动行业映射。
- 数据来源复用项目既有可靠通道：
  - A股行情/PE/PB/市值：DataService.get_stock_basic（多源：通达信→新浪→东方财富）
  - A股财务（ROE/净利率/营收·净利增速/营收）：DataService.get_financial_indicators（东方财富）
  - A股股息率：DataService._get_actual_dividend（东方财富分红方案）
  - 港股行情/PE/PB/市值/股息率：DataService.get_stock_basic（腾讯行情 + akshare 财报计算 PE/PB）
  - 港股财务：DataService.get_financial_indicators（akshare 港股财报）
- PS（市销率）为估算值：市值 / 营收（同币种口径），标注为「估算」。
- 任一指标取不到时留空（None），不参与该指标的分位数与综合评分，绝不编造。
"""

import logging

from app.services.data_service import DataService
from app.core.utils import fetch_tencent_names

logger = logging.getLogger(__name__)


# ============================================================
# 人工精选同业分组（仅含 stock_lists 既有标的，确保分类可靠）
# ============================================================

A_PEER_GROUPS = {
    "银行": ["601398", "601288", "601939", "601988", "600036", "601166", "600016", "600000", "000001", "601818"],
    "保险": ["601318", "601628", "601601", "601336"],
    "券商": ["600030", "601211", "601688"],
    "白酒": ["600519", "000858", "000568", "002304", "600809"],
    "家电": ["000651", "000333", "002032"],
    "医药": ["600276", "000538", "600196"],
    "能源": ["601857", "600028", "601088"],
    "科技": ["002415", "600588"],
}

HK_PEER_GROUPS = {
    "金融": ["00005", "00011", "00388", "00939", "02318", "02628", "01299", "03988", "03328", "03968", "00267", "01398", "06030"],
    "科技互联网": ["00700", "09988", "09618", "09888", "09999", "01024", "01810", "02018", "02382", "09626"],
    "地产": ["00012", "00016", "00101", "00960", "01109", "01929", "01997", "02007", "00688"],
    "消费": ["00291", "00322", "01876", "01928", "02313", "02319", "02688", "06862", "09633"],
    "能源公用事业": ["00003", "00857", "00883", "00386", "00002", "00006", "00066"],
    "医药": ["01093", "01177", "02269", "03692", "06618"],
    "通讯": ["00762", "00941"],
}

SECTOR_LABELS = {
    "A": {
        "银行": "银行", "保险": "保险", "券商": "券商", "白酒": "白酒",
        "家电": "家电", "医药": "医药", "能源": "能源", "科技": "科技",
    },
    "HK": {
        "金融": "金融", "科技互联网": "科技互联网", "地产": "地产", "消费": "消费",
        "能源公用事业": "能源与公用事业", "医药": "医药", "通讯": "通讯",
    },
}

# 每个市场、每个行业的可靠性说明（展示给用户，避免误读估算值/代理值）
DATA_NOTE = {
    "A": "A股 PE/PB/市值/股息率/ROE/净利率/成长性来自东方财富，可靠性高；PS=市值/营收为估算值。",
    "HK": "港股 PE/PB 由 akshare 财报计算（腾讯行情 PE/PB 不可靠，已弃用），股息率取自腾讯行情；PS=市值/营收为估算值，单位按港币口径。",
}


# ============================================================
# 工具函数
# ============================================================

def _safe(v):
    """只保留有限数值，None/异常值一律返回 None（宁可空着）。"""
    if v is None:
        return None
    try:
        f = float(v)
        if f != f or f in (float("inf"), float("-inf")):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _percentile_rank(values, x):
    """返回 x 在 values 中的分位（百分制，越小越靠后）。x 为 None 或样本空返回 None。"""
    vals = [v for v in values if v is not None]
    if x is None or not vals:
        return None
    below = sum(1 for v in vals if v <= x)
    return round(below / len(vals) * 100, 1)


def _median(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    s = sorted(vals)
    n = len(s)
    if n % 2 == 1:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2


# ============================================================
# 单只个股指标抓取
# ============================================================

def _fetch_stock_metrics(code: str, market: str) -> dict | None:
    """抓取单只个股的相对估值所需指标；失败或核心字段缺失返回 None。"""
    try:
        basic = DataService.get_stock_basic(code)
    except Exception as e:
        logger.warning(f"get_stock_basic failed for {code}: {e}")
        return None
    if not basic or basic.get("error"):
        return None

    price = _safe(basic.get("price"))
    if price is None or price <= 0:
        return None

    pe = _safe(basic.get("pe"))
    pb = _safe(basic.get("pb"))
    market_cap = _safe(basic.get("market_cap"))

    # 股息率：A股用分红方案计算；港股直接取行情（腾讯股息率可靠）
    div_yield = None
    if market == "A":
        try:
            dv = DataService._get_actual_dividend(code)
            dps = _safe(dv.get("dividend_per_share"))
            if dps and dps > 0:
                div_yield = round(dps / price * 100, 2)
        except Exception as e:
            logger.debug(f"A股股息率计算失败 {code}: {e}")
            div_yield = None
    else:
        div_yield = _safe(basic.get("dividend_yield"))

    # 财务：ROE/净利率/成长性/营收（用于 PS）
    roe = net_margin = rev_growth = profit_growth = revenue = None
    try:
        fin = DataService.get_financial_indicators(code)
        reports = fin.get("reports") or []
        r0 = reports[0] if reports else {}
        roe = _safe(r0.get("roe"))
        net_margin = _safe(r0.get("net_margin"))
        rev_growth = _safe(r0.get("revenue_growth"))
        profit_growth = _safe(r0.get("profit_growth"))
        revenue = _safe(r0.get("revenue"))
    except Exception as e:
        logger.debug(f"财务指标获取失败 {code}: {e}")

    # PS = 市值 / 营收（同币种口径，估算）
    ps = None
    if market_cap is not None and revenue is not None and revenue > 0:
        ps = round(market_cap / (revenue / 1e8), 2)

    return {
        "code": code,
        "name": basic.get("name") or code,
        "market": market,
        "price": price,
        "change_pct": _safe(basic.get("change_pct")),
        "market_cap": market_cap,
        "pe": pe,
        "pb": pb,
        "ps": ps,
        "dividend_yield": div_yield,
        "roe": roe,
        "net_margin": net_margin,
        "revenue_growth": rev_growth,
        "profit_growth": profit_growth,
    }


# ============================================================
# 分组对比核心
# ============================================================

def _build_group(market: str, sector: str) -> dict:
    """对某一市场某一行业，抓取组内各股并计算分位数、相对中位数偏离、综合吸引力。"""
    groups = A_PEER_GROUPS if market == "A" else HK_PEER_GROUPS
    if sector not in groups:
        return {"error": f"未知行业: {sector}（市场 {market}）"}
    codes = groups[sector]

    raw = []
    for c in codes:
        m = _fetch_stock_metrics(c, market)
        if m:
            raw.append(m)

    if not raw:
        return {
            "market": market,
            "sector": sector,
            "sector_label": SECTOR_LABELS.get(market, {}).get(sector, sector),
            "stocks": [],
            "medians": {},
            "count": 0,
            "data_note": DATA_NOTE.get(market, ""),
            "error": "组内标的均未取得有效行情数据，请稍后重试",
        }

    # 计算各指标分位数与中位数偏离
    pe_list = [s["pe"] for s in raw]
    pb_list = [s["pb"] for s in raw]
    ps_list = [s["ps"] for s in raw]
    div_list = [s["dividend_yield"] for s in raw]

    medians = {
        "pe": _median(pe_list),
        "pb": _median(pb_list),
        "ps": _median(ps_list),
        "dividend_yield": _median(div_list),
    }

    for s in raw:
        s["pe_pct"] = _percentile_rank(pe_list, s["pe"])
        s["pb_pct"] = _percentile_rank(pb_list, s["pb"])
        s["ps_pct"] = _percentile_rank(ps_list, s["ps"])
        s["div_pct"] = _percentile_rank(div_list, s["dividend_yield"])

        s["pe_dev"] = _deviation(s["pe"], medians["pe"])
        s["pb_dev"] = _deviation(s["pb"], medians["pb"])
        s["ps_dev"] = _deviation(s["ps"], medians["ps"])
        s["div_dev"] = _deviation(s["dividend_yield"], medians["dividend_yield"])

        # 综合吸引力评分（0-100，越高越便宜/越有吸引力）
        # PE/PB/PS 越低越便宜 → 吸引力 = 100 - 分位
        # 股息率越高越有吸引力 → 吸引力 = 分位
        scores = []
        if s["pe"] is not None and s["pe_pct"] is not None:
            scores.append(100 - s["pe_pct"])
        if s["pb"] is not None and s["pb_pct"] is not None:
            scores.append(100 - s["pb_pct"])
        if s["ps"] is not None and s["ps_pct"] is not None:
            scores.append(100 - s["ps_pct"])
        if s["dividend_yield"] is not None and s["div_pct"] is not None:
            scores.append(s["div_pct"])
        s["attractiveness"] = round(sum(scores) / len(scores), 1) if scores else None
        s["rating"], s["rating_level"] = _rate(s["attractiveness"])

    # 按综合吸引力降序（最便宜/最有吸引力在前）
    raw.sort(key=lambda x: (x["attractiveness"] is not None, x["attractiveness"] or 0), reverse=True)

    return {
        "market": market,
        "sector": sector,
        "sector_label": SECTOR_LABELS.get(market, {}).get(sector, sector),
        "stocks": raw,
        "medians": medians,
        "count": len(raw),
        "data_note": DATA_NOTE.get(market, ""),
    }


def _deviation(x, median):
    if x is None or median in (None, 0):
        return None
    return round((x - median) / median * 100, 1)


def _rate(attractiveness):
    """综合吸引力 → 评级文案 + 级别（用于前端配色）。"""
    if attractiveness is None:
        return "数据不足", "na"
    if attractiveness >= 70:
        return "低估+", "cheap_plus"
    if attractiveness >= 55:
        return "低估", "cheap"
    if attractiveness >= 45:
        return "合理", "fair"
    if attractiveness >= 30:
        return "偏高", "rich"
    return "高估", "rich_plus"


# ============================================================
# 对外接口
# ============================================================

def get_sectors() -> dict:
    return {
        "A": [{"key": k, "label": SECTOR_LABELS["A"][k]} for k in A_PEER_GROUPS],
        "HK": [{"key": k, "label": SECTOR_LABELS["HK"][k]} for k in HK_PEER_GROUPS],
    }


# ============================================================
# 可搜索标的清单（供前端「选一只标的」自动完成；名称经腾讯批量行情获取，会话内缓存）
# ============================================================

import time
import requests as _requests

_UNIVERSE_CACHE: dict = {"ts": 0.0, "data": {}}  # market -> list
_UNIVERSE_TTL = 3600  # 1 小时


def _tencent_symbol(market: str, code: str) -> str:
    if market == "HK":
        return f"r_hk{code}"
    return f"sh{code}" if code.startswith("6") else f"sz{code}"


def _fetch_universe_names(market: str) -> dict:
    """经腾讯批量行情一次取回 {code: name}，失败返回 {}（前端退化为仅显示代码）。"""
    groups = A_PEER_GROUPS if market == "A" else HK_PEER_GROUPS
    codes = [c for codes in groups.values() for c in codes]
    if not codes:
        return {}
    syms = [_tencent_symbol(market, c) for c in codes]
    sym_names = fetch_tencent_names(syms, timeout=12)
    return {c: sym_names[s] for c, s in zip(codes, syms) if s in sym_names}


def get_stock_universe(market: str) -> dict:
    """返回某市场的可搜索标的清单：[{code, name, sector, sector_label}]（名称缓存）。"""
    market = (market or "").upper()
    if market not in ("A", "HK"):
        return {"error": "market 必须为 A 或 HK"}
    now = time.time()
    if _UNIVERSE_CACHE["ts"] and _UNIVERSE_CACHE["data"].get(market) and now - _UNIVERSE_CACHE["ts"] < _UNIVERSE_TTL:
        return {"market": market, "stocks": _UNIVERSE_CACHE["data"][market]}
    groups = A_PEER_GROUPS if market == "A" else HK_PEER_GROUPS
    names = _fetch_universe_names(market)
    stocks = []
    for sector, codes in groups.items():
        for code in codes:
            stocks.append(
                {
                    "code": code,
                    "name": names.get(code) or code,
                    "sector": sector,
                    "sector_label": SECTOR_LABELS[market][sector],
                }
            )
    # 仅当成功取到数据才刷新缓存，避免失败把清单清空
    if names:
        _UNIVERSE_CACHE["data"][market] = stocks
        _UNIVERSE_CACHE["ts"] = now
    elif _UNIVERSE_CACHE["data"].get(market):
        stocks = _UNIVERSE_CACHE["data"][market]
    return {"market": market, "stocks": stocks}


def compare_sector(market: str, sector: str) -> dict:
    market = (market or "").upper()
    if market not in ("A", "HK"):
        return {"error": "market 必须为 A 或 HK"}
    return _build_group(market, sector)


def compare_stock(market: str, code: str, sector: str | None = None) -> dict:
    """单只股票 vs 其所在行业的已知同业。

    若未指定 sector，自动在 A/H 两个市场的所有行业中查找该代码所属组。
    """
    market = (market or "").upper()
    if market not in ("A", "HK"):
        return {"error": "market 必须为 A 或 HK"}

    # 自动定位行业
    if not sector:
        groups = A_PEER_GROUPS if market == "A" else HK_PEER_GROUPS
        for sec, codes in groups.items():
            if code in codes:
                sector = sec
                break
    if not sector:
        return {
            "error": f"代码 {code} 不在任何已配置的 {market} 同业分组中；"
                     f"相对估值仅支持与已知同业对比，请手动指定 sector 或确认该标的是否在精选列表内。",
            "code": code,
            "market": market,
        }

    group = _build_group(market, sector)
    if group.get("error") and "未知行业" in group.get("error", ""):
        return group

    target = next((s for s in group.get("stocks", []) if s["code"] == code), None)
    if not target:
        # 目标股可能未取得行情，仍返回组内对比供参考
        return {
            **group,
            "target_code": code,
            "target": None,
            "note": f"目标股 {code} 未取得有效行情（可能停牌/数据缺失），已返回同业组对比供参考。",
        }

    return {
        **group,
        "target_code": code,
        "target": target,
    }
