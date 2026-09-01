# -*- coding: utf-8 -*-
"""指数盈利估值 - 自动化管线（免费源重建用户 Excel 口径）

当前覆盖：沪深300（hs300_auto）
数据源（2026-08-16 沙箱实测，详见 CLAUDE.md「指数盈利估值自动取数源」）：
- 收盘价 + PE-TTM：乐咕乐股 stock_index_pe_lg("沪深300")，2005-04 起日频
  （收盘价与 Wind 完全一致；滚动PE 与 Wind 口径差 ~5%，页面明确标注）
- 中/美十年期国债：akshare bond_zh_us_rate（英为财情，与用户 Excel 2000-2007 段同源）
- 官方校验：中证指数官网 stock_zh_index_value_csindex（仅最近 20 条，用于口径比对）

计算口径（复刻用户 Excel 公式，沪深300 变体）：
- 隐含EPS = 收盘价 ÷ PE-TTM
- EPS 周期：隐含EPS 4周平滑 + 4% zigzag（红=上涨 / 绿=下降）
- 中美国债利差(20倍) = (美国10Y − 中国10Y) × 20
- 估值中枢偏移率 = PE-TTM × 中国10Y（基准线 50，低于=折价）
- 合理收盘价 = (100 ÷ 中国10Y) × 0.5 × 隐含EPS
- 风险溢价 = 100 ÷ PE-TTM − 中国10Y（百分点）

周度口径：ISO 自然周，标签=周日日期，取该周最后一个交易日数值（与用户 Excel 一致）。

缓存：日频原始数据落盘 backend/data/manual/hs300_auto_cache.json，
国债增量拉取（首次全量较慢，约1-2分钟，此后每次仅增量几天）。
"""
import json
import logging
import os
import threading
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "manual")
_CACHE_FILE = os.path.join(_CACHE_DIR, "hs300_auto_cache.json")
_CACHE_TTL_HOURS = 12

_BASELINE = 50
_DISCOUNT = 0.5

_mem_cache: dict = {"payload": None, "ts": 0.0}
_lock = threading.Lock()


# ============================================================
# 数据拉取（日频，落盘缓存）
# ============================================================

def _load_cache() -> dict:
    if os.path.exists(_CACHE_FILE):
        try:
            with open(_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"[hs300_auto] 缓存读取失败，重建: {e}")
    return {"legu": {}, "bond": {}, "updated": None}


def _save_cache(cache: dict):
    os.makedirs(_CACHE_DIR, exist_ok=True)
    tmp = _CACHE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    os.replace(tmp, _CACHE_FILE)


def _fetch_legu() -> dict:
    """乐咕 沪深300 日频 收盘+滚动PE → {date: [close, pe]}"""
    import akshare as ak
    df = ak.stock_index_pe_lg(symbol="沪深300")
    out = {}
    for _, r in df.iterrows():
        d = str(r["日期"])[:10]
        close, pe = r.get("指数"), r.get("滚动市盈率")
        try:
            out[d] = [round(float(close), 2) if close == close else None,
                      round(float(pe), 2) if pe == pe else None]
        except (TypeError, ValueError):
            continue
    return out


def _fetch_bond(start_date: str) -> dict:
    """中美国债日频（英为财情）→ {date: [cn10y, us10y]}"""
    import akshare as ak
    df = ak.bond_zh_us_rate(start_date=start_date.replace("-", ""))
    out = {}
    for _, r in df.iterrows():
        d = str(r["日期"])[:10]
        cn, us = r.get("中国国债收益率10年"), r.get("美国国债收益率10年")
        out[d] = [round(float(cn), 4) if cn == cn and cn is not None else None,
                  round(float(us), 4) if us == us and us is not None else None]
    return out


def _update_cache(force: bool = False) -> dict:
    with _lock:
        cache = _load_cache()
        updated = cache.get("updated")
        if not force and updated:
            age_h = (datetime.now() - datetime.fromisoformat(updated)).total_seconds() / 3600
            if age_h < _CACHE_TTL_HOURS:
                return cache

        # 乐咕：全量单请求，直接覆盖
        try:
            cache["legu"] = _fetch_legu()
        except Exception as e:
            logger.error(f"[hs300_auto] 乐咕拉取失败: {e}")
            if not cache.get("legu"):
                raise

        # 国债：增量（从缓存最后日期前一天起；无缓存则全量自2004-12）
        try:
            bond = cache.get("bond") or {}
            if bond:
                last = max(bond.keys())
                start = (datetime.strptime(last, "%Y-%m-%d") - timedelta(days=5)).strftime("%Y-%m-%d")
            else:
                start = "2004-12-01"
            new_bond = _fetch_bond(start)
            bond.update(new_bond)
            cache["bond"] = bond
        except Exception as e:
            logger.error(f"[hs300_auto] 国债拉取失败: {e}")
            if not cache.get("bond"):
                raise

        cache["updated"] = datetime.now().isoformat(timespec="seconds")
        _save_cache(cache)
        return cache


# ============================================================
# 周度重采样 + 衍生计算
# ============================================================

def _week_sunday(date_str: str) -> str:
    """该日期所在 ISO 自然周的周日（与用户 Excel 周标签一致）"""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return (d + timedelta(days=(6 - d.weekday()))).strftime("%Y-%m-%d")


def _weekly_last(series: dict) -> dict:
    """日频 {date: values} → 周频 {sunday: 该周最后交易日 values}"""
    weekly: dict = {}
    for d in sorted(series.keys()):
        key = _week_sunday(d)
        weekly[key] = series[d]  # 日期升序，后写覆盖 → 保留该周最后一天
    return weekly


def _weekly_bond_last(bond_daily: dict) -> dict:
    """国债周对齐：每周取该周内最后一个非空值"""
    weekly: dict = {}
    for d in sorted(bond_daily.keys()):
        key = _week_sunday(d)
        cn, us = bond_daily[d]
        cur = weekly.get(key, [None, None])
        weekly[key] = [cn if cn is not None else cur[0],
                       us if us is not None else cur[1]]
    return weekly


def _sma(values, window):
    out = []
    for i in range(len(values)):
        seg = [v for v in values[max(0, i - window + 1): i + 1] if v is not None]
        out.append(sum(seg) / len(seg) if seg else None)
    return out


def _zigzag_phases(values, th=0.04):
    """zigzag 相位：返回每周 'up'/'down'/None（首个拐点前按其后方向回填）"""
    idxs = [i for i, v in enumerate(values) if v is not None and v > 0]
    phase = [None] * len(values)
    pivots = []  # (idx, direction_starting_here)
    if len(idxs) < 2:
        return phase, pivots
    start = idxs[0]
    lo_i = hi_i = start
    direction = None
    for i in idxs[1:]:
        v = values[i]
        if direction is None:
            if v < values[lo_i]:
                lo_i = i
            if v > values[hi_i]:
                hi_i = i
            if v >= values[lo_i] * (1 + th):
                direction = "up"
                pivots.append((lo_i, "up"))
                hi_i = i
            elif v <= values[hi_i] * (1 - th):
                direction = "down"
                pivots.append((hi_i, "down"))
                lo_i = i
        elif direction == "up":
            if v > values[hi_i]:
                hi_i = i
            elif v <= values[hi_i] * (1 - th):
                pivots.append((hi_i, "down"))
                direction = "down"
                lo_i = i
        else:
            if v < values[lo_i]:
                lo_i = i
            elif v >= values[lo_i] * (1 + th):
                pivots.append((lo_i, "up"))
                direction = "up"
                hi_i = i
    if not pivots:
        return phase, pivots
    # 分段填充
    bounds = [start] + [p[0] for p in pivots] + [idxs[-1]]
    dirs = [pivots[0][1]] + [p[1] for p in pivots]
    for k in range(len(dirs)):
        a, b = bounds[k], bounds[k + 1]
        for i in range(a, b + 1):
            if values[i] is not None:
                phase[i] = dirs[k]
    return phase, pivots

def _round(v, n=2):
    return round(v, n) if v is not None else None


# ============================================================
# 官方校验（中证官网，仅最近20条）
# ============================================================

def _csindex_check(auto_by_date: dict) -> dict:
    try:
        import akshare as ak
        df = ak.stock_zh_index_value_csindex(symbol="000300")
        diffs = []
        for _, r in df.iterrows():
            d = str(r["日期"])[:10]
            pe1 = r.get("市盈率1")
            auto = auto_by_date.get(d)
            if auto and pe1 == pe1 and auto.get("pe"):
                diffs.append(abs(float(pe1) - auto["pe"]) / auto["pe"] * 100)
        if diffs:
            return {
                "source": "中证指数官网 市盈率1（近20个交易日）",
                "n": len(diffs),
                "mean_diff_pct": round(sum(diffs) / len(diffs), 2),
                "max_diff_pct": round(max(diffs), 2),
            }
    except Exception as e:
        logger.warning(f"[hs300_auto] 中证官网校验失败: {e}")
    return {}


# ============================================================
# 对外接口
# ============================================================

def build_payload() -> dict:
    cache = _update_cache()
    legu_w = _weekly_last(cache["legu"])
    bond_w = _weekly_bond_last(cache["bond"])

    weeks = sorted(legu_w.keys())
    implied = []
    for w in weeks:
        close, pe = legu_w[w]
        implied.append(close / pe if close and pe else None)

    smoothed = _sma(implied, 4)
    phases, pivots = _zigzag_phases(smoothed, 0.04)

    rows = []
    cycles = []
    up_weeks = down_weeks = 0

    for i, w in enumerate(weeks):
        close, pe = legu_w[w]
        cn10y, us10y = bond_w.get(w, [None, None])
        ie = implied[i]
        phase = phases[i] if i < len(phases) else None
        if phase == "up":
            up_weeks += 1
        elif phase == "down":
            down_weeks += 1

        dev = pe * cn10y if pe and cn10y else None
        fair = (100 / cn10y) * _DISCOUNT * ie if cn10y and ie else None
        premium = 100 / pe - cn10y if pe and cn10y else None
        spread = (us10y - cn10y) * 20 if us10y is not None and cn10y is not None else None

        row = {
            "date": w,
            "close": close,
            "pe": pe,
            "risk_premium": _round(premium),
            "eps_ttm": None,
            "implied_eps": _round(ie),
            "eps_up": _round(ie) if phase == "up" else None,
            "eps_down": _round(ie) if phase == "down" else None,
            "us_cn_spread": _round(spread),
            "cn10y": cn10y,
            "us10y": us10y,
            "valuation_dev": _round(dev),
            "fair_close": _round(fair),
        }
        rows.append(row)

    # EPS 周期区间表
    for k, (pidx, direction) in enumerate(pivots):
        s = weeks[pidx]
        e_idx = pivots[k + 1][0] if k + 1 < len(pivots) else len(weeks) - 1
        e = weeks[e_idx]
        n_weeks = e_idx - pidx + 1
        cycles.append({
            "start": s, "end": e,
            "direction": "上涨" if direction == "up" else "下降",
            "months": f"{round(n_weeks / 4.33)}个月",
            "weeks": f"{n_weeks}周",
        })

    latest = rows[-1] if rows else {}
    meta = {
        "code": "hs300_auto",
        "name": "沪深300·自动(乐咕)",
        "market": "A股",
        "baseline": _BASELINE,
        "discount": _DISCOUNT,
        "bond_name": "十年期中国国债收益率",
        "start_date": weeks[0] if weeks else None,
        "end_date": weeks[-1] if weeks else None,
        "row_count": len(rows),
        "file_updated": cache.get("updated"),
        "auto": True,
        "up_total_time": up_weeks,
        "down_total_time": down_weeks,
        "latest": {
            "date": latest.get("date"),
            "close": latest.get("close"),
            "pe": latest.get("pe"),
            "risk_premium": latest.get("risk_premium"),
            "valuation_dev": latest.get("valuation_dev"),
            "fair_close": latest.get("fair_close"),
        },
    }

    notes = (
        "【自动重建版 · 与手工 Excel 口径对比用】\n"
        "1、收盘价、PE-TTM：乐咕乐股（沪深300 日频，2005-04-08 起，周度重采样=每周最后交易日）。"
        "收盘价与 Wind 完全一致；滚动PE 与 Wind 存在约 5% 系统性口径差（已实测），结论看趋势不看绝对值。\n"
        "2、EPS 周期：隐含EPS(收盘价÷PE) 4周平滑 + 4% 阈值 zigzag（与手工表口径一致）。\n"
        "3、国债：英为财情（akshare bond_zh_us_rate），与手工表 2000-2007 段同源，按 ISO 自然周对齐。\n"
        "4、估值中枢偏移率 = PE-TTM × 中国10Y（基准线 50，低于=折价）；合理收盘价 = (100÷中国10Y)×0.5×隐含EPS；"
        "风险溢价 = 100÷PE-TTM − 中国10Y（百分点）。\n"
        "5、官方校验：中证指数官网市盈率1（近20条）对照见下方统计。"
    )

    columns = [
        {"key": "date", "label": "交易日期"},
        {"key": "close", "label": "收盘价"},
        {"key": "pe", "label": "PE-TTM(乐咕)"},
        {"key": "risk_premium", "label": "风险溢价(百分点)"},
        {"key": "implied_eps", "label": "隐含EPS"},
        {"key": "us_cn_spread", "label": "中美国债利差(×20)"},
        {"key": "cn10y", "label": "中国十年期国债(%)"},
        {"key": "us10y", "label": "美国十年期国债(%)"},
        {"key": "valuation_dev", "label": "估值中枢偏移率"},
        {"key": "fair_close", "label": "合理收盘价"},
    ]

    compare = _build_compare(rows, cache["legu"])

    return {
        "meta": meta,
        "notes": notes,
        "summary_lines": [_csindex_check_summary(compare)],
        "fields": [c["key"] for c in columns] + ["eps_up", "eps_down"],
        "columns": columns,
        "rows": rows,
        "cycles": cycles,
        "compare": compare,
    }


def _csindex_check_summary(compare: dict) -> str:
    chk = compare.get("csindex_check") or {}
    if chk:
        return (f"◆ 官方校验：乐咕 PE vs 中证官网市盈率1，近 {chk['n']} 个交易日 "
                f"平均偏差 {chk['mean_diff_pct']}%，最大 {chk['max_diff_pct']}%")
    return "◆ 官方校验：中证官网对照暂不可用"


def _build_compare(auto_rows: list, legu_daily: dict) -> dict:
    """与手工 Excel（Wind 口径）同日期对比 PE / 收盘 / 隐含EPS"""
    compare = {"series": [], "stats": {}}
    try:
        from app.services import index_earnings_service
        excel = index_earnings_service.get_index_data("hs300")
        wind_by_date = {r["date"]: r for r in excel["rows"]}
        pe_diffs = []
        series = []
        for r in auto_rows:
            w = wind_by_date.get(r["date"])
            if not w or not w.get("pe") or not r.get("pe"):
                continue
            pe_diffs.append((r["pe"] - w["pe"]) / w["pe"] * 100)
            series.append({
                "date": r["date"],
                "pe_wind": w["pe"],
                "pe_auto": r["pe"],
                "close_wind": w.get("close"),
                "close_auto": r.get("close"),
            })
        if pe_diffs:
            compare["stats"] = {
                "overlap_weeks": len(pe_diffs),
                "pe_mean_diff_pct": round(sum(pe_diffs) / len(pe_diffs), 2),
                "pe_latest_diff_pct": round(pe_diffs[-1], 2),
            }
        compare["series"] = series
    except Exception as e:
        logger.warning(f"[hs300_auto] Wind 对比构建失败: {e}")
    # 官方校验：中证官网日频 PE1 vs 乐咕日频滚动PE
    legu_daily_pe = {d: {"pe": v[1]} for d, v in legu_daily.items() if v[1]}
    compare["csindex_check"] = _csindex_check(legu_daily_pe)
    return compare


def get_auto_meta() -> dict:
    """供 /list 使用：有缓存给真实元信息，无缓存给占位"""
    try:
        payload = get_payload()
        return payload["meta"]
    except Exception as e:
        logger.warning(f"[hs300_auto] meta 获取失败: {e}")
        return {
            "code": "hs300_auto", "name": "沪深300·自动(乐咕)", "market": "A股",
            "baseline": _BASELINE, "discount": _DISCOUNT, "bond_name": "十年期中国国债收益率",
            "auto": True, "error": f"自动数据构建中或失败: {e}",
        }


def get_payload() -> dict:
    import time
    now = time.time()
    if _mem_cache["payload"] and now - _mem_cache["ts"] < _CACHE_TTL_HOURS * 3600:
        return _mem_cache["payload"]
    payload = build_payload()
    _mem_cache["payload"] = payload
    _mem_cache["ts"] = now
    return payload


def is_auto_code(code: str) -> bool:
    return code == "hs300_auto"
