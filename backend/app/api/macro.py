"""
宏观数据API
"""
from fastapi import APIRouter
from app.services.akshare_service import akshare_service

router = APIRouter()


@router.get("/overview")
async def get_macro_overview():
    """获取宏观数据概览（最新值 + 近期序列）"""
    result = {}

    gdp = akshare_service.get_gdp_data()
    if gdp:
        result["gdp"] = {"latest": gdp[0], "series": gdp[:20]}

    cpi = akshare_service.get_cpi_data()
    if cpi:
        result["cpi"] = {"latest": cpi[0], "series": cpi[:24]}

    pmi = akshare_service.get_pmi_data()
    if pmi:
        result["pmi"] = {"latest": pmi[0], "series": pmi[:24]}

    money = akshare_service.get_money_supply()
    if money:
        result["money_supply"] = {"latest": money[0], "series": money[:24]}

    lpr = akshare_service.get_lpr_data()
    if lpr:
        result["lpr"] = {"latest": lpr[-1], "series": lpr[-20:]}  # LPR取最新（列表末尾）

    shrz = akshare_service.get_social_financing()
    if shrz:
        result["social_financing"] = {"latest": shrz[-1], "series": shrz[-24:]}

    return result


@router.get("/china")
async def get_china_macro():
    """获取中国宏观数据全量"""
    return {
        "gdp": akshare_service.get_gdp_data(),
        "cpi": akshare_service.get_cpi_data(),
        "pmi": akshare_service.get_pmi_data(),
        "money_supply": akshare_service.get_money_supply(),
        "social_financing": akshare_service.get_social_financing(),
        "lpr": akshare_service.get_lpr_data(),
    }


@router.get("/us")
async def get_us_macro():
    """获取美国宏观数据"""
    return {
        "cpi": akshare_service.get_us_cpi(),
        "unemployment": akshare_service.get_us_unemployment(),
    }
