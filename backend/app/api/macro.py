"""
宏观数据API - 使用ThreadPoolExecutor并行获取
数据源优先级：FRED(美国官方) > AKShare(东方财富爬虫) > Tushare

指标分类体系（领先/同步/滞后）:
  领先指标(Leading): PMI、消费者信心、收益率曲线、新增信贷、M2、失业金初请
  同步指标(Coincident): GDP、工业增加值、零售销售、非农就业
  滞后指标(Lagging): CPI、PPI、LPR、失业率、房价
"""
from fastapi import APIRouter
from app.services.akshare_service import akshare_service
from app.services.fred_service import fred_service
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

router = APIRouter()

# ==================== 指标分类定义 ====================

INDICATOR_TYPE = {
    # 领先指标 — 经济转折的先行信号
    "pmi": "leading", "caixin_mfg_pmi": "leading", "caixin_services_pmi": "leading",
    "consumer_confidence": "leading", "yield_curve": "leading", "new_credit": "leading",
    "money_supply": "leading", "ism_pmi": "leading", "ism_services_pmi": "leading",
    "initial_claims": "leading", "housing_starts": "leading",
    # 同步指标 — 确认经济当前状态
    "gdp": "coincident", "industrial_production": "coincident",
    "retail_sales": "coincident", "non_farm": "coincident", "trade_balance": "coincident",
    # 滞后指标 — 确认趋势已形成
    "cpi": "lagging", "ppi": "lagging", "lpr": "lagging",
    "unemployment": "lagging", "housing_price": "lagging", "fed_rate": "lagging",
}

# 宏观周期阶段判定阈值
CYCLE_THRESHOLDS = {
    "expansion": {"pmi_min": 50, "cpi_range": (0, 3), "confidence_min": 100},
    "peak": {"pmi_min": 52, "cpi_min": 3},
    "contraction": {"pmi_max": 50, "confidence_max": 100},
    "trough": {"pmi_max": 48, "cpi_max": 0},
}


def _latest_with_value(series):
    """从数据序列中找到第一个value不为None的条目（跳过未来计划发布的空数据）"""
    if not series:
        return None
    for item in series:
        if item.get('value') is not None:
            return item
    return series[0]


def _calc_trend(series, key='value', lookback=6):
    """计算趋势方向和动量

    Returns:
        {"direction": "up"|"down"|"flat", "momentum": float, "change_pct": float}
    """
    if not series or len(series) < 2:
        return {"direction": "flat", "momentum": 0, "change_pct": 0}
    values = []
    for item in series[:lookback]:
        v = item.get(key) if isinstance(item, dict) else item
        if v is not None:
            values.append(float(v))
    if len(values) < 2:
        return {"direction": "flat", "momentum": 0, "change_pct": 0}
    # 最新值 vs 上一期
    latest, prev = values[0], values[1]
    change = latest - prev
    pct = (change / abs(prev) * 100) if prev != 0 else 0
    # 动量：近3期平均变化
    if len(values) >= 3:
        recent_changes = [values[i] - values[i+1] for i in range(min(3, len(values)-1))]
        momentum = sum(recent_changes) / len(recent_changes)
    else:
        momentum = change
    direction = "up" if change > 0 else ("down" if change < 0 else "flat")
    return {"direction": direction, "momentum": round(momentum, 4), "change_pct": round(pct, 2)}


def _fetch_macro_data():
    """并行获取所有中国宏观数据"""
    tasks = {
        'gdp': akshare_service.get_gdp_data,
        'cpi': akshare_service.get_cpi_data,
        'pmi': akshare_service.get_pmi_data,
        'money_supply': akshare_service.get_money_supply,
        'lpr': akshare_service.get_lpr_data,
        'social_financing': akshare_service.get_social_financing,
        'consumer_confidence': akshare_service.get_consumer_confidence,
        'ppi': akshare_service.get_ppi_data,
        'retail_sales': akshare_service.get_retail_sales,
        'housing_price': akshare_service.get_housing_price,
        'unemployment': akshare_service.get_unemployment_rate,
        'industrial_production': akshare_service.get_industrial_production,
        'trade_balance': akshare_service.get_trade_balance,
    }

    results = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(fn): name for name, fn in tasks.items()}
        for f in as_completed(futures):
            name = futures[f]
            try:
                results[name] = f.result()
            except Exception:
                results[name] = None
    return results


def _fetch_us_macro_data():
    """并行获取所有美国宏观数据"""
    tasks = {
        'cpi': akshare_service.get_us_cpi,
        'unemployment': akshare_service.get_us_unemployment,
        'gdp': akshare_service.get_us_gdp,
        'ism_pmi': akshare_service.get_us_ism_pmi,
        'ism_services_pmi': akshare_service.get_us_ism_services_pmi,
        'fed_rate': akshare_service.get_us_fed_rate,
        'non_farm': akshare_service.get_us_non_farm,
        'ppi': akshare_service.get_us_ppi,
        'retail_sales': akshare_service.get_us_retail_sales,
    }

    results = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(fn): name for name, fn in tasks.items()}
        for f in as_completed(futures):
            name = futures[f]
            try:
                results[name] = f.result()
            except Exception:
                results[name] = None
    return results


@router.get("/overview")
def get_macro_overview():
    """获取宏观数据概览（最新值 + 近期序列）"""
    data = _fetch_macro_data()
    result = {}

    gdp = data.get('gdp')
    if gdp:
        result["gdp"] = {"latest": gdp[0], "series": gdp[:20]}

    cpi = data.get('cpi')
    if cpi:
        result["cpi"] = {"latest": cpi[0], "series": cpi[:24]}

    pmi = data.get('pmi')
    if pmi:
        result["pmi"] = {"latest": pmi[0], "series": pmi[:24]}

    money = data.get('money_supply')
    if money:
        result["money_supply"] = {"latest": money[0], "series": money[:24]}

    lpr = data.get('lpr')
    if lpr:
        result["lpr"] = {"latest": lpr[-1], "series": lpr[-20:]}

    shrz = data.get('social_financing')
    if shrz:
        result["social_financing"] = {"latest": shrz[-1], "series": shrz[-24:]}

    consumer_conf = data.get('consumer_confidence')
    if consumer_conf:
        result["consumer_confidence"] = {"latest": consumer_conf[0], "series": consumer_conf[:24]}

    ppi = data.get('ppi')
    if ppi:
        result["ppi"] = {"latest": ppi[0], "series": ppi[:24]}

    retail = data.get('retail_sales')
    if retail:
        result["retail_sales"] = {"latest": retail[0], "series": retail[:24]}

    housing = data.get('housing_price')
    if housing:
        result["housing_price"] = {"latest": housing[0], "series": housing[:24]}

    unemployment = data.get('unemployment')
    if unemployment:
        result["unemployment"] = {"latest": unemployment[0], "series": unemployment[:24]}

    ip = data.get('industrial_production')
    if ip:
        result["industrial_production"] = {"latest": _latest_with_value(ip), "series": ip[:24]}

    tb = data.get('trade_balance')
    if tb:
        result["trade_balance"] = {"latest": _latest_with_value(tb), "series": tb[:24]}

    # 获取美国核心指标（仅最新值，用于概览卡片）
    with ThreadPoolExecutor(max_workers=4) as pool:
        us_futures = {
            pool.submit(akshare_service.get_us_fed_rate): 'us_fed_rate',
            pool.submit(akshare_service.get_us_gdp): 'us_gdp',
            pool.submit(akshare_service.get_us_ism_pmi): 'us_ism_pmi',
            pool.submit(akshare_service.get_us_non_farm): 'us_non_farm',
        }
        for f in as_completed(us_futures):
            name = us_futures[f]
            try:
                d = f.result()
                if d:
                    result[name] = {"latest": _latest_with_value(d), "series": d[:12]}
            except Exception:
                pass

    # 获取收益率曲线利差
    try:
        yc = akshare_service.get_yield_curve()
        if yc:
            us_spread = [d for d in yc.get('us', []) if d.get('spread_10y_2y') is not None]
            cn_spread = [d for d in yc.get('cn', []) if d.get('spread_10y_2y') is not None]
            if us_spread:
                result["us_yield_spread"] = {"latest": us_spread[-1], "series": us_spread[-24:]}
            if cn_spread:
                result["cn_yield_spread"] = {"latest": cn_spread[-1], "series": cn_spread[-24:]}
    except Exception:
        pass

    return result


@router.get("/china")
def get_china_macro():
    """获取中国宏观数据全量"""
    data = _fetch_macro_data()
    return data


@router.get("/us")
def get_us_macro():
    """获取美国宏观数据（9项 + FRED增强）

    数据源优先级：FRED(美国官方权威) > AKShare(东方财富爬虫)
    每项指标附带数据源标记和时效性
    """
    ak_data = _fetch_us_macro_data()
    result = {}

    # FRED增强：对核心指标用FRED数据补充/替换
    fred_available = fred_service._is_available()
    fred_enhanced_keys = {
        "fed_rate": "fed_rate_monthly",
        "unemployment": "unemployment",
        "nonfarm_payroll": "nonfarm_payroll",
        "gdp_real": "gdp_real",
        "industrial_production": "industrial_production",
        "retail_sales": "retail_sales",
        "m2": "m2",
    }
    fred_results = {}
    if fred_available:
        try:
            fred_results = fred_service.get_batch(list(fred_enhanced_keys.keys()))
        except Exception:
            pass

    for ak_key, ak_series in ak_data.items():
        entry = ak_series or []
        # 尝试FRED增强
        fred_key = fred_enhanced_keys.get(ak_key)
        fred_indicator = fred_results.get(fred_key) if fred_key else None
        source = "AKShare(东方财富)"
        if fred_indicator and fred_indicator.get("series"):
            entry = fred_indicator["series"]
            source = "FRED(美国官方)"
        result[ak_key] = {
            "series": entry[:36],
            "latest": _latest_with_value(entry),
            "trend": _calc_trend(entry),
            "source": source,
            "indicator_type": INDICATOR_TYPE.get(ak_key, "coincident"),
        }

    # 补充FRED独有的指标
    if fred_available:
        fred_extra = {
            "core_cpi": "core_cpi",
            "pce": "pce",
            "initial_claims": "initial_claims",
            "consumer_sentiment": "consumer_sentiment",
        }
        try:
            extra_data = fred_service.get_batch(list(fred_extra.keys()))
            for key, series_id in fred_extra.items():
                indicator = extra_data.get(key)
                if indicator and indicator.get("series"):
                    result[f"fred_{key}"] = {
                        "series": indicator["series"][:36],
                        "latest": indicator["series"][0] if indicator["series"] else None,
                        "trend": _calc_trend(indicator["series"]),
                        "source": "FRED(美国官方)",
                        "indicator_type": INDICATOR_TYPE.get(key, "coincident"),
                    }
        except Exception:
            pass

    return result


@router.get("/yield-curve")
def get_yield_curve():
    """获取中美收益率曲线及2Y-10Y利差"""
    return akshare_service.get_yield_curve()


@router.get("/leading-indicators")
def get_leading_indicators():
    """领先指标仪表盘 — 经济转折的先行信号

    领先指标通常在经济拐点前3-6个月发出信号:
    - PMI: 50为荣枯线，连续3月方向确认趋势
    - 收益率曲线: 倒挂→衰退（过去50年100%准确率）
    - 新增信贷: 信用扩张→经济回暖（领先6-9个月）
    - 消费者信心: 领先消费支出2-3个月
    - M2增速: 货币扩张→经济活动增加（领先6-12个月）
    """
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {
            pool.submit(akshare_service.get_pmi_data): 'cn_pmi',
            pool.submit(akshare_service.get_caixin_mfg_pmi): 'caixin_mfg',
            pool.submit(akshare_service.get_consumer_confidence): 'confidence',
            pool.submit(akshare_service.get_yield_curve): 'yield_curve',
            pool.submit(akshare_service.get_new_financial_credit): 'new_credit',
            pool.submit(akshare_service.get_money_supply): 'money_supply',
            pool.submit(akshare_service.get_us_ism_pmi): 'us_ism_pmi',
        }
        data = {}
        for f in as_completed(futures):
            name = futures[f]
            try:
                data[name] = f.result()
            except Exception:
                data[name] = None

    indicators = []

    # 中国制造业PMI
    cn_pmi = data.get('cn_pmi') or []
    if cn_pmi:
        latest = cn_pmi[0]
        mfg_val = latest.get('manufacturing')
        trend = _calc_trend(cn_pmi, 'manufacturing')
        indicators.append({
            "name": "官方制造业PMI", "type": "leading", "country": "CN",
            "value": mfg_val, "date": latest.get('date'),
            "trend": trend,
            "signal": "expansion" if mfg_val and mfg_val >= 50 else "contraction",
            "desc": f"{'扩张区间' if mfg_val and mfg_val >= 50 else '收缩区间'}，连续{'上升' if trend['direction'] == 'up' else '下降' if trend['direction'] == 'down' else '持平'}",
            "lead_months": "1-2个月",
            "source": "AKShare(统计局)",
        })

    # 财新制造业PMI
    caixin = data.get('caixin_mfg') or []
    caixin_latest = _latest_with_value(caixin)
    if caixin_latest:
        val = caixin_latest.get('value')
        trend = _calc_trend(caixin)
        indicators.append({
            "name": "财新制造业PMI", "type": "leading", "country": "CN",
            "value": val, "date": caixin_latest.get('date'),
            "trend": trend,
            "signal": "expansion" if val and val >= 50 else "contraction",
            "desc": f"中小企业景气度，{'扩张' if val and val >= 50 else '收缩'}",
            "lead_months": "1-2个月",
            "source": "AKShare(财新/Markit)",
        })

    # 消费者信心
    conf = data.get('confidence') or []
    if conf:
        latest = conf[0]
        val = latest.get('confidence')
        trend = _calc_trend(conf, 'confidence')
        indicators.append({
            "name": "消费者信心指数", "type": "leading", "country": "CN",
            "value": val, "date": latest.get('date'),
            "trend": trend,
            "signal": "optimistic" if val and val >= 100 else "pessimistic",
            "desc": f"{'乐观' if val and val >= 100 else '悲观'}，领先消费支出2-3个月",
            "lead_months": "2-3个月",
            "source": "AKShare(统计局)",
        })

    # 收益率曲线
    yc = data.get('yield_curve') or {}
    us_spread_list = [d for d in yc.get('us', []) if d.get('spread_10y_2y') is not None]
    if us_spread_list:
        latest = us_spread_list[-1]
        val = latest.get('spread_10y_2y')
        trend = _calc_trend(us_spread_list, 'spread_10y_2y')
        indicators.append({
            "name": "美债10Y-2Y利差", "type": "leading", "country": "US",
            "value": val, "date": latest.get('date'),
            "trend": trend,
            "signal": "normal" if val and val > 0 else "inverted",
            "desc": f"{'倒挂！衰退信号' if val and val < 0 else '正常'}，过去50年衰退预测准确率100%",
            "lead_months": "6-18个月",
            "source": "AKShare(新浪)",
        })

    # 新增信贷
    credit = data.get('new_credit') or []
    if credit:
        latest = credit[0]
        val = latest.get('value')
        trend = _calc_trend(credit, 'value')
        indicators.append({
            "name": "新增人民币贷款", "type": "leading", "country": "CN",
            "value": val, "date": latest.get('date'),
            "trend": trend,
            "signal": "expanding" if trend['direction'] == 'up' else "contracting",
            "desc": f"信用{'扩张' if trend['direction'] == 'up' else '收缩'}，领先经济活动6-9个月",
            "lead_months": "6-9个月",
            "source": "AKShare(央行)",
        })

    # M2增速
    money = data.get('money_supply') or []
    if money:
        latest = money[0]
        val = latest.get('m2_growth')
        trend = _calc_trend(money, 'm2_growth')
        indicators.append({
            "name": "M2同比增速", "type": "leading", "country": "CN",
            "value": val, "date": latest.get('date'),
            "trend": trend,
            "signal": "loose" if val and val >= 8 else "tight",
            "desc": f"货币{'宽松' if val and val >= 8 else '偏紧'}，领先经济6-12个月",
            "lead_months": "6-12个月",
            "source": "AKShare(央行)",
        })

    # 美国ISM PMI
    us_pmi = data.get('us_ism_pmi') or []
    us_pmi_latest = _latest_with_value(us_pmi)
    if us_pmi_latest:
        val = us_pmi_latest.get('value')
        trend = _calc_trend(us_pmi)
        indicators.append({
            "name": "ISM制造业PMI", "type": "leading", "country": "US",
            "value": val, "date": us_pmi_latest.get('date'),
            "trend": trend,
            "signal": "expansion" if val and val >= 50 else "contraction",
            "desc": f"美国制造业{'扩张' if val and val >= 50 else '收缩'}，全球制造业领先指标",
            "lead_months": "1-3个月",
            "source": "AKShare(东方财富)",
        })

    # 综合领先指标评分
    expansion_count = sum(1 for ind in indicators if ind.get('signal') in ('expansion', 'optimistic', 'normal', 'expanding', 'loose'))
    total = len(indicators)
    composite_score = round(expansion_count / total * 100) if total else 50

    return {
        "indicators": indicators,
        "composite": {
            "score": composite_score,
            "level": _score_to_level(composite_score),
            "expansion_signals": expansion_count,
            "total_signals": total,
            "interpretation": _interpret_leading_score(composite_score),
        },
        "updated_at": datetime.now().isoformat(),
    }


def _interpret_leading_score(score):
    """解读领先指标综合得分"""
    if score >= 80:
        return "多数领先指标指向扩张，经济上行周期确认，建议增配权益类资产"
    elif score >= 60:
        return "领先指标偏积极，经济温和扩张，维持均衡配置"
    elif score >= 40:
        return "领先指标分化，经济动能减弱，建议降低风险敞口"
    elif score >= 20:
        return "多数领先指标指向收缩，经济下行风险加大，建议防御配置"
    else:
        return "领先指标全面收缩，衰退信号强烈，建议大幅降低仓位、增持现金和国债"


# ==================== 信号计算引擎 ====================

def _score_to_level(score):
    """分数转红绿灯等级"""
    if score <= 30:
        return "danger"
    elif score <= 50:
        return "warning"
    elif score <= 70:
        return "neutral"
    else:
        return "healthy"


def _clamp(val, lo=0, hi=100):
    return max(lo, min(hi, val))


def _calc_us_recession(us_ism_pmi, us_non_farm, us_yield_spread):
    """美国衰退风险信号：score越高=越安全"""
    drivers = []
    scores = []

    # ISM制造业PMI
    if us_ism_pmi is not None:
        if us_ism_pmi < 45:
            s, lvl = 20, "danger"
        elif us_ism_pmi < 48:
            s, lvl = 40, "warning"
        elif us_ism_pmi < 50:
            s, lvl = 55, "neutral"
        elif us_ism_pmi < 52:
            s, lvl = 70, "healthy"
        else:
            s, lvl = 85, "healthy"
        scores.append(s)
        drivers.append({"name": "ISM制造业PMI", "value": f"{us_ism_pmi:.1f}", "level": lvl, "desc": f"{'收缩区间' if us_ism_pmi < 50 else '扩张区间'}", "type": "leading"})

    # 非农就业
    if us_non_farm is not None:
        if us_non_farm < 5:
            s, lvl = 20, "danger"
        elif us_non_farm < 10:
            s, lvl = 40, "warning"
        elif us_non_farm < 15:
            s, lvl = 60, "neutral"
        elif us_non_farm < 25:
            s, lvl = 75, "healthy"
        else:
            s, lvl = 90, "healthy"
        scores.append(s)
        drivers.append({"name": "非农就业", "value": f"{us_non_farm:.1f}万", "level": lvl, "desc": f"{'大幅低于预期' if us_non_farm < 10 else '稳健'}", "type": "coincident"})

    # 2Y-10Y利差
    if us_yield_spread is not None:
        if us_yield_spread < 0:
            s, lvl = 15, "danger"
        elif us_yield_spread < 0.2:
            s, lvl = 35, "warning"
        elif us_yield_spread < 0.5:
            s, lvl = 55, "neutral"
        elif us_yield_spread < 1.0:
            s, lvl = 70, "healthy"
        else:
            s, lvl = 85, "healthy"
        scores.append(s)
        drivers.append({"name": "2Y-10Y利差", "value": f"{us_yield_spread:.2f}%", "level": lvl, "desc": f"{'倒挂⚠️' if us_yield_spread < 0 else '偏窄' if us_yield_spread < 0.3 else '正常'}", "type": "leading"})

    avg = sum(scores) / len(scores) if scores else 50
    score = _clamp(round(avg))
    recession_prob = _clamp(round(100 - score * 0.8))
    return {
        "id": "us_recession",
        "name": "美国衰退风险",
        "score": score,
        "level": _score_to_level(score),
        "probability": f"{recession_prob}%",
        "detail": f"基于{len(scores)}项指标综合评估",
        "drivers": drivers,
        "indicator_type": "mixed",
    }


def _calc_fed_direction(us_ism_pmi, us_ppi, us_non_farm):
    """美联储方向信号：score越高=越可能降息"""
    drivers = []
    scores = []

    if us_ism_pmi is not None:
        if us_ism_pmi < 45:
            s = 85
        elif us_ism_pmi < 48:
            s = 70
        elif us_ism_pmi < 50:
            s = 55
        elif us_ism_pmi < 52:
            s = 40
        else:
            s = 25
        scores.append(s)
        lvl = _score_to_level(s)
        drivers.append({"name": "制造业PMI", "value": f"{us_ism_pmi:.1f}", "level": lvl, "desc": f"{'经济走弱→降息' if us_ism_pmi < 50 else '经济稳健→维持'}", "type": "leading"})

    if us_ppi is not None:
        if us_ppi < 0:
            s = 80
        elif us_ppi < 0.3:
            s = 65
        elif us_ppi < 0.5:
            s = 50
        elif us_ppi < 1.0:
            s = 35
        else:
            s = 20
        scores.append(s)
        lvl = _score_to_level(s)
        drivers.append({"name": "PPI环比", "value": f"{us_ppi:.1f}%", "level": lvl, "desc": f"{'通胀压力大→不降' if us_ppi > 0.5 else '通胀温和→可降'}", "type": "lagging"})

    if us_non_farm is not None:
        if us_non_farm < 5:
            s = 85
        elif us_non_farm < 10:
            s = 70
        elif us_non_farm < 15:
            s = 50
        elif us_non_farm < 25:
            s = 35
        else:
            s = 20
        scores.append(s)
        lvl = _score_to_level(s)
        drivers.append({"name": "就业数据", "value": f"{us_non_farm:.1f}万", "level": lvl, "desc": f"{'就业疲软→降息' if us_non_farm < 10 else '就业强劲→不降'}", "type": "coincident"})

    avg = sum(scores) / len(scores) if scores else 50
    score = _clamp(round(avg))
    cut_prob = _clamp(round(score * 0.85))
    return {
        "id": "fed_direction",
        "name": "美联储降息概率",
        "score": score,
        "level": _score_to_level(score),
        "probability": f"{cut_prob}%",
        "detail": "score越高=越可能降息",
        "drivers": drivers,
        "indicator_type": "mixed",
    }


def _calc_china_recovery(cpi, ppi, pmi_mfg, retail_yoy, confidence, housing_yoy):
    """中国复苏强度信号"""
    drivers = []
    scores = []

    if pmi_mfg is not None:
        if pmi_mfg < 48:
            s = 25
        elif pmi_mfg < 50:
            s = 45
        elif pmi_mfg < 51:
            s = 60
        elif pmi_mfg < 53:
            s = 75
        else:
            s = 90
        scores.append(s)
        drivers.append({"name": "制造业PMI", "value": f"{pmi_mfg:.1f}", "level": _score_to_level(s), "desc": f"{'收缩' if pmi_mfg < 50 else '扩张'}", "type": "leading"})

    if cpi is not None:
        if cpi < 0:
            s = 30
        elif cpi < 1:
            s = 50
        elif cpi < 2.5:
            s = 75
        elif cpi < 3.5:
            s = 60
        else:
            s = 35
        scores.append(s)
        drivers.append({"name": "CPI同比", "value": f"{cpi:.1f}%", "level": _score_to_level(s), "desc": f"{'通缩' if cpi < 0 else '温和通胀' if cpi < 2.5 else '偏高'}", "type": "lagging"})

    if ppi is not None:
        if ppi < -3:
            s = 20
        elif ppi < 0:
            s = 40
        elif ppi < 3:
            s = 65
        elif ppi < 6:
            s = 75
        else:
            s = 50
        scores.append(s)
        drivers.append({"name": "PPI同比", "value": f"{ppi:.1f}%", "level": _score_to_level(s), "desc": f"{'通缩' if ppi < 0 else '回暖' if ppi < 6 else '偏热'}", "type": "lagging"})

    if retail_yoy is not None:
        if retail_yoy < 0:
            s = 25
        elif retail_yoy < 2:
            s = 45
        elif retail_yoy < 5:
            s = 65
        elif retail_yoy < 8:
            s = 80
        else:
            s = 90
        scores.append(s)
        drivers.append({"name": "社零增速", "value": f"{retail_yoy:.1f}%", "level": _score_to_level(s), "desc": f"{'消费疲软' if retail_yoy < 3 else '消费稳健'}", "type": "coincident"})

    if confidence is not None:
        if confidence < 85:
            s = 25
        elif confidence < 95:
            s = 45
        elif confidence < 105:
            s = 60
        elif confidence < 115:
            s = 75
        else:
            s = 90
        scores.append(s)
        drivers.append({"name": "消费者信心", "value": f"{confidence:.1f}", "level": _score_to_level(s), "desc": f"{'悲观' if confidence < 100 else '乐观'}", "type": "leading"})

    if housing_yoy is not None:
        if housing_yoy < -3:
            s = 20
        elif housing_yoy < -1:
            s = 35
        elif housing_yoy < 0:
            s = 50
        elif housing_yoy < 2:
            s = 70
        else:
            s = 85
        scores.append(s)
        drivers.append({"name": "房价同比", "value": f"{housing_yoy:.1f}%", "level": _score_to_level(s), "desc": f"{'下跌' if housing_yoy < 0 else '企稳回升'}", "type": "lagging"})

    avg = sum(scores) / len(scores) if scores else 50
    score = _clamp(round(avg))
    recovery_prob = _clamp(round(score * 0.8))
    return {
        "id": "china_recovery",
        "name": "中国复苏强度",
        "score": score,
        "level": _score_to_level(score),
        "probability": f"{recovery_prob}%",
        "detail": f"基于{len(scores)}项指标综合评估",
        "drivers": drivers,
        "indicator_type": "mixed",
    }


def _calc_inflation(cn_cpi, cn_ppi, us_ppi):
    """通胀温度信号：score越高=通胀越温和（对市场越友好）"""
    drivers = []
    scores = []

    if cn_cpi is not None:
        if cn_cpi < 0:
            s = 30
        elif cn_cpi < 2:
            s = 75
        elif cn_cpi < 3:
            s = 65
        else:
            s = 35
        scores.append(s)
        drivers.append({"name": "中国CPI", "value": f"{cn_cpi:.1f}%", "level": _score_to_level(s), "desc": f"{'通缩' if cn_cpi < 0 else '温和' if cn_cpi < 2 else '偏高'}", "type": "lagging"})

    if cn_ppi is not None:
        if cn_ppi < -3:
            s = 25
        elif cn_ppi < 0:
            s = 40
        elif cn_ppi < 5:
            s = 70
        else:
            s = 45
        scores.append(s)
        drivers.append({"name": "中国PPI", "value": f"{cn_ppi:.1f}%", "level": _score_to_level(s), "desc": f"{'通缩' if cn_ppi < 0 else '温和上涨'}", "type": "lagging"})

    if us_ppi is not None:
        if us_ppi < 0:
            s = 70
        elif us_ppi < 0.3:
            s = 75
        elif us_ppi < 0.5:
            s = 55
        elif us_ppi < 1.0:
            s = 40
        else:
            s = 25
        scores.append(s)
        drivers.append({"name": "美国PPI环比", "value": f"{us_ppi:.1f}%", "level": _score_to_level(s), "desc": f"{'通胀压力大' if us_ppi > 0.5 else '温和'}", "type": "lagging"})

    avg = sum(scores) / len(scores) if scores else 50
    score = _clamp(round(avg))
    return {
        "id": "inflation",
        "name": "通胀温度",
        "score": score,
        "level": _score_to_level(score),
        "probability": f"{score}%",
        "detail": "score越高=通胀越温和",
        "drivers": drivers,
        "indicator_type": "lagging",
    }


def _calc_liquidity(m2_growth, lpr_1y, fed_rate):
    """流动性环境信号：score越高=流动性越宽松"""
    drivers = []
    scores = []

    if m2_growth is not None:
        if m2_growth < 6:
            s = 30
        elif m2_growth < 8:
            s = 50
        elif m2_growth < 10:
            s = 70
        else:
            s = 85
        scores.append(s)
        drivers.append({"name": "M2增速", "value": f"{m2_growth:.1f}%", "level": _score_to_level(s), "desc": f"{'偏紧' if m2_growth < 8 else '宽松'}", "type": "leading"})

    if lpr_1y is not None:
        if lpr_1y > 4.5:
            s = 30
        elif lpr_1y > 3.5:
            s = 50
        elif lpr_1y > 3.0:
            s = 65
        else:
            s = 80
        scores.append(s)
        drivers.append({"name": "LPR(1Y)", "value": f"{lpr_1y:.2f}%", "level": _score_to_level(s), "desc": f"{'历史低位' if lpr_1y <= 3.0 else '中等' if lpr_1y <= 3.5 else '偏高'}", "type": "lagging"})

    if fed_rate is not None:
        if fed_rate > 5:
            s = 25
        elif fed_rate > 4:
            s = 45
        elif fed_rate > 3:
            s = 65
        elif fed_rate > 2:
            s = 80
        else:
            s = 90
        scores.append(s)
        drivers.append({"name": "美联储利率", "value": f"{fed_rate:.2f}%", "level": _score_to_level(s), "desc": f"{'高利率' if fed_rate > 4 else '中等' if fed_rate > 2.5 else '低利率'}", "type": "lagging"})

    avg = sum(scores) / len(scores) if scores else 50
    score = _clamp(round(avg))
    return {
        "id": "liquidity",
        "name": "流动性环境",
        "score": score,
        "level": _score_to_level(score),
        "probability": f"{score}%",
        "detail": "score越高=流动性越宽松",
        "drivers": drivers,
        "indicator_type": "mixed",
    }


def _calc_yield_curve(us_spread, cn_spread):
    """收益率曲线信号：score越高=曲线越正常（经济预期越好）"""
    drivers = []
    scores = []

    if us_spread is not None:
        if us_spread < 0:
            s = 15
        elif us_spread < 0.2:
            s = 35
        elif us_spread < 0.5:
            s = 55
        elif us_spread < 1.0:
            s = 75
        else:
            s = 90
        scores.append(s)
        drivers.append({"name": "美债10Y-2Y", "value": f"{us_spread:.2f}%", "level": _score_to_level(s), "desc": f"{'倒挂⚠️' if us_spread < 0 else '偏窄' if us_spread < 0.3 else '正常'}", "type": "leading"})

    if cn_spread is not None:
        if cn_spread < 0:
            s = 20
        elif cn_spread < 0.2:
            s = 40
        elif cn_spread < 0.5:
            s = 60
        else:
            s = 80
        scores.append(s)
        drivers.append({"name": "中债10Y-2Y", "value": f"{cn_spread:.2f}%", "level": _score_to_level(s), "desc": f"{'倒挂' if cn_spread < 0 else '偏窄' if cn_spread < 0.3 else '正常'}", "type": "leading"})

    avg = sum(scores) / len(scores) if scores else 50
    score = _clamp(round(avg))
    return {
        "id": "yield_curve",
        "name": "收益率曲线",
        "score": score,
        "level": _score_to_level(score),
        "probability": f"{score}%",
        "detail": "score越高=曲线越正常",
        "drivers": drivers,
        "indicator_type": "leading",
    }


def _calc_asset_signals(signals):
    """基于综合信号推导资产配置方向"""
    # 提取各信号score
    sig_map = {s["id"]: s["score"] for s in signals}
    recession = sig_map.get("us_recession", 50)  # 越高=越安全
    fed = sig_map.get("fed_direction", 50)       # 越高=越可能降息
    china = sig_map.get("china_recovery", 50)     # 越高=复苏越强
    inflation = sig_map.get("inflation", 50)      # 越高=越温和
    liquidity = sig_map.get("liquidity", 50)      # 越高=越宽松
    curve = sig_map.get("yield_curve", 50)        # 越高=越正常

    assets = []

    # 中国国债：经济弱+宽松=看涨
    cn_bond_score = (100 - china) * 0.4 + liquidity * 0.4 + (100 - inflation) * 0.2
    cn_bond_conf = _clamp(round(cn_bond_score))
    assets.append({
        "name": "中国国债",
        "direction": "看涨" if cn_bond_conf > 55 else ("看跌" if cn_bond_conf < 45 else "中性"),
        "confidence": cn_bond_conf,
        "reason": "经济偏弱+货币宽松→利率下行" if cn_bond_conf > 55 else "经济回暖→利率可能上行",
    })

    # A股高股息：低利率+经济弱=类债券吸引力
    div_score = liquidity * 0.4 + (100 - china) * 0.3 + fed * 0.3
    div_conf = _clamp(round(div_score))
    assets.append({
        "name": "A股高股息",
        "direction": "看涨" if div_conf > 55 else ("看跌" if div_conf < 45 else "中性"),
        "confidence": div_conf,
        "reason": "低利率环境下类债券逻辑" if div_conf > 55 else "利率上行压制估值",
    })

    # A股消费：消费复苏=看涨
    cons_score = china * 0.6 + liquidity * 0.2 + inflation * 0.2
    cons_conf = _clamp(round(cons_score))
    assets.append({
        "name": "A股消费",
        "direction": "看涨" if cons_conf > 60 else ("看跌" if cons_conf < 40 else "中性"),
        "confidence": cons_conf,
        "reason": "消费复苏信号增强" if cons_conf > 60 else "消费疲软，复苏缓慢",
    })

    # A股出口链：经济好+无衰退=看涨
    export_score = china * 0.4 + recession * 0.3 + inflation * 0.3
    export_conf = _clamp(round(export_score))
    assets.append({
        "name": "A股出口链",
        "direction": "看涨" if export_conf > 55 else ("看跌" if export_conf < 45 else "中性"),
        "confidence": export_conf,
        "reason": "外需稳健+中国制造业强" if export_conf > 55 else "外需走弱+关税风险",
    })

    # 美股科技：降息+无衰退=看涨
    tech_score = fed * 0.4 + recession * 0.4 + liquidity * 0.2
    tech_conf = _clamp(round(tech_score))
    assets.append({
        "name": "美股科技",
        "direction": "看涨" if tech_conf > 55 else ("看跌" if tech_conf < 45 else "中性"),
        "confidence": tech_conf,
        "reason": "降息预期+AI叙事" if tech_conf > 55 else "高利率压制估值",
    })

    # 美股防御：衰退风险=看涨
    def_score = (100 - recession) * 0.5 + (100 - inflation) * 0.3 + fed * 0.2
    def_conf = _clamp(round(def_score))
    assets.append({
        "name": "美股防御",
        "direction": "看涨" if def_conf > 55 else ("看跌" if def_conf < 45 else "中性"),
        "confidence": def_conf,
        "reason": "衰退预期→避风港" if def_conf > 55 else "经济强劲→跑输大盘",
    })

    # 黄金：降息+避险+通胀=看涨
    gold_score = fed * 0.3 + (100 - recession) * 0.3 + (100 - inflation) * 0.2 + liquidity * 0.2
    gold_conf = _clamp(round(gold_score))
    assets.append({
        "name": "黄金",
        "direction": "看涨" if gold_conf > 55 else ("看跌" if gold_conf < 45 else "中性"),
        "confidence": gold_conf,
        "reason": "降息预期+避险需求" if gold_conf > 55 else "实际利率上行压制金价",
    })

    # 美元：利差收窄+降息=看跌
    usd_score = (100 - fed) * 0.5 + recession * 0.3 + (100 - liquidity) * 0.2
    usd_conf = _clamp(round(usd_score))
    assets.append({
        "name": "美元",
        "direction": "看涨" if usd_conf > 55 else ("看跌" if usd_conf < 45 else "中性"),
        "confidence": usd_conf,
        "reason": "利差扩大+避险" if usd_conf > 55 else "降息预期压制美元",
    })

    return assets


@router.get("/signals")
def get_macro_signals():
    """
    宏观信号仪表盘：基于实时数据计算核心信号 + 资产配置建议

    数据源优先级：
    - 美国数据：FRED(官方权威) > AKShare(东方财富爬虫)
    - 中国数据：AKShare(统计局/央行) + 财新PMI交叉验证

    每条数据附带质量标记：source(来源), quality(官方/第三方), freshness(数据时效)
    """
    # ========== 并行获取所有数据源 ==========
    all_data = {}
    fred_data = {}

    with ThreadPoolExecutor(max_workers=10) as pool:
        # AKShare 数据
        ak_futures = {
            pool.submit(akshare_service.get_us_ism_pmi): 'us_ism_pmi',
            pool.submit(akshare_service.get_us_non_farm): 'us_non_farm',
            pool.submit(akshare_service.get_us_fed_rate): 'us_fed_rate',
            pool.submit(akshare_service.get_us_ppi): 'us_ppi',
            pool.submit(akshare_service.get_cpi_data): 'cn_cpi',
            pool.submit(akshare_service.get_ppi_data): 'cn_ppi',
            pool.submit(akshare_service.get_pmi_data): 'cn_pmi',
            pool.submit(akshare_service.get_retail_sales): 'cn_retail',
            pool.submit(akshare_service.get_consumer_confidence): 'cn_confidence',
            pool.submit(akshare_service.get_housing_price): 'cn_housing',
            pool.submit(akshare_service.get_money_supply): 'cn_money',
            pool.submit(akshare_service.get_lpr_data): 'cn_lpr',
            pool.submit(akshare_service.get_yield_curve): 'yield_curve',
            pool.submit(akshare_service.get_caixin_mfg_pmi): 'caixin_mfg_pmi',
            pool.submit(akshare_service.get_caixin_services_pmi): 'caixin_services_pmi',
            pool.submit(akshare_service.get_fx_gold_reserves): 'fx_gold',
            pool.submit(akshare_service.get_new_financial_credit): 'new_credit',
        }
        for f in as_completed(ak_futures):
            name = ak_futures[f]
            try:
                all_data[name] = f.result()
            except Exception:
                all_data[name] = None

    # FRED 数据（如果可用）
    fred_available = fred_service._is_available()
    if fred_available:
        try:
            fred_keys = ["unemployment", "nonfarm_payroll", "fed_rate", "treasury_10y", "treasury_2y", "yield_spread_10y2y", "consumer_sentiment"]
            fred_data = fred_service.get_batch(fred_keys)
        except Exception:
            fred_data = {}

    # ========== 数据质量追踪 ==========
    data_quality = []

    def _track(name, value, source, date_str=None, confidence="medium"):
        """记录数据质量"""
        if value is not None:
            freshness = "unknown"
            if date_str:
                try:
                    d = datetime.strptime(str(date_str)[:10], "%Y-%m-%d")
                    days = (datetime.now() - d).days
                    freshness = "fresh" if days < 30 else "recent" if days < 90 else "stale"
                except:
                    pass
            data_quality.append({
                "name": name, "value": value, "source": source,
                "date": date_str, "freshness": freshness, "confidence": confidence,
            })

    # ========== 提取最新值（优先FRED，降级AKShare）==========

    # 美国ISM PMI — 仅AKShare（FRED无此数据）
    us_ism_pmi_data = _latest_with_value(all_data.get('us_ism_pmi') or [])
    us_ism_pmi = us_ism_pmi_data.get('value') if us_ism_pmi_data else None
    _track("ISM制造业PMI", us_ism_pmi, "AKShare(东方财富)", us_ism_pmi_data.get('date') if us_ism_pmi_data else None)

    # 美国非农 — 优先FRED
    if fred_data.get('nonfarm_payroll') and fred_data['nonfarm_payroll'].get('latest'):
        us_non_farm = fred_data['nonfarm_payroll']['latest'].get('value')
        _track("非农就业", us_non_farm, "FRED(美国官方)", fred_data['nonfarm_payroll']['latest'].get('date'), "high")
    else:
        us_non_farm_data = _latest_with_value(all_data.get('us_non_farm') or [])
        us_non_farm = us_non_farm_data.get('value') if us_non_farm_data else None
        _track("非农就业", us_non_farm, "AKShare(东方财富)", us_non_farm_data.get('date') if us_non_farm_data else None)

    # 美联储利率 — 优先FRED（每日更新）
    if fred_data.get('fed_rate') and fred_data['fed_rate'].get('latest'):
        fed_rate = fred_data['fed_rate']['latest'].get('value')
        _track("美联储利率", fed_rate, "FRED(美国官方)", fred_data['fed_rate']['latest'].get('date'), "high")
    else:
        us_fed_data = _latest_with_value(all_data.get('us_fed_rate') or [])
        fed_rate = us_fed_data.get('value') if us_fed_data else None
        _track("美联储利率", fed_rate, "AKShare(东方财富)", us_fed_data.get('date') if us_fed_data else None)

    # 美国PPI — AKShare
    us_ppi_data = _latest_with_value(all_data.get('us_ppi') or [])
    us_ppi = us_ppi_data.get('value') if us_ppi_data else None
    _track("美国PPI", us_ppi, "AKShare(东方财富)", us_ppi_data.get('date') if us_ppi_data else None)

    # 收益率曲线 — 优先FRED
    if fred_data.get('yield_spread_10y2y') and fred_data['yield_spread_10y2y'].get('latest'):
        us_spread = fred_data['yield_spread_10y2y']['latest'].get('value')
        _track("美债10Y-2Y利差", us_spread, "FRED(美国官方)", fred_data['yield_spread_10y2y']['latest'].get('date'), "high")
    else:
        yc = all_data.get('yield_curve') or {}
        us_spread_list = [d for d in yc.get('us', []) if d.get('spread_10y_2y') is not None]
        us_spread = us_spread_list[-1]['spread_10y_2y'] if us_spread_list else None
        _track("美债10Y-2Y利差", us_spread, "AKShare(新浪)", us_spread_list[-1].get('date') if us_spread_list else None)

    yc = all_data.get('yield_curve') or {}
    cn_spread_list = [d for d in yc.get('cn', []) if d.get('spread_10y_2y') is not None]
    cn_spread = cn_spread_list[-1]['spread_10y_2y'] if cn_spread_list else None
    _track("中债10Y-2Y利差", cn_spread, "AKShare(新浪)", cn_spread_list[-1].get('date') if cn_spread_list else None)

    # 消费者信心 — 优先FRED
    if fred_data.get('consumer_sentiment') and fred_data['consumer_sentiment'].get('latest'):
        fred_conf = fred_data['consumer_sentiment']['latest'].get('value')
        _track("消费者信心(FRED)", fred_conf, "FRED(密歇根大学)", fred_data['consumer_sentiment']['latest'].get('date'), "high")

    # 中国数据 — AKShare为主
    cn_cpi_data = (all_data.get('cn_cpi') or [None])[0]
    cn_cpi = cn_cpi_data.get('cpi_yoy') if cn_cpi_data else None
    _track("中国CPI", cn_cpi, "AKShare(统计局)", cn_cpi_data.get('date') if cn_cpi_data else None, "high")

    cn_ppi_data = (all_data.get('cn_ppi') or [None])[0]
    cn_ppi = cn_ppi_data.get('yoy') if cn_ppi_data else None
    _track("中国PPI", cn_ppi, "AKShare(统计局)", cn_ppi_data.get('date') if cn_ppi_data else None, "high")

    cn_pmi_data = (all_data.get('cn_pmi') or [None])[0]
    pmi_mfg = cn_pmi_data.get('manufacturing') if cn_pmi_data else None
    _track("官方制造业PMI", pmi_mfg, "AKShare(统计局)", cn_pmi_data.get('date') if cn_pmi_data else None, "high")

    # 财新PMI — 交叉验证
    caixin_mfg_data = _latest_with_value(all_data.get('caixin_mfg_pmi') or [])
    caixin_mfg = caixin_mfg_data.get('value') if caixin_mfg_data else None
    _track("财新制造业PMI", caixin_mfg, "AKShare(财新/Markit)", caixin_mfg_data.get('date') if caixin_mfg_data else None, "high")

    # PMI交叉验证
    pmi_cross_check = None
    if pmi_mfg is not None and caixin_mfg is not None:
        diff = abs(pmi_mfg - caixin_mfg)
        if diff > 2:
            pmi_cross_check = f"⚠️ 官方PMI({pmi_mfg})与财新PMI({caixin_mfg})差异较大({diff:.1f}点)，需关注"
        else:
            pmi_cross_check = f"✓ 官方({pmi_mfg})与财新({caixin_mfg})一致"

    cn_retail_data = (all_data.get('cn_retail') or [None])[0]
    retail_yoy = cn_retail_data.get('yoy') if cn_retail_data else None
    _track("社零增速", retail_yoy, "AKShare(统计局)", cn_retail_data.get('date') if cn_retail_data else None, "high")

    cn_conf_data = (all_data.get('cn_confidence') or [None])[0]
    confidence = cn_conf_data.get('confidence') if cn_conf_data else None
    _track("消费者信心指数", confidence, "AKShare(统计局)", cn_conf_data.get('date') if cn_conf_data else None, "high")

    cn_housing_data = (all_data.get('cn_housing') or [None])[0]
    housing_yoy = cn_housing_data.get('avg_yoy') if cn_housing_data else None
    _track("房价同比(一线)", housing_yoy, "AKShare(统计局)", cn_housing_data.get('date') if cn_housing_data else None, "medium")

    cn_money_data = (all_data.get('cn_money') or [None])[0]
    m2_growth = cn_money_data.get('m2_growth') if cn_money_data else None
    _track("M2增速", m2_growth, "AKShare(央行)", cn_money_data.get('date') if cn_money_data else None, "high")

    cn_lpr_data = all_data.get('cn_lpr') or []
    lpr_1y = cn_lpr_data[-1].get('lpr_1y') if cn_lpr_data else None
    _track("LPR(1Y)", lpr_1y, "AKShare(央行)", cn_lpr_data[-1].get('date') if cn_lpr_data else None, "high")

    # 外汇储备
    fx_data = (all_data.get('fx_gold') or [None])[0] if all_data.get('fx_gold') else None
    forex_reserves = fx_data.get('forex_reserves') if fx_data else None
    _track("外汇储备", forex_reserves, "AKShare(央行)", fx_data.get('date') if fx_data else None, "high")

    # 新增信贷
    credit_data = (all_data.get('new_credit') or [None])[0] if all_data.get('new_credit') else None
    new_credit = credit_data.get('value') if credit_data else None
    _track("新增人民币贷款", new_credit, "AKShare(央行)", credit_data.get('date') if credit_data else None, "high")

    # ========== 计算信号 ==========
    signals = [
        _calc_us_recession(us_ism_pmi, us_non_farm, us_spread),
        _calc_fed_direction(us_ism_pmi, us_ppi, us_non_farm),
        _calc_china_recovery(cn_cpi, cn_ppi, pmi_mfg, retail_yoy, confidence, housing_yoy),
        _calc_inflation(cn_cpi, cn_ppi, us_ppi),
        _calc_liquidity(m2_growth, lpr_1y, fed_rate),
        _calc_yield_curve(us_spread, cn_spread),
    ]

    # 雷达图数据
    radar = {
        "dimensions": [s["name"] for s in signals],
        "values": [s["score"] for s in signals],
    }

    # 资产配置建议
    assets = _calc_asset_signals(signals)

    # ========== 宏观周期判定 ==========
    macro_cycle = _detect_macro_cycle(pmi_mfg, cn_cpi, confidence, retail_yoy, us_ism_pmi, us_spread)

    # ========== 领先/同步/滞后指标统计 ==========
    indicator_type_counts = {"leading": 0, "coincident": 0, "lagging": 0}
    for sig in signals:
        it = sig.get("indicator_type", "mixed")
        if it in indicator_type_counts:
            indicator_type_counts[it] += 1

    return {
        "signals": signals,
        "radar": radar,
        "assets": assets,
        "macro_cycle": macro_cycle,
        "data_quality": data_quality,
        "cross_validation": {
            "pmi": pmi_cross_check,
            "fred_available": fred_available,
            "fred_indicators": len([d for d in data_quality if d["source"].startswith("FRED")]),
            "akshare_indicators": len([d for d in data_quality if d["source"].startswith("AKShare")]),
        },
        "indicator_types": {
            "summary": indicator_type_counts,
            "legend": {
                "leading": "领先指标 — 在经济拐点前3-18个月发出信号",
                "coincident": "同步指标 — 确认经济当前状态",
                "lagging": "滞后指标 — 确认趋势已形成",
            },
        },
        "methodology": {
            "description": "基于宏观指标的规则引擎，score=0-100（0=极度悲观，100=极度乐观）",
            "indicator_classification": "每个信号的驱动因素标注了领先/同步/滞后属性，帮助判断信号的前瞻性和可靠性",
            "cycle_detection": "基于PMI、CPI、消费者信心等核心指标综合判定宏观周期阶段（扩张/过热/收缩/底部）",
            "limitations": [
                "概率数字基于指标阈值映射，非统计模型，仅供参考",
                "数据源存在延迟和修订，FRED为官方权威源，AKShare为第三方聚合",
                "信号不构成投资建议，需结合其他分析使用",
            ],
            "data_sources": [
                {"name": "FRED", "desc": "美联储经济数据库，美国官方权威数据", "priority": "高"},
                {"name": "AKShare/东方财富", "desc": "中国统计局/央行数据聚合", "priority": "高"},
                {"name": "AKShare/财新", "desc": "财新PMI（S&P Global编制），与官方PMI交叉验证", "priority": "高"},
                {"name": "AKShare/新浪", "desc": "债券收益率数据", "priority": "中"},
            ],
        },
        "updated_at": datetime.now().isoformat(),
    }


def _detect_macro_cycle(pmi, cpi, confidence, retail_yoy, us_pmi, us_spread):
    """判定宏观周期阶段

    周期四阶段：
    - expansion（扩张）: PMI>50 + CPI温和 + 消费者信心乐观
    - peak（过热）: PMI高位 + CPI偏高 + 通胀压力
    - contraction（收缩）: PMI<50 + 消费者信心下降
    - trough（底部）: PMI极低 + CPI通缩 + 信心极低

    返回：阶段、置信度、关键证据、配置建议
    """
    stage_scores = {"expansion": 0, "peak": 0, "contraction": 0, "trough": 0}
    evidence = []

    # PMI判断（权重最高）
    if pmi is not None:
        if pmi >= 52:
            stage_scores["peak"] += 3
            evidence.append(f"PMI {pmi:.1f} 高位扩张")
        elif pmi >= 50:
            stage_scores["expansion"] += 3
            evidence.append(f"PMI {pmi:.1f} 温和扩张")
        elif pmi >= 48:
            stage_scores["contraction"] += 3
            evidence.append(f"PMI {pmi:.1f} 轻度收缩")
        else:
            stage_scores["trough"] += 3
            evidence.append(f"PMI {pmi:.1f} 深度收缩")

    # CPI判断
    if cpi is not None:
        if cpi >= 3:
            stage_scores["peak"] += 2
            evidence.append(f"CPI {cpi:.1f}% 通胀偏高")
        elif cpi >= 1:
            stage_scores["expansion"] += 2
            evidence.append(f"CPI {cpi:.1f}% 温和通胀")
        elif cpi >= 0:
            stage_scores["contraction"] += 1
            evidence.append(f"CPI {cpi:.1f}% 通胀低迷")
        else:
            stage_scores["trough"] += 2
            evidence.append(f"CPI {cpi:.1f}% 通缩")

    # 消费者信心
    if confidence is not None:
        if confidence >= 110:
            stage_scores["expansion"] += 2
            evidence.append(f"信心 {confidence:.0f} 乐观")
        elif confidence >= 100:
            stage_scores["expansion"] += 1
        elif confidence >= 90:
            stage_scores["contraction"] += 1
            evidence.append(f"信心 {confidence:.0f} 偏弱")
        else:
            stage_scores["trough"] += 2
            evidence.append(f"信心 {confidence:.0f} 悲观")

    # 社零增速
    if retail_yoy is not None:
        if retail_yoy >= 5:
            stage_scores["expansion"] += 1
        elif retail_yoy >= 0:
            stage_scores["contraction"] += 1
        else:
            stage_scores["trough"] += 1

    # 判定阶段
    if not evidence:
        return {"stage": "unknown", "confidence": 0, "evidence": [], "recommendation": "数据不足，无法判定"}

    stage = max(stage_scores, key=stage_scores.get)
    total = sum(stage_scores.values())
    confidence_pct = round(stage_scores[stage] / total * 100) if total else 0

    stage_info = {
        "expansion": {
            "label": "扩张期",
            "emoji": "expanding",
            "recommendation": "经济上行，企业盈利改善。建议增配权益（消费、科技），适度降低债券仓位",
            "asset_bias": "权益 > 债券 > 黄金",
        },
        "peak": {
            "label": "过热期",
            "emoji": "overheating",
            "recommendation": "通胀压力上升，政策收紧预期。建议降低久期，增配商品和抗通胀资产",
            "asset_bias": "商品 > 现金 > 权益 > 债券",
        },
        "contraction": {
            "label": "收缩期",
            "emoji": "contracting",
            "recommendation": "经济下行，企业盈利承压。建议防御配置，增持债券和高股息",
            "asset_bias": "债券 > 高股息 > 现金 > 成长股",
        },
        "trough": {
            "label": "底部期",
            "emoji": "bottoming",
            "recommendation": "经济触底，政策刺激加码。左侧布局窗口，逐步增配成长和周期",
            "asset_bias": "成长股 > 周期股 > 债券",
        },
    }

    info = stage_info[stage]
    return {
        "stage": stage,
        "label": info["label"],
        "confidence": confidence_pct,
        "evidence": evidence,
        "recommendation": info["recommendation"],
        "asset_bias": info["asset_bias"],
    }
