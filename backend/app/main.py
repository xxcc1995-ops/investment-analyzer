from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import stocks, funds, cb, scraper, bonds, index_valuation, openbb, dividend, cigar_butt, cross_analysis, value_investing, reit, crypto, macro, futures, jc_screener, polymarket, export_champions, options, grid, xueqiu, national_team

app = FastAPI(title="新源的Invest工具", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stocks.router, prefix="/api/stocks", tags=["stocks"])
app.include_router(funds.router, prefix="/api/funds", tags=["funds"])
app.include_router(cb.router, prefix="/api/cb", tags=["cb"])
app.include_router(scraper.router, prefix="/api/scraper", tags=["scraper"])
app.include_router(bonds.router, prefix="/api/bonds", tags=["bonds"])
app.include_router(index_valuation.router, prefix="/api/index-valuation", tags=["index-valuation"])
app.include_router(openbb.router, prefix="/api/openbb", tags=["openbb"])
app.include_router(dividend.router, prefix="/api/dividend", tags=["dividend"])
app.include_router(cigar_butt.router, prefix="/api/cigar-butt", tags=["cigar-butt"])
app.include_router(cross_analysis.router, prefix="/api/cross-analysis", tags=["cross-analysis"])
app.include_router(value_investing.router, prefix="/api/value-investing", tags=["value-investing"])
app.include_router(reit.router, prefix="/api/reit", tags=["reit"])
app.include_router(crypto.router, prefix="/api/crypto", tags=["crypto"])
app.include_router(macro.router, prefix="/api/macro", tags=["macro"])
app.include_router(futures.router, prefix="/api/futures", tags=["futures"])
app.include_router(jc_screener.router, prefix="/api/jc", tags=["金渐成体系"])
app.include_router(polymarket.router, prefix="/api/polymarket", tags=["Polymarket"])
app.include_router(export_champions.router, prefix="/api/export-champions", tags=["出口冠军"])
app.include_router(options.router, prefix="/api/options", tags=["期权轮动"])
app.include_router(grid.router, prefix="/api/grid", tags=["网格交易"])
app.include_router(xueqiu.router, prefix="/api/xueqiu", tags=["雪球大V"])
app.include_router(national_team.router, prefix="/api/national-team", tags=["国家队监控"])


@app.on_event("startup")
async def restore_jisilu_login():
    """启动时自动恢复集思录登录态"""
    from app.services.fund_service import FundService
    FundService.restore_login()


@app.get("/")
async def root():
    return {"message": "新源的Invest工具 API"}
