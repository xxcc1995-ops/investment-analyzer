from fastapi import APIRouter, HTTPException, Depends
from app.services.data_service import DataService
from app.services.multi_source_quote import multi_source_service
from app.deps import get_data_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/search")
def search_stock(keyword: str, data_service: DataService = Depends(get_data_service)):
    """搜索股票"""
    results = data_service.search_stock(keyword)
    return {"results": results}


@router.get("/data-source-status")
def get_data_source_status():
    """获取数据源状态"""
    return multi_source_service.get_source_status()


@router.post("/data-source-reconnect")
def reconnect_data_sources():
    """重新连接所有数据源"""
    multi_source_service.reconnect_all()
    return {"message": "正在重新连接数据源...", "status": multi_source_service.get_source_status()}


@router.get("/{stock_code}/basic")
def get_stock_basic(stock_code: str, data_service: DataService = Depends(get_data_service)):
    """获取股票基本信息和实时行情"""
    data = data_service.get_stock_basic(stock_code)
    if "error" in data:
        raise HTTPException(status_code=400, detail=data["error"])
    return data


@router.get("/{stock_code}/financials")
def get_stock_financials(stock_code: str, data_service: DataService = Depends(get_data_service)):
    """获取财务指标"""
    data = data_service.get_financial_indicators(stock_code)
    if "error" in data:
        raise HTTPException(status_code=400, detail=data["error"])
    return data


@router.get("/{stock_code}/fragility")
def get_fragility(stock_code: str):
    """商业模式脆弱性/反脆弱性分析"""
    from app.services.fragility_service import analyze_fragility
    result = analyze_fragility(stock_code)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/{stock_code}/valuation-history")
def get_valuation_history(stock_code: str, data_service: DataService = Depends(get_data_service)):
    """获取历史PE/PB估值数据"""
    return data_service.get_valuation_history(stock_code)


@router.get("/{stock_code}/dividend-history")
def get_dividend_history(stock_code: str, data_service: DataService = Depends(get_data_service)):
    """获取历史分红明细"""
    return data_service.get_dividend_history(stock_code)


@router.get("/{stock_code}/financial-statements")
def get_financial_statements(stock_code: str, data_service: DataService = Depends(get_data_service)):
    """获取三大报表（利润表/资产负债表/现金流量表）"""
    data = data_service.get_financial_statements(stock_code)
    if "error" in data:
        raise HTTPException(status_code=400, detail=data["error"])
    return data


@router.get("/{stock_code}/derived-metrics")
def get_derived_metrics(stock_code: str, data_service: DataService = Depends(get_data_service)):
    """获取派生指标 - EV/EBITDA、FCF Yield、杜邦分解等

    综合市值数据和三大报表计算机构级指标
    """
    from app.core.cache import get_cache, set_cache, TTL_DAILY

    cache_key = f"derived_metrics_{stock_code}"
    cached = get_cache(cache_key, TTL_DAILY)
    if cached:
        return cached

    try:
        # 获取市值数据
        basic = data_service.get_stock_basic(stock_code)
        if "error" in basic:
            return {"error": basic["error"]}

        market_cap = basic.get("market_cap")  # 亿元
        price = basic.get("price", 0)

        # 获取三大报表
        stmts = data_service.get_financial_statements(stock_code)
        income = stmts.get("income", [])
        balance = stmts.get("balance", [])
        cashflow = stmts.get("cashflow", [])

        result = {"code": stock_code, "fetch_time": basic.get("fetch_time")}

        if market_cap and market_cap > 0:
            market_cap_yuan = market_cap * 1e8  # 转为元

            # --- EV/EBITDA ---
            if balance and income:
                latest_bal = balance[0]
                latest_inc = income[0]

                total_debt = (latest_bal.get("short_term_borrowing") or 0) + (latest_bal.get("long_term_borrowing") or 0)
                cash = latest_bal.get("monetary_funds") or 0
                ev = market_cap_yuan + total_debt - cash

                # EBITDA = 营业利润 + 折旧摊销
                # 优先使用现金流量表中的实际折旧摊销数据
                operate_profit = latest_inc.get("operate_profit")
                total_assets = latest_bal.get("total_assets") or 0
                da = None
                if cashflow:
                    da = cashflow[0].get("depreciation_amortization")
                if not da and total_assets > 0:
                    da = total_assets * 0.03  # fallback: 约3%总资产近似
                # operate_profit可能为None，da可能存在；需要安全加法
                op = operate_profit or 0
                da_val = da or 0
                ebitda = op + da_val if (op or da_val) else None

                if ebitda and ebitda > 0:
                    ev_ebitda = round(ev / ebitda, 2)
                    result["ev"] = round(ev / 1e8, 2)  # 亿元
                    result["ebitda"] = round(ebitda / 1e8, 2)
                    result["ev_ebitda"] = ev_ebitda
                    # 合理区间标记
                    if ev_ebitda < 8:
                        result["ev_ebitda_level"] = "低估"
                    elif ev_ebitda < 15:
                        result["ev_ebitda_level"] = "合理"
                    elif ev_ebitda < 25:
                        result["ev_ebitda_level"] = "偏高"
                    else:
                        result["ev_ebitda_level"] = "高估"

            # --- FCF Yield ---
            if cashflow:
                latest_cf = cashflow[0]
                fcf = latest_cf.get("free_cashflow")
                if fcf and fcf > 0:
                    fcf_yield = round(fcf / market_cap_yuan * 100, 2)
                    result["free_cashflow"] = round(fcf / 1e8, 2)
                    result["fcf_yield"] = fcf_yield
                    if fcf_yield > 8:
                        result["fcf_yield_level"] = "高"
                    elif fcf_yield > 4:
                        result["fcf_yield_level"] = "适中"
                    else:
                        result["fcf_yield_level"] = "低"

            # --- 杜邦分析分解 ---
            if income and balance:
                latest_inc = income[0]
                latest_bal = balance[0]
                net_profit = latest_inc.get("parent_net_profit")
                revenue = latest_inc.get("total_revenue")
                total_assets_val = latest_bal.get("total_assets")
                equity = latest_bal.get("total_equity")

                if all(v and v > 0 for v in [net_profit, revenue, total_assets_val, equity]):
                    net_margin = net_profit / revenue
                    asset_turnover = revenue / total_assets_val
                    equity_multiplier = total_assets_val / equity
                    roe_calc = net_margin * asset_turnover * equity_multiplier

                    result["dupont"] = {
                        "net_margin": round(net_margin * 100, 2),
                        "asset_turnover": round(asset_turnover, 3),
                        "equity_multiplier": round(equity_multiplier, 2),
                        "roe": round(roe_calc * 100, 2),
                    }

        set_cache(cache_key, result)
        return result

    except Exception as e:
        logger.error(f"get_derived_metrics failed for {stock_code}: {e}")
        return {"code": stock_code, "error": f"计算派生指标失败: {str(e)}"}


@router.get("/{stock_code}/financial-analysis")
def get_financial_analysis(stock_code: str, data_service: DataService = Depends(get_data_service)):
    """自动财务分析 - 基于三大报表数据生成投资分析报告"""
    from app.services.financial_analysis import analyze_financials
    from app.core.cache import get_cache, set_cache, TTL_DAILY

    cache_key = f"financial_analysis_{stock_code}"
    cached = get_cache(cache_key, TTL_DAILY)
    if cached:
        return cached

    # 获取三大报表数据
    data = data_service.get_financial_statements(stock_code)
    if "error" in data:
        raise HTTPException(status_code=400, detail=data["error"])

    # 分析
    result = analyze_financials(
        income=data.get("income", []),
        balance=data.get("balance", []),
        cashflow=data.get("cashflow", []),
    )
    result["code"] = stock_code

    set_cache(cache_key, result)
    return result
