"""Web Scraping API 路由"""

import logging
from urllib.parse import urlparse
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from typing import Optional
from app.utils.scraper import scrape, scrape_stealthy, scrape_dynamic, extract_text, extract_table

logger = logging.getLogger(__name__)

router = APIRouter()

# SSRF防护：禁止访问的内网地址前缀
_BLOCKED_HOSTS = {
    'localhost', '127.0.0.1', '0.0.0.0', '::1',
    '169.254.169.254',  # 云实例元数据
    'metadata.google.internal',
}
_BLOCKED_PREFIXES = ('10.', '172.16.', '172.17.', '172.18.', '172.19.',
                     '172.20.', '172.21.', '172.22.', '172.23.', '172.24.',
                     '172.25.', '172.26.', '172.27.', '172.28.', '172.29.',
                     '172.30.', '172.31.', '192.168.')


def _validate_url(url: str) -> str:
    """验证URL，防止SSRF攻击"""
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        raise ValueError(f"不支持的协议: {parsed.scheme}")
    hostname = parsed.hostname or ''
    if hostname in _BLOCKED_HOSTS:
        raise ValueError(f"禁止访问内部地址: {hostname}")
    if any(hostname.startswith(p) for p in _BLOCKED_PREFIXES):
        raise ValueError(f"禁止访问内网地址: {hostname}")
    return url


class ScrapeRequest(BaseModel):
    url: str
    mode: str = "fast"  # fast / stealthy / dynamic
    selector: Optional[str] = None
    extract_type: str = "text"  # text / table / html
    headless: bool = True

    @field_validator('url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        _validate_url(v)
        return v


class ScrapeResponse(BaseModel):
    success: bool
    data: Optional[list] = None
    html: Optional[str] = None
    error: Optional[str] = None


@router.post("/fetch", response_model=ScrapeResponse)
def fetch_page(req: ScrapeRequest):
    """爬取网页内容

    mode:
        - fast: 快速 HTTP 请求（默认）
        - stealthy: 隐身模式，绕过 Cloudflare
        - dynamic: 完整浏览器，处理 JS 渲染
    """
    try:
        # 选择爬取方式
        if req.mode == "stealthy":
            page = scrape_stealthy(req.url, headless=req.headless)
        elif req.mode == "dynamic":
            page = scrape_dynamic(req.url, headless=req.headless)
        else:
            page = scrape(req.url)

        # 提取数据
        if req.extract_type == "html":
            return ScrapeResponse(success=True, html=str(page.body))

        if req.extract_type == "table" and req.selector:
            data = extract_table(page, req.selector)
            return ScrapeResponse(success=True, data=data)

        if req.selector:
            data = extract_text(page, req.selector)
            return ScrapeResponse(success=True, data=data)

        # 默认返回页面标题和文本
        title = page.css("title::text").get() or ""
        body_text = page.css("body").text[:2000] if page.css("body") else ""
        return ScrapeResponse(success=True, data=[title, body_text])

    except ValueError as e:
        return ScrapeResponse(success=False, error=str(e))
    except Exception as e:
        logger.exception("爬取失败: %s", req.url)
        return ScrapeResponse(success=False, error=str(e))


@router.get("/test")
def test_scrapling():
    """测试 Scrapling 是否正常工作"""
    try:
        from scrapling.fetchers import Fetcher
        page = Fetcher.get("https://quotes.toscrape.com/")
        quotes = page.css(".quote .text::text").getall()
        return {
            "success": True,
            "quotes_count": len(quotes),
            "sample": quotes[:3] if quotes else [],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
