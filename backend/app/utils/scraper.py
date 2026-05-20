"""
Web Scraping 工具模块 - 基于 Scrapling

提供多种爬取方式：
1. Fetcher - 快速 HTTP 请求（可伪装浏览器指纹）
2. StealthyFetcher - 隐身模式，可绕过 Cloudflare 等反爬
3. DynamicFetcher - 完整浏览器自动化（Playwright/Chrome）

使用示例：
    from app.utils.scraper import scrape, scrape_stealthy, scrape_dynamic

    # 简单请求
    page = scrape("https://example.com")
    titles = page.css("h1::text").getall()

    # 隐身模式（绕过 Cloudflare）
    page = scrape_stealthy("https://protected-site.com")

    # 完整浏览器（处理 JS 渲染）
    page = scrape_dynamic("https://spa-site.com")
"""

import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


def scrape(url: str, **kwargs) -> Any:
    """快速 HTTP 请求，支持浏览器指纹伪装

    Args:
        url: 目标 URL
        **kwargs: 传递给 Fetcher.get() 的参数
            - impersonate: 伪装浏览器 ('chrome', 'firefox', 等)
            - stealthy_headers: 使用隐身请求头
            - timeout: 超时时间

    Returns:
        Scrapling Response 对象，支持 .css(), .xpath(), .find_all() 等方法
    """
    from scrapling.fetchers import Fetcher
    try:
        page = Fetcher.get(url, **kwargs)
        return page
    except Exception as e:
        logger.error(f"Scrape failed for {url}: {e}")
        raise


def scrape_stealthy(url: str, headless: bool = True, **kwargs) -> Any:
    """隐身模式爬取，可绕过 Cloudflare Turnstile

    Args:
        url: 目标 URL
        headless: 是否无头模式
        **kwargs: 传递给 StealthyFetcher.fetch() 的参数
            - solve_cloudflare: 自动解决 Cloudflare 验证
            - network_idle: 等待网络空闲
            - google_search: 允许 Google 搜索

    Returns:
        Scrapling Response 对象
    """
    from scrapling.fetchers import StealthyFetcher
    try:
        page = StealthyFetcher.fetch(url, headless=headless, **kwargs)
        return page
    except Exception as e:
        logger.error(f"Stealthy scrape failed for {url}: {e}")
        raise


def scrape_dynamic(url: str, headless: bool = True, **kwargs) -> Any:
    """完整浏览器爬取，处理 JS 渲染的页面

    Args:
        url: 目标 URL
        headless: 是否无头模式
        **kwargs: 传递给 DynamicFetcher.fetch() 的参数
            - disable_resources: 禁用图片等资源加载
            - network_idle: 等待网络空闲

    Returns:
        Scrapling Response 对象
    """
    from scrapling.fetchers import DynamicFetcher
    try:
        page = DynamicFetcher.fetch(url, headless=headless, **kwargs)
        return page
    except Exception as e:
        logger.error(f"Dynamic scrape failed for {url}: {e}")
        raise


def extract_text(page: Any, selector: str) -> List[str]:
    """从页面提取文本列表

    Args:
        page: Scrapling Response 对象
        selector: CSS 选择器

    Returns:
        文本列表
    """
    return page.css(f"{selector}::text").getall()


def extract_attr(page: Any, selector: str, attr: str) -> List[str]:
    """从页面提取属性列表

    Args:
        page: Scrapling Response 对象
        selector: CSS 选择器
        attr: 属性名 (如 'href', 'src')

    Returns:
        属性值列表
    """
    return page.css(f"{selector}::attr({attr})").getall()


def extract_table(page: Any, table_selector: str) -> List[Dict[str, str]]:
    """提取 HTML 表格为字典列表

    Args:
        page: Scrapling Response 对象
        table_selector: 表格的 CSS 选择器

    Returns:
        字典列表，每行一个字典
    """
    tables = page.css(table_selector)
    if not tables:
        return []

    result = []
    table = tables[0]

    # 获取表头
    headers = []
    header_row = table.css("thead tr") or table.css("tr:first-child")
    if header_row:
        for th in header_row[0].css("th"):
            headers.append(th.text.strip())

    # 获取数据行
    rows = table.css("tbody tr") or table.css("tr")[1:]
    for row in rows:
        cells = row.css("td")
        if cells:
            if headers:
                row_data = {}
                for i, cell in enumerate(cells):
                    key = headers[i] if i < len(headers) else f"col_{i}"
                    row_data[key] = cell.text.strip()
                result.append(row_data)
            else:
                result.append({f"col_{i}": cell.text.strip() for i, cell in enumerate(cells)})

    return result
