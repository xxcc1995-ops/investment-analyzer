from fastapi import APIRouter, HTTPException
from app.services.data_service import DataService

router = APIRouter()
data_service = DataService()


@router.get("/search")
async def search_stock(keyword: str):
    """搜索股票"""
    results = data_service.search_stock(keyword)
    return {"results": results}


@router.get("/{stock_code}/basic")
async def get_stock_basic(stock_code: str):
    """获取股票基本信息和实时行情"""
    data = data_service.get_stock_basic(stock_code)
    if "error" in data:
        raise HTTPException(status_code=400, detail=data["error"])
    return data


@router.get("/{stock_code}/financials")
async def get_stock_financials(stock_code: str):
    """获取财务指标"""
    data = data_service.get_financial_indicators(stock_code)
    if "error" in data:
        raise HTTPException(status_code=400, detail=data["error"])
    return data
