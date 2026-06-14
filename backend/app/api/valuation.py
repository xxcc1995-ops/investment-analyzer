"""估值服务模块 - 机构级多模型估值分析

提供：
1. 多模型估值仪表盘（PE/PB/PS/EV-EBITDA/DCF/PEG）
2. 历史分位数分析（PE/PB/股息率带状图数据）
3. 行业对比估值（同行横向比较）
4. 估值预警系统（多维度信号）
5. 可视化数据接口（ECharts-ready）
"""

import logging
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from app.services.data_service import DataService
from app.services.dcf import (
    DCFService,
    calc_ps_ratio,
    calc_peg,
    get_pe_level,
    get_pb_level,
    get_ps_level,
    get_peg_level,
    get_ev_ebitda_level,
    get_percentile_signal,
    calc_percentile,
    calculate_composite_score,
    generate_valuation_alerts,
    build_sensitivity_matrix,
    calculate_graham_number,
    estimate_wacc,
)
from app.core.cache import get_cache, set_cache, TTL_DAILY, TTL_STATIC

logger = logging.getLogger(__name__)
router = APIRouter()

# 行业竞品映射（复用 cross_analysis 的数据）
INDUSTRY_PEERS = {
    '600519': ['600519', '000858', '000568', '600809', '002304', '000596'],
    '000858': ['600519', '000858', '000568', '600809', '002304', '000596'],
    '000568': ['600519', '000858', '000568', '600809', '002304', '000596'],
    '600809': ['600519', '000858', '000568', '600809', '002304', '000596'],
    '002304': ['600519', '000858', '000568', '600809', '002304', '000596'],
    '000596': ['600519', '000858', '000568', '600809', '002304', '000596'],
    '000799': ['600519', '000858', '000568', '600809', '002304', '000596', '000799'],
    '601398': ['601398', '601288', '601939', '601988', '600036', '601166', '600016', '601818'],
    '601288': ['601398', '601288', '601939', '601988', '600036', '601166', '600016', '601818'],
    '601939': ['601398', '601288', '601939', '601988', '600036', '601166', '600016', '601818'],
    '601988': ['601398', '601288', '601939', '601988', '600036', '601166', '600016', '601818'],
    '600036': ['601398', '601288', '601939', '601988', '600036', '601166', '600016', '601818'],
    '601166': ['601398', '601288', '601939', '601988', '600036', '601166', '600016', '601818'],
    '600016': ['601398', '601288', '601939', '601988', '600036', '601166', '600016', '601818'],
    '601818': ['601398', '601288', '601939', '601988', '600036', '601166', '600016', '601818'],
    '000333': ['000333', '000651', '600690', '002032'],
    '000651': ['000333', '000651', '600690', '002032'],
    '600690': ['000333', '000651', '600690', '002032'],
    '002032': ['000333', '000651', '600690', '002032'],
    '300750': ['300750', '002594', '600438', '601012'],
    '002594': ['300750', '002594', '600438', '601012'],
    '600276': ['600276', '000538', '002001', '600196', '300015'],
    '000538': ['600276', '000538', '002001', '600196', '300015'],
    '600196': ['600276', '000538', '002001', '600196', '300015'],
    '00700': ['00700', '09988', '03690', '09618', '09888'],
    '09988': ['00700', '09988', '03690', '09618', '09888'],
    '601088': ['601088', '600188', '601857', '600028', '601898'],
    '601857': ['601088', '600188', '601857', '600028', '601898'],
    '600028': ['601088', '600188', '601857', '600028', '601898'],
    '600900': ['600900', '600886', '600795', '600023', '601985'],
    '600886': ['600900', '600886', '600795', '600023', '601985'],
    '601318': ['601318', '601628', '601601', '02628'],
    '601628': ['601318', '601628', '601601', '02628'],
    '001979': ['001979', '600048', '000002', '601155'],
    '600048': ['001979', '600048', '000002', '601155'],
    '000002': ['001979', '600048', '000002', '601155'],
    '600019': ['600019', '601003', '000898', '000709'],
    '601003': ['600019', '601003', '000898', '000709'],
    '601238': ['002594', '601238', '000625', '600104'],
    '601211': ['601211', '600030', '601688', '601066', '600999'],
    '600030': ['601211', '600030', '601688', '601066', '600999'],
    '600887': ['600887', '002714', '603288', '600597'],
    '603288': ['600887', '002714', '603288', '600597'],
}

INDUSTRY_NAMES = {
    '600519': '白酒', '000858': '白酒', '000568': '白酒', '600809': '白酒',
    '002304': '白酒', '000596': '白酒', '000799': '白酒',
    '601398': '银行', '601288': '银行', '601939': '银行', '601988': '银行',
    '600036': '银行', '601166': '银行', '600016': '银行', '601818': '银行',
    '000333': '家电', '000651': '家电', '600690': '家电', '002032': '家电',
    '300750': '新能源', '002594': '新能源', '600438': '新能源', '601012': '新能源',
    '600276': '医药', '000538': '医药', '002001': '医药', '600196': '医药', '300015': '医药',
    '00700': '互联网', '09988': '互联网', '03690': '互联网', '09618': '互联网', '09888': '互联网',
    '601088': '能源', '600188': '能源', '601857': '能源', '600028': '能源', '601898': '能源',
    '600900': '电力', '600886': '电力', '600795': '电力', '600023': '电力', '601985': '电力',
    '601318': '保险', '601628': '保险', '601601': '保险', '02628': '保险',
    '001979': '地产', '600048': '地产', '000002': '地产', '601155': '地产',
    '600019': '钢铁', '601003': '钢铁', '000898': '钢铁', '000709': '钢铁',
    '002594': '汽车', '601238': '汽车', '000625': '汽车', '600104': '汽车',
    '601211': '证券', '600030': '证券', '601688': '证券', '601066': '证券', '600999': '证券',
    '600887': '食品饮料', '002714': '食品饮料', '603288': '食品饮料', '600597': '食品饮料',
}


def _get_peers(stock_code: str) -> list:
    """获取同行业竞品代码列表"""
    return INDUSTRY_PEERS.get(stock_code, [])


def _get_industry(stock_code: str) -> str:
    """获取行业名称"""
    return INDUSTRY_NAMES.get(stock_code, "未知行业")


def _safe(val, default=None):
    """安全取值"""
    return val if val is not None else default


# ============================================================
# 1. 多模型估值仪表盘
# ============================================================

@router.get("/{stock_code}/dashboard")
def valuation_dashboard(stock_code: str):
    """
    综合估值仪表盘 - 一站式获取所有估值指标

    返回:
    - 基本信息（股价、市值、名称）
    - 多模型估值（PE/PB/PS/EV-EBITDA/PEG/DCF/格雷厄姆）
    - 综合评分
    - 估值预警
    """
    cache_key = f"valuation_dashboard_{stock_code}"
    cached = get_cache(cache_key, TTL_DAILY)
    if cached:
        return cached

    try:
        ds = DataService()

        # 1. 获取基本信息
        basic = ds.get_stock_basic(stock_code)
        if "error" in basic:
            raise HTTPException(400, basic["error"])

        price = basic.get("price", 0)
        market_cap = basic.get("market_cap", 0)  # 亿元
        pe = basic.get("pe")
        pb = basic.get("pb")
        name = basic.get("name", stock_code)
        dividend_yield = basic.get("dividend_yield")

        # 2. 获取财务数据
        financials = ds.get_financial_indicators(stock_code)
        reports = financials.get("reports", [])

        # 最新报告期数据
        latest_report = reports[0] if reports else {}
        eps = latest_report.get("eps")
        bps = latest_report.get("bps") or financials.get("latest_bps")
        revenue = latest_report.get("revenue")  # 元
        net_profit = latest_report.get("net_profit")
        profit_growth = latest_report.get("profit_growth")  # 百分比
        revenue_growth = latest_report.get("revenue_growth")

        # 3. 获取三大报表（用于EV/EBITDA和DCF）
        stmts = ds.get_financial_statements(stock_code)
        income = stmts.get("income", [])
        balance = stmts.get("balance", [])
        cashflow = stmts.get("cashflow", [])

        # 4. 获取历史估值（用于分位数）
        val_history = ds.get_valuation_history(stock_code)
        stats = val_history.get("stats", {})

        # ============ 计算各模型估值 ============

        # --- PE ---
        pe_level = get_pe_level(pe) if pe else "N/A"
        pe_pct = stats.get("pe", {}).get("percentile") if stats else None
        pe_signal = get_percentile_signal(pe_pct) if pe_pct is not None else "N/A"

        # --- PB ---
        pb_level = get_pb_level(pb) if pb else "N/A"
        pb_pct = stats.get("pb", {}).get("percentile") if stats else None
        pb_signal = get_percentile_signal(pb_pct) if pb_pct is not None else "N/A"

        # --- PS ---
        ps = None
        ps_level = "N/A"
        if market_cap and market_cap > 0 and revenue and revenue > 0:
            total_shares = market_cap * 1e8 / price if price > 0 else 0
            rev_per_share = revenue / total_shares if total_shares > 0 else 0
            ps = calc_ps_ratio(price, rev_per_share)
            ps_level = get_ps_level(ps) if ps else "N/A"

        # --- PEG ---
        peg = None
        peg_level_val = "N/A"
        if pe and pe > 0 and profit_growth and profit_growth > 0:
            peg = calc_peg(pe, profit_growth / 100)
            peg_level_val = get_peg_level(peg) if peg else "N/A"

        # --- EV/EBITDA ---
        ev_ebitda = None
        ev_ebitda_level = "N/A"
        ev_val = None
        ebitda_val = None
        if market_cap and market_cap > 0 and balance and income:
            market_cap_yuan = market_cap * 1e8
            latest_bal = balance[0] if balance else {}
            latest_inc = income[0] if income else {}
            total_debt = ((latest_bal.get("short_term_borrowing") or 0)
                         + (latest_bal.get("long_term_borrowing") or 0))
            cash = latest_bal.get("monetary_funds") or 0
            ev_val = market_cap_yuan + total_debt - cash

            operate_profit = latest_inc.get("operate_profit")
            total_assets = latest_bal.get("total_assets") or 0
            da = None
            if cashflow:
                da = cashflow[0].get("depreciation_amortization")
            if not da and total_assets > 0:
                da = total_assets * 0.03
            ebitda_val = operate_profit + da if operate_profit and da else operate_profit

            if ebitda_val and ebitda_val > 0:
                ev_ebitda = round(ev_val / ebitda_val, 2)
                ev_ebitda_level = get_ev_ebitda_level(ev_ebitda)

        # --- FCF Yield ---
        fcf_yield = None
        fcf_val = None
        if cashflow and market_cap and market_cap > 0:
            fcf_val = cashflow[0].get("free_cashflow")
            if fcf_val and fcf_val > 0:
                fcf_yield = round(fcf_val / (market_cap * 1e8) * 100, 2)

        # --- 格雷厄姆公式 ---
        graham = None
        if eps and bps:
            graham = calculate_graham_number(eps, bps)
            if graham.get("applicable") and price > 0:
                gv = graham["graham_value"]
                graham["current_price"] = price
                graham["upside_pct"] = round((gv / price - 1) * 100, 1) if gv else None
                graham["is_undervalued"] = price < gv if gv else None

        # --- 综合评分 ---
        composite = calculate_composite_score(
            pe=pe,
            pb=pb,
            ps=ps,
            ev_ebitda=ev_ebitda,
            peg=peg,
            fcf_yield=fcf_yield,
            dividend_yield=dividend_yield,
            pe_percentile=pe_pct,
            pb_percentile=pb_pct,
        )

        # --- 估值预警 ---
        alerts = generate_valuation_alerts(
            pe=pe, pb=pb, ps=ps, peg=peg, ev_ebitda=ev_ebitda,
            fcf_yield=fcf_yield, dividend_yield=dividend_yield,
            pe_percentile=pe_pct, pb_percentile=pb_pct,
            composite_score=composite.get("score"),
        )

        # --- DCF快速估算（如果有足够数据） ---
        dcf_quick = None
        if cashflow and market_cap and market_cap > 0:
            try:
                fcf_list = []
                for cf in cashflow[:5]:
                    ocf = cf.get("netcash_operate")
                    invest = cf.get("netcash_invest")
                    if ocf is not None:
                        est_fcf = ocf + (invest if invest and invest < 0 else 0)
                        if est_fcf > 0:
                            fcf_list.append(est_fcf / 1e8)  # 转亿元
                if fcf_list:
                    dcf_svc = DCFService(discount_rate=0.10, terminal_growth_rate=0.03, safety_margin=0.30)
                    growth = dcf_svc.estimate_growth_rate(fcf_list)
                    shares = market_cap / price if price > 0 else 0
                    net_debt = 0
                    if balance:
                        bal = balance[0]
                        sd = bal.get("short_term_borrowing") or 0
                        ld = bal.get("long_term_borrowing") or 0
                        c = bal.get("monetary_funds") or 0
                        net_debt = (sd + ld - c) / 1e8
                    if shares > 0:
                        dcf_result = dcf_svc.calculate_intrinsic_value(
                            current_fcf=fcf_list[0],
                            growth_rate=growth,
                            shares=shares,
                            net_debt=net_debt,
                            current_price=price,
                        )
                        dcf_quick = {
                            "intrinsic_value": dcf_result["intrinsic_value"],
                            "buy_price": dcf_result["buy_price"],
                            "upside_pct": dcf_result.get("upside_pct"),
                            "is_undervalued": dcf_result.get("is_undervalued"),
                            "is_buy_zone": dcf_result.get("is_buy_zone"),
                            "growth_rate": round(growth * 100, 1),
                            "fcf_raw": round(fcf_list[0], 2),
                            "terminal_pct": dcf_result["terminal_pct"],
                        }
            except Exception as e:
                logger.debug(f"DCF quick estimate failed for {stock_code}: {e}")

        result = {
            "code": stock_code,
            "name": name,
            "price": price,
            "market_cap": market_cap,
            "industry": _get_industry(stock_code),
            "fetch_time": basic.get("fetch_time"),
            "report_period": latest_report.get("date"),

            # 多模型估值
            "valuation_models": {
                "pe": {
                    "value": pe,
                    "level": pe_level,
                    "percentile": pe_pct,
                    "signal": pe_signal,
                    "stats": stats.get("pe") if stats else None,
                },
                "pb": {
                    "value": pb,
                    "level": pb_level,
                    "percentile": pb_pct,
                    "signal": pb_signal,
                    "stats": stats.get("pb") if stats else None,
                },
                "ps": {"value": ps, "level": ps_level},
                "peg": {"value": peg, "level": peg_level_val},
                "ev_ebitda": {
                    "value": ev_ebitda,
                    "level": ev_ebitda_level,
                    "ev": round(ev_val / 1e8, 2) if ev_val else None,
                    "ebitda": round(ebitda_val / 1e8, 2) if ebitda_val else None,
                },
                "fcf_yield": {"value": fcf_yield, "fcf": round(fcf_val / 1e8, 2) if fcf_val else None},
                "dividend_yield": dividend_yield,
                "graham": graham,
                "dcf": dcf_quick,
            },

            # 综合评分
            "composite_score": composite,

            # 估值预警
            "alerts": alerts,
        }

        set_cache(cache_key, result)
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"valuation_dashboard failed for {stock_code}: {e}")
        raise HTTPException(500, f"估值分析失败: {str(e)}")


# ============================================================
# 2. 历史分位数分析
# ============================================================

@router.get("/{stock_code}/percentiles")
def valuation_percentiles(stock_code: str, years: int = Query(5, ge=1, le=10, description="历史年数")):
    """
    历史分位数分析 - PE/PB/股息率的历史分布和当前位置

    返回:
    - PE/PB/股息率的历史统计（min/max/median/分位数）
    - 历史百分位排名
    - 可视化用的带状图数据（p10/p25/median/p75/p90）
    """
    cache_key = f"valuation_percentiles_{stock_code}_{years}"
    cached = get_cache(cache_key, TTL_STATIC)
    if cached:
        return cached

    try:
        ds = DataService()
        val_history = ds.get_valuation_history(stock_code)

        pe_history = val_history.get("pe_history", [])
        pb_history = val_history.get("pb_history", [])
        div_history = val_history.get("div_history", [])
        stats = val_history.get("stats", {})

        # 按年份过滤
        if years < 10 and pe_history:
            from datetime import datetime, timedelta
            cutoff = (datetime.now() - timedelta(days=years * 365)).strftime("%Y-%m-%d")
            pe_filtered = [h for h in pe_history if h["date"] >= cutoff]
            pb_filtered = [h for h in pb_history if h["date"] >= cutoff]
            div_filtered = [h for h in div_history if h["date"] >= cutoff] if div_history else []
        else:
            pe_filtered = pe_history
            pb_filtered = pb_history
            div_filtered = div_history

        # 重新计算过滤后的统计
        import numpy as np

        def _build_stats(values, upper_limit=None):
            if not values:
                return None
            vals = [v["value"] for v in values if v.get("value") and v["value"] > 0]
            if upper_limit:
                vals = [v for v in vals if v < upper_limit]
            if len(vals) < 5:
                return None
            arr = np.array(vals)
            current = vals[-1]
            count_below = int(np.sum(arr <= current))
            return {
                "current": round(current, 2),
                "min": round(float(np.min(arr)), 2),
                "max": round(float(np.max(arr)), 2),
                "mean": round(float(np.mean(arr)), 2),
                "median": round(float(np.median(arr)), 2),
                "p10": round(float(np.percentile(arr, 10)), 2),
                "p25": round(float(np.percentile(arr, 25)), 2),
                "p75": round(float(np.percentile(arr, 75)), 2),
                "p90": round(float(np.percentile(arr, 90)), 2),
                "percentile": round(count_below / len(vals) * 100, 1),
                "signal": get_percentile_signal(round(count_below / len(vals) * 100, 1)),
                "count": len(vals),
            }

        pe_stats = _build_stats(pe_filtered, 500)
        pb_stats = _build_stats(pb_filtered, 100)
        div_stats = _build_stats(div_filtered, 30) if div_filtered else None

        # 构建带状图数据（按月采样，减少数据量）
        def _sample_band_data(history, max_points=200):
            if not history or len(history) <= max_points:
                return history
            step = max(1, len(history) // max_points)
            return history[::step]

        result = {
            "code": stock_code,
            "years": years,
            "pe": {
                "stats": pe_stats,
                "history": _sample_band_data(pe_filtered),
            },
            "pb": {
                "stats": pb_stats,
                "history": _sample_band_data(pb_filtered),
            },
            "dividend_yield": {
                "stats": div_stats,
                "history": _sample_band_data(div_filtered) if div_filtered else [],
            },
        }

        set_cache(cache_key, result, persist=True)
        return result

    except Exception as e:
        logger.error(f"valuation_percentiles failed for {stock_code}: {e}")
        raise HTTPException(500, f"历史分位数分析失败: {str(e)}")


# ============================================================
# 3. 行业对比估值
# ============================================================

@router.get("/{stock_code}/industry-comparison")
def industry_comparison(stock_code: str):
    """
    行业对比估值 - 与同行业公司横向比较

    返回:
    - 行业PE/PB/ROE均值
    - 各对标公司估值数据
    - 目标公司在行业中的估值排名
    - 相对估值溢价/折价
    """
    cache_key = f"valuation_industry_{stock_code}"
    cached = get_cache(cache_key, TTL_DAILY)
    if cached:
        return cached

    try:
        peer_codes = _get_peers(stock_code)
        industry = _get_industry(stock_code)

        if not peer_codes:
            return {
                "code": stock_code,
                "industry": industry,
                "error": "未找到行业对标公司",
                "peers": [],
            }

        ds = DataService()
        peers_data = []
        target_data = None

        for code in peer_codes:
            try:
                basic = ds.get_stock_basic(code)
                if "error" in basic:
                    continue

                fin = ds.get_financial_indicators(code)
                reports = fin.get("reports", [])
                latest = reports[0] if reports else {}

                entry = {
                    "code": code,
                    "name": basic.get("name", code),
                    "price": basic.get("price", 0),
                    "pe": basic.get("pe"),
                    "pb": basic.get("pb"),
                    "market_cap": basic.get("market_cap"),
                    "roe": latest.get("roe"),
                    "gross_margin": latest.get("gross_margin"),
                    "net_margin": latest.get("net_margin"),
                    "revenue_growth": latest.get("revenue_growth"),
                    "profit_growth": latest.get("profit_growth"),
                    "debt_ratio": latest.get("debt_ratio"),
                    "dividend_yield": basic.get("dividend_yield"),
                }

                # 计算PS
                revenue = latest.get("revenue")
                price = basic.get("price", 0)
                market_cap = basic.get("market_cap", 0)
                if market_cap and market_cap > 0 and price > 0 and revenue and revenue > 0:
                    total_shares = market_cap * 1e8 / price
                    rev_per_share = revenue / total_shares if total_shares > 0 else 0
                    entry["ps"] = calc_ps_ratio(price, rev_per_share)
                else:
                    entry["ps"] = None

                # 计算PEG
                pe_val = basic.get("pe")
                pg = latest.get("profit_growth")
                if pe_val and pe_val > 0 and pg and pg > 0:
                    entry["peg"] = calc_peg(pe_val, pg / 100)
                else:
                    entry["peg"] = None

                if code == stock_code:
                    target_data = entry
                peers_data.append(entry)

            except Exception as e:
                logger.debug(f"Failed to fetch peer data for {code}: {e}")
                continue

        if not peers_data:
            return {
                "code": stock_code,
                "industry": industry,
                "error": "无法获取行业数据",
                "peers": [],
            }

        # 如果目标不在peers里，单独获取
        if target_data is None:
            try:
                basic = ds.get_stock_basic(stock_code)
                if "error" not in basic:
                    fin = ds.get_financial_indicators(stock_code)
                    reports = fin.get("reports", [])
                    latest = reports[0] if reports else {}
                    target_data = {
                        "code": stock_code,
                        "name": basic.get("name", stock_code),
                        "price": basic.get("price", 0),
                        "pe": basic.get("pe"),
                        "pb": basic.get("pb"),
                        "market_cap": basic.get("market_cap"),
                        "roe": latest.get("roe"),
                        "gross_margin": latest.get("gross_margin"),
                        "net_margin": latest.get("net_margin"),
                        "revenue_growth": latest.get("revenue_growth"),
                        "profit_growth": latest.get("profit_growth"),
                        "debt_ratio": latest.get("debt_ratio"),
                        "dividend_yield": basic.get("dividend_yield"),
                    }
            except Exception:
                pass

        # 行业均值计算（排除None）
        def _avg(values):
            valid = [v for v in values if v is not None]
            return round(sum(valid) / len(valid), 2) if valid else None

        pe_values = [p["pe"] for p in peers_data if p.get("pe") and p["pe"] > 0]
        pb_values = [p["pb"] for p in peers_data if p.get("pb") and p["pb"] > 0]
        roe_values = [p["roe"] for p in peers_data if p.get("roe") is not None]
        ps_values = [p.get("ps") for p in peers_data if p.get("ps") and p["ps"] > 0]
        gm_values = [p["gross_margin"] for p in peers_data if p.get("gross_margin") is not None]
        nm_values = [p["net_margin"] for p in peers_data if p.get("net_margin") is not None]

        industry_avg = {
            "pe": _avg(pe_values),
            "pb": _avg(pb_values),
            "roe": _avg(roe_values),
            "ps": _avg(ps_values),
            "gross_margin": _avg(gm_values),
            "net_margin": _avg(nm_values),
            "peer_count": len(peers_data),
        }

        # 排名计算
        def _rank(values, target_val, reverse=False):
            """计算排名（reverse=True表示越高越好）"""
            if target_val is None:
                return None
            valid = sorted([v for v in values if v is not None], reverse=reverse)
            if not valid:
                return None
            try:
                rank = valid.index(target_val) + 1
            except ValueError:
                # 找不到精确值，插入排序后找位置
                rank = sum(1 for v in valid if v <= target_val) if not reverse else sum(1 for v in valid if v >= target_val)
            return {"rank": rank, "total": len(valid)}

        target_pe = target_data.get("pe") if target_data else None
        target_pb = target_data.get("pb") if target_data else None
        target_roe = target_data.get("roe") if target_data else None

        rankings = {
            "pe": _rank(pe_values, target_pe, reverse=False),  # PE越低排名越前
            "pb": _rank(pb_values, target_pb, reverse=False),
            "roe": _rank(roe_values, target_roe, reverse=True),  # ROE越高排名越前
        }

        # 溢价/折价计算
        premium = {}
        if target_pe and industry_avg["pe"] and industry_avg["pe"] > 0:
            premium["pe"] = round((target_pe / industry_avg["pe"] - 1) * 100, 1)
        if target_pb and industry_avg["pb"] and industry_avg["pb"] > 0:
            premium["pb"] = round((target_pb / industry_avg["pb"] - 1) * 100, 1)

        result = {
            "code": stock_code,
            "industry": industry,
            "target": target_data,
            "peers": peers_data,
            "industry_avg": industry_avg,
            "rankings": rankings,
            "premium": premium,
        }

        set_cache(cache_key, result)
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"industry_comparison failed for {stock_code}: {e}")
        raise HTTPException(500, f"行业对比分析失败: {str(e)}")


# ============================================================
# 4. 估值预警
# ============================================================

@router.get("/{stock_code}/alerts")
def valuation_alerts(stock_code: str):
    """
    估值预警系统 - 基于多维度指标生成预警信号

    预警级别:
    - danger: 高估风险，建议卖出/减仓
    - warning: 偏高估值，需关注
    - info: 信息提示
    - safe: 低估信号，可关注买入

    预警维度:
    - PE/PB绝对值和历史分位数
    - PEG增速匹配度
    - EV/EBITDA
    - FCF Yield
    - DCF内在价值 vs 市价
    - 综合评分
    """
    try:
        # 复用dashboard的数据
        dashboard = valuation_dashboard.__wrapped__(stock_code) if hasattr(valuation_dashboard, '__wrapped__') else None
        if dashboard is None:
            # 直接调用
            dashboard = valuation_dashboard(stock_code)

        return {
            "code": stock_code,
            "name": dashboard.get("name"),
            "price": dashboard.get("price"),
            "composite_score": dashboard.get("composite_score"),
            "alerts": dashboard.get("alerts", []),
            "summary": _build_alert_summary(dashboard.get("alerts", []), dashboard.get("composite_score")),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"valuation_alerts failed for {stock_code}: {e}")
        raise HTTPException(500, f"估值预警失败: {str(e)}")


def _build_alert_summary(alerts: list, composite: dict) -> dict:
    """构建预警摘要"""
    danger_count = sum(1 for a in alerts if a.get("level") == "danger")
    warning_count = sum(1 for a in alerts if a.get("level") == "warning")
    safe_count = sum(1 for a in alerts if a.get("level") == "safe")

    # 总体判断
    score = composite.get("score") if composite else None
    if score is not None:
        if score >= 70:
            overall = "低估区间 - 可关注买入机会"
            color = "green"
        elif score >= 45:
            overall = "合理区间 - 持有观望"
            color = "yellow"
        else:
            overall = "高估区间 - 注意风险"
            color = "red"
    elif danger_count > safe_count:
        overall = "多指标显示高估 - 注意风险"
        color = "red"
    elif safe_count > danger_count:
        overall = "多指标显示低估 - 可关注机会"
        color = "green"
    else:
        overall = "估值信号中性"
        color = "gray"

    return {
        "overall": overall,
        "color": color,
        "danger_count": danger_count,
        "warning_count": warning_count,
        "safe_count": safe_count,
        "score": score,
        "level": composite.get("level") if composite else "N/A",
    }


# ============================================================
# 5. 可视化数据接口
# ============================================================

@router.get("/{stock_code}/chart-data")
def valuation_chart_data(stock_code: str):
    """
    估值可视化数据 - ECharts-ready格式

    返回图表数据:
    1. 估值雷达图（多维度评分）
    2. 历史PE/PB趋势图（含分位带）
    3. 行业对比柱状图
    4. 估值仪表盘（综合评分）
    5. DCF敏感性热力图
    """
    cache_key = f"valuation_chart_{stock_code}"
    cached = get_cache(cache_key, TTL_DAILY)
    if cached:
        return cached

    try:
        ds = DataService()
        basic = ds.get_stock_basic(stock_code)
        if "error" in basic:
            raise HTTPException(400, basic["error"])

        price = basic.get("price", 0)
        market_cap = basic.get("market_cap", 0)
        pe = basic.get("pe")
        pb = basic.get("pb")
        dividend_yield = basic.get("dividend_yield")

        # 历史数据
        val_history = ds.get_valuation_history(stock_code)
        pe_history = val_history.get("pe_history", [])
        pb_history = val_history.get("pb_history", [])
        stats = val_history.get("stats", {})

        # 财务数据
        financials = ds.get_financial_indicators(stock_code)
        reports = financials.get("reports", [])
        latest = reports[0] if reports else {}

        # 三大报表
        stmts = ds.get_financial_statements(stock_code)
        income = stmts.get("income", [])
        balance = stmts.get("balance", [])
        cashflow = stmts.get("cashflow", [])

        charts = {}

        # ---- 图1: 估值雷达图 ----
        pe_pct = stats.get("pe", {}).get("percentile") if stats else None
        pb_pct = stats.get("pb", {}).get("percentile") if stats else None

        composite = calculate_composite_score(
            pe=pe, pb=pb,
            ev_ebitda=_calc_ev_ebitda(market_cap, price, balance, income, cashflow),
            fcf_yield=_calc_fcf_yield(market_cap, cashflow),
            dividend_yield=dividend_yield,
            pe_percentile=pe_pct,
            pb_percentile=pb_pct,
        )

        radar_indicators = []
        radar_values = []
        for metric, detail in composite.get("details", {}).items():
            radar_indicators.append({"name": metric.upper(), "max": 100})
            radar_values.append(detail.get("score", 50))

        if radar_indicators:
            charts["radar"] = {
                "indicators": radar_indicators,
                "values": radar_values,
                "title": "估值多维度评分",
            }

        # ---- 图2: 历史PE趋势图（含分位带） ----
        if pe_history:
            # 采样减少数据量
            step = max(1, len(pe_history) // 300)
            sampled = pe_history[::step]

            pe_stats = stats.get("pe", {}) if stats else {}
            charts["pe_trend"] = {
                "dates": [h["date"] for h in sampled],
                "values": [h["value"] for h in sampled],
                "bands": {
                    "p10": pe_stats.get("p10"),
                    "p25": pe_stats.get("p25"),
                    "median": pe_stats.get("median"),
                    "p75": pe_stats.get("p75"),
                    "p90": pe_stats.get("p90"),
                },
                "current_percentile": pe_stats.get("percentile"),
                "title": "PE(TTM)历史走势",
                "y_axis_label": "PE",
            }

        # ---- 图3: 历史PB趋势图（含分位带） ----
        if pb_history:
            step = max(1, len(pb_history) // 300)
            sampled = pb_history[::step]

            pb_stats = stats.get("pb", {}) if stats else {}
            charts["pb_trend"] = {
                "dates": [h["date"] for h in sampled],
                "values": [h["value"] for h in sampled],
                "bands": {
                    "p10": pb_stats.get("p10"),
                    "p25": pb_stats.get("p25"),
                    "median": pb_stats.get("median"),
                    "p75": pb_stats.get("p75"),
                    "p90": pb_stats.get("p90"),
                },
                "current_percentile": pb_stats.get("percentile"),
                "title": "PB历史走势",
                "y_axis_label": "PB",
            }

        # ---- 图4: 行业对比柱状图 ----
        peer_codes = _get_peers(stock_code)
        if peer_codes:
            peer_pe_list = []
            peer_pb_list = []
            peer_roe_list = []
            peer_names = []
            for code in peer_codes[:10]:
                try:
                    pb_basic = ds.get_stock_basic(code)
                    if "error" not in pb_basic:
                        peer_names.append(pb_basic.get("name", code))
                        peer_pe_list.append(pb_basic.get("pe"))
                        peer_pb_list.append(pb_basic.get("pb"))
                        fin = ds.get_financial_indicators(code)
                        reps = fin.get("reports", [])
                        peer_roe_list.append(reps[0].get("roe") if reps else None)
                except Exception:
                    continue

            if peer_names:
                charts["industry_bar"] = {
                    "names": peer_names,
                    "pe": peer_pe_list,
                    "pb": peer_pb_list,
                    "roe": peer_roe_list,
                    "target_code": stock_code,
                    "title": f"{_get_industry(stock_code)}行业估值对比",
                }

        # ---- 图5: 估值仪表盘（综合评分） ----
        charts["gauge"] = {
            "value": composite.get("score", 0),
            "level": composite.get("level", "N/A"),
            "max": 100,
            "title": "综合估值评分",
            "segments": [
                {"from": 0, "to": 25, "color": "#ff4444", "label": "高估"},
                {"from": 25, "to": 45, "color": "#ffaa00", "label": "偏高"},
                {"from": 45, "to": 65, "color": "#ffff00", "label": "合理"},
                {"from": 65, "to": 80, "color": "#aaff00", "label": "低估"},
                {"from": 80, "to": 100, "color": "#00ff00", "label": "严重低估"},
            ],
        }

        # ---- 图6: DCF敏感性热力图 ----
        if cashflow and market_cap and market_cap > 0:
            try:
                fcf_list = []
                for cf in cashflow[:5]:
                    ocf = cf.get("netcash_operate")
                    invest = cf.get("netcash_invest")
                    if ocf is not None:
                        est_fcf = ocf + (invest if invest and invest < 0 else 0)
                        if est_fcf > 0:
                            fcf_list.append(est_fcf / 1e8)
                if fcf_list:
                    dcf_svc = DCFService(discount_rate=0.10, terminal_growth_rate=0.03, safety_margin=0.30)
                    growth = dcf_svc.estimate_growth_rate(fcf_list)
                    shares = market_cap / price if price > 0 else 0
                    if shares > 0:
                        sensitivity = build_sensitivity_matrix(
                            current_fcf=fcf_list[0],
                            growth_rate=growth,
                            shares=shares,
                        )
                        charts["sensitivity_heatmap"] = {
                            **sensitivity,
                            "current_price": price,
                            "title": "DCF敏感性分析（内在价值 vs 增长率/折现率）",
                            "x_label": "折现率",
                            "y_label": "增长率",
                        }
            except Exception as e:
                logger.debug(f"Sensitivity chart failed for {stock_code}: {e}")

        result = {
            "code": stock_code,
            "charts": charts,
        }

        set_cache(cache_key, result)
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"valuation_chart_data failed for {stock_code}: {e}")
        raise HTTPException(500, f"可视化数据生成失败: {str(e)}")


# ============================================================
# 6. DCF详细估值
# ============================================================

@router.post("/{stock_code}/dcf")
def stock_dcf_valuation(
    stock_code: str,
    growth_rate: float = Query(None, description="增长率（小数），不填则自动估算"),
    discount_rate: float = Query(None, description="折现率/WACC，不填则自动估算"),
    safety_margin: float = Query(0.30, description="安全边际（小数）"),
):
    """
    DCF估值 - 自动获取数据并计算

    自动获取: FCF（从现金流表）、增长率（历史CAGR）、股本、净负债、WACC
    """
    cache_key = f"valuation_dcf_{stock_code}_{growth_rate}_{discount_rate}_{safety_margin}"
    cached = get_cache(cache_key, TTL_DAILY)
    if cached:
        return cached

    try:
        ds = DataService()

        # 获取基本信息
        basic = ds.get_stock_basic(stock_code)
        if "error" in basic:
            raise HTTPException(400, basic["error"])

        price = basic.get("price", 0)
        market_cap = basic.get("market_cap", 0)
        if not price or price <= 0:
            raise HTTPException(400, f"无法获取 {stock_code} 的价格数据")

        # 获取财务数据
        financials = ds.get_financial_indicators(stock_code)
        reports = financials.get("reports", [])
        if not reports:
            raise HTTPException(404, f"未找到 {stock_code} 的财务数据")

        # 获取现金流数据
        stmts = ds.get_financial_statements(stock_code)
        cashflow = stmts.get("cashflow", [])
        balance = stmts.get("balance", [])

        # 估算FCF
        fcf_estimates = []
        for cf in cashflow[:5]:
            ocf = cf.get("netcash_operate")
            invest = cf.get("netcash_invest")
            if ocf is not None:
                fcf = ocf + (invest if invest and invest < 0 else 0)
                if fcf > 0:
                    fcf_estimates.append(fcf / 1e8)  # 转亿元

        if not fcf_estimates:
            latest_profit = reports[0].get("net_profit")
            if latest_profit and latest_profit > 0:
                current_fcf = latest_profit * 0.8 / 1e8
            else:
                raise HTTPException(400, f"无法估算 {stock_code} 的自由现金流")
        else:
            current_fcf = fcf_estimates[0]

        # 估算增长率
        if growth_rate is not None:
            g_rate = growth_rate
        elif len(fcf_estimates) >= 2:
            dcf_svc_tmp = DCFService(discount_rate=0.10, terminal_growth_rate=0.03, safety_margin=0.30)
            g_rate = dcf_svc_tmp.estimate_growth_rate(fcf_estimates)
        else:
            g_rate = 0.08

        # 股本
        shares = market_cap / price if market_cap and market_cap > 0 and price > 0 else 0
        if shares <= 0:
            raise HTTPException(400, f"无法获取 {stock_code} 的股本数据")

        # 净负债
        net_debt = 0.0
        if balance:
            bal = balance[0]
            sd = bal.get("short_term_borrowing") or 0
            ld = bal.get("long_term_borrowing") or 0
            c = bal.get("monetary_funds") or 0
            net_debt = (sd + ld - c) / 1e8

        # WACC
        if discount_rate is not None:
            d_rate = discount_rate
        else:
            debt_ratio = reports[0].get("debt_ratio", 0) or 0
            d_rate = estimate_wacc(debt_ratio=debt_ratio)

        # DCF计算
        dcf_svc = DCFService(
            discount_rate=d_rate,
            terminal_growth_rate=0.03,
            safety_margin=safety_margin,
        )

        result = dcf_svc.calculate_intrinsic_value(
            current_fcf=current_fcf,
            growth_rate=g_rate,
            shares=shares,
            net_debt=net_debt,
            current_price=price,
        )

        # 两阶段DCF
        two_stage = dcf_svc.calculate_two_stage_dcf(
            current_fcf=current_fcf,
            high_growth_rate=g_rate,
            stable_growth_rate=min(g_rate * 0.5, 0.05),
            shares=shares,
            high_growth_years=5,
            net_debt=net_debt,
            current_price=price,
        )

        # 敏感性分析
        sensitivity = build_sensitivity_matrix(
            current_fcf=current_fcf,
            growth_rate=g_rate,
            shares=shares,
            discount_rate=d_rate,
            safety_margin=safety_margin,
            net_debt=net_debt,
        )

        # 数据来源信息
        data_source = {
            "fcf_source": "cashflow_statement" if fcf_estimates else "estimated_from_profit",
            "fcf_raw": round(current_fcf, 2),
            "growth_rate_source": "historical_cagr" if growth_rate is None else "manual",
            "growth_rate_pct": round(g_rate * 100, 1),
            "discount_rate_source": "wacc_estimated" if discount_rate is None else "manual",
            "discount_rate_pct": round(d_rate * 100, 1),
            "debt_ratio": reports[0].get("debt_ratio"),
            "report_period": reports[0].get("date"),
        }

        final = {
            "code": stock_code,
            "name": basic.get("name"),
            "price": price,
            "single_stage": result,
            "two_stage": two_stage,
            "sensitivity": sensitivity,
            "data_source": data_source,
        }

        set_cache(cache_key, final)
        return final

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"stock_dcf_valuation failed for {stock_code}: {e}")
        raise HTTPException(500, f"DCF估值失败: {str(e)}")


# ============================================================
# 辅助函数
# ============================================================

def _calc_ev_ebitda(market_cap, price, balance, income, cashflow):
    """辅助：计算EV/EBITDA"""
    if not market_cap or market_cap <= 0 or not balance or not income:
        return None
    try:
        market_cap_yuan = market_cap * 1e8
        latest_bal = balance[0]
        latest_inc = income[0]
        total_debt = ((latest_bal.get("short_term_borrowing") or 0)
                     + (latest_bal.get("long_term_borrowing") or 0))
        cash = latest_bal.get("monetary_funds") or 0
        ev = market_cap_yuan + total_debt - cash
        operate_profit = latest_inc.get("operate_profit")
        da = None
        if cashflow:
            da = cashflow[0].get("depreciation_amortization")
        if not da:
            total_assets = latest_bal.get("total_assets") or 0
            da = total_assets * 0.03 if total_assets > 0 else 0
        ebitda = operate_profit + da if operate_profit and da else operate_profit
        if ebitda and ebitda > 0:
            return round(ev / ebitda, 2)
    except Exception:
        pass
    return None


def _calc_fcf_yield(market_cap, cashflow):
    """辅助：计算FCF Yield"""
    if not market_cap or market_cap <= 0 or not cashflow:
        return None
    try:
        fcf = cashflow[0].get("free_cashflow")
        if fcf and fcf > 0:
            return round(fcf / (market_cap * 1e8) * 100, 2)
    except Exception:
        pass
    return None
