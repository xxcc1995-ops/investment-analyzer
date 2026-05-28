from fastapi import APIRouter, HTTPException
from app.services.data_service import DataService

router = APIRouter()
data_service = DataService()


@router.get("/search")
def search_stock(keyword: str):
    """搜索股票"""
    results = data_service.search_stock(keyword)
    return {"results": results}


@router.get("/{stock_code}/basic")
def get_stock_basic(stock_code: str):
    """获取股票基本信息和实时行情"""
    data = data_service.get_stock_basic(stock_code)
    if "error" in data:
        raise HTTPException(status_code=400, detail=data["error"])
    return data


@router.get("/{stock_code}/financials")
def get_stock_financials(stock_code: str):
    """获取财务指标"""
    data = data_service.get_financial_indicators(stock_code)
    if "error" in data:
        raise HTTPException(status_code=400, detail=data["error"])
    return data


@router.get("/{stock_code}/valuation-history")
def get_valuation_history(stock_code: str):
    """获取历史PE/PB估值数据"""
    return data_service.get_valuation_history(stock_code)


@router.get("/{stock_code}/dividend-history")
def get_dividend_history(stock_code: str):
    """获取历史分红明细"""
    return data_service.get_dividend_history(stock_code)
