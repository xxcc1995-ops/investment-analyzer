"""Screen HK stocks for wheel strategy suitability."""
import math
import httpx
from datetime import datetime, timedelta

def fetch(code, years=2):
    end = datetime.now()
    start = end - timedelta(days=years*365+60)
    url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get'
    params = {'param': f'hk{code},day,{start.strftime("%Y-%m-%d")},{end.strftime("%Y-%m-%d")},{years*365+60},qfq'}
    r = httpx.get(url, params=params, timeout=15)
    data = r.json()
    if 'data' in data and f'hk{code}' in data['data']:
        klines = data['data'][f'hk{code}']
        raw = klines.get('qfqday') or klines.get('day') or []
        closes = [float(row[2]) for row in raw if len(row) >= 3]
        return closes
    return []

stocks = [
    ('00700', '腾讯控股'),
    ('00005', '汇丰控股'),
    ('00941', '中国移动'),
    ('00883', '中国海油'),
    ('00939', '建设银行'),
    ('01299', '友邦保险'),
    ('03988', '中国银行'),
    ('00388', '港交所'),
    ('02318', '中国平安'),
    ('00002', '中电控股'),
    ('00003', '中华煤气'),
    ('00016', '新鸿基地产'),
    ('01398', '工商银行'),
    ('03690', '美团'),
    ('09988', '阿里巴巴'),
    ('09618', '京东'),
    ('01038', '长江基建'),
    ('00006', '电能实业'),
    ('00012', '恒基地产'),
    ('00688', '中国海外发展'),
    ('02020', '安踏体育'),
    ('02382', '舜宇光学'),
]

print("=" * 90)
print("  HK Stock Wheel Strategy Screening")
print("  Criteria: sideways/range-bound, decent HV, quality name")
print("=" * 90)
print()
header = f"  {'Code':<8} {'Name':<12} {'Start':>8} {'End':>8} {'Chg%':>7} {'MaxUp':>7} {'MaxDn':>7} {'HV20':>6} {'Range':>7}"
print(header)
print("  " + "-" * 82)

results = []
for code, name in stocks:
    closes = fetch(code)
    if len(closes) < 60:
        continue
    start_p = closes[0]
    end_p = closes[-1]
    chg = (end_p - start_p) / start_p * 100
    max_p = max(closes)
    min_p = min(closes)
    max_gain = (max_p - start_p) / start_p * 100
    max_loss = (min_p - start_p) / start_p * 100
    recent = closes[-21:]
    lr = [math.log(recent[i]/recent[i-1]) for i in range(1, len(recent))]
    mean = sum(lr)/len(lr)
    var = sum((r-mean)**2 for r in lr)/(len(lr)-1)
    hv = math.sqrt(var) * math.sqrt(252) * 100
    range_pct = (max_p - min_p) / start_p * 100
    # Wheel score: prefer lower |chg|, higher range (oscillation), decent HV
    # Ideal: chg near 0%, high range, HV 20-40%
    chg_penalty = abs(chg) * 2  # penalize strong trends
    wheel_score = range_pct * 0.4 + hv * 0.3 - chg_penalty * 0.3
    results.append((wheel_score, code, name, start_p, end_p, chg, max_gain, max_loss, hv, range_pct))
    line = f"  {code:<8} {name:<12} {start_p:>8.1f} {end_p:>8.1f} {chg:>+6.1f}% {max_gain:>+6.1f}% {max_loss:>+6.1f}% {hv:>5.0f}% {range_pct:>6.1f}%"
    print(line)

print()
print("=" * 90)
print("  WHEEL STRATEGY RANKING (higher = better for wheel)")
print("  Score = Range*0.4 + HV*0.3 - |Trend|*0.2")
print("=" * 90)
results.sort(reverse=True)
print()
print(f"  {'Rank':<5} {'Code':<8} {'Name':<12} {'Score':>6} {'Trend':>7} {'Range':>7} {'HV':>6} {'Why'}")
print("  " + "-" * 78)
for rank, (score, code, name, sp, ep, chg, mg, ml, hv, rng) in enumerate(results, 1):
    if abs(chg) < 10:
        trend = "SIDEWAYS"
    elif abs(chg) < 25:
        trend = "MILD"
    else:
        trend = "TRENDING"
    reason = ""
    if rng > 40 and abs(chg) < 15:
        reason = "Great - high oscillation, low trend"
    elif rng > 30 and abs(chg) < 20:
        reason = "Good - decent oscillation"
    elif abs(chg) < 10:
        reason = "OK - very flat"
    elif abs(chg) > 40:
        reason = "Poor - strong trend, B&H better"
    else:
        reason = "Fair"
    print(f"  {rank:<5} {code:<8} {name:<12} {score:>6.1f} {chg:>+6.1f}% {rng:>6.1f}% {hv:>5.0f}% {reason}")
