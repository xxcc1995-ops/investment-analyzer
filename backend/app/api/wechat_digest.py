"""
微信公众号日报 API 路由
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from typing import Optional, Dict, Any, List
from app.services.wechat_digest_service import wechat_digest_service

router = APIRouter()


# ==================== 登录 ====================

@router.post("/login/start")
async def login_start():
    try:
        return wechat_digest_service.login_start()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/login/qr/{uuid}")
async def login_qr(uuid: str):
    try:
        b64 = wechat_digest_service.login_qr_image(uuid)
        import base64
        return Response(content=base64.b64decode(b64), media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/login/check/{uuid}")
async def login_check(uuid: str):
    try:
        return wechat_digest_service.login_check(uuid)
    except Exception:
        return {"status": "error"}

@router.get("/status")
async def get_status():
    return wechat_digest_service.get_login_status()

@router.post("/logout")
async def logout():
    wechat_digest_service.logout()
    return {"ok": True}


# ==================== 公众号管理 ====================

@router.get("/accounts")
async def get_accounts():
    return wechat_digest_service.get_accounts()

@router.post("/accounts/add")
async def add_account(body: Dict[str, str]):
    name = body.get("name", "").strip()
    mp_id = body.get("mpId", "").strip()
    if not name or not mp_id:
        raise HTTPException(status_code=400, detail="名称和ID不能为空")
    try:
        return wechat_digest_service.add_account(name, mp_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/accounts/remove")
async def remove_account(body: Dict[str, str]):
    mp_id = body.get("mpId", "").strip()
    if not mp_id:
        raise HTTPException(status_code=400, detail="mpId不能为空")
    return wechat_digest_service.remove_account(mp_id)


# ==================== 文章管理 ====================

@router.post("/articles/add")
async def add_article(body: Dict[str, str]):
    """通过微信文章链接添加文章"""
    url = body.get("url", "").strip()
    mp_name = body.get("mpName", "")
    mp_id = body.get("mpId", "")
    if not url:
        raise HTTPException(status_code=400, detail="链接不能为空")
    try:
        return wechat_digest_service.add_article_by_url(url, mp_name=mp_name, mp_id=mp_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/articles/batch")
async def add_articles_batch(body: Dict[str, Any]):
    """批量添加文章"""
    urls = body.get("urls", [])
    mp_name = body.get("mpName", "")
    mp_id = body.get("mpId", "")
    if not urls:
        raise HTTPException(status_code=400, detail="链接列表不能为空")
    return wechat_digest_service.add_articles_batch(urls, mp_name=mp_name, mp_id=mp_id)

@router.get("/articles")
async def get_articles(
    days: Optional[int] = Query(None),
    mp_id: Optional[str] = Query(None),
):
    return wechat_digest_service.get_articles(days=days, mp_id=mp_id)


# ==================== 日报 ====================

@router.get("/digest")
async def get_digest(days: Optional[int] = Query(None)):
    return wechat_digest_service.generate_daily_digest(days=days)


# ==================== 配置 ====================

@router.get("/config")
async def get_config():
    from app.services.wechat_digest_service import _load_config
    return _load_config()

@router.post("/config")
async def update_config(body: Dict[str, Any]):
    from app.services.wechat_digest_service import _load_config, _save_config
    config = _load_config()
    allowed = {"syncDays", "maxArticlesPerAccount", "wereadApiBase"}
    for k, v in body.items():
        if k in allowed:
            config[k] = v
    _save_config(config)
    return config
