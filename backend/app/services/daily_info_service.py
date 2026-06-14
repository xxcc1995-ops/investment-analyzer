"""
每日信息服务 v3 - 机构级每日投资简报

核心原则：
1. 只用可靠数据源：新浪财经（实时行情）、东方财富（板块/个股）、AKShare（宏观）
2. 并行获取 + 严格超时：每个数据源独立超时，互不阻塞
3. 优雅降级：任何数据源失败不影响其他数据展示
4. 分层缓存：实时数据短TTL，宏观数据长TTL

v3 新增：
- 多维市场情绪评分（价格/涨跌比/资金流/波动率 → 0-100分）
- 重大事件自动标注（宏观发布/涨跌异动/政策关键词）
- 新闻多源交叉验证（标题相似度 → 置信度等级）
- 信息优先级排序（critical/high/medium/low四级）
"""

import logging
import re
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.core.cache import get_cache, set_cache, TTL_DAILY, TTL_REALTIME, TTL_WEEKLY
from app.core.utils import safe_float

logger = logging.getLogger(__name__)

# 共享HTTP会话
_session = requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://finance.sina.com.cn",
})


# ==================== 底层数据获取 ====================

def _fetch_sina_indices() -> Dict[str, Any]:
    """从新浪财经获取A股+港股+美股指数（最可靠，秒级响应）"""
    result = {"a_share": [], "hk": [], "us": []}

    # A股指数
    try:
        r = _session.get(
            "https://hq.sinajs.cn/list=s_sh000001,s_sz399001,s_sz399006",
            timeout=5
        )
        r.encoding = 'gbk'
        name_map = {"s_sh000001": "上证指数", "s_sz399001": "深证成指", "s_sz399006": "创业板指"}
        code_map = {"s_sh000001": "000001", "s_sz399001": "399001", "s_sz399006": "399006"}
        for line in r.text.strip().split('\n'):
            if '=' not in line:
                continue
            key = line.split('hq_str_')[1].split('=')[0] if 'hq_str_' in line else ''
            val = line.split('"')[1] if '"' in line else ''
            if key in name_map and val:
                parts = val.split(',')
                if len(parts) >= 4:
                    result["a_share"].append({
                        "code": code_map.get(key, ""),
                        "name": name_map.get(key, ""),
                        "close": safe_float(parts[1]),
                        "change": safe_float(parts[2]),
                        "change_pct": safe_float(parts[3]),
                        "volume": safe_float(parts[4]) if len(parts) > 4 else 0,
                        "date": datetime.now().strftime("%Y-%m-%d"),
                    })
    except Exception as e:
        logger.warning(f"新浪A股指数失败: {e}")

    # 港股指数
    try:
        r = _session.get(
            "https://hq.sinajs.cn/list=rt_hkHSI,rt_hkHSCEI",
            timeout=5
        )
        r.encoding = 'gbk'
        hk_map = {"rt_hkHSI": "恒生指数", "rt_hkHSCEI": "国企指数"}
        for line in r.text.strip().split('\n'):
            if '=' not in line:
                continue
            key = line.split('hq_str_')[1].split('=')[0] if 'hq_str_' in line else ''
            val = line.split('"')[1] if '"' in line else ''
            if key in hk_map and val:
                parts = val.split(',')
                if len(parts) >= 8:
                    result["hk"].append({
                        "code": key.replace("rt_hk", ""),
                        "name": hk_map.get(key, ""),
                        "close": safe_float(parts[6]),
                        "change": safe_float(parts[7]),
                        "change_pct": safe_float(parts[8]),
                        "date": datetime.now().strftime("%Y-%m-%d"),
                    })
    except Exception as e:
        logger.warning(f"新浪港股指数失败: {e}")

    # 美股指数
    try:
        r = _session.get(
            "https://hq.sinajs.cn/list=gb_$dji,gb_$inx,gb_$ixic",
            timeout=5
        )
        r.encoding = 'gbk'
        us_map = {"gb_$dji": "道琼斯", "gb_$inx": "标普500", "gb_$ixic": "纳斯达克"}
        for line in r.text.strip().split('\n'):
            if '=' not in line:
                continue
            key = line.split('hq_str_')[1].split('=')[0] if 'hq_str_' in line else ''
            val = line.split('"')[1] if '"' in line else ''
            if key in us_map and val:
                parts = val.split(',')
                if len(parts) >= 5:
                    close = safe_float(parts[1])
                    pct = safe_float(parts[2])     # 涨跌幅（已经是百分比）
                    change = safe_float(parts[4])  # 涨跌额
                    result["us"].append({
                        "name": us_map.get(key, ""),
                        "close": round(close, 2),
                        "change": round(change, 2),
                        "change_pct": round(pct, 2),
                        "date": datetime.now().strftime("%Y-%m-%d"),
                    })
    except Exception as e:
        logger.warning(f"新浪美股指数失败: {e}")

    result["update_time"] = datetime.now().isoformat()
    return result


def _fetch_eastmoney_sectors() -> List[Dict[str, Any]]:
    """获取行业板块涨跌幅（东方财富直接API + AKShare备用）"""
    # 方案1: 东方财富直接API
    try:
        url = "https://push2.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": "1", "pz": "30", "po": "1",
            "np": "1", "fltt": "2", "invt": "2",
            "fid": "f3", "fs": "m:90+t:2",
            "fields": "f2,f3,f4,f12,f14,f104,f105,f128,f136,f140",
        }
        r = _session.get(url, params=params, timeout=5)
        data = r.json()
        sectors = []
        for item in (data.get("data") or {}).get("diff") or []:
            sectors.append({
                "code": item.get("f12", ""),
                "name": item.get("f14", ""),
                "change_pct": safe_float(item.get("f3")),
                "up_count": item.get("f104", 0),
                "down_count": item.get("f105", 0),
                "leader": item.get("f140", ""),
                "leader_change": safe_float(item.get("f136")),
            })
        if sectors:
            return sectors
    except Exception as e:
        logger.warning(f"东方财富板块API失败: {e}")

    return []


def _fetch_eastmoney_top_movers() -> Dict[str, Any]:
    """从东方财富获取涨幅榜/跌幅榜/换手率榜"""
    result = {"gainers": [], "losers": [], "active": []}

    # 涨幅榜
    try:
        url = "https://push2.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": "1", "pz": "10", "po": "1",
            "np": "1", "fltt": "2", "invt": "2",
            "fid": "f3", "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
            "fields": "f2,f3,f4,f12,f14,f15,f16,f17",
        }
        r = _session.get(url, params=params, timeout=5)
        data = r.json()
        for item in (data.get("data") or {}).get("diff") or []:
            result["gainers"].append({
                "code": item.get("f12", ""),
                "name": item.get("f14", ""),
                "price": safe_float(item.get("f2")),
                "change_pct": safe_float(item.get("f3")),
            })
    except Exception as e:
        logger.warning(f"涨幅榜获取失败: {e}")

    # 跌幅榜
    try:
        params["po"] = "0"  # 升序 = 跌幅榜
        r = _session.get(url, params=params, timeout=5)
        data = r.json()
        for item in (data.get("data") or {}).get("diff") or []:
            result["losers"].append({
                "code": item.get("f12", ""),
                "name": item.get("f14", ""),
                "price": safe_float(item.get("f2")),
                "change_pct": safe_float(item.get("f3")),
            })
    except Exception as e:
        logger.warning(f"跌幅榜获取失败: {e}")

    return result


def _fetch_eastmoney_fund_flow() -> List[Dict[str, Any]]:
    """从东方财富获取主力资金流向（行业级别）"""
    try:
        url = "https://push2.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": "1", "pz": "20", "po": "1",
            "np": "1", "fltt": "2", "invt": "2",
            "fid": "f62", "fs": "m:90+t:2",
            "fields": "f12,f14,f62,f184,f66,f69,f72,f75,f78,f81",
        }
        r = _session.get(url, params=params, timeout=5)
        data = r.json()
        flows = []
        for item in (data.get("data") or {}).get("diff") or []:
            main_net = safe_float(item.get("f62"))  # 主力净流入
            flows.append({
                "name": item.get("f14", ""),
                "main_net_inflow": main_net,
                "main_net_pct": safe_float(item.get("f184")),
                "super_large_net": safe_float(item.get("f66")),  # 超大单净流入
                "large_net": safe_float(item.get("f72")),  # 大单净流入
                "medium_net": safe_float(item.get("f78")),  # 中单净流入
                "small_net": safe_float(item.get("f81")),  # 小单净流入
            })
        return flows
    except Exception as e:
        logger.warning(f"资金流向获取失败: {e}")
        return []


def _fetch_macro_indicators() -> Dict[str, Any]:
    """获取宏观经济指标（AKShare，有超时保护）"""
    result = {}
    try:
        import akshare as ak

        # GDP
        try:
            df = ak.macro_china_gdp()
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                result["gdp"] = {
                    "date": str(latest.get("日期", "")),
                    "gdp": safe_float(latest.get("国内生产总值-绝对值", 0)),
                    "gdp_growth": safe_float(latest.get("国内生产总值-同比增长", 0)),
                }
        except Exception:
            pass

        # CPI
        try:
            df = ak.macro_china_cpi()
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                result["cpi"] = {
                    "date": str(latest.get("日期", "")),
                    "cpi_yoy": safe_float(latest.get("同比增长", 0)),
                }
        except Exception:
            pass

        # PMI
        try:
            df = ak.macro_china_pmi()
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                result["pmi"] = {
                    "date": str(latest.get("日期", "")),
                    "manufacturing": safe_float(latest.get("制造业", 0)),
                    "non_manufacturing": safe_float(latest.get("非制造业", 0)),
                }
        except Exception:
            pass

        # M2
        try:
            df = ak.macro_china_money_supply()
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                result["money_supply"] = {
                    "date": str(latest.get("日期", "")),
                    "m2": safe_float(latest.get("M2-数量", 0)),
                    "m2_growth": safe_float(latest.get("M2-同比增长", 0)),
                }
        except Exception:
            pass

    except ImportError:
        logger.warning("AKShare未安装，跳过宏观数据")
    except Exception as e:
        logger.warning(f"宏观数据获取失败: {e}")

    return result


# ==================== 重大事件自动检测 ====================

# 重大事件关键词库
_MACRO_EVENT_KEYWORDS = [
    # 央行/货币政策
    "美联储", "FOMC", "加息", "降息", "利率决议", "LPR调整",
    "央行", "货币政策", "MLF", "逆回购", "降准", "公开市场操作",
    "Fed", "rate cut", "rate hike", "federal reserve",
    # 重大经济数据发布
    "GDP", "CPI", "PPI", "PMI", "非农", "就业数据",
    "社融", "M2", "进出口", "贸易顺差", "贸易逆差",
    # 监管/政策
    "证监会", "银保监", "国务院", "国常会", "政治局会议",
    "监管", "新规", "政策", "刺激", "纾困",
    # 市场异动
    "暴跌", "暴涨", "熔断", "涨停潮", "跌停潮",
    "恐慌", "VIX", "避险", "黑天鹅",
]

_MARKET_SHOCK_THRESHOLDS = {
    "index_swing_pct": 3.0,      # 指数日内振幅超过3%
    "sector_max_change_pct": 5.0, # 最大板块涨跌幅超过5%
    "sector_divergence_pct": 8.0, # 最强最弱板块差超过8%
}


def _detect_critical_events(indices: Dict, sectors: List, macro: Dict,
                            fund_flow: List, overseas_news: Optional[Dict] = None) -> List[Dict[str, Any]]:
    """自动检测重大事件，返回事件列表"""
    events = []

    # 1. 指数异动检测
    for idx in indices.get("a_share", []):
        pct = idx.get("change_pct", 0)
        if abs(pct) >= 3:
            level = "critical" if abs(pct) >= 5 else "high"
            direction = "暴涨" if pct > 0 else "暴跌"
            events.append({
                "type": "market_shock",
                "level": level,
                "title": f"{idx['name']}{direction} {abs(pct):.2f}%",
                "description": f"{idx['name']}收盘{idx.get('close', 0):.2f}，涨跌幅{pct:+.2f}%，需关注市场风险",
                "source": "行情异动",
                "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            })

    for idx in indices.get("us", []):
        pct = idx.get("change_pct", 0)
        if abs(pct) >= 2:
            level = "critical" if abs(pct) >= 4 else "high"
            direction = "暴涨" if pct > 0 else "暴跌"
            events.append({
                "type": "market_shock",
                "level": level,
                "title": f"{idx['name']}{direction} {abs(pct):.2f}%",
                "description": f"美股{idx['name']}大幅波动，关注对A股的传导效应",
                "source": "美股行情",
                "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            })

    # 2. 板块极端分化
    if sectors:
        changes = [s.get("change_pct", 0) for s in sectors]
        if changes:
            max_change = max(changes)
            min_change = min(changes)
            spread = max_change - min_change
            if spread >= _MARKET_SHOCK_THRESHOLDS["sector_divergence_pct"]:
                top_sector = max(sectors, key=lambda s: s.get("change_pct", 0))
                bottom_sector = min(sectors, key=lambda s: s.get("change_pct", 0))
                events.append({
                    "type": "sector_divergence",
                    "level": "high",
                    "title": f"板块极端分化：{top_sector['name']} +{max_change:.1f}% vs {bottom_sector['name']} {min_change:.1f}%",
                    "description": f"最强与最弱板块差{spread:.1f}个百分点，市场风格切换信号明显",
                    "source": "板块数据",
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                })

    # 3. 资金流向异动（净流入/流出超过100亿）
    if fund_flow:
        total_main_net = sum(f.get("main_net_inflow", 0) for f in fund_flow[:10])
        if abs(total_main_net) > 10_000_000_000:  # 100亿（单位：元）
            direction = "大幅流入" if total_main_net > 0 else "大幅流出"
            events.append({
                "type": "fund_flow_shock",
                "level": "high",
                "title": f"主力资金{direction}：前10大行业净额{total_main_net / 1e8:.0f}亿",
                "description": f"主力资金出现显著方向性流动，关注市场主力意图",
                "source": "资金流向",
                "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            })

    # 4. 宏观数据发布日（基于数据日期与当前日期接近）
    pmi = macro.get("pmi", {})
    if pmi.get("manufacturing"):
        mfg = pmi["manufacturing"]
        if mfg < 49:
            events.append({
                "type": "macro_alert",
                "level": "high",
                "title": f"制造业PMI {mfg:.1f} 跌破荣枯线",
                "description": "制造业PMI低于50荣枯线，经济收缩信号，需关注逆周期政策力度",
                "source": "宏观数据",
                "time": pmi.get("date", ""),
            })
        elif mfg >= 52:
            events.append({
                "type": "macro_alert",
                "level": "medium",
                "title": f"制造业PMI {mfg:.1f} 进入强扩张区间",
                "description": "制造业PMI显著高于50，经济扩张动力强劲",
                "source": "宏观数据",
                "time": pmi.get("date", ""),
            })

    # 5. 海外新闻中的高影响力事件提取
    if overseas_news:
        for cat_key in ("us_stock", "crypto"):
            cat_data = overseas_news.get(cat_key, {})
            high_items = [i for i in cat_data.get("items", []) if i.get("impact") == "high"]
            for item in high_items[:3]:
                events.append({
                    "type": "overseas_event",
                    "level": "high",
                    "title": item.get("title", "")[:80],
                    "description": item.get("summary", "")[:200],
                    "source": item.get("source", "海外媒体"),
                    "time": item.get("published", ""),
                    "link": item.get("link", ""),
                })

    # 按重要性排序：critical > high > medium
    level_order = {"critical": 0, "high": 1, "medium": 2}
    events.sort(key=lambda e: level_order.get(e.get("level", "medium"), 9))

    return events


# ==================== 多维市场情绪评分 ====================

def _compute_sentiment_score(indices: Dict, sectors: List, fund_flow: List) -> Dict[str, Any]:
    """计算多维市场情绪评分（0-100分）

    维度：
    1. 价格动量（35%权重）：指数涨跌幅综合（A股+港股+美股加权）
    2. 市场广度（25%权重）：板块涨跌比例 + 涨跌家数
    3. 资金动向（20%权重）：主力资金净流入
    4. 波动率（10%权重）：涨跌幅标准差
    5. 极端信号（10%权重）：涨跌停比、板块极端分化
    """
    import math
    scores = {}
    data_quality = 0  # 数据完整度（0-4），用于加权

    # --- 维度1: 价格动量 (35%) ---
    # A股权重60%，港股20%，美股20%（A股对国内市场情绪影响最大）
    a_changes = [idx.get("change_pct", 0) for idx in indices.get("a_share", [])]
    hk_changes = [idx.get("change_pct", 0) for idx in indices.get("hk", [])]
    us_changes = [idx.get("change_pct", 0) for idx in indices.get("us", [])]

    weighted_change = 0
    weight_sum = 0
    if a_changes:
        weighted_change += sum(a_changes) / len(a_changes) * 0.6
        weight_sum += 0.6
        data_quality += 1
    if hk_changes:
        weighted_change += sum(hk_changes) / len(hk_changes) * 0.2
        weight_sum += 0.2
    if us_changes:
        weighted_change += sum(us_changes) / len(us_changes) * 0.2
        weight_sum += 0.2
        data_quality += 1

    if weight_sum > 0:
        avg_change = weighted_change / weight_sum
        momentum_score = max(0, min(100, 50 + avg_change * 10))
    else:
        momentum_score = 50
    scores["momentum"] = round(momentum_score, 1)

    # --- 维度2: 市场广度 (25%) ---
    if sectors:
        up_count = sum(1 for s in sectors if s.get("change_pct", 0) > 0)
        down_count = sum(1 for s in sectors if s.get("change_pct", 0) < 0)
        total = len(sectors)
        breadth_ratio = up_count / total if total > 0 else 0.5
        # 涨跌比信号：涨多跌少→乐观，跌多涨少→悲观
        if total > 0:
            adv_ratio = up_count / max(down_count, 1)  # 涨跌比
            # 涨跌比 1:1→50, 2:1→65, 3:1→75, 1:2→35, 1:3→25
            ratio_score = max(0, min(100, 50 + math.log(max(adv_ratio, 0.1), 2) * 15))
        else:
            ratio_score = 50
        breadth_score = max(0, min(100, 20 + breadth_ratio * 60)) * 0.6 + ratio_score * 0.4
        data_quality += 1
    else:
        breadth_score = 50
    scores["breadth"] = round(breadth_score, 1)

    # --- 维度3: 资金动向 (20%) ---
    if fund_flow:
        total_net = sum(f.get("main_net_inflow", 0) for f in fund_flow[:15])
        net_in_yi = total_net / 1e8  # 转为亿
        # 非线性映射：大额流入/流出的信号更强
        # -100亿→20, -50亿→35, 0→50, +50亿→65, +100亿→80
        fund_score = max(0, min(100, 50 + math.copysign(abs(net_in_yi) ** 0.8, net_in_yi) * 0.6))
        data_quality += 1
    else:
        fund_score = 50
    scores["fund_flow"] = round(fund_score, 1)

    # --- 维度4: 波动率 (10%) ---
    all_changes = a_changes + us_changes
    if len(all_changes) >= 2:
        mean_c = sum(all_changes) / len(all_changes)
        variance = sum((c - mean_c) ** 2 for c in all_changes) / len(all_changes)
        std_dev = math.sqrt(variance)
        # 高波动=恐慌，低波动=平稳。std_dev=0→80, 2→50, 4→20
        vol_score = max(0, min(100, 80 - std_dev * 15))
    else:
        vol_score = 60
    scores["volatility"] = round(vol_score, 1)

    # --- 维度5: 极端信号 (10%) ---
    extreme_score = 50  # 默认中性
    if sectors:
        changes = [s.get("change_pct", 0) for s in sectors]
        if changes:
            max_c = max(changes)
            min_c = min(changes)
            spread = max_c - min_c
            # 板块分化越严重，市场越不稳定
            # spread<3→60（平稳）, 3-6→50（正常）, 6-10→35（分化）, >10→20（极端分化）
            if spread < 3:
                extreme_score = 60
            elif spread < 6:
                extreme_score = 50
            elif spread < 10:
                extreme_score = 35
            else:
                extreme_score = 20
            # 如果有涨跌停股，信号更强
            limit_up = sum(1 for s in sectors if s.get("change_pct", 0) >= 9.9)
            limit_down = sum(1 for s in sectors if s.get("change_pct", 0) <= -9.9)
            if limit_up > 3:
                extreme_score = min(100, extreme_score + 15)  # 涨停潮→乐观
            if limit_down > 3:
                extreme_score = max(0, extreme_score - 15)  # 跌停潮→悲观
    scores["extreme"] = round(extreme_score, 1)

    # --- 综合评分 ---
    composite = (
        scores["momentum"] * 0.35 +
        scores["breadth"] * 0.25 +
        scores["fund_flow"] * 0.20 +
        scores["volatility"] * 0.10 +
        scores["extreme"] * 0.10
    )
    scores["composite"] = round(composite, 1)

    # 情绪等级
    if composite >= 75:
        level = "极度乐观"
        color = "bullish"
    elif composite >= 60:
        level = "偏多"
        color = "slightly_bullish"
    elif composite >= 45:
        level = "中性"
        color = "neutral"
    elif composite >= 30:
        level = "偏空"
        color = "slightly_bearish"
    else:
        level = "极度悲观"
        color = "bearish"

    scores["level"] = level
    scores["color"] = color
    scores["description"] = (
        f"情绪评分 {composite:.0f}/100（{level}）。"
        f"动量{scores['momentum']:.0f}、广度{scores['breadth']:.0f}、"
        f"资金{scores['fund_flow']:.0f}、波动{scores['volatility']:.0f}、"
        f"极端{scores['extreme']:.0f}"
    )

    return scores


# ==================== 新闻交叉验证 ====================

def _cross_validate_news(overseas_news: Optional[Dict]) -> List[Dict[str, Any]]:
    """对海外新闻进行多源交叉验证：多个源报道同一事件 → 置信度提升"""
    if not overseas_news:
        return []

    all_items = []
    for cat_key in ("us_stock", "crypto"):
        cat_data = overseas_news.get(cat_key, {})
        for item in cat_data.get("items", []):
            item["_category"] = cat_key
            all_items.append(item)

    if not all_items:
        return []

    # 标题相似度匹配（简化版：提取关键词集合比较）
    def _extract_keywords(title: str) -> set:
        # 移除标点，提取有意义的词（英文按空格，中文取连续字符）
        clean = re.sub(r'[^\w\s一-鿿]', '', title.lower())
        words = set()
        for w in clean.split():
            if len(w) >= 3:
                words.add(w)
        # 中文：取2-gram
        for i in range(len(clean) - 1):
            if '一' <= clean[i] <= '鿿' and '一' <= clean[i+1] <= '鿿':
                words.add(clean[i:i+2])
        return words

    # 构建关键词 → 索引映射
    item_keywords = [_extract_keywords(item.get("title", "")) for item in all_items]

    # 简单聚类：两两比较，Jaccard > 0.3 视为同一事件
    clusters: List[List[int]] = []
    assigned = set()

    for i in range(len(all_items)):
        if i in assigned:
            continue
        cluster = [i]
        assigned.add(i)
        for j in range(i + 1, len(all_items)):
            if j in assigned:
                continue
            kw_i = item_keywords[i]
            kw_j = item_keywords[j]
            if not kw_i or not kw_j:
                continue
            intersection = len(kw_i & kw_j)
            union = len(kw_i | kw_j)
            jaccard = intersection / union if union > 0 else 0
            if jaccard > 0.3:
                cluster.append(j)
                assigned.add(j)
        clusters.append(cluster)

    # 提取多源验证的事件
    verified_events = []
    for cluster in clusters:
        if len(cluster) >= 2:
            sources = list(set(all_items[i].get("source", "") for i in cluster))
            # 取标题最长的作为代表
            representative_idx = max(cluster, key=lambda i: len(all_items[i].get("title", "")))
            rep = all_items[representative_idx]
            verified_events.append({
                "title": rep.get("title", ""),
                "summary": rep.get("summary", ""),
                "link": rep.get("link", ""),
                "source_count": len(sources),
                "sources": sources,
                "confidence": "high" if len(sources) >= 3 else "medium",
                "impact": rep.get("impact", "medium"),
                "category": rep.get("_category", ""),
                "published": rep.get("published", ""),
            })

    # 按置信度和源数量排序
    verified_events.sort(key=lambda x: (-x["source_count"], 0 if x["confidence"] == "high" else 1))

    return verified_events


# ==================== 主服务类 ====================

class DailyInfoService:
    """每日信息服务 v3 - 机构级标准"""

    def get_daily_briefing(self) -> Dict[str, Any]:
        """获取每日投资简报（并行获取，严格超时）"""
        cache_key = "daily_briefing_v3"
        cached = get_cache(cache_key, TTL_DAILY)
        if cached:
            return cached

        # 定义任务
        tasks = {
            "indices": ("指数行情", _fetch_sina_indices),
            "sectors": ("行业板块", _fetch_eastmoney_sectors),
            "movers": ("涨跌榜", _fetch_eastmoney_top_movers),
            "fund_flow": ("资金流向", _fetch_eastmoney_fund_flow),
            "macro": ("宏观数据", _fetch_macro_indicators),
            # 五大大师模块
            "value": ("价值投资", self.get_value_investing_insights),
            "arbitrage": ("套利机会", self.get_arbitrage_opportunities),
            "cb": ("可转债", self.get_convertible_bond_insights),
            "crypto": ("币圈", self.get_crypto_insights),
            "airdrops": ("空投", self.get_airdrop_opportunities),
            # 海外高质量信息源
            "overseas_news": ("海外新闻", self.get_overseas_news),
        }

        # 并行执行
        results = {}
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_map = {}
            for key, (label, fn) in tasks.items():
                future_map[executor.submit(fn)] = key

            try:
                for future in as_completed(future_map, timeout=30):
                    key = future_map[future]
                    try:
                        results[key] = future.result(timeout=10)
                    except Exception as e:
                        logger.warning(f"获取{key}失败: {e}")
            except Exception:
                for f in future_map:
                    f.cancel()

        # 提取数据
        indices = results.get("indices", {"a_share": [], "hk": [], "us": []})
        sectors = results.get("sectors", [])
        movers = results.get("movers", {"gainers": [], "losers": []})
        fund_flow = results.get("fund_flow", [])
        macro = results.get("macro", {})
        overseas_news = results.get("overseas_news")

        # 生成市场情绪（兼容旧版 + 新版多维评分）
        sentiment = self._analyze_sentiment(indices, sectors)
        sentiment_v3 = _compute_sentiment_score(indices, sectors, fund_flow)

        # 生成投资摘要（v3: 传入资金流向数据）
        summary = self._generate_summary(indices, sectors, macro, sentiment, fund_flow)

        # v3: 重大事件自动检测
        critical_events = _detect_critical_events(indices, sectors, macro, fund_flow, overseas_news)

        # v3: 新闻多源交叉验证
        cross_validated = _cross_validate_news(overseas_news)

        result = {
            "title": f"每日投资简报 - {datetime.now().strftime('%Y年%m月%d日')}",
            "market_overview": {
                "china": {
                    "a_share": indices.get("a_share", []),
                    "hk": indices.get("hk", []),
                    "update_time": datetime.now().isoformat(),
                },
                "us": {
                    "indices": indices.get("us", []),
                    "update_time": datetime.now().isoformat(),
                },
            },
            "sector_performance": sectors[:20],
            "top_movers": movers,
            "fund_flow": fund_flow[:15],
            "macro_indicators": {
                "china": macro,
            },
            "market_sentiment": sentiment,
            "market_sentiment_v3": sentiment_v3,
            "investment_summary": summary,
            # v3: 重大事件（按优先级排序）
            "critical_events": critical_events,
            # v3: 交叉验证新闻
            "cross_validated_news": cross_validated,
            # 五大大师模块
            "value_investing": results.get("value", {}),
            "arbitrage": results.get("arbitrage", {}),
            "convertible_bonds": results.get("cb", {}),
            "crypto": results.get("crypto", {}),
            "airdrops": results.get("airdrops", {}),
            # 海外高质量信息源
            "overseas_news": overseas_news or {
                "us_stock": {"items": [], "sources_ok": [], "sources_failed": [], "count": 0, "high_impact_count": 0, "medium_impact_count": 0},
                "crypto": {"items": [], "sources_ok": [], "sources_failed": [], "count": 0, "high_impact_count": 0, "medium_impact_count": 0},
                "update_time": datetime.now().isoformat(),
            },
            "update_time": datetime.now().isoformat(),
        }

        set_cache(cache_key, result)
        return result

    def _analyze_sentiment(self, indices: Dict, sectors: List) -> Dict[str, Any]:
        """分析市场情绪（v3增强：增加平均涨跌幅和最大板块涨跌幅）"""
        # A股涨跌
        a_changes = [idx.get("change_pct", 0) for idx in indices.get("a_share", [])]
        a_up = sum(1 for x in a_changes if x > 0)
        a_down = sum(1 for x in a_changes if x < 0)
        a_avg = sum(a_changes) / len(a_changes) if a_changes else 0

        # 美股涨跌
        us_changes = [idx.get("change_pct", 0) for idx in indices.get("us", [])]
        us_up = sum(1 for x in us_changes if x > 0)
        us_down = sum(1 for x in us_changes if x < 0)
        us_avg = sum(us_changes) / len(us_changes) if us_changes else 0

        # 板块涨跌
        s_up = sum(1 for s in sectors if s.get("change_pct", 0) > 0)
        s_down = sum(1 for s in sectors if s.get("change_pct", 0) < 0)
        s_total = len(sectors)
        s_changes = [s.get("change_pct", 0) for s in sectors]

        total_up = a_up + us_up + s_up
        total_down = a_down + us_down + s_down

        if total_up > total_down * 2:
            sentiment, desc = "强势", "市场整体强势，多数指数和板块上涨"
        elif total_up > total_down * 1.3:
            sentiment, desc = "偏多", "市场偏积极，上涨多于下跌"
        elif total_down > total_up * 2:
            sentiment, desc = "弱势", "市场整体疲软，多数指数和板块下跌"
        elif total_down > total_up * 1.3:
            sentiment, desc = "偏空", "市场偏消极，下跌多于上涨"
        else:
            sentiment, desc = "震荡", "市场分化明显，涨跌互见"

        return {
            "sentiment": sentiment,
            "description": desc,
            "a_share": {"up": a_up, "down": a_down, "avg_change": round(a_avg, 2)},
            "us": {"up": us_up, "down": us_down, "avg_change": round(us_avg, 2)},
            "sectors": {
                "up": s_up, "down": s_down, "total": s_total,
                "max_change": round(max(s_changes), 2) if s_changes else 0,
                "min_change": round(min(s_changes), 2) if s_changes else 0,
            },
        }

    def _generate_summary(self, indices: Dict, sectors: List, macro: Dict, sentiment: Dict,
                          fund_flow: Optional[List] = None) -> Dict[str, Any]:
        """生成投资建议摘要（v3增强：加入资金流向分析）"""
        advices = []
        risks = []

        # 基于指数表现
        for idx in indices.get("a_share", []):
            pct = idx.get("change_pct", 0)
            if abs(pct) > 2:
                direction = "大涨" if pct > 0 else "大跌"
                advices.append(f"{idx['name']}{direction}{abs(pct):.1f}%，注意{'追高' if pct > 0 else '抄底'}风险")

        # 基于板块表现
        if sectors:
            top_sector = max(sectors, key=lambda s: s.get("change_pct", 0))
            bottom_sector = min(sectors, key=lambda s: s.get("change_pct", 0))
            if top_sector.get("change_pct", 0) > 2:
                advices.append(f"{top_sector['name']}板块领涨({top_sector['change_pct']:.1f}%)，关注持续性")
            if bottom_sector.get("change_pct", 0) < -2:
                risks.append(f"{bottom_sector['name']}板块领跌({bottom_sector['change_pct']:.1f}%)，注意风险")

            # 板块分化度分析
            s_changes = [s.get("change_pct", 0) for s in sectors]
            if s_changes:
                spread = max(s_changes) - min(s_changes)
                if spread > 6:
                    risks.append(f"板块分化严重（强弱差{spread:.1f}pct），市场风格切换频繁，短线操作难度大")

        # 基于宏观数据
        pmi = macro.get("pmi", {})
        if pmi.get("manufacturing"):
            if pmi["manufacturing"] < 50:
                risks.append(f"制造业PMI {pmi['manufacturing']:.1f}低于荣枯线，经济承压")
            elif pmi["manufacturing"] > 51:
                advices.append(f"制造业PMI {pmi['manufacturing']:.1f}扩张区间，经济向好")

        cpi = macro.get("cpi", {})
        if cpi.get("cpi_yoy"):
            cpi_yoy = cpi["cpi_yoy"]
            if cpi_yoy > 3:
                risks.append(f"CPI同比{cpi_yoy:.1f}%，通胀压力较大，关注货币政策收紧风险")
            elif cpi_yoy < 0:
                risks.append(f"CPI同比{cpi_yoy:.1f}%，通缩信号，关注需求不足风险")

        # 基于资金流向
        if fund_flow:
            total_net = sum(f.get("main_net_inflow", 0) for f in fund_flow[:10])
            net_yi = total_net / 1e8
            if abs(net_yi) > 50:
                if net_yi > 0:
                    advices.append(f"主力资金大幅流入{net_yi:.0f}亿，市场做多意愿强")
                else:
                    risks.append(f"主力资金大幅流出{abs(net_yi):.0f}亿，注意资金面压力")

        return {
            "advices": advices[:5],
            "risks": risks[:5],
            "sentiment": sentiment.get("sentiment", "中性"),
        }

    # ==================== 兼容方法 ====================

    def _analyze_market_sentiment(self, china_market: Dict, us_market: Dict, sectors: List) -> Dict[str, Any]:
        """分析市场情绪（兼容旧API调用）"""
        indices = {
            "a_share": china_market.get("a_share", []),
            "us": us_market.get("indices", []),
        }
        return self._analyze_sentiment(indices, sectors)

    def verify_data_sources(self) -> Dict[str, Any]:
        """验证数据源可用性"""
        sources = {}
        # 测试新浪
        try:
            r = _session.get("https://hq.sinajs.cn/list=s_sh000001", timeout=5)
            sources["sina"] = {"status": "ok" if r.status_code == 200 else "error", "name": "新浪财经"}
        except Exception as e:
            sources["sina"] = {"status": "error", "error": str(e), "name": "新浪财经"}

        # 测试东方财富
        try:
            r = _session.get("https://push2.eastmoney.com/api/qt/clist/get", params={"pn": "1", "pz": "1", "fs": "m:90+t:2", "fields": "f14"}, timeout=5)
            sources["eastmoney"] = {"status": "ok" if r.status_code == 200 else "error", "name": "东方财富"}
        except Exception as e:
            sources["eastmoney"] = {"status": "error", "error": str(e), "name": "东方财富"}

        # 测试AKShare
        try:
            import akshare
            sources["akshare"] = {"status": "ok", "name": "AKShare"}
        except Exception as e:
            sources["akshare"] = {"status": "error", "error": str(e), "name": "AKShare"}

        # 测试RSSHub
        try:
            import os
            rsshub_base = os.getenv("RSSHUB_BASE", "https://rsshub.app")
            r = _session.get(f"{rsshub_base}/cls/telegraph", timeout=8)
            sources["rsshub"] = {"status": "ok" if r.status_code == 200 else "error", "name": "RSSHub"}
        except Exception as e:
            sources["rsshub"] = {"status": "error", "error": str(e), "name": "RSSHub"}

        # 测试CoinGecko
        try:
            r = _session.get("https://api.coingecko.com/api/v3/ping", timeout=5)
            sources["coingecko"] = {"status": "ok" if r.status_code == 200 else "error", "name": "CoinGecko"}
        except Exception as e:
            sources["coingecko"] = {"status": "error", "error": str(e), "name": "CoinGecko"}

        # 测试DefiLlama
        try:
            r = _session.get("https://api.llama.fi/protocols", timeout=5)
            sources["defillama"] = {"status": "ok" if r.status_code == 200 else "error", "name": "DefiLlama"}
        except Exception as e:
            sources["defillama"] = {"status": "error", "error": str(e), "name": "DefiLlama"}

        return {"sources": sources, "check_time": datetime.now().isoformat()}

    # ==================== 子模块API ====================
    # 缓存策略：实时行情300s、板块300s、宏观TTL_WEEKLY(24h)、大师模块TTL_DAILY(1h)

    def get_china_market_summary(self) -> Dict[str, Any]:
        """获取中国市场摘要（行情数据，5分钟缓存）"""
        cache_key = "daily_china_market"
        cached = get_cache(cache_key, 300)
        if cached:
            return cached
        data = _fetch_sina_indices()
        result = {
            "a_share": data.get("a_share", []),
            "hk": data.get("hk", []),
            "update_time": datetime.now().isoformat(),
        }
        set_cache(cache_key, result)
        return result

    def get_us_market_summary(self) -> Dict[str, Any]:
        """获取美国市场摘要（行情数据，5分钟缓存）"""
        cache_key = "daily_us_market"
        cached = get_cache(cache_key, 300)
        if cached:
            return cached
        data = _fetch_sina_indices()
        result = {
            "indices": data.get("us", []),
            "update_time": datetime.now().isoformat(),
        }
        set_cache(cache_key, result)
        return result

    def get_global_market_overview(self) -> Dict[str, Any]:
        """获取全球市场概览（A股+港股+美股指数汇总）"""
        cache_key = "daily_global_market"
        cached = get_cache(cache_key, 300)
        if cached:
            return cached
        data = _fetch_sina_indices()
        # 合并所有指数为统一列表
        all_indices = []
        for idx in data.get("a_share", []):
            idx["market"] = "A股"
            all_indices.append(idx)
        for idx in data.get("hk", []):
            idx["market"] = "港股"
            all_indices.append(idx)
        for idx in data.get("us", []):
            idx["market"] = "美股"
            all_indices.append(idx)
        result = {"indices": all_indices, "update_time": datetime.now().isoformat()}
        set_cache(cache_key, result)
        return result

    def get_macro_indicators(self) -> Dict[str, Any]:
        """获取中国宏观数据（低频更新，24小时缓存）"""
        cache_key = "daily_macro_cn"
        cached = get_cache(cache_key, TTL_WEEKLY)
        if cached:
            return cached
        result = _fetch_macro_indicators()
        set_cache(cache_key, result)
        return result

    def get_us_macro_indicators(self) -> Dict[str, Any]:
        """获取美国宏观数据（FRED，24小时缓存）"""
        cache_key = "daily_us_macro"
        cached = get_cache(cache_key, TTL_WEEKLY)
        if cached:
            return cached
        try:
            from app.services.fred_service import fred_service
            if not fred_service._is_available():
                return {"indicators": {}, "source": "FRED", "available": False,
                        "reason": "FRED_API_KEY未设置", "update_time": datetime.now().isoformat()}
            keys = ["cpi", "unemployment", "fed_rate", "treasury_10y", "treasury_2y",
                    "yield_spread_10y2y", "gdp_real", "nonfarm_payroll"]
            result = fred_service.get_batch(keys)
            indicators = {}
            for key, data in result.items():
                if data and data.get("latest"):
                    indicators[key] = {
                        "value": data["latest"]["value"],
                        "date": data["latest"]["date"],
                        "series": data.get("series", [])[:12],
                        "series_id": data.get("series_id", ""),
                    }
            formatted = {"indicators": indicators, "source": "FRED", "available": True,
                         "update_time": datetime.now().isoformat()}
            set_cache(cache_key, formatted)
            return formatted
        except Exception as e:
            logger.warning(f"FRED数据获取失败: {e}")
            return {"indicators": {}, "source": "FRED", "available": False,
                    "error": str(e), "update_time": datetime.now().isoformat()}

    def get_sector_performance(self) -> List[Dict[str, Any]]:
        """获取行业板块表现（板块数据，5分钟缓存）"""
        cache_key = "daily_sectors"
        cached = get_cache(cache_key, 300)
        if cached:
            return cached
        result = _fetch_eastmoney_sectors()
        set_cache(cache_key, result)
        return result

    def get_investment_insights(self) -> List[Dict[str, Any]]:
        """获取投资观点（基于市场数据自动生成）"""
        cache_key = "daily_insights"
        cached = get_cache(cache_key, 300)
        if cached:
            return cached
        try:
            indices = _fetch_sina_indices()
            sectors = _fetch_eastmoney_sectors()
            fund_flow = _fetch_eastmoney_fund_flow()
            insights = []

            # 基于指数表现生成观点
            for idx in indices.get("a_share", []) + indices.get("us", []):
                pct = idx.get("change_pct", 0)
                if abs(pct) >= 2:
                    direction = "大涨" if pct > 0 else "大跌"
                    insights.append({
                        "type": "market", "level": "high",
                        "title": f"{idx['name']}{direction}{abs(pct):.2f}%",
                        "detail": f"关注{'追高' if pct > 0 else '抄底'}风险",
                    })

            # 基于板块分化
            if sectors:
                top = max(sectors, key=lambda s: s.get("change_pct", 0))
                bottom = min(sectors, key=lambda s: s.get("change_pct", 0))
                spread = top.get("change_pct", 0) - bottom.get("change_pct", 0)
                if spread > 5:
                    insights.append({
                        "type": "sector", "level": "medium",
                        "title": f"板块分化：{top['name']} vs {bottom['name']}（差{spread:.1f}pct）",
                        "detail": "市场风格切换频繁，短线操作难度大",
                    })

            # 基于资金流向
            if fund_flow:
                total_net = sum(f.get("main_net_inflow", 0) for f in fund_flow[:10])
                net_yi = total_net / 1e8
                if abs(net_yi) > 50:
                    direction = "流入" if net_yi > 0 else "流出"
                    insights.append({
                        "type": "fund_flow", "level": "high",
                        "title": f"主力资金{direction}{abs(net_yi):.0f}亿",
                        "detail": "关注市场主力意图",
                    })

            set_cache(cache_key, insights)
            return insights
        except Exception as e:
            logger.warning(f"投资观点生成失败: {e}")
            return []

    def get_market_sentiment(self) -> Dict[str, Any]:
        """获取市场情绪（v3: 含多维评分）"""
        indices = _fetch_sina_indices()
        sectors = _fetch_eastmoney_sectors()
        fund_flow = _fetch_eastmoney_fund_flow()
        v1 = self._analyze_sentiment(indices, sectors)
        v3 = _compute_sentiment_score(indices, sectors, fund_flow)
        return {**v1, "sentiment_v3": v3}

    def get_investment_summary(self) -> Dict[str, Any]:
        """获取投资摘要"""
        return {}

    # ==================== 海外新闻模块 ====================

    def get_overseas_news(self) -> Dict[str, Any]:
        """获取海外高质量新闻（Reuters/CoinDesk等）"""
        cache_key = "daily_overseas_news"
        cached = get_cache(cache_key, 1800)  # 30分钟缓存
        if cached:
            return cached
        try:
            from app.services.overseas_news_service import overseas_news_service
            result = overseas_news_service.get_all_overseas_news()
        except Exception as e:
            logger.warning(f"海外新闻模块失败: {e}")
            result = {
                "us_stock": {"items": [], "sources_ok": [], "sources_failed": [], "count": 0, "high_impact_count": 0, "medium_impact_count": 0},
                "crypto": {"items": [], "sources_ok": [], "sources_failed": [], "count": 0, "high_impact_count": 0, "medium_impact_count": 0},
                "update_time": datetime.now().isoformat(),
            }
        set_cache(cache_key, result)
        return result

    # ==================== 五大大师模块 ====================

    def get_value_investing_insights(self) -> Dict[str, Any]:
        """获取价值投资信息（财经快讯 + 研报 + 热门板块）"""
        cache_key = "daily_value_investing"
        cached = get_cache(cache_key, TTL_DAILY)
        if cached:
            return cached
        try:
            from app.services.rss_service import rss_service
            result = rss_service.get_value_investing_news()
        except Exception as e:
            logger.warning(f"价值投资模块失败: {e}")
            result = {}
        set_cache(cache_key, result)
        return result

    def get_arbitrage_opportunities(self) -> Dict[str, Any]:
        """获取套利机会（并购公告 + A/H溢价 + ETF溢折价）"""
        cache_key = "daily_arbitrage"
        cached = get_cache(cache_key, TTL_DAILY)
        if cached:
            return cached
        try:
            from app.services.rss_service import rss_service
            result = rss_service.get_arbitrage_news()
        except Exception as e:
            logger.warning(f"套利模块失败: {e}")
            result = {}
        set_cache(cache_key, result)
        return result

    def get_convertible_bond_insights(self) -> Dict[str, Any]:
        """获取可转债信息（双低策略 + 交易所公告事件）"""
        cache_key = "daily_cb"
        cached = get_cache(cache_key, TTL_DAILY)
        if cached:
            return cached
        try:
            from app.services.rss_service import rss_service
            from app.services.cb_service import CBService
            # 结构化数据：双低策略
            structured = CBService.get_double_low_list(top_n=10)
            bonds = structured.get("bonds", []) if isinstance(structured, dict) else []
            # RSS 新闻/公告事件
            news = rss_service.get_cb_news()
            result = {
                "hot_bonds": bonds,
                "low_premium": [b for b in bonds if (b.get("premium") or 999) < 5],
                "high_yield": [b for b in bonds if (b.get("ytm") or 0) > 2],
                "events": news.get("events", []),
                "update_time": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.warning(f"可转债模块失败: {e}")
            result = {}
        set_cache(cache_key, result)
        return result

    def get_crypto_insights(self) -> Dict[str, Any]:
        """获取加密市场信息（CoinGecko行情 + DefiLlama稳定币）"""
        cache_key = "daily_crypto"
        cached = get_cache(cache_key, TTL_DAILY)
        if cached:
            return cached
        try:
            from app.services.rss_service import rss_service
            result = rss_service.get_crypto_news()
        except Exception as e:
            logger.warning(f"币圈模块失败: {e}")
            result = {}
        set_cache(cache_key, result)
        return result

    def get_airdrop_opportunities(self) -> Dict[str, Any]:
        """获取空投机会（DefiLlama未发币高TVL协议）"""
        cache_key = "daily_airdrops"
        cached = get_cache(cache_key, TTL_DAILY)
        if cached:
            return cached
        try:
            from app.services.rss_service import rss_service
            result = rss_service.get_airdrop_news()
        except Exception as e:
            logger.warning(f"空投模块失败: {e}")
            result = {}
        set_cache(cache_key, result)
        return result


# 单例
daily_info_service = DailyInfoService()
