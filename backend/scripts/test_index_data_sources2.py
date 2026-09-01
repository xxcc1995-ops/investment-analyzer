# -*- coding: utf-8 -*-
"""数据源实测第二轮：万得全A估值(乐咕/韭圈儿)、标普500(multpl/S&P官方)、纳指100(stockanalysis)"""
import sys, io, json, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import requests
import akshare as ak

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# 0. akshare 里与指数估值/乐咕/韭圈儿相关的函数名
attrs = [a for a in dir(ak) if any(k in a.lower() for k in ("funddb", "_lg", "index_value", "jiucai"))]
print("akshare 相关函数:", attrs)

def probe_url(name, url, check=None, timeout=15):
    print(f"\n{'='*70}\n[探测] {name}\n  {url}")
    try:
        r = requests.get(url, headers=H, timeout=timeout)
        print(f"  HTTP {r.status_code}, {len(r.content)} bytes")
        if r.status_code == 200 and check:
            check(r)
    except Exception as e:
        print(f"  FAIL {type(e).__name__}: {e}")

def check_legu(r):
    # 乐咕页面内嵌 JSON 数据检测
    m = re.findall(r'\[\["\d{4}-\d{2}-\d{2}"[^\]]{0,200}', r.text)
    print("  内嵌数据样例:", m[:1] if m else "未找到")
    for kw in ["万得全A", "ttm", "pe"]:
        print(f"  含关键词 {kw!r}:", kw in r.text)

def check_json_keys(r, n=3):
    try:
        d = r.json()
        s = json.dumps(d, ensure_ascii=False)
        print("  JSON 前300字符:", s[:300])
    except Exception:
        print("  非JSON，文本前200:", r.text[:200])

# 1. 乐咕乐股：万得全A / 沪深300 PE-TTM 页面
probe_url("乐咕 沪深300 PE-TTM 页面", "https://legulegu.com/stockdata/hs300-ttm-lyr", check_legu)
probe_url("乐咕 万得全A PE-TTM 页面(候选1)", "https://legulegu.com/stockdata/all-a-ttm-lyr", check_legu)
probe_url("乐咕 万得全A 页面(候选2)", "https://legulegu.com/stockdata/wind-all-a", check_legu)

# 2. 韭圈儿 API（指数估值列表，看有没有万得全A）
probe_url("韭圈儿 指数估值列表", "https://api.jiucaishuo.com/v2/guzhi/newcategory?type=1", check_json_keys)

# 3. multpl 标普500 PE 月度历史表
def check_multpl(r):
    rows = re.findall(r'<td>([A-Z][a-z]{2} \d{1,2}, \d{4})</td>\s*<td>([\d.]+)</td>', r.text)
    print(f"  解析到月度PE记录 {len(rows)} 条，最新3条: {rows[:3]}")
probe_url("multpl 标普500 PE 月度表", "https://www.multpl.com/s-p-500-pe-ratio/table/by-month", check_multpl)
probe_url("multpl 标普500 Earnings 月度表", "https://www.multpl.com/s-p-500-earnings/table/by-month", check_multpl)

# 4. S&P 官方 EPS 估算表（周更 Excel）
def check_xlsx(r):
    ct = r.headers.get("Content-Type", "")
    print(f"  Content-Type: {ct}; 前4字节: {r.content[:4]}")
probe_url("S&P官方 EPS估算表", "https://www.spglobal.com/spdji/en/documents/additional-material/sp-500-eps-est.xlsx", check_xlsx)

# 5. stockanalysis 纳指100
def check_ndx(r):
    m = re.findall(r'PE Ratio[^<]*</t[dh]>\s*<td[^>]*>([\d.]+)', r.text)
    print("  PE 字段:", m[:2] if m else "未匹配", "| 含 NDX:", "NDX" in r.text or "Nasdaq 100" in r.text)
probe_url("stockanalysis 纳指100指数页", "https://stockanalysis.com/quote/index/NDX/", check_ndx)

# 6. 腾讯行情试探 万得全A 881001（指数行情兜底）
probe_url("腾讯行情 881001", "https://qt.gtimg.cn/q=sh881001", lambda r: print("  返回:", r.text[:150]))
