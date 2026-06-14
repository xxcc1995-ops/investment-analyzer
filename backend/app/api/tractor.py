# -*- coding: utf-8 -*-
"""拖拉机套利自动化API (V2 - 机构级)

提供拖拉机账户管理、策略扫描、资金分配、风控、损益追踪的REST接口。

端点：
- GET  /status                系统状态（AutoIt安装、客户端、账户、交易时段）
- GET  /accounts              账户列表
- GET  /accounts/balances     账户资金信息
- POST /accounts              添加账户
- PUT  /accounts/{id}         更新账户
- DELETE /accounts/{id}       删除账户
- POST /sync                  同步账户配置到AutoIt脚本
- POST /run                   执行操作（带风控预检）
- GET  /operation-status      当前操作状态
- GET  /log                   操作日志
- GET  /strategy/overview     策略总览（扫描+分配+风控一体化）
- GET  /strategy/scan         扫描套利机会
- POST /strategy/allocation   计算资金分配方案
- GET  /risk/settings         获取风控设置
- PUT  /risk/settings         更新风控设置
- POST /risk/check            风控预检
- GET  /history               操作历史
- GET  /history/pnl           损益汇总
- POST /history/{id}/pnl      回填操作损益
"""

import logging
from fastapi import APIRouter, HTTPException, Body, Query
from typing import Optional

from tractor.tractor_service import get_tractor_service
from tractor.tractor_config import (
    list_accounts,
    add_account,
    remove_account,
    update_account,
    sync_to_autoit,
    load_accounts,
)
from tractor.tractor_models import (
    AccountCreateRequest,
    AccountUpdateRequest,
    ScanRequest,
    RiskSettings,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ==================== 系统状态 ====================

@router.get("/status")
def get_status():
    """获取系统状态"""
    try:
        svc = get_tractor_service()
        return svc.get_system_status()
    except Exception as e:
        logger.error(f"获取系统状态失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 账户管理 ====================

@router.get("/accounts")
def get_accounts():
    """获取所有账户列表"""
    try:
        return {"accounts": list_accounts()}
    except Exception as e:
        logger.error(f"获取账户列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/accounts/balances")
def get_account_balances():
    """获取账户资金信息"""
    try:
        svc = get_tractor_service()
        balances = svc.get_account_balances()
        return {"accounts": [b.model_dump() for b in balances]}
    except Exception as e:
        logger.error(f"获取账户资金信息失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/accounts")
def create_account(
    account_id: str = Body(..., embed=True),
    password: str = Body(..., embed=True),
    broker_type: str = Body("huabao", embed=True),
    name: str = Body("", embed=True),
):
    """添加新账户"""
    try:
        # 参数校验
        if not account_id or not password:
            raise HTTPException(status_code=400, detail="资金账号和密码不能为空")
        if broker_type not in ("huabao", "yinhe"):
            raise HTTPException(status_code=400, detail="券商类型必须为 huabao 或 yinhe")

        account = add_account(account_id, password, broker_type, name)
        sync_to_autoit()
        return {"success": True, "account": account}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"添加账户失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/accounts/{account_id}")
def modify_account(
    account_id: str,
    password: Optional[str] = Body(None, embed=True),
    broker_type: Optional[str] = Body(None, embed=True),
    name: Optional[str] = Body(None, embed=True),
    enabled: Optional[bool] = Body(None, embed=True),
    available_cash: Optional[float] = Body(None, embed=True),
):
    """更新账户信息"""
    try:
        kwargs = {}
        if password is not None:
            kwargs["password"] = password
        if broker_type is not None:
            if broker_type not in ("huabao", "yinhe"):
                raise HTTPException(status_code=400, detail="券商类型必须为 huabao 或 yinhe")
            kwargs["broker_type"] = broker_type
        if name is not None:
            kwargs["name"] = name
        if enabled is not None:
            kwargs["enabled"] = enabled

        account = update_account(account_id, **kwargs)
        if not account:
            raise HTTPException(status_code=404, detail=f"账户 {account_id} 不存在")

        # 更新资金缓存
        if available_cash is not None:
            svc = get_tractor_service()
            svc.update_account_balance(account_id, {"available_cash": available_cash})

        sync_to_autoit()
        return {"success": True, "account": account}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新账户失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/accounts/{account_id}")
def delete_account(account_id: str):
    """删除账户"""
    try:
        success = remove_account(account_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"账户 {account_id} 不存在")

        sync_to_autoit()
        return {"success": True, "message": f"账户 {account_id} 已删除"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除账户失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync")
def sync_config():
    """同步账户配置到AutoIt脚本"""
    try:
        success = sync_to_autoit()
        return {"success": success, "message": "配置已同步" if success else "同步失败"}
    except Exception as e:
        logger.error(f"同步配置失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 操作执行 ====================

@router.post("/run")
def run_operation(
    operation: str = Body(..., embed=True),
    fund_code: str = Body("162411", embed=True),
    sell_price: str = Body("", embed=True),
    sell_quantity: str = Body("", embed=True),
    account_ids: list = Body(None, embed=True),
    premium_pct: float = Body(0, embed=True),
    fund_name: str = Body("", embed=True),
    apply_status: str = Body("", embed=True),
    turnover: float = Body(0, embed=True),
    est_nav: float = Body(0, embed=True),
    fund_price: float = Body(0, embed=True),
):
    """执行拖拉机操作（带风控预检）

    Args:
        operation: 操作类型
        fund_code: 基金代码（默认162411华宝油气）
        sell_price: 卖出价格（卖出时需要）
        sell_quantity: 卖出数量（卖出时需要）
        account_ids: 指定账户列表（None表示全部）
        premium_pct: 当前溢价率%（用于风控）
        fund_name: 基金名称
        apply_status: 申购状态
        turnover: 成交额(万)
        est_nav: 估算净值
        fund_price: 场内价格
    """
    try:
        svc = get_tractor_service()

        extra_context = {
            "premium_pct": premium_pct,
            "fund_name": fund_name,
            "apply_status": apply_status,
            "turnover": turnover,
            "est_nav": est_nav,
            "fund_price": fund_price,
        }

        result = svc.run_operation(
            operation=operation,
            fund_code=fund_code,
            sell_price=sell_price,
            sell_quantity=sell_quantity,
            account_ids=account_ids,
            extra_context=extra_context,
        )
        return result
    except Exception as e:
        logger.error(f"执行操作失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/operation-status")
def get_operation_status():
    """获取当前操作状态"""
    try:
        svc = get_tractor_service()
        return svc.get_status()
    except Exception as e:
        logger.error(f"获取操作状态失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/log")
def get_operation_log(tail: int = 50):
    """获取操作日志"""
    try:
        svc = get_tractor_service()
        return {"log": svc.get_log(tail)}
    except Exception as e:
        logger.error(f"获取日志失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 策略引擎 ====================

@router.get("/strategy/overview")
def get_strategy_overview(
    min_premium: float = Query(2.0, description="最低溢价率绝对值%"),
    min_amount: float = Query(1000, description="最低成交额(万元)"),
    direction: str = Query("all", description="方向: all/溢价/折价"),
):
    """获取策略总览

    整合扫描、分配、风控，输出一站式策略建议。
    包含：套利机会列表、每基金推荐操作、资金分配方案、风控状态。
    """
    try:
        svc = get_tractor_service()
        overview = svc.get_strategy_overview(min_premium, min_amount, direction)
        return {"success": True, "data": overview.model_dump()}
    except Exception as e:
        logger.error(f"获取策略总览失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategy/scan")
def scan_opportunities(
    min_premium: float = Query(2.0, description="最低溢价率绝对值%"),
    min_amount: float = Query(1000, description="最低成交额(万元)"),
    direction: str = Query("all", description="方向: all/溢价/折价"),
):
    """扫描LOF套利机会"""
    try:
        svc = get_tractor_service()
        opportunities = svc.scan_opportunities(min_premium, min_amount, direction)
        return {
            "success": True,
            "data": {
                "opportunities": [o.model_dump() for o in opportunities],
                "total": len(opportunities),
            },
        }
    except Exception as e:
        logger.error(f"扫描套利机会失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/strategy/allocation")
def calculate_allocation(
    fund_code: str = Body(..., embed=True),
    fund_name: str = Body("", embed=True),
    direction: str = Body("溢价", embed=True),
    premium_pct: float = Body(0, embed=True),
    apply_limit: str = Body("", embed=True),
    apply_status: str = Body("", embed=True),
    est_nav: float = Body(0, embed=True),
    fund_price: float = Body(0, embed=True),
    account_ids: list = Body(None, embed=True),
):
    """计算资金分配方案

    基于账户余额、限购金额、风控参数，计算每个账户的最优分配。
    """
    try:
        svc = get_tractor_service()
        plan = svc.calculate_allocation(
            fund_code=fund_code,
            fund_name=fund_name,
            direction=direction,
            premium_pct=premium_pct,
            apply_limit_str=apply_limit,
            apply_status=apply_status,
            est_nav=est_nav,
            fund_price=fund_price,
            account_ids=account_ids,
        )
        return {"success": True, "data": plan.model_dump()}
    except Exception as e:
        logger.error(f"计算资金分配失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 风险控制 ====================

@router.get("/risk/settings")
def get_risk_settings():
    """获取风控设置"""
    try:
        svc = get_tractor_service()
        return {"success": True, "data": svc.get_risk_settings()}
    except Exception as e:
        logger.error(f"获取风控设置失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/risk/settings")
def update_risk_settings(
    min_premium_pct: Optional[float] = Body(None, embed=True),
    max_single_amount: Optional[float] = Body(None, embed=True),
    max_total_amount: Optional[float] = Body(None, embed=True),
    min_cash_reserve: Optional[float] = Body(None, embed=True),
    max_daily_operations: Optional[int] = Body(None, embed=True),
    require_trading_hours: Optional[bool] = Body(None, embed=True),
    block_low_liquidity: Optional[bool] = Body(None, embed=True),
    min_turnover: Optional[float] = Body(None, embed=True),
):
    """更新风控设置"""
    try:
        svc = get_tractor_service()
        kwargs = {}
        for k, v in {
            "min_premium_pct": min_premium_pct,
            "max_single_amount": max_single_amount,
            "max_total_amount": max_total_amount,
            "min_cash_reserve": min_cash_reserve,
            "max_daily_operations": max_daily_operations,
            "require_trading_hours": require_trading_hours,
            "block_low_liquidity": block_low_liquidity,
            "min_turnover": min_turnover,
        }.items():
            if v is not None:
                kwargs[k] = v

        settings = svc.update_risk_settings(**kwargs)
        return {"success": True, "data": settings}
    except Exception as e:
        logger.error(f"更新风控设置失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/risk/check")
def check_risk(
    operation: str = Body(..., embed=True),
    fund_code: str = Body("", embed=True),
    premium_pct: float = Body(0, embed=True),
    amount: float = Body(0, embed=True),
    apply_status: str = Body("", embed=True),
    turnover: float = Body(0, embed=True),
    account_ids: list = Body(None, embed=True),
):
    """风控预检

    在执行操作前检查所有风控条件。
    """
    try:
        svc = get_tractor_service()
        result = svc.check_risk(
            operation=operation,
            fund_code=fund_code,
            premium_pct=premium_pct,
            amount=amount,
            apply_status=apply_status,
            turnover=turnover,
            account_ids=account_ids,
        )
        return {"success": True, "data": result.model_dump()}
    except Exception as e:
        logger.error(f"风控检查失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 操作历史 ====================

@router.get("/history")
def get_operation_history(
    limit: int = Query(50, ge=1, le=500),
    fund_code: str = Query("", description="按基金代码筛选"),
    operation: str = Query("", description="按操作类型筛选"),
):
    """获取操作历史"""
    try:
        svc = get_tractor_service()
        history = svc.get_operation_history(limit, fund_code, operation)
        return {
            "success": True,
            "data": {
                "records": history,
                "total": len(history),
            },
        }
    except Exception as e:
        logger.error(f"获取操作历史失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/pnl")
def get_pnl_summary(days: int = Query(30, ge=0, description="统计天数，0=全部")):
    """获取损益汇总"""
    try:
        svc = get_tractor_service()
        summary = svc.get_pnl_summary(days)
        return {"success": True, "data": summary.model_dump()}
    except Exception as e:
        logger.error(f"获取损益汇总失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/history/{operation_id}/pnl")
def update_operation_pnl(
    operation_id: str,
    realized_pnl: float = Body(..., embed=True),
    exit_price: float = Body(0, embed=True),
):
    """回填操作损益

    在卖出/赎回完成后，回填实际成交价格和已实现损益。
    """
    try:
        svc = get_tractor_service()
        success = svc.update_operation_pnl(operation_id, realized_pnl, exit_price)
        if not success:
            raise HTTPException(status_code=404, detail=f"操作记录 {operation_id} 不存在")
        return {"success": True, "message": "损益已更新"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新操作损益失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
