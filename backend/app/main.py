from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import stocks

app = FastAPI(title="新源的Invest工具", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stocks.router, prefix="/api/stocks", tags=["stocks"])


@app.get("/")
async def root():
    return {"message": "新源的Invest工具 API"}
