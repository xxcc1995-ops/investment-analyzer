from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import stocks, funds, cb, scraper, bonds, index_valuation, openbb, dividend, cigar_butt, cross_analysis, value_investing, reit, crypto, macro, futures

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


@app.get("/")
async def root():
    return {"message": "新源的Invest工具 API"}
