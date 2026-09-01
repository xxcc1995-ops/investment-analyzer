# -*- coding: utf-8 -*-
"""
临期可转债筛选服务（税后保本价安全垫）

移植自 cb-bond-screener 技能（已验证 akshare 接口），由「导出 Excel」改为「返回 JSON」供前端渲染。
所有数据源均为 akshare 直连，无需集思录登录态：
  - bond_zh_hs_cov_spot()  在交易转债实时价（现价/涨跌幅/成交额/成交量）
  - bond_zh_cov()          转股价/转股溢价率/转股价值/正股代码等
  - bond_cb_redeem_jsl()   到期日/最后交易日/剩余规模/强赎状态
  - bond_zh_cov_info(sym)  单只到期赎回条款文本（正则解析「到期赎回价」）

筛选逻辑（用户自定义，沿用技能）：
  条件1（安全垫）：剩余期限 < 1 年，且现价贴税后保本价 ±1 元（债底信用风险已定价，向下有底）
  条件2（期权属性）：转股溢价率 <= 20%，保留看涨期权价值
  主表（双条件精选）= 钝化区 + 溢价率<=20% + 未公告强赎
"""
import os
import re
import datetime as dt
import logging
from typing import Optional, Tuple, Dict, List

import pandas as pd

from app.core.cache import get_cache, set_cache, get_realtime_ttl

logger = logging.getLogger(__name__)

# ---------------- 参数（可按需调整） ----------------
MAX_REMAIN_YEARS = 1.0      # 剩余期限上限（年）
PRICE_TOL = 1.0             # 保本价容忍度（元）：|现价 - 税后保本价| <= 1
MAX_PREMIUM = 20.0          # 转股溢价率上限（%）
TAX_RATE = 0.20             # 个人利息所得税 20%
ELASTIC_LOOKBACK = 20       # 正股弹性观察窗口（交易日）

# 进程内赎回价缓存：symbol -> (timestamp, price)，避免重复 per-bond 解析
_REDEEM_PRICE_CACHE: Dict[str, Tuple[float, Optional[float]]] = {}
_REDEEM_PRICE_TTL = 3600    # 1 小时


def parse_redeem_price(clause: str) -> Optional[float]:
    """从到期赎回条款文本解析到期赎回价（含最后一期利息，每百元面值）

    例：「在本次发行的可转债期满后五个交易日内，公司将以债券面值的 112%（含最后一期利息）向投资者兑付」
    """
    if not isinstance(clause, str):
        return None
    m = re.search(r"(\d+(?:\.\d+)?)%\s*[（(]含最后一期利息", clause)
    if m:
        return float(m.group(1))
    m = re.search(r"面值的\s*(\d+(?:\.\d+)?)%", clause)
    if m:
        return float(m.group(1))
    return None


def _stock_elasticity(stock_code: str) -> Tuple[Optional[float], Optional[float]]:
    """近 20 日涨跌幅 + 近 20 日日均振幅，作为正股弹性代理指标"""
    try:
        import akshare as ak
        prefix = "sh" if stock_code.startswith(("6", "9")) else ("bj" if stock_code.startswith(("4", "8")) else "sz")
        hist = ak.stock_zh_a_daily(symbol=prefix + stock_code, adjust="qfq")
        if hist is None or len(hist) < ELASTIC_LOOKBACK + 1:
            return None, None
        h = hist.tail(ELASTIC_LOOKBACK + 1)
        ret = (h["close"].iloc[-1] / h["close"].iloc[0] - 1) * 100
        amp = ((h["high"] - h["low"]) / h["close"]).tail(ELASTIC_LOOKBACK).mean() * 100
        return round(ret, 2), round(amp, 2)
    except Exception as e:
        logger.warning(f"正股弹性计算失败 {stock_code}: {e}")
        return None, None


def _fetch_redeem_price(symbol: str, force: bool = False) -> Optional[float]:
    """带进程内缓存的到期赎回价解析（仅对候选债调用，数量可控）"""
    now = dt.datetime.now().timestamp()
    if not force and symbol in _REDEEM_PRICE_CACHE:
        ts, price = _REDEEM_PRICE_CACHE[symbol]
        if now - ts < _REDEEM_PRICE_TTL:
            return price
    try:
        import akshare as ak
        detail = ak.bond_zh_cov_info(symbol=symbol)
        price = None
        if detail is not None and len(detail) > 0:
            price = parse_redeem_price(detail.iloc[0].get("REDEEM_CLAUSE"))
        _REDEEM_PRICE_CACHE[symbol] = (now, price)
        return price
    except Exception as e:
        logger.warning(f"到期赎回价获取失败 {symbol}: {e}")
        _REDEEM_PRICE_CACHE[symbol] = (now, None)
        return None


def get_near_mature_list(
    include_elasticity: bool = False,
    max_remain_years: float = MAX_REMAIN_YEARS,
    price_tol: float = PRICE_TOL,
    max_premium: float = MAX_PREMIUM,
) -> dict:
    """获取临期可转债筛选结果（JSON 结构）

    Args:
        include_elasticity: 是否计算正股弹性（近20日涨幅/振幅），会额外发起多笔正股行情请求，较慢
        max_remain_years: 剩余期限上限（年）
        price_tol: 保本价容忍度（元），钝化区判定阈值
        max_premium: 转股溢价率上限（%），双条件精选判定阈值

    Returns:
        dict: {
            params, summary, data_source, fetch_time,
            double_condition: [...],    # 双条件精选（主表）
            floor_zone: [...],          # 钝化区（条件1）
            all_linqi: [...],           # 临期债全表（观察区）
            error/soft_error: 可选
        }
    """
    cache_key = f"cb_nm_{include_elasticity}_{max_remain_years}_{price_tol}_{max_premium}"
    cached = get_cache(cache_key, get_realtime_ttl())
    if cached:
        return cached

    try:
        import akshare as ak
    except Exception as e:
        return {
            'error': f'akshare 不可用: {e}',
            'double_condition': [], 'floor_zone': [], 'all_linqi': [],
            'summary': {}, 'params': {}, 'data_source': 'none',
            'fetch_time': dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

    try:
        # 1. 在交易转债实时行情（沪深京）
        spot = ak.bond_zh_hs_cov_spot()
        for c in ["trade", "changepercent", "amount", "volume"]:
            if c in spot.columns:
                spot[c] = pd.to_numeric(spot[c], errors="coerce")
        spot = spot[spot["trade"] > 0].copy() if "trade" in spot.columns else spot.copy()
        spot["code"] = spot["code"].astype(str).str.zfill(6) if "code" in spot.columns else spot.index.astype(str)
        spot = spot.rename(columns={"name": "bond_nm", "trade": "price", "changepercent": "changepct"})

        # 2. 转股价 / 溢价率 / 正股代码（东财转债比价全表）
        cov = ak.bond_zh_cov()
        cov["债券代码"] = cov["债券代码"].astype(str).str.zfill(6)
        cov_cols = {
            "债券代码": "code", "正股代码": "stock_id", "正股简称": "stock_nm",
            "正股价": "stock_price", "转股价": "convert_price", "转股价值": "convert_value",
            "转股溢价率": "premium_rt", "发行规模": "issue_size", "信用评级": "rating_cd",
        }
        cov = cov[[c for c in cov_cols if c in cov.columns]].rename(columns=cov_cols)

        # 3. 集思录强赎表：到期日 / 最后交易日 / 剩余规模 / 强赎状态
        rd = ak.bond_cb_redeem_jsl()
        rd["代码"] = rd["代码"].astype(str).str.zfill(6)
        rd_cols = {
            "代码": "code", "剩余规模": "remain_size", "最后交易日": "last_trade_dt",
            "到期日": "maturity_dt", "强赎状态": "force_redeem",
        }
        rd = rd[[c for c in rd_cols if c in rd.columns]].rename(columns=rd_cols)
        if "maturity_dt" in rd.columns:
            rd["maturity_dt"] = pd.to_datetime(rd["maturity_dt"], errors="coerce").dt.date
        if "last_trade_dt" in rd.columns:
            rd["last_trade_dt"] = pd.to_datetime(rd["last_trade_dt"], errors="coerce").dt.date

        df = spot.merge(cov, on="code", how="left").merge(rd, on="code", how="left")
    except Exception as e:
        logger.error(f"临期债基础数据获取失败: {e}")
        return {
            'error': f'基础数据获取失败: {e}',
            'double_condition': [], 'floor_zone': [], 'all_linqi': [],
            'summary': {}, 'params': {}, 'data_source': 'none',
            'fetch_time': dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

    # 4. 筛选剩余期限 < max_remain_years（到期日缺失的剔除）
    today = dt.date.today()

    def _year_left(d):
        if pd.isna(d):
            return None
        try:
            return round((d - today).days / 365.0, 3)
        except Exception:
            return None

    if "maturity_dt" in df.columns:
        df["year_left"] = df["maturity_dt"].apply(_year_left)
    else:
        df["year_left"] = None

    cand = df[df["year_left"].notna()]
    cand = cand[(cand["year_left"] > 0) & (cand["year_left"] < max_remain_years)].copy()

    if len(cand) == 0:
        result = _build_empty(include_elasticity, max_remain_years, price_tol, max_premium,
                              data_source="akshare", note="当前无剩余<1年的在交易转债")
        set_cache(cache_key, result)
        return result

    # 5. 逐只解析到期赎回价（仅候选，数量可控）
    rows = []
    for _, r in cand.iterrows():
        code = str(r.get("code", "")).zfill(6)
        rows.append({"code": code, "redeem_price": _fetch_redeem_price(code)})
    extra = pd.DataFrame(rows)
    cand = cand.merge(extra, on="code", how="left")

    # 6. 税后保本价 = 100 + (到期赎回价 - 100) * (1 - 利息税)
    cand["after_tax_floor"] = cand["redeem_price"].apply(
        lambda x: round(100 + (x - 100) * (1 - TAX_RATE), 2) if pd.notna(x) else None
    )
    cand["price"] = pd.to_numeric(cand.get("price"), errors="coerce").round(2)
    cand["dist_to_floor"] = (cand["price"] - cand["after_tax_floor"]).round(2)

    # 7. 正股弹性（可选）
    if include_elasticity:
        elast: Dict[str, Tuple] = {}
        for sc in cand["stock_id"].dropna().astype(str).str.zfill(6).unique():
            elast[sc] = _stock_elasticity(sc)
        cand["stock_id"] = cand["stock_id"].astype(str).str.zfill(6)
        cand["stock_20d_chg"] = cand["stock_id"].map(lambda c: elast.get(c, (None, None))[0])
        cand["stock_20d_amp"] = cand["stock_id"].map(lambda c: elast.get(c, (None, None))[1])

    # 8. 输出字段整理
    def _row(r) -> dict:
        return {
            "bond_id": str(r.get("code", "")).zfill(6),
            "bond_nm": r.get("bond_nm", ""),
            "price": _num(r.get("price")),
            "changepct": _num(r.get("changepct")),
            "after_tax_floor": _num(r.get("after_tax_floor")),
            "redeem_price_pre": _num(r.get("redeem_price")),
            "dist_to_floor": _num(r.get("dist_to_floor")),
            "year_left": _num(r.get("year_left")),
            "maturity_dt": str(r.get("maturity_dt")) if pd.notna(r.get("maturity_dt")) else "",
            "last_trade_dt": str(r.get("last_trade_dt")) if pd.notna(r.get("last_trade_dt")) else "",
            "premium_rt": _num(r.get("premium_rt")),
            "convert_value": _num(r.get("convert_value")),
            "convert_price": _num(r.get("convert_price")),
            "stock_id": str(r.get("stock_id", "")).zfill(6) if pd.notna(r.get("stock_id")) else "",
            "stock_nm": r.get("stock_nm", ""),
            "stock_price": _num(r.get("stock_price")),
            "stock_20d_chg": _num(r.get("stock_20d_chg")) if include_elasticity else None,
            "stock_20d_amp": _num(r.get("stock_20d_amp")) if include_elasticity else None,
            "remain_size": _num(r.get("remain_size")),
            "issue_size": _num(r.get("issue_size")),
            "rating_cd": str(r.get("rating_cd", "")) if pd.notna(r.get("rating_cd")) else "",
            "force_redeem": str(r.get("force_redeem", "")) if pd.notna(r.get("force_redeem")) else "",
            "amount": _num(r.get("amount")),
            "volume": _num(r.get("volume")),
        }

    all_linqi = [_row(r) for _, r in cand.sort_values("dist_to_floor", key=lambda s: s.abs()).iterrows()]

    # 钝化区：|距保本价| <= price_tol
    floor = [x for x in all_linqi if x["dist_to_floor"] is not None and abs(x["dist_to_floor"]) <= price_tol]

    # 双条件精选：钝化区 + 溢价率<=max_premium + 未公告强赎
    def _excluded(r):
        fr = r.get("force_redeem", "")
        return fr in ("已公告强赎", "公告要强赎")
    main = [x for x in floor if (x["premium_rt"] is not None and x["premium_rt"] <= max_premium) and not _excluded(x)]
    main.sort(key=lambda x: x["year_left"])

    result = {
        'params': {
            'max_remain_years': max_remain_years,
            'price_tol': price_tol,
            'max_premium': max_premium,
            'tax_rate': TAX_RATE,
            'include_elasticity': include_elasticity,
        },
        'summary': {
            'all_count': len(all_linqi),
            'floor_count': len(floor),
            'double_condition_count': len(main),
            'as_of': str(today),
        },
        'data_source': 'akshare',
        'fetch_time': dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'double_condition': main,
        'floor_zone': floor,
        'all_linqi': all_linqi,
    }

    set_cache(cache_key, result)
    return result


def _num(v):
    if v is None:
        return None
    try:
        f = float(v)
        if pd.isna(f):
            return None
        return round(f, 2)
    except Exception:
        return None


def _build_empty(include_elasticity, max_remain_years, price_tol, max_premium, data_source, note=""):
    return {
        'params': {
            'max_remain_years': max_remain_years, 'price_tol': price_tol,
            'max_premium': max_premium, 'tax_rate': TAX_RATE,
            'include_elasticity': include_elasticity,
        },
        'summary': {'all_count': 0, 'floor_count': 0, 'double_condition_count': 0, 'as_of': str(dt.date.today()), 'note': note},
        'data_source': data_source,
        'fetch_time': dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'double_condition': [], 'floor_zone': [], 'all_linqi': [],
    }
