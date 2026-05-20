"""Web Scraping API 路由"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from app.utils.scraper import scrape, scrape_stealthy, scrape_dynamic, extract_text, extract_table

router = APIRouter()


class ScrapeRequest(BaseModel):
    url: str
    mode: str = "fast"  # fast / stealthy / dynamic
    selector: Optional[str] = None
    extract_type: str = "text"  # text / table / html
    headless: bool = True


class ScrapeResponse(BaseModel):
    success: bool
    data: Optional[list] = None
    html: Optional[str] = None
    error: Optional[str] = None


@router.post("/fetch", response_model=ScrapeResponse)
async def fetch_page(req: ScrapeRequest):
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

    except Exception as e:
        return ScrapeResponse(success=False, error=str(e))


@router.get("/test")
async def test_scrapling():
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
