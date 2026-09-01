"""相对估值法 API — 同行业 A股/港股 跨市场相对估值对比

端点：
  GET /api/relative-valuation/sectors   返回 A/H 市场可选行业清单
  GET /api/relative-valuation/stocks?market=A   返回可搜索标的清单（代码/名称/行业）
  GET /api/relative-valuation/compare?market=A&sector=银行   组内同业对比
  GET /api/relative-valuation/stock?market=A&code=600519&sector=白酒   单只 vs 同业
"""

from fastapi import APIRouter, Query

from app.services import relative_valuation_service as rv

router = APIRouter()


@router.get("/sectors")
def get_sectors():
    """返回 A/H 市场可对比的行业清单。"""
    return rv.get_sectors()


@router.get("/stocks")
def get_stocks(market: str = Query(..., description="市场: A 或 HK")):
    """返回该市场可搜索的标的清单（代码/名称/行业），供前端「选一只标的」自动完成。"""
    return rv.get_stock_universe(market)


@router.get("/compare")
def compare_sector(
    market: str = Query(..., description="市场: A 或 HK"),
    sector: str = Query(..., description="行业 key（来自 /sectors）"),
):
    """同一行业内各股票的 PE/PB/PS/股息率 组内分位、相对中位数偏离与综合吸引力评级。"""
    return rv.compare_sector(market, sector)


@router.get("/stock")
def compare_stock(
    market: str = Query(..., description="市场: A 或 HK"),
    code: str = Query(..., description="股票代码"),
    sector: str = Query(None, description="行业 key；不填则自动定位"),
):
    """单只股票与其所在行业已知同业的相对估值对比。"""
    return rv.compare_stock(market, code, sector)
