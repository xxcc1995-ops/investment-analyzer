"""
期货数据API
"""
from fastapi import APIRouter
from app.services.akshare_service import akshare_service

router = APIRouter()


@router.get("/list")
async def get_futures_list():
    """获取期货实时行情列表"""
    data = akshare_service.get_futures_list()
    return {"futures": data or [], "count": len(data) if data else 0}


@router.get("/commodities")
async def get_commodities():
    """获取关键商品快照"""
    data = akshare_service.get_commodity_snapshot()
    return {"commodities": data}


@router.get("/history/{symbol}")
async def get_futures_history(symbol: str):
    """获取期货历史行情"""
    data = akshare_service.get_futures_hist(symbol)
    return {"symbol": symbol, "data": data or [], "count": len(data) if data else 0}


@router.get("/industry")
async def get_industry_rank():
    """获取行业板块排名"""
    data = akshare_service.get_industry_rank()
    return {"industries": data or [], "count": len(data) if data else 0}


@router.get("/fund-flow")
async def get_sector_fund_flow():
    """获取行业资金流向"""
    data = akshare_service.get_sector_fund_flow()
    return {"sectors": data or [], "count": len(data) if data else 0}


@router.get("/north-flow")
async def get_north_flow():
    """获取北向资金数据"""
    data = akshare_service.get_north_flow()
    return {"flows": data or [], "count": len(data) if data else 0}
