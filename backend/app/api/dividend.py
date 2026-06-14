"""攒股收息筛选 API 路由"""

from fastapi import APIRouter, Query
from app.services.dividend_service import get_dividend_screener
from app.services.data_service import DataService

router = APIRouter()


@router.get("/screener")
def dividend_screener(master: str = Query("combined", description="筛选标准: combined/wangwen/sanhuyi")):
    """
    基于王文和散户乙投资思想的股票筛选

    参数:
    - master: 筛选标准 (combined/wangwen/sanhuyi)
    """
    return get_dividend_screener(master)


@router.get("/history/{stock_code}")
def dividend_history(stock_code: str):
    """
    获取个股历史分红明细（含年度汇总、CAGR、连续分红年数）

    用于攒股收息计算器和详细分析
    """
    return DataService.get_dividend_history(stock_code)
