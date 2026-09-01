# -*- coding: utf-8 -*-
"""数据源实测第五轮（收尾）：韭圈儿POST接口、QQQ PE、同口径数值交叉验证"""
import sys, io, re, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import requests
import akshare as ak

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
     "Content-Type": "application/x-www-form-urlencoded"}

# 1. 韭圈儿指数估值 POST（老 funddb 接口模式）
print("=== 韭圈儿 POST 试探 ===")
for url, data in [
    ("https://api.jiucaishuo.com/v2/guzhi/newcategory", {"type": "1"}),
    ("https://api.jiucaishuo.com/v2/guzhi/newtubiaolines", {"gu_code": "881001.WI", "pe_category": "pe", "year": "-1"}),
]:
    try:
        r = requests.post(url, headers=H, data=data, timeout=15)
        print(f"POST {url} -> HTTP {r.status_code}, 前200字符: {r.text[:200]}")
    except Exception as e:
        print(f"POST {url} FAIL {type(e).__name__}: {e}")

# 2. QQQ PE（现有代码源）
print("\n=== stockanalysis /etf/qqq ===")
try:
    r = requests.get("https://stockanalysis.com/etf/qqq/", headers={"User-Agent": H["User-Agent"]}, timeout=15)
    print("HTTP", r.status_code)
    m = re.findall(r'PE Ratio.{0,150}', r.text, re.S)
    print("PE 上下文:", (m[:1] or ["未匹配"])[0][:150].replace("\n", " "))
except Exception as e:
    print("FAIL", type(e).__name__, e)

# 3. 口径交叉验证：乐咕沪深300 滚动市盈率 vs 用户Excel(Wind) 同一日期
print("\n=== 口径交叉验证（2026-07-31 周收盘） ===")
df = ak.stock_index_pe_lg(symbol="沪深300")
df["日期"] = df["日期"].astype(str)
row = df[df["日期"] == "2026-07-31"]
print("乐咕 2026-07-31:", row.to_string() if len(row) else "无该日数据")
# 用户 Excel 同日期（2026-08-02 周记录，对应周五 07-31 收盘）
import openpyxl
wb = openpyxl.load_workbook(r"D:/2005年~2026年沪深300盈利与估值/沪深300_2005-2026盈利与估值分析表.xlsx", data_only=True, read_only=True)
ws = wb["Sheet1"]
for r_ in ws.iter_rows(min_row=3, values_only=True):
    d = str(r_[0])[:10] if r_[0] else ""
    if d in ("2026-07-31", "2026-08-02"):
        print(f"用户Excel {d}: 收盘={r_[1]} PE-TTM={r_[2]} 隐含EPS={r_[14]}")
wb.close()

# 4. 乐咕沪深300 最早日期 vs 用户需求(2005-01起)
print("\n乐咕沪深300 最早日期:", df["日期"].min(), "最晚:", df["日期"].max(), "总行数:", len(df))
