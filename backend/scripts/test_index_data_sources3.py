# -*- coding: utf-8 -*-
"""数据源实测第三轮：akshare乐咕封装函数、乐咕指数清单、multpl表格结构、QQQ"""
import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import requests
import akshare as ak

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# 1. 函数签名
print("=== stock_index_pe_lg 签名 ===")
print(ak.stock_index_pe_lg.__doc__)
print("=== stock_market_pe_lg 签名 ===")
print(ak.stock_market_pe_lg.__doc__)

# 2. 乐咕沪深300页面里枚举所有 stockdata 指数链接（找万得全A）
r = requests.get("https://legulegu.com/stockdata/hs300-ttm-lyr", headers=H, timeout=15)
links = sorted(set(re.findall(r'/stockdata/[a-z0-9\-]+', r.text)))
print("\n=== 乐咕 stockdata 链接清单 ===")
for l in links:
    print(" ", l)

# 3. 实测 stock_index_pe_lg
print("\n=== stock_index_pe_lg('沪深300') ===")
try:
    df = ak.stock_index_pe_lg(symbol="沪深300")
    print(f"OK {len(df)} 行, 列={list(df.columns)}")
    print(df.head(2).to_string())
    print(df.tail(2).to_string())
except Exception as e:
    print("FAIL", type(e).__name__, e)

# 4. 实测 stock_market_pe_lg
print("\n=== stock_market_pe_lg ===")
try:
    df = ak.stock_market_pe_lg(symbol="上海市场")
    print(f"上海市场 OK {len(df)} 行, 列={list(df.columns)}")
    print(df.tail(2).to_string())
except Exception as e:
    print("上海市场 FAIL", type(e).__name__, e)

# 5. multpl 表格真实结构
print("\n=== multpl 表格结构 ===")
r = requests.get("https://www.multpl.com/s-p-500-pe-ratio/table/by-month", headers=H, timeout=15)
i = r.text.find("<table")
print(r.text[i:i+800] if i >= 0 else "无 table 标签")

# 6. stockanalysis QQQ
print("\n=== stockanalysis /etf/qqq ===")
r = requests.get("https://stockanalysis.com/etf/qqq/", headers=H, timeout=15)
print("HTTP", r.status_code, len(r.content), "bytes")
m = re.findall(r'PE Ratio.{0,300}', r.text, re.S)
print("PE Ratio 上下文:", m[:1])
