# -*- coding: utf-8 -*-
"""数据源实测：万得全A/沪深300 PE-TTM、中美国债收益率（只读探测，不修改项目数据）"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import traceback
import akshare as ak
print("akshare", ak.__version__)

def probe(name, fn):
    print(f"\n{'='*70}\n[探测] {name}")
    try:
        df = fn()
        print(f"OK 行数={len(df)} 列={list(df.columns)}")
        print("头部:\n", df.head(2).to_string())
        print("尾部:\n", df.tail(2).to_string())
    except Exception as e:
        print(f"FAIL {type(e).__name__}: {e}")
        traceback.print_exc(limit=1)

# 1. 沪深300 官方估值（中证指数公司）
probe("中证指数官网 沪深300 估值 (stock_zh_index_value_csindex 000300)",
      lambda: ak.stock_zh_index_value_csindex(symbol="000300"))

# 2. 韭圈儿 funddb 万得全A 市盈率
probe("韭圈儿 funddb 万得全A 市盈率 (index_value_hist_funddb)",
      lambda: ak.index_value_hist_funddb(symbol="万得全A", indicator="市盈率"))

# 3. 韭圈儿 funddb 指数清单（看有哪些指数可用）
probe("韭圈儿 funddb 指数清单 (index_value_name_funddb)",
      lambda: ak.index_value_name_funddb())

# 4. 中美国债收益率（英为财情，与用户 Excel 口径同源）
probe("中美国债收益率 (bond_zh_us_rate)",
      lambda: ak.bond_zh_us_rate(start_date="20260101"))

# 5. 中国国债收益率官方（中国债券信息网 chinabond）
probe("中国国债收益率曲线官方 (bond_china_yield)",
      lambda: ak.bond_china_yield(start_date="20260801", end_date="20260815"))

# 6. 万得全A 收盘价：新浪指数日线（881001 是否可得）
probe("万得全A 收盘价 新浪 (stock_zh_index_daily sh881001)",
      lambda: ak.stock_zh_index_daily(symbol="sh881001"))

# 7. 沪深300 收盘价：新浪指数日线
probe("沪深300 收盘价 新浪 (stock_zh_index_daily sh000300)",
      lambda: ak.stock_zh_index_daily(symbol="sh000300"))
