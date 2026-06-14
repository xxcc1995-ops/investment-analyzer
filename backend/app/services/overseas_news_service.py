"""
海外高质量信息源服务 - 直接HTTP获取 + RSS解析

聚焦美股和币圈的高质量新闻。

获取策略：
1. 直接爬取网站HTML（用 requests + 简单解析）
2. RSS feed解析（部分源提供RSS）
3. 代理支持（通过环境变量配置）

信息源筛选原则：
- 一手源优先：交易所、央行、监管披露
- 专业媒体：Reuters、MarketWatch、CoinDesk、The Block
- 避免：社交媒体噪音、自媒体、未验证消息
"""

import os
import re
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin
from app.core.cache import get_cache, set_cache

logger = logging.getLogger(__name__)

TTL_OVERSEAS_NEWS = 1800

# 代理配置
PROXY = os.getenv("POLYMARKET_PROXY") or os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY")

# 共享HTTP会话
import requests as _requests
_session = _requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
})
if PROXY:
    _session.proxies = {"http": PROXY, "https": PROXY}


# ==================== 影响力评分 ====================

HIGH_IMPACT_KEYWORDS = [
    "fed", "fomc", "rate cut", "rate hike", "interest rate", "federal reserve",
    "ecb", "boj", "pboc", "central bank", "monetary policy",
    "cpi", "inflation", "gdp", "unemployment", "nonfarm", "jobs report",
    "ppi", "retail sales", "pmi",
    "sec", "regulation", "regulatory", "ban", "approve", "approval",
    "etf approved", "spot etf", "ruling",
    "crash", "surge", "soar", "plunge", "tumble", "bear market", "bull market",
    "recession", "default", "bankruptcy", "bailout",
    "bitcoin etf", "halving", "hack", "exploit", "bridge", "rug pull",
    "stablecoin depeg",
    "美联储", "加息", "降息", "利率", "监管", "批准", "禁止",
    "暴跌", "暴涨", "崩盘", "比特币", "减半", "黑客", "稳定币",
]

MEDIUM_IMPACT_KEYWORDS = [
    "earnings", "revenue", "profit", "guidance", "forecast", "outlook",
    "upgrade", "downgrade", "price target", "analyst",
    "ipo", "merger", "acquisition", "buyback", "dividend",
    "layer 2", "defi", "staking", "yield", "airdrop",
    "ipo", "并购", "收购", "回购", "分红", "质押",
]

AD_KEYWORDS = [
    "sponsored", "partner content", "paid post", "advertisement",
    "promoted", "affiliate", "best broker", "best exchange",
    "sign up", "open an account", "learn more",
    "top 5", "top 10", "best stocks to buy", "must-buy",
    "5 stocks", "10 stocks", "you should buy",
    "赞助", "广告", "开户", "推荐买入",
]


def _score_impact(title: str, summary: str) -> str:
    text = (title + " " + summary).lower()
    for kw in HIGH_IMPACT_KEYWORDS:
        if kw in text:
            return "high"
    for kw in MEDIUM_IMPACT_KEYWORDS:
        if kw in text:
            return "medium"
    return "low"


def _is_ad_or_clickbait(title: str, summary: str) -> bool:
    text = (title + " " + summary).lower()
    for kw in AD_KEYWORDS:
        if kw in text:
            return True
    if title.count("!") >= 3:
        return True
    return False


def _normalize_time(raw_time: str) -> str:
    if not raw_time:
        return ""
    if any(kw in raw_time.lower() for kw in ["ago", "前", "分钟", "小时", "天"]):
        return raw_time
    try:
        raw_clean = raw_time.replace("Z", "+00:00")
        dt = datetime.fromisoformat(raw_clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        diff = now - dt
        if diff.total_seconds() < 0:
            return raw_time
        if diff.total_seconds() < 3600:
            mins = int(diff.total_seconds() / 60)
            return f"{mins}分钟前" if mins > 0 else "刚刚"
        if diff.total_seconds() < 86400:
            hours = int(diff.total_seconds() / 3600)
            return f"{hours}小时前"
        days = diff.days
        if days == 1:
            return "昨天"
        if days < 7:
            return f"{days}天前"
        return raw_time[:10]
    except Exception:
        pass
    for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
        try:
            dt = datetime.strptime(raw_time[:19], fmt)
            now = datetime.now()
            diff = now - dt
            if diff.total_seconds() < 3600:
                return f"{int(diff.total_seconds() / 60)}分钟前"
            if diff.total_seconds() < 86400:
                return f"{int(diff.total_seconds() / 3600)}小时前"
            if diff.days < 7:
                return f"{diff.days}天前"
            return raw_time[:10]
        except Exception:
            continue
    return raw_time


def _make_news_item(title: str, summary: str, link: str, published: str,
                    source: str, category: str, impact: str = "low",
                    key_points: Optional[List[str]] = None) -> Dict[str, Any]:
    return {
        "title": title.strip(),
        "summary": summary.strip()[:500] if summary else "",
        "link": link.strip(),
        "published": _normalize_time(published),
        "source": source,
        "category": category,
        "impact": impact,
        "key_points": key_points or [],
    }


# ==================== RSS Feed 解析 ====================

def _parse_rss(xml_text: str) -> List[Dict[str, str]]:
    """简单RSS/Atom XML解析，不依赖feedparser"""
    items = []
    # RSS 2.0 格式
    for match in re.finditer(r'<item>(.*?)</item>', xml_text, re.DOTALL):
        block = match.group(1)
        title = re.search(r'<title[^>]*>(.*?)</title>', block, re.DOTALL)
        link = re.search(r'<link[^>]*>(.*?)</link>', block, re.DOTALL)
        desc = re.search(r'<description[^>]*>(.*?)</description>', block, re.DOTALL)
        # 也尝试 content:encoded（更完整的正文）
        content = re.search(r'<content:encoded[^>]*>(.*?)</content:encoded>', block, re.DOTALL)
        pub = re.search(r'<pubDate[^>]*>(.*?)</pubDate>', block, re.DOTALL)
        # 优先用 content:encoded，其次 description
        raw_desc = ""
        if content:
            raw_desc = _clean_html(content.group(1))
        elif desc:
            raw_desc = _clean_html(desc.group(1))
        # 过滤掉纯链接描述（Google News常见）
        if raw_desc.startswith('http') or raw_desc.startswith('<a '):
            raw_desc = ""
        # 过滤掉太短或无意义的描述
        if len(raw_desc) < 20:
            raw_desc = ""
        items.append({
            "title": _clean_html(title.group(1)) if title else "",
            "link": link.group(1).strip() if link else "",
            "summary": raw_desc[:500],
            "published": pub.group(1).strip() if pub else "",
        })
    # Atom 格式
    if not items:
        for match in re.finditer(r'<entry>(.*?)</entry>', xml_text, re.DOTALL):
            block = match.group(1)
            title = re.search(r'<title[^>]*>(.*?)</title>', block, re.DOTALL)
            link = re.search(r'<link[^>]*href="([^"]*)"', block)
            summary = re.search(r'<summary[^>]*>(.*?)</summary>', block, re.DOTALL)
            content = re.search(r'<content[^>]*>(.*?)</content>', block, re.DOTALL)
            updated = re.search(r'<updated[^>]*>(.*?)</updated>', block, re.DOTALL)
            raw_desc = ""
            if content:
                raw_desc = _clean_html(content.group(1))
            elif summary:
                raw_desc = _clean_html(summary.group(1))
            if raw_desc.startswith('http') or raw_desc.startswith('<a '):
                raw_desc = ""
            if len(raw_desc) < 20:
                raw_desc = ""
            items.append({
                "title": _clean_html(title.group(1)) if title else "",
                "link": link.group(1).strip() if link else "",
                "summary": raw_desc[:500],
                "published": updated.group(1).strip() if updated else "",
            })
    return items


def _clean_html(text: str) -> str:
    """去除HTML标签和噪音"""
    import html as _html
    text = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', text, flags=re.DOTALL)
    # 去除 style/script 标签及其内容
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # 去除 SVG
    text = re.sub(r'<svg[^>]*>.*?</svg>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # 去除所有HTML标签
    text = re.sub(r'<[^>]+>', ' ', text)
    # 解码所有HTML实体（标准库处理 &#x2019; &#8217; &rsquo; 等全部实体）
    text = _html.unescape(text)
    # 去除多余空白
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _fetch_rss(url: str, timeout: int = 15) -> List[Dict[str, str]]:
    """获取并解析RSS feed"""
    try:
        r = _session.get(url, timeout=timeout)
        r.raise_for_status()
        return _parse_rss(r.text)
    except Exception as e:
        logger.debug(f"RSS获取失败 {url}: {e}")
        return []


def _fetch_article_key_points(url: str, timeout: int = 10) -> List[str]:
    """抓取文章页面，提取关键段落作为要点"""
    if not url or not url.startswith("http"):
        return []
    try:
        r = _session.get(url, timeout=timeout, allow_redirects=True)
        r.raise_for_status()
        html = r.text

        # 提取正文段落（启发式方法）
        paragraphs = []

        # 方法1: 查找 <article> 标签内的 <p> 标签
        article_match = re.search(r'<article[^>]*>(.*?)</article>', html, re.DOTALL | re.IGNORECASE)
        if article_match:
            article_html = article_match.group(1)
            for p_match in re.finditer(r'<p[^>]*>(.*?)</p>', article_html, re.DOTALL | re.IGNORECASE):
                text = _clean_html(p_match.group(1))
                if len(text) > 30:  # 过滤短段落（导航、按钮等）
                    paragraphs.append(text)

        # 方法2: 如果没有 <article>，查找 <main> 或 class 包含 article/content 的 div
        if not paragraphs:
            main_match = re.search(
                r'<(?:main|div)[^>]*class="[^"]*(?:article|content|post|story|body)[^"]*"[^>]*>(.*?)</(?:main|div)>',
                html, re.DOTALL | re.IGNORECASE
            )
            if main_match:
                for p_match in re.finditer(r'<p[^>]*>(.*?)</p>', main_match.group(1), re.DOTALL | re.IGNORECASE):
                    text = _clean_html(p_match.group(1))
                    if len(text) > 30:
                        paragraphs.append(text)

        # 方法3: 全页面 <p> 标签（最后手段）
        if not paragraphs:
            for p_match in re.finditer(r'<p[^>]*>(.*?)</p>', html, re.DOTALL | re.IGNORECASE):
                text = _clean_html(p_match.group(1))
                if len(text) > 50:  # 更严格的过滤
                    paragraphs.append(text)

        # 取前5个有意义的段落
        key_points = []
        for p in paragraphs[:12]:
            p = p.strip()
            # 过滤太短的段落
            if len(p) < 30:
                continue
            # 过滤CSS/JS残留
            if re.search(r'[{};]|fill:|stroke:|function\s*\(|var\s+\w+\s*=', p):
                continue
            # 过滤导航/版权/广告文本
            skip_patterns = [
                r'cookie', r'privacy', r'terms of', r'subscribe', r'sign up',
                r'©', r'all rights', r'related articles', r'you may also',
                r'read more', r'continue reading', r'click here',
                r'price data by', r'st\d+\{', r'\.st\d',
                r'follow us', r'newsletter', r'download our',
                r'cookie', r'隐私', r'条款', r'订阅', r'版权所有',
                r'advertisement', r'sponsored',
            ]
            if any(re.search(pat, p, re.IGNORECASE) for pat in skip_patterns):
                continue
            # 过滤纯数字/符号
            if re.match(r'^[\d\s\.\,\-\+\%\$]+$', p):
                continue
            key_points.append(p[:250])
            if len(key_points) >= 5:
                break

        return key_points
    except Exception as e:
        logger.debug(f"文章内容获取失败 {url}: {e}")
        return []


def _enrich_high_impact_items(items: List[Dict[str, Any]], max_fetch: int = 10) -> None:
    """为高影响力新闻补充文章内容（原地修改）"""
    high_items = [item for item in items if item.get("impact") == "high" and item.get("link")]
    if not high_items:
        return

    # 限制抓取数量
    to_fetch = high_items[:max_fetch]

    with ThreadPoolExecutor(max_workers=5) as executor:
        future_map = {}
        for item in to_fetch:
            future_map[executor.submit(_fetch_article_key_points, item["link"])] = item

        for future in as_completed(future_map, timeout=20):
            item = future_map[future]
            try:
                points = future.result(timeout=10)
                if points:
                    item["key_points"] = points
                    # 如果summary为空，用第一个要点作为摘要
                    if not item.get("summary") and points:
                        item["summary"] = points[0][:200]
            except Exception:
                pass  # 失败不影响已有的summary


# ==================== HTML 简单解析 ====================

def _extract_articles_from_html(html: str, base_url: str) -> List[Dict[str, str]]:
    """从HTML中提取文章链接和标题（通用启发式方法）"""
    articles = []
    # 查找所有带 href 的 a 标签，其中包含 h2/h3 标题
    pattern = r'<a[^>]*href="([^"]*)"[^>]*>\s*<(?:h[23])[^>]*>(.*?)</(?:h[23])>'
    for match in re.finditer(pattern, html, re.DOTALL | re.IGNORECASE):
        href = match.group(1).strip()
        title = _clean_html(match.group(2))
        if title and len(title) > 10 and not href.startswith('#') and not href.startswith('javascript:'):
            full_url = urljoin(base_url, href)
            articles.append({"title": title, "link": full_url})

    # 备选：查找 article 标签内的标题
    if not articles:
        for match in re.finditer(r'<article[^>]*>(.*?)</article>', html, re.DOTALL | re.IGNORECASE):
            block = match.group(1)
            title_m = re.search(r'<h[23][^>]*>(.*?)</h[23]>', block, re.DOTALL | re.IGNORECASE)
            link_m = re.search(r'<a[^>]*href="([^"]*)"', block)
            if title_m:
                title = _clean_html(title_m.group(1))
                href = link_m.group(1).strip() if link_m else ""
                if title and len(title) > 10:
                    articles.append({
                        "title": title,
                        "link": urljoin(base_url, href) if href else "",
                    })
    return articles


# ==================== 数据源定义 ====================

class NewsSource:
    """单个新闻源配置"""
    def __init__(self, name: str, name_cn: str, tier: int, category: str,
                 rss_url: Optional[str] = None, html_url: Optional[str] = None,
                 html_base_url: Optional[str] = None, max_items: int = 15):
        self.name = name
        self.name_cn = name_cn
        self.tier = tier
        self.category = category
        self.rss_url = rss_url
        self.html_url = html_url
        self.html_base_url = html_base_url or html_url
        self.max_items = max_items


NEWS_SOURCES = [
    # ── 美股 ──
    NewsSource("Reuters", "路透社", 1, "us_stock",
               rss_url="https://news.google.com/rss/search?q=site:reuters.com+markets&hl=en-US&gl=US&ceid=US:en"),
    NewsSource("MarketWatch", "市场观察", 1, "us_stock",
               rss_url="https://feeds.marketwatch.com/marketwatch/topstories/",
               html_url="https://www.marketwatch.com/markets"),
    NewsSource("Yahoo Finance", "雅虎财经", 2, "us_stock",
               rss_url="https://finance.yahoo.com/news/rssindex",
               html_url="https://finance.yahoo.com/topic/stock-market-news/"),
    NewsSource("Seeking Alpha", "Seeking Alpha", 2, "us_stock",
               rss_url="https://seekingalpha.com/market_currents.xml"),

    # ── 币圈 ──
    NewsSource("CoinDesk", "CoinDesk", 1, "crypto",
               rss_url="https://www.coindesk.com/arc/outboundfeeds/rss/",
               html_url="https://www.coindesk.com"),
    NewsSource("The Block", "The Block", 1, "crypto",
               rss_url="https://www.theblock.co/rss.xml",
               html_url="https://www.theblock.co"),
    NewsSource("CoinTelegraph", "CoinTelegraph", 2, "crypto",
               rss_url="https://cointelegraph.com/rss",
               html_url="https://cointelegraph.com"),
    NewsSource("Decrypt", "Decrypt", 2, "crypto",
               rss_url="https://decrypt.co/feed",
               html_url="https://decrypt.co"),
]


# ==================== 爬取引擎 ====================

def _scrape_source(source: NewsSource) -> List[Dict[str, Any]]:
    """爬取单个数据源：优先RSS，fallback到HTML"""
    items = []

    # 策略1: RSS feed
    if source.rss_url:
        rss_items = _fetch_rss(source.rss_url)
        for item in rss_items[:source.max_items]:
            title = item.get("title", "")
            if not title or len(title) < 5:
                continue
            summary = item.get("summary", "")
            if _is_ad_or_clickbait(title, summary):
                continue
            items.append(_make_news_item(
                title=title,
                summary=summary,
                link=item.get("link", ""),
                published=item.get("published", ""),
                source=source.name,
                category=source.category,
                impact=_score_impact(title, summary),
            ))
        if items:
            logger.info(f"[{source.name}] RSS成功，获取{len(items)}条")
            return items

    # 策略2: 直接爬取HTML
    if source.html_url:
        try:
            r = _session.get(source.html_url, timeout=15)
            r.raise_for_status()
            articles = _extract_articles_from_html(r.text, source.html_base_url or source.html_url)
            for art in articles[:source.max_items]:
                title = art.get("title", "")
                if not title or len(title) < 5:
                    continue
                if _is_ad_or_clickbait(title, ""):
                    continue
                items.append(_make_news_item(
                    title=title,
                    summary="",
                    link=art.get("link", ""),
                    published="",
                    source=source.name,
                    category=source.category,
                    impact=_score_impact(title, ""),
                ))
            if items:
                logger.info(f"[{source.name}] HTML成功，获取{len(items)}条")
                return items
        except Exception as e:
            logger.debug(f"[{source.name}] HTML失败: {e}")

    logger.warning(f"[{source.name}] 所有获取方式均失败")
    return []


def _parallel_scrape(sources: List[NewsSource]) -> Dict[str, Any]:
    """并行爬取多个数据源"""
    all_items = []
    sources_ok = []
    sources_failed = []

    with ThreadPoolExecutor(max_workers=6) as executor:
        future_map = {executor.submit(_scrape_source, s): s for s in sources}
        for future in as_completed(future_map, timeout=60):
            source = future_map[future]
            try:
                items = future.result(timeout=15)
                if items:
                    all_items.extend(items)
                    sources_ok.append({
                        "name": source.name,
                        "name_cn": source.name_cn,
                        "tier": source.tier,
                        "count": len(items),
                    })
                else:
                    sources_failed.append(source.name)
            except Exception as e:
                logger.warning(f"源 {source.name} 爬取异常: {e}")
                sources_failed.append(source.name)

    # 按标题去重
    seen = set()
    unique_items = []
    for item in all_items:
        key = re.sub(r'\s+', '', item["title"])[:40].lower()
        if key not in seen:
            seen.add(key)
            unique_items.append(item)

    # 按影响力排序
    impact_order = {"high": 0, "medium": 1, "low": 2}
    unique_items.sort(key=lambda x: impact_order.get(x.get("impact", "low"), 9))

    # 为高影响力新闻补充文章内容
    _enrich_high_impact_items(unique_items, max_fetch=10)

    high_count = sum(1 for i in unique_items if i.get("impact") == "high")
    medium_count = sum(1 for i in unique_items if i.get("impact") == "medium")

    return {
        "items": unique_items,
        "sources_ok": sources_ok,
        "sources_failed": sources_failed,
        "count": len(unique_items),
        "high_impact_count": high_count,
        "medium_impact_count": medium_count,
        "update_time": datetime.now().isoformat(),
    }


# ==================== 公开接口 ====================

def get_us_stock_news() -> Dict[str, Any]:
    cache_key = "overseas_news_us_stock"
    cached = get_cache(cache_key, TTL_OVERSEAS_NEWS)
    if cached:
        return cached
    us_sources = [s for s in NEWS_SOURCES if s.category == "us_stock"]
    result = _parallel_scrape(us_sources)
    set_cache(cache_key, result)
    return result


def get_crypto_news() -> Dict[str, Any]:
    cache_key = "overseas_news_crypto"
    cached = get_cache(cache_key, TTL_OVERSEAS_NEWS)
    if cached:
        return cached
    crypto_sources = [s for s in NEWS_SOURCES if s.category == "crypto"]
    result = _parallel_scrape(crypto_sources)
    set_cache(cache_key, result)
    return result


def get_all_overseas_news() -> Dict[str, Any]:
    cache_key = "overseas_news_all"
    cached = get_cache(cache_key, TTL_OVERSEAS_NEWS)
    if cached:
        return cached
    with ThreadPoolExecutor(max_workers=2) as executor:
        f_us = executor.submit(get_us_stock_news)
        f_crypto = executor.submit(get_crypto_news)
        us_result = f_us.result(timeout=90)
        crypto_result = f_crypto.result(timeout=90)
    result = {
        "us_stock": us_result,
        "crypto": crypto_result,
        "update_time": datetime.now().isoformat(),
    }
    set_cache(cache_key, result)
    return result


# ==================== 单例 ====================

overseas_news_service = type("OverseasNewsService", (), {
    "get_us_stock_news": staticmethod(get_us_stock_news),
    "get_crypto_news": staticmethod(get_crypto_news),
    "get_all_overseas_news": staticmethod(get_all_overseas_news),
})()
