"""
微信公众号日报 API 路由
提供登录、同步、文章查询、日报生成等接口
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from typing import Optional, Dict, Any
from app.services.wechat_digest_service import wechat_digest_service

router = APIRouter()


# ==================== 登录流程 ====================

@router.post("/login/start")
async def login_start():
    """发起微信读书登录，返回 uuid 和二维码链接"""
    try:
        result = wechat_digest_service.login_start()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"登录发起失败: {str(e)}")


@router.get("/login/qr/{uuid}")
async def login_qr(uuid: str):
    """获取二维码 PNG 图片"""
    try:
        b64 = wechat_digest_service.login_qr_image(uuid)
        import base64
        img_bytes = base64.b64decode(b64)
        return Response(content=img_bytes, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成二维码失败: {str(e)}")


@router.get("/login/check/{uuid}")
async def login_check(uuid: str):
    """轮询登录结果"""
    try:
        return wechat_digest_service.login_check(uuid)
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.get("/status")
async def get_status():
    """获取登录状态"""
    return wechat_digest_service.get_login_status()


@router.post("/logout")
async def logout():
    """退出登录"""
    wechat_digest_service.logout()
    return {"ok": True}


# ==================== 公众号管理 ====================

@router.get("/accounts")
async def get_accounts():
    """获取已关注公众号列表"""
    try:
        return wechat_digest_service.get_accounts()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取公众号列表失败: {str(e)}")


@router.post("/accounts/sync")
async def sync_accounts():
    """从微信读书同步公众号列表"""
    try:
        accounts = wechat_digest_service.sync_accounts()
        return {"accounts": accounts, "count": len(accounts)}
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"同步公众号列表失败: {str(e)}")


# ==================== 文章同步 ====================

@router.post("/sync")
async def sync_articles(body: Optional[Dict[str, Any]] = None):
    """同步文章（增量拉取最近 N 天）"""
    body = body or {}
    mp_id = body.get("mp_id")
    days = body.get("days")
    try:
        return wechat_digest_service.sync_articles(mp_id=mp_id, days=days)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"同步文章失败: {str(e)}")


# ==================== 文章查询 ====================

@router.get("/articles")
async def get_articles(
    days: Optional[int] = Query(None, description="获取最近几天的文章"),
    mp_id: Optional[str] = Query(None, description="指定公众号ID"),
):
    """获取文章列表"""
    try:
        return wechat_digest_service.get_articles(days=days, mp_id=mp_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取文章失败: {str(e)}")


# ==================== 日报生成 ====================

@router.get("/digest")
async def get_digest(
    days: Optional[int] = Query(None, description="获取最近几天的文章生成日报"),
):
    """生成/获取每日日报（含 AI 摘要）"""
    try:
        return wechat_digest_service.generate_daily_digest(days=days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成日报失败: {str(e)}")


# ==================== 配置管理 ====================

@router.get("/config")
async def get_config():
    """获取配置"""
    from app.services.wechat_digest_service import _load_config
    return _load_config()


@router.post("/config")
async def update_config(body: Dict[str, Any]):
    """更新配置"""
    from app.services.wechat_digest_service import _load_config, _save_config
    config = _load_config()
    # 只允许更新特定字段
    allowed = {"syncDays", "maxArticlesPerAccount", "retryMaxAttempts", "retryDelayMs", "wereadApiBase"}
    for k, v in body.items():
        if k in allowed:
            config[k] = v
    _save_config(config)
    return config
