"""
组合管理 API
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..services.portfolio_service import (
    add_transaction,
    get_positions,
    get_transactions,
    get_portfolio_summary,
    get_performance_history,
    get_risk_exposure,
    delete_transaction,
)

router = APIRouter()


class AddTransactionRequest(BaseModel):
    code: str
    name: str
    type: str  # buy / sell / dividend / split
    shares: float
    price: float
    fee: float = 0
    market: str = "A"
    reason: str = ""
    decision_id: str = ""


@router.post("/transaction")
async def api_add_transaction(req: AddTransactionRequest):
    """添加交易记录"""
    if not req.code.strip():
        raise HTTPException(400, "股票代码不能为空")
    if req.type not in ("buy", "sell", "dividend", "split"):
        raise HTTPException(400, "交易类型必须是 buy/sell/dividend/split")
    if req.type in ("buy", "sell") and (req.shares <= 0 or req.price <= 0):
        raise HTTPException(400, "买入/卖出的股数和价格必须大于0")

    txn = add_transaction(
        code=req.code.strip(),
        name=req.name.strip(),
        txn_type=req.type,
        shares=req.shares,
        price=req.price,
        fee=req.fee,
        market=req.market,
        reason=req.reason,
        decision_id=req.decision_id,
    )
    return txn.model_dump()


@router.get("/positions")
async def api_get_positions():
    """获取当前持仓（含实时价格）"""
    positions = get_positions()
    return {
        "positions": [p.model_dump() for p in positions],
        "count": len(positions),
    }


@router.get("/transactions")
async def api_get_transactions(code: str = None, limit: int = 100):
    """获取交易记录"""
    txns = get_transactions(code=code, limit=limit)
    return {
        "transactions": [t.model_dump() for t in txns],
        "count": len(txns),
    }


@router.get("/summary")
async def api_get_summary():
    """组合概览"""
    summary = get_portfolio_summary()
    return summary.model_dump()


@router.get("/performance")
async def api_get_performance():
    """收益曲线"""
    points = get_performance_history()
    return {
        "points": [p.model_dump() for p in points],
    }


@router.get("/risk")
async def api_get_risk():
    """风险暴露"""
    risk = get_risk_exposure()
    return risk.model_dump()


@router.delete("/transaction/{txn_id}")
async def api_delete_transaction(txn_id: str):
    """删除交易记录"""
    ok = delete_transaction(txn_id)
    if not ok:
        raise HTTPException(404, "交易记录不存在")
    return {"success": True, "message": "交易记录已删除"}
