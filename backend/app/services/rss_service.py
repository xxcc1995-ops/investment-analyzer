"""
RSS 信息聚合服务 - 通过 RSSHub + 直接 API 获取高质量财经信息

信息源原则：
- 一手源：交易所公告、央行数据、监管披露
- 专业媒体：财联社、华尔街见闻、FT中文网、CoinDesk
- 专业平台：集思录（可转债）、DefiLlama（DeFi）、CoinGecko（加密）
- 避免：股吧、雪球热帖、自媒体公众号

数据源类型：
- RSSHub feeds: 财联社电报、华尔街见闻、巨潮资讯、交易所公告等
- 直接 API: CoinGecko（加密行情）、DefiLlama（DeFi TVL/稳定币）
"""

import os
import logging
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# RSSHub 实例地址（支持多个备用实例，逗号分隔）
_rsshub_env = os.getenv("RSSHUB_BASE", "")
RSSHUB_INSTANCES = [u.strip() for u in _rsshub_env.split(",") if u.strip()] if _rsshub_env else []
# 默认备用实例列表（公共实例 + 社区镜像）
if not RSSHUB_INSTANCES:
    RSSHUB_INSTANCES = [
        "https://rsshub.app",
        "https://rsshub.rssforever.com",
        "https://rsshub-instance.zeabur.app",
    ]

# 共享 HTTP 会话
_session = requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
})


# ==================== 底层工具 ====================

def _fetch_feed(url: str, timeout: int = 10) -> List[Dict[str, Any]]:
    """获取并解析单个 RSS feed，返回标准化条目列表"""
    try:
        import feedparser
        resp = _session.get(url, timeout=timeout)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
        items = []
        for entry in feed.entries[:20]:  # 每个源最多取 20 条
            items.append({
                "title": getattr(entry, "title", ""),
                "link": getattr(entry, "link", ""),
                "summary": getattr(entry, "summary", "")[:200],
                "published": getattr(entry, "published", ""),
                "source": feed.feed.get("title", ""),
            })
        return items
    except ImportError:
        logger.warning("feedparser 未安装，跳过 RSS 获取")
        return []
    except Exception as e:
        logger.warning(f"RSS 获取失败 {url}: {e}")
        return []


def _fetch_rsshub_feed(path: str, timeout: int = 10) -> List[Dict[str, Any]]:
    """从 RSSHub 实例获取 feed，自动尝试多个备用实例"""
    for base in RSSHUB_INSTANCES:
        url = f"{base}{path}"
        items = _fetch_feed(url, timeout=timeout)
        if items:
            return items
    return []


def _fetch_json(url: str, timeout: int = 10) -> Optional[Any]:
    """获取 JSON API 响应"""
    try:
        resp = _session.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"JSON API 获取失败 {url}: {e}")
        return None


def _extract_stock_code(title: str) -> str:
    """从标题中提取股票代码（如 600519、SZ000001 等）"""
    import re
    patterns = [
        r'[SZHBszhb]{2}(\d{6})',  # SZ000001 格式
        r'[\(（](\d{6})[\)）]',    # (600519) 格式
        r'\b(\d{6})\b',           # 纯 6 位数字
    ]
    for p in patterns:
        m = re.search(p, title)
        if m:
            return m.group(1)
    return ""


# ==================== 价值投资模块 ====================

def get_value_investing_news() -> Dict[str, Any]:
    """获取价值投资信息：财经快讯 + 研报 + 热门板块"""
    # 并行获取多个 RSS 源
    with ThreadPoolExecutor(max_workers=3) as executor:
        f_cls = executor.submit(_fetch_rsshub_feed, "/cls/telegraph")
        f_wscn = executor.submit(_fetch_rsshub_feed, "/wallstreetcn/news/global")
        f_report = executor.submit(_fetch_rsshub_feed, "/eastmoney/report/strategy")
        try:
            cls_items = f_cls.result(timeout=15)
            wscn_items = f_wscn.result(timeout=15)
            report_items = f_report.result(timeout=15)
        except Exception:
            cls_items, wscn_items, report_items = [], [], []

    # 合并快讯 → announcements
    announcements = []
    for item in cls_items[:10]:
        announcements.append({
            "title": item["title"],
            "code": _extract_stock_code(item["title"]),
            "date": item["published"] or datetime.now().strftime("%Y-%m-%d"),
            "type": "快讯",
        })
    for item in wscn_items[:10]:
        announcements.append({
            "title": item["title"],
            "code": _extract_stock_code(item["title"]),
            "date": item["published"] or datetime.now().strftime("%Y-%m-%d"),
            "type": "快讯",
        })

    # 研报（东方财富策略研报）
    analyst_reports = []
    for item in report_items[:10]:
        analyst_reports.append({
            "name": item["title"],
            "institution": item.get("source", "东方财富"),
            "score": 0,
            "recommend_count": 0,
        })

    # 热门板块（从东方财富获取结构化数据）
    concept_boards = _fetch_eastmoney_hot_sectors()

    return {
        "announcements": announcements[:15],
        "analyst_reports": analyst_reports[:10],
        "concept_boards": concept_boards[:10],
        "update_time": datetime.now().isoformat(),
    }


def _fetch_eastmoney_hot_sectors() -> List[Dict[str, Any]]:
    """从东方财富获取热门概念板块"""
    try:
        url = "https://push2.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": "1", "pz": "10", "po": "1",
            "np": "1", "fltt": "2", "invt": "2",
            "fid": "f3", "fs": "m:90+t:3",  # t:3 = 概念板块
            "fields": "f2,f3,f4,f12,f14,f104,f105",
        }
        r = _session.get(url, params=params, timeout=5)
        data = r.json()
        boards = []
        for item in (data.get("data") or {}).get("diff") or []:
            boards.append({
                "name": item.get("f14", ""),
                "change_pct": item.get("f3", 0),
                "turnover": 0,
                "amount": 0,
            })
        return boards
    except Exception as e:
        logger.warning(f"东方财富概念板块获取失败: {e}")
        return []


# ==================== 套利模块 ====================

def get_arbitrage_news() -> Dict[str, Any]:
    """获取套利机会信息：证监会并购公告 + ETF 溢价"""
    # 证监会/交易所公告（并行获取）
    with ThreadPoolExecutor(max_workers=2) as executor:
        f_csrc = executor.submit(_fetch_rsshub_feed, "/csrc/news")
        f_sse = executor.submit(_fetch_rsshub_feed, "/sse/disclosure")
        try:
            csrc_items = f_csrc.result(timeout=15)
            sse_items = f_sse.result(timeout=15)
        except Exception:
            csrc_items, sse_items = [], []

    all_items = csrc_items + sse_items

    # 筛选并购重组相关公告
    merger_keywords = ["并购", "重组", "收购", "吸收合并", "要约收购"]
    merger_arbitrage = []
    for item in all_items:
        title = item["title"]
        if any(kw in title for kw in merger_keywords):
            merger_arbitrage.append({
                "code": _extract_stock_code(title),
                "name": title[:30],
                "status": "公告",
                "progress": item.get("published", ""),
            })

    # A/H 股溢价（从 AKShare 获取）
    cross_market = _fetch_ah_premium()

    # ETF 溢价（从东方财富获取）
    etf_premium = _fetch_etf_premium()

    return {
        "merger_arbitrage": merger_arbitrage[:10],
        "cross_market_spreads": cross_market[:10],
        "etf_premium": etf_premium[:10],
        "update_time": datetime.now().isoformat(),
    }


def _fetch_ah_premium() -> List[Dict[str, Any]]:
    """获取 A/H 股溢价数据"""
    try:
        import akshare as ak
        df = ak.stock_zh_ah_spot()
        if df is None or df.empty:
            return []
        results = []
        for _, row in df.head(10).iterrows():
            results.append({
                "name": str(row.get("名称", "")),
                "a_price": float(row.get("最新价", 0) or 0),
                "h_price": float(row.get("H股最新价", 0) or 0),
                "premium": float(row.get("溢价率", 0) or 0),
            })
        return results
    except Exception as e:
        logger.warning(f"A/H 溢价获取失败: {e}")
        return []


def _fetch_etf_premium() -> List[Dict[str, Any]]:
    """获取 ETF 溢价/折价数据"""
    try:
        import akshare as ak
        df = ak.fund_etf_spot_em()
        if df is None or df.empty:
            return []
        results = []
        # 筛选有溢价/折价的 ETF
        for _, row in df.iterrows():
            price = float(row.get("最新价", 0) or 0)
            nav = float(row.get("IOPV实时估值", 0) or 0)
            if nav > 0 and price > 0:
                premium = (price - nav) / nav * 100
                if abs(premium) > 0.5:  # 只保留溢价/折价超过 0.5% 的
                    results.append({
                        "code": str(row.get("代码", "")),
                        "name": str(row.get("名称", "")),
                        "price": round(price, 4),
                        "nav": round(nav, 4),
                        "premium": round(premium, 2),
                    })
        # 按溢价率绝对值排序
        results.sort(key=lambda x: abs(x["premium"]), reverse=True)
        return results[:10]
    except Exception as e:
        logger.warning(f"ETF 溢价获取失败: {e}")
        return []


# ==================== 可转债模块 ====================

def get_cb_news() -> Dict[str, Any]:
    """获取可转债信息：交易所公告中的可转债事件"""
    # 并行获取上交所/深交所公告
    with ThreadPoolExecutor(max_workers=2) as executor:
        f_sse = executor.submit(_fetch_rsshub_feed, "/sse/disclosure")
        f_szse = executor.submit(_fetch_rsshub_feed, "/szse/disclosure")
        try:
            sse_items = f_sse.result(timeout=15)
            szse_items = f_szse.result(timeout=15)
        except Exception:
            sse_items, szse_items = [], []

    all_items = sse_items + szse_items

    # 筛选可转债相关公告
    cb_keywords = ["可转债", "转债", "赎回", "下修", "回售", "付息"]
    events = []
    seen_titles = set()
    for item in all_items:
        title = item["title"]
        if title in seen_titles:
            continue
        if any(kw in title for kw in cb_keywords):
            seen_titles.add(title)
            # 识别事件类型
            event_type = "公告"
            if "赎回" in title:
                event_type = "强制赎回"
            elif "下修" in title:
                event_type = "转股价下修"
            elif "回售" in title:
                event_type = "回售"
            elif "付息" in title:
                event_type = "付息"

            events.append({
                "code": _extract_stock_code(title),
                "name": title[:30],
                "event": event_type,
                "date": item.get("published", datetime.now().strftime("%Y-%m-%d")),
            })

    return {
        "events": events[:15],
        "update_time": datetime.now().isoformat(),
    }


# ==================== 币圈模块 ====================

def get_crypto_news() -> Dict[str, Any]:
    """获取加密市场信息：CoinGecko 行情 + DefiLlama 稳定币"""
    # CoinGecko 市场数据（免费 API，无需 key）
    market_overview = _fetch_coingecko_market()
    top_gainers = _fetch_coingecko_gainers()

    # DefiLlama 稳定币市值
    stablecoin_mcap = _fetch_defillama_stablecoins()

    # 补充：RSS 新闻
    crypto_feed = _fetch_rsshub_feed("/coindesk", timeout=8)

    return {
        "market_overview": market_overview[:10],
        "top_gainers": top_gainers[:10],
        "stablecoin_mcap": stablecoin_mcap,
        "defi_tvl": [],  # TODO: 从 DefiLlama 获取
        "update_time": datetime.now().isoformat(),
    }


def _fetch_coingecko_market() -> List[Dict[str, Any]]:
    """从 CoinGecko 获取市值 Top 10 加密货币"""
    data = _fetch_json(
        "https://api.coingecko.com/api/v3/coins/markets"
        "?vs_currency=usd&order=market_cap_desc&per_page=10&page=1"
        "&sparkline=false&price_change_percentage=24h",
        timeout=10,
    )
    if not data:
        return []
    results = []
    for coin in data:
        results.append({
            "name": coin.get("name", ""),
            "symbol": coin.get("symbol", "").upper(),
            "price": coin.get("current_price", 0),
            "change_24h": coin.get("price_change_percentage_24h", 0) or 0,
            "market_cap": coin.get("market_cap", 0),
            "volume": coin.get("total_volume", 0),
        })
    return results


def _fetch_coingecko_gainers() -> List[Dict[str, Any]]:
    """从 CoinGecko 获取 24h 涨幅 Top 10"""
    data = _fetch_json(
        "https://api.coingecko.com/api/v3/coins/markets"
        "?vs_currency=usd&order=market_cap_desc&per_page=100&page=1"
        "&sparkline=false&price_change_percentage=24h",
        timeout=10,
    )
    if not data:
        return []
    # 按 24h 涨幅排序
    sorted_coins = sorted(
        data,
        key=lambda x: x.get("price_change_percentage_24h", 0) or 0,
        reverse=True,
    )
    results = []
    for coin in sorted_coins[:10]:
        results.append({
            "name": coin.get("name", ""),
            "symbol": coin.get("symbol", "").upper(),
            "price": coin.get("current_price", 0),
            "change_24h": coin.get("price_change_percentage_24h", 0) or 0,
        })
    return results


def _fetch_defillama_stablecoins() -> Optional[float]:
    """从 DefiLlama 获取稳定币总市值"""
    data = _fetch_json("https://stablecoins.llama.fi/stablecoins?includePrices=false", timeout=10)
    if not data:
        return None
    total = 0
    for coin in data.get("peggedAssets", []):
        total += coin.get("circulating", {}).get("peggedUSD", 0)
    return round(total / 1e9, 2)  # 返回十亿美元单位


# ==================== 空投模块 ====================

def get_airdrop_news() -> Dict[str, Any]:
    """获取空投机会：DefiLlama 未发币高 TVL 协议"""
    # DefiLlama 全量协议
    protocols = _fetch_defillama_protocols()

    # 筛选未发币 + TVL > $100M 的协议
    defi_protocols = []
    for p in protocols:
        name = p.get("name", "")
        tvl = p.get("tvl") or 0
        symbol = p.get("symbol", "")
        category = p.get("category", "")
        chain = p.get("chain", "Multi")
        gecko_id = p.get("gecko_id")

        # 判断未发币：symbol 为 "-" 或空，且 gecko_id 为空
        is_no_token = (symbol in ("-", "", "N/A")) and not gecko_id
        if is_no_token and tvl > 100_000_000:
            defi_protocols.append({
                "name": name,
                "chain": chain,
                "tvl": round(tvl / 1e6, 2),  # 百万美元
                "category": category,
                "url": p.get("url", ""),
            })

    # 按 TVL 排序
    defi_protocols.sort(key=lambda x: x["tvl"], reverse=True)

    # RSS 补充：DeFi 相关新闻作为潜在空投信号
    defi_feed = _fetch_rsshub_feed("/coindesk", timeout=8)
    potential_airdrops = []
    airdrop_keywords = ["airdrop", "空投", "token launch", "代币发行", "reward"]
    for item in defi_feed:
        title_lower = item["title"].lower()
        if any(kw in title_lower for kw in airdrop_keywords):
            potential_airdrops.append({
                "name": item["title"][:50],
                "chain": "",
                "status": "新闻信号",
                "description": item.get("summary", "")[:100],
                "url": item.get("link", ""),
            })

    return {
        "potential_airdrops": potential_airdrops[:10],
        "active_campaigns": [],
        "defi_protocols": defi_protocols[:20],
        "update_time": datetime.now().isoformat(),
    }


def _fetch_defillama_protocols() -> List[Dict[str, Any]]:
    """从 DefiLlama 获取全量 DeFi 协议列表"""
    data = _fetch_json("https://api.llama.fi/protocols", timeout=15)
    if not data:
        return []
    return data


# ==================== 单例 ====================

rss_service = type("RSSService", (), {
    "get_value_investing_news": staticmethod(get_value_investing_news),
    "get_arbitrage_news": staticmethod(get_arbitrage_news),
    "get_cb_news": staticmethod(get_cb_news),
    "get_crypto_news": staticmethod(get_crypto_news),
    "get_airdrop_news": staticmethod(get_airdrop_news),
})()
