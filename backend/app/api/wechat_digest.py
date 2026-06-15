"""
微信公众号日报 API 路由
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, Dict, Any
from app.services.wechat_digest_service import wechat_digest_service

router = APIRouter()


@router.get("/status")
async def get_status():
    return wechat_digest_service.get_login_status()

@router.post("/cookie")
async def set_cookie(body: Dict[str, str]):
    """设置 cookie（从浏览器 DevTools 复制的完整 cookie 字符串）"""
    cookie_str = body.get("cookie", "").strip()
    if not cookie_str:
        raise HTTPException(400, "cookie 不能为空")
    try:
        return wechat_digest_service.set_cookie(cookie_str)
    except ValueError as e:
        raise HTTPException(400, str(e))

@router.post("/cookie/direct")
async def set_cookie_direct(body: Dict[str, str]):
    """直接设置 vid 和 skey"""
    vid = body.get("vid", "").strip()
    skey = body.get("skey", "").strip()
    if not vid or not skey:
        raise HTTPException(400, "vid 和 skey 不能为空")
    try:
        return wechat_digest_service.set_cookie_direct(vid, skey)
    except Exception as e:
        raise HTTPException(500, str(e))

@router.post("/extract-cookie")
async def extract_cookie():
    """尝试从浏览器自动提取 cookie"""
    return wechat_digest_service.try_extract_cookie()

@router.post("/logout")
async def logout():
    wechat_digest_service.logout()
    return {"ok": True}


@router.get("/accounts")
async def get_accounts():
    try:
        return wechat_digest_service.get_accounts()
    except ValueError as e:
        raise HTTPException(401, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))

@router.post("/sync")
async def sync(body: Optional[Dict[str, Any]] = None):
    body = body or {}
    try:
        return wechat_digest_service.sync_articles(mp_id=body.get("mp_id"), limit=body.get("limit", 20))
    except ValueError as e:
        raise HTTPException(401, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/articles")
async def get_articles(days: Optional[int] = Query(None), mp_id: Optional[str] = Query(None)):
    return wechat_digest_service.get_articles(days=days, mp_id=mp_id)

@router.post("/articles/fetch-content")
async def fetch_content(body: Dict[str, str]):
    url = body.get("url", "").strip()
    if not url:
        raise HTTPException(400, "url 不能为空")
    return wechat_digest_service.extract_content(url)

@router.get("/digest")
async def get_digest(days: Optional[int] = Query(None)):
    return wechat_digest_service.generate_daily_digest(days=days)

@router.get("/config")
async def get_config():
    from app.services.wechat_digest_service import _load_config
    return _load_config()

@router.post("/config")
async def update_config(body: Dict[str, Any]):
    from app.services.wechat_digest_service import _load_config, _save_config
    config = _load_config()
    for k in ("syncDays", "maxArticlesPerAccount"):
        if k in body:
            config[k] = body[k]
    _save_config(config)
    return config
