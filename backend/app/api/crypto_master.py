"""
币圈大师 - 加密货币学习+实战API
从零到一的完整加密货币投资教育体系
"""
from fastapi import APIRouter, HTTPException
from app.services.crypto_master_service import CryptoMasterService

router = APIRouter()
svc = CryptoMasterService()


# ========== 市场数据 ==========

@router.get("/market-overview")
async def market_overview():
    """加密市场全景 - BTC/ETH主导率、总市值、恐惧贪婪指数"""
    return await svc.get_market_overview()


@router.get("/top-coins")
async def top_coins(limit: int = 50):
    """Top N 加密货币排行"""
    return await svc.get_top_coins(limit)


@router.get("/trending")
async def trending():
    """热门币种 + 涨幅榜 + 跌幅榜"""
    return await svc.get_trending()


@router.get("/stablecoins")
async def stablecoins():
    """稳定币市值监控 - 资金流入流出信号"""
    return await svc.get_stablecoin_monitor()


@router.get("/btc-dominance-history")
async def btc_dominance_history():
    """BTC主导率历史趋势"""
    return await svc.get_btc_dominance_history()


# ========== 链上数据 ==========

@router.get("/defi-tvl")
async def defi_tvl():
    """DeFi总锁仓量 + 各链分布"""
    return await svc.get_defi_tvl()


@router.get("/chain-comparison")
async def chain_comparison():
    """公链对比 - TVL、活跃地址、交易量"""
    return await svc.get_chain_comparison()


# ========== 知识体系 ==========

@router.get("/knowledge/{level}")
async def knowledge_by_level(level: str):
    """按级别获取知识: beginner / intermediate / advanced / master"""
    result = svc.get_knowledge(level)
    if not result:
        raise HTTPException(status_code=404, detail=f"未找到级别: {level}")
    return result


@router.get("/glossary")
async def glossary():
    """加密货币术语词典"""
    return svc.get_glossary()


@router.get("/learning-path")
async def learning_path():
    """学习路径 - 从小白到专家的完整路线图"""
    return svc.get_learning_path()


# ========== 策略工具 ==========

@router.get("/strategies")
async def strategies():
    """策略工具箱 - 各种实战策略"""
    return svc.get_strategies()


@router.post("/dca-simulator")
async def dca_simulator(payload: dict):
    """定投模拟器 - 计算DCA收益"""
    coin = payload.get("coin", "bitcoin")
    monthly_amount = payload.get("monthly_amount", 1000)
    months = payload.get("months", 12)
    return svc.simulate_dca(coin, monthly_amount, months)


@router.post("/position-calculator")
async def position_calculator(payload: dict):
    """仓位计算器 - Kelly公式 + 风险平价"""
    total_capital = payload.get("total_capital", 100000)
    risk_per_trade = payload.get("risk_per_trade", 0.02)
    win_rate = payload.get("win_rate", 0.55)
    avg_win = payload.get("avg_win", 0.15)
    avg_loss = payload.get("avg_loss", 0.08)
    return svc.calculate_position(total_capital, risk_per_trade, win_rate, avg_win, avg_loss)


# ========== 风险管理 ==========

@router.get("/risk-checklist")
async def risk_checklist():
    """投资前检查清单"""
    return svc.get_risk_checklist()


@router.get("/common-mistakes")
async def common_mistakes():
    """常见亏损原因 & 如何避免"""
    return svc.get_common_mistakes()


@router.get("/security-guide")
async def security_guide():
    """安全指南 - 钱包、交易所、防钓鱼"""
    return svc.get_security_guide()


# ========== DeFi指南 ==========

@router.get("/defi-guide")
async def defi_guide():
    """DeFi实操指南 - 从入门到精通"""
    return svc.get_defi_guide()


@router.get("/airdrop-guide")
async def airdrop_guide():
    """空投猎人指南"""
    return svc.get_airdrop_guide()


# ========== 实战检查清单 ==========

@router.get("/trading-checklist")
async def trading_checklist():
    """交易前/中/后完整检查清单"""
    return svc.get_trading_checklist()


@router.get("/master-wisdom")
async def master_wisdom():
    """大师语录 - 加密圈大佬的智慧"""
    return svc.get_master_wisdom()
