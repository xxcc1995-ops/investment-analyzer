from fastapi import APIRouter, Query
from app.services.export_service import screen_export_champions, get_philosophy

router = APIRouter()


@router.get("/screener")
def screener(
    market: str = Query('all', description="市场: A/HK/all"),
    min_score: int = Query(0, description="最低分数"),
    min_dividend_yield: float = Query(1.5, description="最低股息率(%)"),
    top_n: int = Query(50, description="返回前N只"),
):
    return screen_export_champions(
        market=market,
        min_score=min_score,
        min_dividend_yield=min_dividend_yield,
        top_n=top_n,
    )


@router.get("/philosophy")
def philosophy():
    return get_philosophy()
