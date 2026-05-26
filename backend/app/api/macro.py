"""
宏观数据API - 使用ThreadPoolExecutor并行获取
"""
from fastapi import APIRouter
from app.services.akshare_service import akshare_service
from concurrent.futures import ThreadPoolExecutor, as_completed

router = APIRouter()


def _fetch_macro_data():
    """并行获取所有宏观数据"""
    tasks = {
        'gdp': akshare_service.get_gdp_data,
        'cpi': akshare_service.get_cpi_data,
        'pmi': akshare_service.get_pmi_data,
        'money_supply': akshare_service.get_money_supply,
        'lpr': akshare_service.get_lpr_data,
        'social_financing': akshare_service.get_social_financing,
        'consumer_confidence': akshare_service.get_consumer_confidence,
        'ppi': akshare_service.get_ppi_data,
        'retail_sales': akshare_service.get_retail_sales,
        'housing_price': akshare_service.get_housing_price,
        'unemployment': akshare_service.get_unemployment_rate,
    }

    results = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(fn): name for name, fn in tasks.items()}
        for f in as_completed(futures):
            name = futures[f]
            try:
                results[name] = f.result()
            except Exception:
                results[name] = None
    return results


@router.get("/overview")
def get_macro_overview():
    """获取宏观数据概览（最新值 + 近期序列）"""
    data = _fetch_macro_data()
    result = {}

    gdp = data.get('gdp')
    if gdp:
        result["gdp"] = {"latest": gdp[0], "series": gdp[:20]}

    cpi = data.get('cpi')
    if cpi:
        result["cpi"] = {"latest": cpi[0], "series": cpi[:24]}

    pmi = data.get('pmi')
    if pmi:
        result["pmi"] = {"latest": pmi[0], "series": pmi[:24]}

    money = data.get('money_supply')
    if money:
        result["money_supply"] = {"latest": money[0], "series": money[:24]}

    lpr = data.get('lpr')
    if lpr:
        result["lpr"] = {"latest": lpr[-1], "series": lpr[-20:]}

    shrz = data.get('social_financing')
    if shrz:
        result["social_financing"] = {"latest": shrz[-1], "series": shrz[-24:]}

    consumer_conf = data.get('consumer_confidence')
    if consumer_conf:
        result["consumer_confidence"] = {"latest": consumer_conf[0], "series": consumer_conf[:24]}

    ppi = data.get('ppi')
    if ppi:
        result["ppi"] = {"latest": ppi[0], "series": ppi[:24]}

    retail = data.get('retail_sales')
    if retail:
        result["retail_sales"] = {"latest": retail[0], "series": retail[:24]}

    housing = data.get('housing_price')
    if housing:
        result["housing_price"] = {"latest": housing[0], "series": housing[:24]}

    unemployment = data.get('unemployment')
    if unemployment:
        result["unemployment"] = {"latest": unemployment[0], "series": unemployment[:24]}

    return result


@router.get("/china")
def get_china_macro():
    """获取中国宏观数据全量"""
    data = _fetch_macro_data()
    return data


@router.get("/us")
def get_us_macro():
    """获取美国宏观数据"""
    with ThreadPoolExecutor(max_workers=2) as pool:
        cpi_f = pool.submit(akshare_service.get_us_cpi)
        unemp_f = pool.submit(akshare_service.get_us_unemployment)
        return {
            "cpi": cpi_f.result(),
            "unemployment": unemp_f.result(),
        }
