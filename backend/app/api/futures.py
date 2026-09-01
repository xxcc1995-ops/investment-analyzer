"""
期货数据API - 期货洞察模块
包含：商品快照、COT持仓、基差分析、展期收益、库存仓单、商品指数
"""
from fastapi import APIRouter, Query
from typing import Optional
from app.core.validators import validate_stock_code
from app.services.akshare_service import akshare_service

router = APIRouter()


# ==================== 原有端点 ====================

@router.get("/list")
def get_futures_list():
    """获取期货实时行情列表"""
    data = akshare_service.get_futures_list()
    return {"futures": data or [], "count": len(data) if data else 0}


@router.get("/commodities")
def get_commodities():
    """获取关键商品快照"""
    data = akshare_service.get_commodity_snapshot()
    return {"commodities": data}


@router.get("/history/{symbol}")
def get_futures_history(symbol: str):
    """获取期货历史行情"""
    symbol = validate_stock_code(symbol)
    data = akshare_service.get_futures_hist(symbol)
    return {"symbol": symbol, "data": data or [], "count": len(data) if data else 0}


@router.get("/industry")
def get_industry_rank():
    """获取行业板块排名"""
    data = akshare_service.get_industry_rank()
    return {"industries": data or [], "count": len(data) if data else 0}


@router.get("/fund-flow")
def get_sector_fund_flow():
    """获取行业资金流向"""
    data = akshare_service.get_sector_fund_flow()
    return {"sectors": data or [], "count": len(data) if data else 0}


@router.get("/north-flow")
def get_north_flow():
    """获取北向资金数据"""
    data = akshare_service.get_north_flow()
    return {"flows": data or [], "count": len(data) if data else 0}


# ==================== 期货洞察新增端点 ====================

@router.get("/global-commodities")
def get_global_commodities():
    """获取全球商品分类数据（按类别分组）

    返回贵金属、基本金属、黑色系、能源化工、农产品五大类商品数据，
    每个类别包含价格、涨跌幅和驱动因素说明。
    """
    data = akshare_service.get_global_commodities()
    return {"categories": data or {}}


@router.get("/cot-ranking")
def get_cot_ranking(
    vars: Optional[str] = Query(None, description="品种代码，逗号分隔，如 AU,CU,RB"),
    date: Optional[str] = Query(None, description="日期，格式YYYYMMDD"),
):
    """获取COT持仓排名数据（多空对比）

    COT (Commitments of Traders) 是期货交易所发布的持仓报告，
    显示前5/10/20名多空持仓及变化。商业净多头增加通常是看涨信号。
    """
    vars_list = vars.split(',') if vars else None
    data = akshare_service.get_cot_ranking(vars_list=vars_list, date=date)
    return {"cot": data or [], "count": len(data) if data else 0}


@router.get("/basis")
def get_basis(
    vars: Optional[str] = Query(None, description="品种代码，逗号分隔，如 AU,CU,RB"),
):
    """获取基差分析数据（现货vs期货）

    基差 = 期货价格 - 现货价格
    升水(Contango)：期货>现货，通常表示供应充足
    贴水(Backwardation)：期货<现货，通常表示供应紧张
    """
    vars_list = vars.split(',') if vars else None
    data = akshare_service.get_basis_data(vars_list=vars_list)
    return {"basis": data or [], "count": len(data) if data else 0}


@router.get("/roll-yield")
def get_roll_yield(
    var: str = Query("AU", description="品种代码，如 AU"),
    start_day: Optional[str] = Query(None, description="开始日期，格式YYYYMMDD"),
    end_day: Optional[str] = Query(None, description="结束日期，格式YYYYMMDD"),
):
    """获取展期收益率数据

    展期收益率：持有近月合约到期后换仓到远月的年化收益/损失。
    正值表示贴水结构有利于多头持仓。
    """
    data = akshare_service.get_roll_yield(var=var, start_day=start_day, end_day=end_day)
    return {"var": var, "roll_yield": data or [], "count": len(data) if data else 0}


@router.get("/inventory")
def get_inventory(
    symbols: Optional[str] = Query(None, description="品种代码，逗号分隔，如 CU,AL,RB"),
):
    """获取商品库存数据

    库存变化是判断供需关系的重要指标。
    库存下降 + 贴水结构 → 可能出现供应紧张。
    """
    symbols_list = symbols.split(',') if symbols else None
    data = akshare_service.get_inventory_data(symbols=symbols_list)
    return {"inventory": data or {}}


@router.get("/commodity-indices")
def get_commodity_indices():
    """获取中证商品期货指数数据

    中证商品期货指数跟踪国内一篮子商品期货的表现，
    是衡量商品市场整体走势的重要基准。
    """
    data = akshare_service.get_commodity_indices()
    return {"indices": data or [], "count": len(data) if data else 0}


@router.get("/institutional-allocation")
def get_institutional_allocation():
    """获取机构配置参考模型

    基于桥水、Citadel等顶级机构和CTA基金的公开配置比例。
    展示典型的商品期货配置策略和比例。
    """
    data = akshare_service.get_institutional_allocation()
    return data


# ==================== 金融期货 + 期限结构 + 套利分析 ====================

@router.get("/financial-futures")
def get_financial_futures():
    """获取金融期货快照（股指期货+国债期货）

    股指期货(IF/IC/IH/IM): 与对应指数高度相关，可用于对冲或杠杆化暴露
    国债期货(T/TF/TS): 利率下行时价格上涨，久期越长弹性越大
    """
    data = akshare_service.get_financial_futures_snapshot()
    return {"categories": data or {}}


@router.get("/term-structure")
def get_term_structure(
    var: str = Query("AU", description="品种代码，如 AU/CU/RB"),
):
    """获取期限结构数据（近月到远月价格曲线）

    从同一品种不同到期月份合约的价格构建期限结构曲线。
    - 升水(Contango): 远月>近月，通常表示供应充足
    - 贴水(Backwardation): 近月>远月，通常表示供应紧张
    """
    data = akshare_service.get_term_structure(var=var)
    return {"term_structure": data}


@router.get("/spread-signals")
def get_spread_signals():
    """获取跨期套利信号检测

    检测以下信号:
    1. 极端价差: 年化价差超过阈值的品种
    2. 换月压力: 近月持仓量远高于远月
    3. 蝶式套利: 三合约间价差异常
    """
    data = akshare_service.get_spread_signals()
    return {"signals": data or [], "count": len(data) if data else 0}


@router.get("/oi-analysis")
def get_oi_analysis(
    vars: Optional[str] = Query(None, description="品种代码，逗号分隔，如 AU,CU,RB"),
):
    """获取持仓量-价格分析

    分析主力合约的持仓量和价格关系:
    - 价格上涨+持仓量高: 多方入场，看涨信号
    - 价格下跌+持仓量高: 空方入场，看跌信号
    - 价格涨+持仓量低: 空头回补反弹，信号弱
    - 价格跌+持仓量低: 多头平仓下跌，信号弱
    """
    vars_list = vars.split(',') if vars else None
    data = akshare_service.get_oi_price_analysis(vars_list=vars_list)
    return {"analysis": data or [], "count": len(data) if data else 0}
