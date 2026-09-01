# -*- coding: utf-8 -*-
"""指数盈利与估值 API - 用户手工维护的标普500/万得全A/沪深300 盈利与估值周度数据
另含 hs300_auto：免费源自动重建版（乐咕收盘+PE-TTM / 英为财情国债），用于与手工 Wind 口径对比。"""
import logging

from fastapi import APIRouter, HTTPException

from app.services import index_earnings_service
from app.services import index_earnings_auto_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/list")
def get_index_list():
    """指数列表与元信息（数据区间、基准线、最新值等），含自动重建版"""
    indices = index_earnings_service.get_index_list()
    indices.append(index_earnings_auto_service.get_auto_meta())
    return {"indices": indices}


@router.get("/data/{code}")
def get_index_data(code: str):
    """单个指数完整数据：周度序列 + EPS周期 + 口径说明；hs300_auto 为自动重建版"""
    if index_earnings_auto_service.is_auto_code(code):
        try:
            return index_earnings_auto_service.get_payload()
        except Exception as e:
            logger.exception(f"[index-earnings] 自动管线构建失败: {code}")
            raise HTTPException(status_code=500, detail=f"自动数据构建失败: {e}")
    try:
        data = index_earnings_service.get_index_data(code)
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception(f"[index-earnings] 解析失败: {code}")
        raise HTTPException(status_code=500, detail=f"数据解析失败: {e}")
    if data is None:
        raise HTTPException(status_code=404, detail=f"未知指数代码: {code}（可选: sp500 / wind_all_a / hs300 / hs300_auto）")
    return data
