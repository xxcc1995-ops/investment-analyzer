"""DeFi收益率排行榜 - 基于DeFiLlama数据"""

import logging
import math
import time
from datetime import datetime
from enum import Enum
from typing import Optional

import requests
from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)

router = APIRouter()

# ========== 模块级缓存 ==========
# DeFiLlama Pools API 返回约20000+条记录，缓存30分钟避免频繁请求

CACHE_TTL_SECONDS = 30 * 60  # 30分钟
_HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}
_TIMEOUT = 30


class _Cache:
    """带TTL的简单缓存容器，使用单调时钟避免系统时间回拨问题。"""

    def __init__(self) -> None:
        self.data: Optional[list] = None
        self._ts: float = 0.0

    def is_valid(self) -> bool:
        return self.data is not None and (time.monotonic() - self._ts) < CACHE_TTL_SECONDS

    def set(self, data: list) -> None:
        self.data = data
        self._ts = time.monotonic()


_pools_cache = _Cache()
_protocols_cache = _Cache()


# ---------- 通用工具 ----------


def _safe_float(val, default: float = 0.0) -> float:
    """安全转换为 float，处理 None / NaN / Inf / 非数字。"""
    if val is None:
        return default
    try:
        v = float(val)
        return default if (math.isnan(v) or math.isinf(v)) else v
    except (ValueError, TypeError):
        return default


def _fetch_json(url: str) -> dict | list:
    """发起 GET 请求并返回 JSON，统一超时和头信息。"""
    r = requests.get(url, headers=_HTTP_HEADERS, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


def _build_pool_item(pool: dict, *, include_predictions: bool = True) -> dict:
    """从原始 pool dict 提取标准化的池信息字段。"""
    tvl = _safe_float(pool.get("tvlUsd"))
    apy = _safe_float(pool.get("apy"))

    item: dict = {
        "pool": pool.get("pool", ""),
        "project": pool.get("project", ""),
        "chain": pool.get("chain", ""),
        "symbol": pool.get("symbol", ""),
        "tvlUsd": round(tvl, 2),
        "apy": round(apy, 4),
        "apyBase": round(_safe_float(pool.get("apyBase")), 4),
        "apyReward": round(_safe_float(pool.get("apyReward")), 4),
        "stablecoin": pool.get("stablecoin", False),
        "ilRisk": pool.get("ilRisk", "no"),
    }

    if include_predictions:
        predictions = pool.get("predictions") or {}
        item["exposure"] = pool.get("exposure", "single")
        item["predictions"] = {
            "predictedClass": predictions.get("predictedClass", ""),
            "predictedProbability": _safe_float(predictions.get("predictedProbability")),
            "binnedConfidence": _safe_float(predictions.get("binnedConfidence")),
        }

    return item


def _build_protocol_item(p: dict) -> dict:
    """从原始 protocol dict 提取标准化的协议信息字段。"""
    return {
        "name": p.get("name", ""),
        "tvl": round(_safe_float(p.get("tvl")), 2),
        "chain": p.get("chain", "Multi-chain"),
        "chains": p.get("chains", []),
        "category": p.get("category", ""),
        "change_1d": round(_safe_float(p.get("change_1d")), 2),
        "change_7d": round(_safe_float(p.get("change_7d")), 2),
        "change_1m": round(_safe_float(p.get("change_1m")), 2),
    }


# ---------- 数据获取（带缓存）----------


def _fetch_pools() -> list:
    """获取DeFiLlama Pools数据（带缓存）。"""
    if _pools_cache.is_valid():
        return _pools_cache.data  # type: ignore[return-value]

    try:
        data = _fetch_json("https://yields.llama.fi/pools")

        if data.get("status") != "success":
            logger.warning("DeFiLlama Pools API返回异常: %s", data.get("status"))
            return _pools_cache.data or []

        pools = data.get("data", [])
        _pools_cache.set(pools)
        logger.info("DeFiLlama Pools数据已更新，共 %d 个池子", len(pools))
        return pools

    except Exception as e:
        logger.error("获取DeFiLlama Pools数据失败: %s", e)
        return _pools_cache.data or []


def _fetch_protocols() -> list:
    """获取DeFiLlama Protocols数据（带缓存）。"""
    if _protocols_cache.is_valid():
        return _protocols_cache.data  # type: ignore[return-value]

    try:
        protocols = _fetch_json("https://api.llama.fi/protocols")

        if not isinstance(protocols, list):
            logger.warning("DeFiLlama Protocols API返回格式异常")
            return _protocols_cache.data or []

        _protocols_cache.set(protocols)
        logger.info("DeFiLlama Protocols数据已更新，共 %d 个协议", len(protocols))
        return protocols

    except Exception as e:
        logger.error("获取DeFiLlama Protocols数据失败: %s", e)
        return _protocols_cache.data or []


# ---------- 排序枚举 ----------


class SortBy(str, Enum):
    tvl = "tvl"
    apy = "apy"
    project = "project"


# ---------- 路由 ----------


@router.get("/pools")
def get_pools(
    chain: Optional[str] = Query(None, description="按链筛选 (ETH, BSC, Arbitrum, Solana等)"),
    min_tvl: float = Query(1_000_000, ge=0, description="最低TVL过滤"),
    min_apy: float = Query(0, ge=0, description="最低APY过滤"),
    max_apy: float = Query(1000, gt=0, description="最高APY过滤（过滤异常高APY）"),
    stablecoin: Optional[str] = Query(None, description="true/false 筛选稳定币池"),
    sort_by: SortBy = Query(SortBy.tvl, description="排序字段: tvl/apy/project"),
    limit: int = Query(100, ge=1, le=500, description="返回数量"),
):
    """DeFi收益率池列表

    从DeFiLlama获取所有DeFi收益池数据，支持按链、TVL、APY等筛选和排序。
    """
    pools = _fetch_pools()

    if not pools:
        return {"error": "获取DeFiLlama数据失败，请稍后重试", "data": [], "total": 0}

    # 解析稳定币筛选为 bool | None
    stablecoin_flag: Optional[bool] = None
    if stablecoin is not None:
        stablecoin_flag = stablecoin.lower() == "true"

    # 筛选
    filtered: list[dict] = []
    chain_upper = chain.upper() if chain else None

    for pool in pools:
        tvl = _safe_float(pool.get("tvlUsd"))
        apy = _safe_float(pool.get("apy"))

        if tvl < min_tvl or apy < min_apy or apy > max_apy:
            continue

        if chain_upper and pool.get("chain", "").upper() != chain_upper:
            continue

        if stablecoin_flag is not None and pool.get("stablecoin", False) != stablecoin_flag:
            continue

        filtered.append(_build_pool_item(pool))

    # 排序
    sort_key_map = {
        SortBy.apy: lambda x: x["apy"],
        SortBy.project: lambda x: x["project"],
        SortBy.tvl: lambda x: x["tvlUsd"],
    }
    reverse = sort_by != SortBy.project  # project 按字母升序，其余降序
    filtered.sort(key=sort_key_map[sort_by], reverse=reverse)

    result = filtered[:limit]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return {
        "data": result,
        "total": len(filtered),
        "returned": len(result),
        "filters": {
            "chain": chain,
            "min_tvl": min_tvl,
            "min_apy": min_apy,
            "max_apy": max_apy,
            "stablecoin": stablecoin,
            "sort_by": sort_by.value,
        },
        "update_time": now,
    }


@router.get("/protocols")
def get_protocols():
    """协议TVL排行榜

    从DeFiLlama获取所有DeFi协议数据，返回按TVL降序排列的Top 50协议。
    """
    protocols = _fetch_protocols()

    if not protocols:
        return {"error": "获取DeFiLlama协议数据失败，请稍后重试", "data": [], "total": 0}

    result = [_build_protocol_item(p) for p in protocols if _safe_float(p.get("tvl")) > 0]
    result.sort(key=lambda x: x["tvl"], reverse=True)

    top50 = result[:50]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return {
        "data": top50,
        "total": len(result),
        "returned": len(top50),
        "update_time": now,
    }


@router.get("/chains")
def get_chains():
    """支持的链列表

    从Pools数据中提取所有唯一的chain值，返回排序后的链列表。
    """
    pools = _fetch_pools()

    if not pools:
        return {"error": "获取DeFiLlama数据失败，请稍后重试", "data": [], "total": 0}

    chains_list = sorted({pool.get("chain", "") for pool in pools if pool.get("chain")})
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return {
        "data": chains_list,
        "total": len(chains_list),
        "update_time": now,
    }


@router.get("/overview")
def get_overview():
    """DeFi概览统计

    返回总TVL、总池数、平均APY、链数量，以及Top 5高APY池和Top 5 TVL最大的协议。
    """
    pools = _fetch_pools()
    protocols = _fetch_protocols()

    if not pools:
        return {"error": "获取DeFiLlama数据失败，请稍后重试"}

    # ---- 池子统计 ----
    total_tvl = 0.0
    total_apy_sum = 0.0
    apy_count = 0
    chains_set: set[str] = set()
    high_apy_candidates: list[dict] = []

    for pool in pools:
        tvl = _safe_float(pool.get("tvlUsd"))
        apy = _safe_float(pool.get("apy"))
        chain = pool.get("chain", "")

        total_tvl += tvl
        if chain:
            chains_set.add(chain)

        if apy > 0:
            total_apy_sum += apy
            apy_count += 1

        if tvl > 1_000_000 and apy > 0:
            high_apy_candidates.append(_build_pool_item(pool, include_predictions=False))

    high_apy_candidates.sort(key=lambda x: x["apy"], reverse=True)

    # ---- 协议统计 ----
    top5_tvl_protocols: list[dict] = []
    if protocols:
        valid = [_build_protocol_item(p) for p in protocols if _safe_float(p.get("tvl")) > 0]
        valid.sort(key=lambda x: x["tvl"], reverse=True)
        top5_tvl_protocols = valid[:5]

    avg_apy = round(total_apy_sum / apy_count, 2) if apy_count > 0 else 0.0
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return {
        "summary": {
            "total_tvl": round(total_tvl, 2),
            "total_pools": len(pools),
            "avg_apy": avg_apy,
            "chain_count": len(chains_set),
        },
        "top5_high_apy": high_apy_candidates[:5],
        "top5_tvl_protocols": top5_tvl_protocols,
        "update_time": now,
    }
