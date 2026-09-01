# -*- coding: utf-8 -*-
"""数据源实测第四轮：乐咕全A口径确认、数据API模式、乐咕指数PE函数实测、multpl/QQQ结构"""
import sys, io, re, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import requests
import akshare as ak

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# 1. 乐咕链接清单完整版（找 wind/全A 相关）
r = requests.get("https://legulegu.com/stockdata/hs300-ttm-lyr", headers=H, timeout=15)
links = sorted(set(re.findall(r'/stockdata/[a-z0-9\-]+', r.text)))
print("=== 全A/万得/中证全指 相关链接 ===")
for l in links:
    if any(k in l for k in ("all", "wind", "a-", "zz", "csi")):
        print(" ", l)
apis = sorted(set(re.findall(r'["\'](/api/[^"\']+)["\']', r.text)))
print("=== 页面调用的 API ===")
for a in apis:
    print(" ", a)

# 2. 全A TTM 页面口径确认
print("\n=== /stockdata/a-ttm-lyr 页面口径 ===")
r2 = requests.get("https://legulegu.com/stockdata/a-ttm-lyr", headers=H, timeout=15)
print("HTTP", r2.status_code)
text = re.sub(r'<[^>]+>', ' ', r2.text)
text = re.sub(r'\s+', ' ', text)
i = text.find("市盈率")
print("页面文本片段:", text[max(0, i-200):i+400])

# 3. stock_index_pe_lg 实测（沪深300 长历史）
print("\n=== stock_index_pe_lg('沪深300') ===")
try:
    df = ak.stock_index_pe_lg(symbol="沪深300")
    print(f"OK {len(df)} 行, 列={list(df.columns)}")
    print(df.head(2).to_string())
    print(df.tail(2).to_string())
except Exception as e:
    print("FAIL", type(e).__name__, e)

# 4. multpl 表格结构
print("\n=== multpl 表格结构 ===")
r3 = requests.get("https://www.multpl.com/s-p-500-pe-ratio/table/by-month", headers=H, timeout=15)
i3 = r3.text.find("<table")
print(r3.text[i3:i3+600] if i3 >= 0 else "无 table")

# 5. stockanalysis QQQ PE
print("\n=== stockanalysis /etf/qqq ===")
r4 = requests.get("https://stockanalysis.com/etf/qqq/", headers=H, timeout=15)
print("HTTP", r4.status_code)
m = re.findall(r'PE Ratio.{0,200}', r4.text, re.S)
print("PE Ratio 上下文:", m[:1])

# 6. 乐咕 中国10年国债页面（备选国债源）
r5 = requests.get("https://legulegu.com/stockdata/china-10-year-bond-yield", headers=H, timeout=15)
print("\n=== 乐咕中国10年国债页面 HTTP", r5.status_code, "===")
