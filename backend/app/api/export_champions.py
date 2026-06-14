from fastapi import APIRouter, Query
from app.services.export_service import (
    screen_export_champions,
    get_philosophy,
    get_exchange_rate_data,
    TARIFF_RISK_MATRIX,
    EXPORT_STOCKS,
)

router = APIRouter()


@router.get("/screener")
def screener(
    market: str = Query('all', description="市场: A/HK/all"),
    min_score: int = Query(0, description="最低分数"),
    min_dividend_yield: float = Query(1.5, description="最低股息率(%)"),
    top_n: int = Query(50, description="返回前N只"),
):
    return screen_export_champions(
        market=market,
        min_score=min_score,
        min_dividend_yield=min_dividend_yield,
        top_n=top_n,
    )


@router.get("/philosophy")
def philosophy():
    return get_philosophy()


@router.get("/exchange-rate")
def exchange_rate():
    """获取USD/CNY汇率数据及对出口企业的影响分析"""
    data = get_exchange_rate_data()
    if not data:
        return {"error": "汇率数据获取失败", "update_time": ""}
    return data


@router.get("/tariff-matrix")
def tariff_matrix():
    """获取行业关税/贸易政策风险矩阵"""
    return {
        'matrix': TARIFF_RISK_MATRIX,
        'update_time': '2025-06',
        'data_source': '基于2024-2025年公开贸易政策整理，需定期更新',
        'disclaimer': '关税政策变化频繁，本矩阵仅供参考，不构成投资建议',
    }


@router.get("/industry-summary")
def industry_summary():
    """获取出口冠军行业分布汇总"""
    industries = {}
    for code, info in EXPORT_STOCKS.items():
        ind = info['industry']
        if ind not in industries:
            industries[ind] = {
                'name': info['industry'],
                'sub_industries': set(),
                'companies': [],
                'avg_overseas_pct': [],
                'tariff_sensitivity': info.get('tariff_sensitivity', 'medium'),
                'main_export_markets': set(),
            }
        industries[ind]['companies'].append({'code': code, 'name': info['name']})
        industries[ind]['sub_industries'].add(info.get('sub_industry', ''))
        industries[ind]['avg_overseas_pct'].append(info.get('est_overseas_pct', 0))
        for m in info.get('main_export_markets', []):
            industries[ind]['main_export_markets'].add(m)

    # Convert sets to lists and compute averages
    result = {}
    for ind, data in industries.items():
        result[ind] = {
            'name': data['name'],
            'sub_industries': sorted(data['sub_industries']),
            'companies': data['companies'],
            'company_count': len(data['companies']),
            'avg_overseas_pct': round(sum(data['avg_overseas_pct']) / len(data['avg_overseas_pct']), 1),
            'tariff_sensitivity': data['tariff_sensitivity'],
            'main_export_markets': sorted(data['main_export_markets']),
            'tariff_risk': TARIFF_RISK_MATRIX.get(ind, {}),
        }

    return result
