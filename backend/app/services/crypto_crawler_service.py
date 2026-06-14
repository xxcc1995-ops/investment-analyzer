"""
币圈情报搜集器 - 定期从互联网各角落抓取币圈实用信息
数据源：RSS、API、网页爬取
"""
import json
import logging
import os
import time
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import requests

logger = logging.getLogger(__name__)

# 代理配置
PROXY = os.getenv("POLYMARKET_PROXY") or os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY")
_PROXIES = {"http": PROXY, "https": PROXY} if PROXY else None

# 共享Session
_session = requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
})
if _PROXIES:
    _session.proxies.update(_PROXIES)

# 数据存储路径
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
DATA_FILE = os.path.join(DATA_DIR, "crypto_intel.json")

# 缓存
_cache: dict = {}
CACHE_TTL = 1800  # 30分钟


def _get_cached(key: str):
    if key in _cache:
        val, ts = _cache[key]
        if time.time() - ts < CACHE_TTL:
            return val
    return None


def _set_cached(key: str, val):
    _cache[key] = (val, time.time())


def _load_data() -> dict:
    """从文件加载历史数据"""
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"加载数据文件失败: {e}")
    return {"items": [], "last_crawl": None, "sources": {}}


def _save_data(data: dict):
    """保存数据到文件"""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"保存数据文件失败: {e}")


def _item_hash(title: str, url: str) -> str:
    """生成内容唯一ID"""
    return hashlib.md5(f"{title}:{url}".encode()).hexdigest()[:12]


def _fetch_rss(url: str, timeout: int = 10) -> List[dict]:
    """获取RSS feed"""
    try:
        import feedparser
        resp = _session.get(url, timeout=timeout)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
        items = []
        for entry in feed.entries[:20]:
            published = ""
            if hasattr(entry, "published"):
                published = entry.published
            elif hasattr(entry, "updated"):
                published = entry.updated
            items.append({
                "title": entry.get("title", ""),
                "url": entry.get("link", ""),
                "summary": entry.get("summary", "")[:300],
                "published": published,
            })
        return items
    except Exception as e:
        logger.warning(f"RSS获取失败 {url}: {e}")
        return []


def _fetch_json(url: str, timeout: int = 10) -> Optional[dict]:
    """获取JSON API"""
    try:
        resp = _session.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"JSON API获取失败 {url}: {e}")
        return None


class CryptoCrawlerService:
    """币圈情报搜集服务"""

    # ==================================================================
    # 数据源定义
    # ==================================================================

    RSS_SOURCES = [
        # 英文源
        {"name": "CoinDesk", "url": "https://www.coindesk.com/arc/outboundfeeds/rss/", "lang": "en", "tier": 1, "category": "news"},
        {"name": "The Block", "url": "https://www.theblock.co/rss.xml", "lang": "en", "tier": 1, "category": "news"},
        {"name": "CoinTelegraph", "url": "https://cointelegraph.com/rss", "lang": "en", "tier": 2, "category": "news"},
        {"name": "Decrypt", "url": "https://decrypt.co/feed", "lang": "en", "tier": 2, "category": "news"},
        {"name": "Bitcoin Magazine", "url": "https://bitcoinmagazine.com/feed", "lang": "en", "tier": 1, "category": "btc"},
        {"name": "The Defiant", "url": "https://thedefiant.io/feed", "lang": "en", "tier": 2, "category": "defi"},
        {"name": "Bankless", "url": "https://www.bankless.com/rss", "lang": "en", "tier": 1, "category": "defi"},
        {"name": "Messari", "url": "https://messari.io/rss", "lang": "en", "tier": 1, "category": "research"},
        # 中文源
        {"name": "PANews", "url": "https://www.panewslab.com/rss", "lang": "zh", "tier": 1, "category": "news"},
        {"name": "Odaily", "url": "https://www.odaily.news/rss", "lang": "zh", "tier": 1, "category": "news"},
        {"name": "Foresight News", "url": "https://www.foresightnews.pro/rss", "lang": "zh", "tier": 2, "category": "news"},
        {"name": "BlockBeats", "url": "https://www.theblockbeats.info/rss", "lang": "zh", "tier": 1, "category": "news"},
        # 链上/数据分析
        {"name": "Dune Blog", "url": "https://dune.com/blog/rss.xml", "lang": "en", "tier": 1, "category": "onchain"},
        {"name": "Nansen", "url": "https://www.nansen.ai/blog/rss.xml", "lang": "en", "tier": 1, "category": "onchain"},
        {"name": "Delphi Digital", "url": "https://members.delphidigital.io/feed", "lang": "en", "tier": 1, "category": "research"},
    ]

    # 高影响力关键词
    HIGH_IMPACT_KEYWORDS = [
        "bitcoin etf", "halving", "sec", "regulation", "hack", "exploit", "rug pull",
        "stablecoin depeg", "fed rate", "interest rate", "blackrock", "fidelity",
        "airdrop", "token launch", "mainnet", "partnership", "acquisition",
        "layer 2", "zk", "restaking", "rwa", "ai", "meme coin",
    ]

    MEDIUM_IMPACT_KEYWORDS = [
        "defi", "staking", "yield", "bridge", "oracle", "governance",
        "nft", "dao", "metaverse", "gaming", "social fi", "depin",
        "solana", "ethereum", "bitcoin", "base", "arbitrum", "optimism",
    ]

    # ==================================================================
    # 核心搜集逻辑
    # ==================================================================

    def crawl_all(self, max_per_source: int = 15) -> dict:
        """从所有数据源搜集信息"""
        cached = _get_cached("crawl_all")
        if cached:
            return cached

        data = _load_data()
        existing_hashes = {item.get("hash") for item in data.get("items", [])}
        new_items = []
        source_status = {}

        for source in self.RSS_SOURCES:
            name = source["name"]
            try:
                rss_items = _fetch_rss(source["url"], timeout=12)
                added = 0
                for ri in rss_items[:max_per_source]:
                    h = _item_hash(ri["title"], ri["url"])
                    if h in existing_hashes:
                        continue
                    # 分析影响力
                    impact = self._analyze_impact(ri["title"], ri.get("summary", ""))
                    item = {
                        "hash": h,
                        "source": name,
                        "source_tier": source["tier"],
                        "source_lang": source["lang"],
                        "source_category": source["category"],
                        "title": ri["title"],
                        "url": ri["url"],
                        "summary": ri.get("summary", "")[:300],
                        "published": ri.get("published", ""),
                        "impact": impact["level"],
                        "impact_reason": impact["reason"],
                        "tags": impact["tags"],
                        "collected_at": datetime.now().isoformat(),
                    }
                    new_items.append(item)
                    existing_hashes.add(h)
                    added += 1
                source_status[name] = {"status": "ok", "fetched": len(rss_items), "new": added}
            except Exception as e:
                source_status[name] = {"status": "error", "error": str(e)[:100]}
                logger.warning(f"搜集失败 {name}: {e}")

        # 合并新旧数据，保留最近7天
        cutoff = (datetime.now() - timedelta(days=7)).isoformat()
        all_items = data.get("items", [])
        all_items.extend(new_items)
        all_items = [i for i in all_items if i.get("collected_at", "") > cutoff]

        # 按影响力和时间排序
        impact_order = {"high": 0, "medium": 1, "low": 2}
        all_items.sort(key=lambda x: (impact_order.get(x.get("impact", "low"), 2), x.get("collected_at", "")))

        # 限制总量
        all_items = all_items[:500]

        result = {
            "items": all_items,
            "new_count": len(new_items),
            "total_count": len(all_items),
            "last_crawl": datetime.now().isoformat(),
            "sources": source_status,
        }

        # 保存
        data["items"] = all_items
        data["last_crawl"] = result["last_crawl"]
        data["sources"] = source_status
        _save_data(data)

        _set_cached("crawl_all", result)
        return result

    def _analyze_impact(self, title: str, summary: str) -> dict:
        """分析新闻影响力"""
        text = f"{title} {summary}".lower()
        tags = []

        # 检查高影响力关键词
        for kw in self.HIGH_IMPACT_KEYWORDS:
            if kw in text:
                tags.append(kw)

        if tags:
            return {"level": "high", "reason": f"包含关键词: {', '.join(tags[:3])}", "tags": tags}

        # 检查中影响力关键词
        for kw in self.MEDIUM_IMPACT_KEYWORDS:
            if kw in text:
                tags.append(kw)

        if tags:
            return {"level": "medium", "reason": f"包含关键词: {', '.join(tags[:3])}", "tags": tags}

        return {"level": "low", "reason": "一般资讯", "tags": []}

    # ==================================================================
    # 分类查询
    # ==================================================================

    def get_latest(self, category: str = None, impact: str = None, limit: int = 50) -> dict:
        """获取最新搜集的情报"""
        data = _load_data()
        items = data.get("items", [])

        if category:
            items = [i for i in items if i.get("source_category") == category]
        if impact:
            items = [i for i in items if i.get("impact") == impact]

        # 按时间排序取最新
        items.sort(key=lambda x: x.get("collected_at", ""), reverse=True)

        return {
            "items": items[:limit],
            "total": len(items),
            "last_crawl": data.get("last_crawl"),
            "source_count": len(data.get("sources", {})),
        }

    def get_high_impact(self, limit: int = 20) -> dict:
        """获取高影响力情报"""
        return self.get_latest(impact="high", limit=limit)

    def get_by_category(self, category: str, limit: int = 30) -> dict:
        """按分类获取"""
        return self.get_latest(category=category, limit=limit)

    def get_sources_status(self) -> dict:
        """获取数据源状态"""
        data = _load_data()
        return {
            "sources": data.get("sources", {}),
            "last_crawl": data.get("last_crawl"),
            "total_items": len(data.get("items", [])),
        }

    # ==================================================================
    # 热门话题分析
    # ==================================================================

    def get_trending_topics(self) -> dict:
        """分析当前热门话题"""
        data = _load_data()
        items = data.get("items", [])

        # 统计标签出现频率
        tag_count: Dict[str, int] = {}
        for item in items:
            for tag in item.get("tags", []):
                tag_count[tag] = tag_count.get(tag, 0) + 1

        # 排序
        sorted_tags = sorted(tag_count.items(), key=lambda x: x[1], reverse=True)

        return {
            "trending": [{"topic": t[0], "count": t[1]} for t in sorted_tags[:15]],
            "analyzed_items": len(items),
            "last_crawl": data.get("last_crawl"),
        }

    # ==================================================================
    # 一键搜集（手动触发）
    # ==================================================================

    def force_crawl(self) -> dict:
        """强制重新搜集（清除缓存）"""
        _cache.clear()
        return self.crawl_all()
