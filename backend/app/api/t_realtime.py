"""实时做T API + WebSocket 端点（腾讯控股 00700.HK）

REST 端点（按需拉取，供前端初始化展示）：
- GET  /quote/{code}        实时行情（含五档）
- GET  /minute/{code}       当日1分钟分时
- GET  /orderbook/{code}    五档买卖盘结构化
- GET  /5min/{code}         5分钟K线（支撑压力）
- GET  /config              监控参数
- POST /config              更新参数
- GET  /status              监控运行状态
- GET  /signal/{code}       单次信号分析（不入推送循环）

WebSocket 端点（实时推送）：
- WS   /ws/{code}           订阅实时做T信号推送

推送消息类型见 realtime_t_monitor 模块文档。
"""

import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional

from app.services.quote_sources.tencent_source import TencentSource
from app.services.realtime_t_monitor import (
    realtime_monitor,
    get_best_order_book,
    get_best_5min_kline,
)
from app.services.intraday_t_signal_service import (
    analyze_intraday_signal, DEFAULT_CONFIG as SIGNAL_DEFAULT_CONFIG,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# 模块级腾讯源实例（REST 按需拉取用）
_tencent = TencentSource()


def _ensure_connected():
    if not _tencent.is_connected():
        _tencent.connect()


@router.get("/quote/{code}")
def get_quote(code: str, market: str = Query("HK", description="市场")):
    """实时行情快照（含五档买卖盘）"""
    _ensure_connected()
    quote = _tencent.get_quote(code, market)
    if not quote:
        return {"error": f"获取 {code} 行情失败（可能非交易时段或数据源异常）", "code": code}
    return quote.to_dict()


@router.get("/minute/{code}")
def get_minute(code: str, market: str = Query("HK")):
    """当日1分钟分时线"""
    _ensure_connected()
    data = _tencent.get_minute_kline(code, market)
    if not data:
        return {"error": f"获取 {code} 分时数据为空（非交易时段或接口异常）", "code": code, "data": []}
    return {"code": code, "count": len(data), "data": data}


@router.get("/orderbook/{code}")
def get_orderbook(code: str, market: str = Query("HK")):
    """五档买卖盘结构化（含价差/失衡）

    优先富途 OpenAPI 真实五档（需本地 FutuOpenD + 港股LV2权限），
    不可用时落回腾讯（腾讯港股盘口量恒为0，source 字段会标明）。
    """
    _ensure_connected()
    ob = get_best_order_book(code, market)
    if not ob:
        return {"error": f"获取 {code} 盘口失败（富途未连接且腾讯源无数据）", "code": code}
    return ob


@router.get("/5min/{code}")
def get_5min(code: str, market: str = Query("HK"), count: int = Query(300, description="返回根数")):
    """5分钟K线（日内支撑压力计算用）"""
    _ensure_connected()
    data = get_best_5min_kline(code, market, count)
    if not data:
        return {"error": f"获取 {code} 5分钟K线为空（富途未连接且腾讯mkline接口已失效）", "code": code, "data": []}
    return {"code": code, "count": len(data), "data": data}


@router.get("/signal/{code}")
def get_signal(code: str, market: str = Query("HK")):
    """单次信号分析（不入推送循环，供前端主动查询）"""
    _ensure_connected()
    minute = _tencent.get_minute_kline(code, market)
    k5 = get_best_5min_kline(code, market, 300)
    ob = get_best_order_book(code, market)
    quote = _tencent.get_quote(code, market)

    if not quote:
        return {"error": f"获取 {code} 行情失败"}

    signal = analyze_intraday_signal(
        code=code,
        name=quote.name,
        minute_klines=minute,
        kline_5min=k5,
        order_book=ob,
        config=realtime_monitor.config.signal_config,
    )
    return {
        **signal.to_dict(),
        "quote": quote.to_dict(),
    }


@router.get("/config")
def get_config():
    """获取当前监控配置"""
    cfg = realtime_monitor.config
    return {
        "enabled": cfg.enabled,
        "monitor_interval_sec": cfg.monitor_interval_sec,
        "idle_interval_sec": cfg.idle_interval_sec,
        "signal_cooldown_sec": cfg.signal_cooldown_sec,
        "spread_threshold_pct": cfg.spread_threshold_pct,
        "stop_loss_pct": cfg.stop_loss_pct,
        "max_t_ratio_pct": cfg.max_t_ratio_pct,
        "signal_config": cfg.signal_config,
    }


@router.post("/config")
def update_config(
    enabled: Optional[bool] = Query(None),
    monitor_interval_sec: Optional[int] = Query(None, ge=2, le=60),
    signal_cooldown_sec: Optional[int] = Query(None, ge=0, le=3600),
    spread_threshold_pct: Optional[float] = Query(None, ge=0, le=5),
    stop_loss_pct: Optional[float] = Query(None, ge=0, le=20),
    max_t_ratio_pct: Optional[float] = Query(None, ge=0, le=100),
):
    """更新监控参数（传参即更新，未传保留原值）"""
    updates = {}
    if enabled is not None: updates["enabled"] = enabled
    if monitor_interval_sec is not None: updates["monitor_interval_sec"] = monitor_interval_sec
    if signal_cooldown_sec is not None: updates["signal_cooldown_sec"] = signal_cooldown_sec
    if spread_threshold_pct is not None: updates["spread_threshold_pct"] = spread_threshold_pct
    if stop_loss_pct is not None: updates["stop_loss_pct"] = stop_loss_pct
    if max_t_ratio_pct is not None: updates["max_t_ratio_pct"] = max_t_ratio_pct

    # 同步更新 signal_config 里的价差阈值
    if spread_threshold_pct is not None:
        updates["signal_config"] = {"spread_threshold_pct": spread_threshold_pct}

    if updates:
        realtime_monitor.update_config(**updates)

    return {"message": "配置已更新", "updated": list(updates.keys()), "current": get_config()}


@router.get("/status")
def get_status():
    """监控运行状态"""
    return realtime_monitor.get_status()


# ============================================================
# WebSocket 实时推送端点
# ============================================================

@router.websocket("/ws/{code}")
async def t_realtime_ws(ws: WebSocket, code: str):
    """实时做T信号 WebSocket 推送

    客户端连接：ws://host:8022/api/t-realtime/ws/00700
    推送消息类型：subscribed / quote / signal / risk / heartbeat
    """
    await ws.accept()
    await realtime_monitor.subscribe(code, ws)
    try:
        # 保持连接，接收客户端控制消息（如暂停/恢复）
        while True:
            msg = await ws.receive_text()
            # 可扩展：处理客户端指令（如 {"action":"pause"}）
            logger.debug(f"WS 收到 {code} 消息: {msg}")
    except WebSocketDisconnect:
        logger.info(f"WebSocket 断开 {code}")
    except Exception as e:
        logger.warning(f"WebSocket 异常 {code}: {e}")
    finally:
        await realtime_monitor.unsubscribe(code, ws)
