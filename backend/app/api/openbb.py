"""OpenBB API 路由 - 美股/加密货币数据（使用直接Yahoo Finance API）"""

from fastapi import APIRouter, HTTPException
from typing import Optional, List, Dict
import requests
import logging
from datetime import datetime

router = APIRouter()
logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}


def _fetch_yahoo_chart(symbol: str, range: str = "1mo", interval: str = "1d") -> Dict:
    """直接从Yahoo Finance API获取行情数据"""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval={interval}&range={range}"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        else:
            logger.warning(f"Yahoo Finance返回{resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.warning(f"Yahoo Finance请求失败: {e}")
    return None


def _parse_chart_data(data: Dict) -> List[Dict]:
    """解析Yahoo Finance图表数据"""
    records = []
    if not data or "chart" not in data:
        return records

    result = data["chart"]["result"]
    if not result:
        return records

    chart = result[0]
    timestamps = chart.get("timestamp", [])
    quote = chart.get("indicators", {}).get("quote", [{}])[0]

    opens = quote.get("open", [])
    highs = quote.get("high", [])
    lows = quote.get("low", [])
    closes = quote.get("close", [])
    volumes = quote.get("volume", [])

    for i in range(len(timestamps)):
        ts = timestamps[i]
        date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        records.append({
            "date": date,
            "open": round(float(opens[i]), 2) if opens[i] else 0,
            "high": round(float(highs[i]), 2) if highs[i] else 0,
            "low": round(float(lows[i]), 2) if lows[i] else 0,
            "close": round(float(closes[i]), 2) if closes[i] else 0,
            "volume": int(volumes[i]) if volumes[i] else 0,
        })

    return records


@router.get("/equity/price/{symbol}")
def get_equity_price(symbol: str, range: str = "1mo"):
    """获取美股行情数据

    - symbol: 股票代码 (如 AAPL, MSFT, GOOGL)
    - range: 时间范围 (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max)
    """
    data = _fetch_yahoo_chart(symbol.upper(), range=range)
    if not data:
        raise HTTPException(status_code=404, detail=f"未找到{symbol}的数据")

    records = _parse_chart_data(data)
    if not records:
        raise HTTPException(status_code=404, detail=f"未找到{symbol}的数据")

    meta = data["chart"]["result"][0].get("meta", {})
    return {
        "symbol": symbol.upper(),
        "name": meta.get("longName", meta.get("shortName", symbol.upper())),
        "currency": meta.get("currency", "USD"),
        "data": records,
        "count": len(records),
    }


@router.get("/equity/quote/{symbol}")
def get_equity_quote(symbol: str):
    """获取美股实时报价"""
    data = _fetch_yahoo_chart(symbol.upper(), range="5d", interval="1d")
    if not data:
        raise HTTPException(status_code=404, detail=f"未找到{symbol}的数据")

    meta = data["chart"]["result"][0].get("meta", {})
    records = _parse_chart_data(data)

    current_price = meta.get("regularMarketPrice", 0)
    prev_close = meta.get("chartPreviousClose", 0)
    change = round(current_price - prev_close, 2) if prev_close else 0
    change_pct = round(change / prev_close * 100, 2) if prev_close else 0

    return {
        "symbol": symbol.upper(),
        "name": meta.get("longName", meta.get("shortName", symbol.upper())),
        "price": round(current_price, 2),
        "change": change,
        "change_pct": change_pct,
        "volume": meta.get("regularMarketVolume", 0),
        "market_cap": None,  # Yahoo Chart API不直接提供市值
        "pe_ratio": None,
        "fifty_two_week_high": meta.get("fiftyTwoWeekHigh"),
        "fifty_two_week_low": meta.get("fiftyTwoWeekLow"),
        "currency": meta.get("currency", "USD"),
    }


@router.get("/crypto/price/{symbol}")
def get_crypto_price(symbol: str, range: str = "1mo"):
    """获取加密货币行情

    - symbol: 加密货币代码 (如 BTC, ETH, SOL)
    - range: 时间范围 (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max)
    """
    # Yahoo Finance用 BTC-USD 格式
    ticker_symbol = f"{symbol.upper()}-USD"
    data = _fetch_yahoo_chart(ticker_symbol, range=range)
    if not data:
        raise HTTPException(status_code=404, detail=f"未找到{symbol}的数据")

    records = _parse_chart_data(data)
    if not records:
        raise HTTPException(status_code=404, detail=f"未找到{symbol}的数据")

    meta = data["chart"]["result"][0].get("meta", {})
    return {
        "symbol": symbol.upper(),
        "name": meta.get("longName", meta.get("shortName", symbol.upper())),
        "currency": meta.get("currency", "USD"),
        "data": records,
        "count": len(records),
    }


@router.get("/crypto/quote/{symbol}")
def get_crypto_quote(symbol: str):
    """获取加密货币实时报价"""
    ticker_symbol = f"{symbol.upper()}-USD"
    data = _fetch_yahoo_chart(ticker_symbol, range="5d", interval="1d")
    if not data:
        raise HTTPException(status_code=404, detail=f"未找到{symbol}的数据")

    meta = data["chart"]["result"][0].get("meta", {})
    current_price = meta.get("regularMarketPrice", 0)
    prev_close = meta.get("chartPreviousClose", 0)
    change = round(current_price - prev_close, 2) if prev_close else 0
    change_pct = round(change / prev_close * 100, 2) if prev_close else 0

    return {
        "symbol": symbol.upper(),
        "name": meta.get("longName", meta.get("shortName", symbol.upper())),
        "price": round(current_price, 2),
        "change": change,
        "change_pct": change_pct,
        "volume": meta.get("regularMarketVolume", 0),
        "currency": meta.get("currency", "USD"),
    }
