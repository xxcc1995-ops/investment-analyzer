"""
Expand stock universe: fetch financial data for 100+ quality stocks
Uses DataService which works reliably
"""
import json
import os
import sys
import time
sys.path.insert(0, os.path.dirname(__file__))

from app.services.data_service import DataService

# 100+ quality A-share stocks
TARGET_STOCKS = [
    # 银行
    '601398', '601939', '600036', '601166', '600000', '000001', '601288', '601328', '600016', '601818',
    # 白酒
    '600519', '000858', '000568', '002304', '600809', '000799',
    # 家电
    '000333', '000651', '600690', '002032', '002508',
    # 医药
    '600276', '300760', '603259', '000538', '600436', '002007',
    # 新能源
    '300750', '002594', '601012', '002459', '300274',
    # 化工
    '600309', '002601', '600989', '000830', '600426',
    # 电力/能源
    '600900', '601088', '600585', '601857', '600028',
    # 机械
    '600031', '000338', '002008', '601100', '300124',
    # 保险/证券
    '601318', '601601', '600030', '601688', '300059',
    # 食品/消费
    '603288', '600887', '002714', '300498', '600298',
    # 科技/电子
    '002415', '002475', '603501', '002371', '300782',
    # 地产/建筑
    '000002', '600048', '001979', '600019', '601668',
    # 交通运输
    '601006', '600009', '601111', '002352', '601888',
    # 其他
    '000725', '601899', '002466', '600050', '002230',
    # 补充优质股
    '600585', '601012', '002001', '002007', '600196',
    '000963', '002044', '600660', '002271', '601225',
    '000423', '002311', '600521', '002241', '000661',
]

# Remove duplicates
TARGET_STOCKS = list(dict.fromkeys(TARGET_STOCKS))

cache_path = os.path.join(os.path.dirname(__file__), 'data', 'financial_cache_v2.json')

def fetch_all():
    """Fetch financial data for all target stocks"""
    # Load existing cache
    existing = {}
    if os.path.exists(cache_path):
        with open(cache_path, 'r', encoding='utf-8') as f:
            existing = json.load(f)

    result = dict(existing)
    total = len(TARGET_STOCKS)
    success = 0
    failed = []

    for i, code in enumerate(TARGET_STOCKS):
        if code in result and result[code].get('roe'):
            success += 1
            continue

        print(f'[{i+1}/{total}] {code}...', end=' ')
        try:
            data = DataService.get_financial_indicators(code)
            reports = data.get('reports', [])
            if reports:
                latest = reports[0]
                result[code] = {
                    'roe': latest.get('roe'),
                    'eps': latest.get('eps'),
                    'bps': latest.get('bps'),
                    'revenue_growth': latest.get('revenue_growth'),
                    'profit_growth': latest.get('profit_growth'),
                    'gross_margin': latest.get('gross_margin'),
                    'net_margin': latest.get('net_margin'),
                    'debt_ratio': latest.get('debt_ratio'),
                    'report_date': latest.get('date'),
                }
                print(f'OK ROE={latest.get("roe")} EPS={latest.get("eps")}')
                success += 1
            else:
                print('No data')
                failed.append(code)
        except Exception as e:
            print(f'Error: {e}')
            failed.append(code)
        time.sleep(0.3)

    # Save
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f'\nDone: {success}/{total} success, {len(failed)} failed')
    print(f'Failed: {failed}')
    return result

if __name__ == '__main__':
    fetch_all()
