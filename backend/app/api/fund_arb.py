"""LOF基金套利统一API

合并自：fund_arb.py / fund_est.py / fund_est_detail.py / funds.py

三源融合数据流：
  1. 集思录 -> 基金列表、场内价格、净值、成交额、申购状态、限购
     (未登录时降级到东方财富+AKShare)
  2. 东方财富 -> 官方净值(T-1)、基金持仓数据
  3. 新浪 -> 底层资产实时价格(美股ETF/期货/港股指数)

EST计算：动态比率法（主），校准值法（验证）
排序：按扣除费用后的净收益从高到低
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from app.core.validators import validate_stock_code
from pydantic import BaseModel

from app.api.fund_config import FUND_CONFIG, get_fund_config, get_underlying_symbols
from app.api.fund_est_engine import calc_fund_est, get_official_est_batch
from app.api.fund_est import (
    LOF_FUND_CONFIG,
    MULTI_UNDERLYING_FUNDS,
    _calc_est_nav,
    _calc_multi_underlying_est_nav,
    _process_single_fund,
)
from app.api.fund_arb_engine import evaluate_arbitrage, _parse_fee_value
from app.api.fund_t_strategy import scan_t_opportunities, backtest_t_strategy
from app.api.fund_utils import (
    determine_market_status,
    get_est_accuracy_stats,
    get_fund_nav_batch,
    get_fund_nav_from_eastmoney,
    get_hkdcny_rate,
    get_sina_fund_code,
    get_sina_realtime,
    get_usdcny_rate,
    make_success_response,
    normalize_fund_code,
    parse_underlying_price,
    record_est_accuracy,
)
from app.services.fund_service import FundService
from app.core.cache import get_cache, set_cache
from app.core.utils import safe_float as _safe_float_orig


def _safe_float(val, default=0.0) -> float:
    """安全转换为float，None返回default"""
    result = _safe_float_orig(val)
    return result if result is not None else default

logger = logging.getLogger(__name__)

router = APIRouter()


def _merge_fund_data(jisilu_funds: list, est_results: dict) -> list:
    """合并集思录数据和EST计算结果

    Args:
        jisilu_funds: 集思录标准化后的基金列表
        est_results: EST计算结果 {fund_code: est_result}

    Returns:
        合并后的基金列表
    """
    merged = []

    for fund in jisilu_funds:
        fund_id = fund.get("fund_id", "")
        if not fund_id:
            continue

        # 安全获取数值字段
        # turnover=成交额(万元)。注意 amount 在集思录口径是"份额(万份)"，不可当成交额用
        price = _safe_float(fund.get("price"))
        turnover = _safe_float(fund.get("turnover"))
        if turnover <= 0:
            volume = _safe_float(fund.get("volume"))
            if volume > 0 and price > 0:
                turnover = round(volume * price, 2)  # 成交量(万份)×价格 → 万元
        nav_discount_rt = _safe_float(fund.get("nav_discount_rt"))
        increase_rt = _safe_float(fund.get("increase_rt"))

        # 查找对应的EST结果
        est = est_results.get(fund_id)
        if not est:
            # 没有EST配置的基金，使用集思录自带的数据
            merged.append({
                "fund_code": fund_id,
                "fund_name": fund.get("fund_nm", ""),
                "fund_price": price,
                "fund_change_pct": increase_rt,
                "official_nav": _safe_float(fund.get("fund_nav")),
                "official_nav_date": fund.get("nav_dt", ""),
                "est_nav": _safe_float(fund.get("est_nav")),
                "est_nav_cal": 0,
                "est_confidence": "unknown",
                "underlying_code": "",
                "underlying_name": fund.get("underlying_name", ""),
                "underlying_type": "unknown",
                "underlying_price": 0,
                "underlying_change_pct": _safe_float(fund.get("underlying_change")),
                "premium_pct": nav_discount_rt,
                "is_multi_underlying": False,
                "holdings_detail": [],
                "turnover": turnover,
                "amount": _safe_float(fund.get("amount")),
                "apply_status": fund.get("apply_status", ""),
                "apply_limit": fund.get("apply_limit", ""),
                "redeem_status": fund.get("redeem_status", ""),
                "direction": fund.get("direction", ""),
                "apply_fee": fund.get("apply_fee", ""),
                "redeem_fee": fund.get("redeem_fee", ""),
                "arb_eval": None,
            })
            continue

        # 有EST配置的基金，使用EST引擎计算的结果
        apply_status = fund.get("apply_status", "")

        # 解析实际费率（集思录提供）
        actual_apply_fee = _parse_fee_value(fund.get("apply_fee"))
        actual_redeem_fee = _parse_fee_value(fund.get("redeem_fee"))

        # 获取底层资产类型和仓位比例
        bare_code = fund_id[2:] if fund_id[:2] in ('SH', 'SZ') else fund_id
        fund_cfg = FUND_CONFIG.get(bare_code, {})
        underlying_type = fund_cfg.get("underlying_type", est.get("underlying_type", "unknown"))
        position = fund_cfg.get("position", 0.95)

        # 套利评估
        # 溢价套利: holding_days=2 (T+2结算)
        # 折价套利: holding_days取决于用户是否已持有（默认0=刚买入，赎回费1.5%）
        arb_eval = evaluate_arbitrage(
            est_result=est,
            turnover=turnover,
            apply_status=apply_status,
            holding_days=2,  # T+2结算周期
            apply_fee=actual_apply_fee,
            redeem_fee=actual_redeem_fee,
            underlying_type=underlying_type,
            position=position,
        )

        merged.append({
            "fund_code": fund_id,
            "fund_name": est.get("fund_name", fund.get("fund_nm", "")),
            "fund_price": est.get("fund_price", price),
            "fund_change_pct": increase_rt,
            "official_nav": est.get("official_nav", _safe_float(fund.get("fund_nav"))),
            "official_nav_date": est.get("official_nav_date", fund.get("nav_dt", "")),
            # 三种EST（参考Palmmicro）
            "est_nav_official": est.get("est_nav_official", 0),  # 官方EST（天天基金）
            "est_nav_cal": est.get("est_nav_cal", 0),            # 参考EST（校准值法）
            "est_nav": est.get("est_nav", 0),                    # 实时EST（动态比率法）
            "est_confidence": est.get("est_confidence", "unknown"),
            "est_change_official": est.get("est_change_official", "0"),
            "est_time_official": est.get("est_time_official", ""),
            "underlying_code": est.get("underlying_code", ""),
            "underlying_name": est.get("underlying_name", ""),
            "underlying_type": est.get("underlying_type", ""),
            "underlying_price": est.get("underlying_price", 0),
            "underlying_change_pct": est.get("underlying_change_pct", 0),
            # 三种溢价率
            "premium_pct": est.get("premium_pct", nav_discount_rt),           # 基于实时EST
            "premium_official": est.get("premium_official", 0),               # 基于官方EST
            "premium_cal": est.get("premium_cal", 0),                         # 基于参考EST
            "is_multi_underlying": est.get("is_multi_underlying", False),
            "holdings_detail": est.get("holdings_detail", []),
            "turnover": turnover,
            "amount": _safe_float(fund.get("amount")),
            "apply_status": apply_status,
            "apply_limit": fund.get("apply_limit", ""),
            "redeem_status": fund.get("redeem_status", ""),
            "direction": arb_eval.get("direction", "none"),
            "apply_fee": fund.get("apply_fee", ""),
            "redeem_fee": fund.get("redeem_fee", ""),
            "arb_eval": arb_eval,
        })

    return merged


@router.get("/scan")
def scan_arbitrage(
    min_premium: float = Query(2.0, description="最低溢价率绝对值%"),
    min_amount: float = Query(1000, description="最低成交额(万元)"),
    direction: str = Query("all", description="方向: all/溢价/折价"),
    holding_days: int = Query(2, description="持有天数(用于计算赎回费, 默认2=T+2结算)"),
):
    """扫描全部LOF基金的套利机会

    三源融合：
    1. 集思录 -> 基金列表、场内价格、净值、成交额、申购状态
    2. 新浪 -> 底层资产实时价格
    3. EST计算引擎 -> 动态比率法净值估算

    返回按净收益排序的套利机会列表。
    """
    try:
        # 1. 从集思录获取全部LOF基金数据（经 _normalize_fund 标准化：
        #    补齐 turnover=成交量×价格、apply_limit 限额解析，原始 cell 无这两个字段）
        jisilu_funds = [
            n for n in (FundService._normalize_fund(c) for c in FundService._fetch_jisilu_lof())
            if n
        ]
        data_source = "集思录"

        # 降级到备用数据源
        if not jisilu_funds:
            jisilu_funds = FundService._fetch_akshare_lof()
            data_source = "AKShare"
        if not jisilu_funds:
            jisilu_funds = FundService._fetch_eastmoney_lof_list()
            data_source = "东方财富"

        if not jisilu_funds:
            return make_success_response({
                "funds": [],
                "total": 0,
                "data_source": "无数据",
                "error": "无法获取基金数据",
            })

        # 2. 获取底层资产实时价格
        underlying_symbols = get_underlying_symbols()
        underlying_data = get_sina_realtime(list(underlying_symbols))

        # 3. 获取汇率（USD/CNY和HKD/CNY）
        usdcny_rate = get_usdcny_rate()
        hkdcny_rate = get_hkdcny_rate()

        # 4. 批量获取官方净值
        fund_codes_with_config = [fc for fc in FUND_CONFIG.keys() if any(f.get("fund_id") == fc for f in jisilu_funds)]
        nav_data = get_fund_nav_batch(fund_codes_with_config)

        # 5. 批量获取天天基金官方EST
        official_est_data = get_official_est_batch(fund_codes_with_config)

        # 6. 计算EST
        est_results = {}
        for fund in jisilu_funds:
            fund_id = fund.get("fund_id", "")
            if fund_id not in FUND_CONFIG:
                continue

            fund_price = _safe_float(fund.get("price"))
            if fund_price <= 0:
                continue

            nav_info = nav_data.get(fund_id, {})
            official_nav = _safe_float(nav_info.get("nav")) or _safe_float(fund.get("fund_nav"))
            official_nav_date = nav_info.get("nav_date", fund.get("nav_dt", ""))

            if official_nav <= 0:
                continue

            # 获取该基金的官方EST
            official_est = official_est_data.get(fund_id)

            est = calc_fund_est(
                fund_code=fund_id,
                fund_price=fund_price,
                underlying_data=underlying_data,
                usdcny_rate=usdcny_rate,
                official_nav=official_nav,
                official_nav_date=official_nav_date,
                official_est=official_est,
            )
            if est:
                est_results[fund_id] = est

        # 6. 合并数据
        merged = _merge_fund_data(jisilu_funds, est_results)

        # 6.1 申购状态兜底：集思录未提供时（未登录/备用源），用天天基金数据补齐
        try:
            em_status = FundService.get_em_purchase_status_map()
            for f in merged:
                if not f.get("apply_status"):
                    code = f.get("fund_code", "")
                    bare = code[2:] if code[:2] in ("SH", "SZ") else code
                    st = em_status.get(bare)
                    if st:
                        f["apply_status"] = st.get("apply_status", "")
                        f["apply_limit"] = st.get("apply_limit", "")
                        if not f.get("redeem_status"):
                            f["redeem_status"] = st.get("redeem_status", "")
        except Exception as _e:
            logger.warning(f"天天基金申购状态兜底失败(不影响scan): {_e}")

        # 7. 筛选
        filtered = []
        for fund in merged:
            premium_abs = abs(_safe_float(fund.get("premium_pct")))
            amount = _safe_float(fund.get("turnover"))  # 成交额(万元)，勿用 amount(份额)
            fund_direction = fund.get("direction", "none")

            # 溢价率筛选
            if premium_abs < min_premium:
                continue

            # 成交额筛选
            if amount < min_amount:
                continue

            # 方向筛选
            if direction == "溢价" and fund_direction != "premium":
                continue
            if direction == "折价" and fund_direction != "discount":
                continue

            filtered.append(fund)

        # 8. 按净收益排序
        filtered.sort(
            key=lambda f: f.get("arb_eval", {}).get("net_profit", 0) if f.get("arb_eval") else 0,
            reverse=True,
        )

        # 9. 统计
        all_premiums = [_safe_float(f.get("premium_pct")) for f in merged if f.get("premium_pct")]
        stats = {
            "total_funds": len(merged),
            "filtered_count": len(filtered),
            "avg_premium": round(sum(all_premiums) / len(all_premiums), 2) if all_premiums else 0,
            "max_premium": round(max(all_premiums), 2) if all_premiums else 0,
            "min_premium": round(min(all_premiums), 2) if all_premiums else 0,
            "premium_count": len([p for p in all_premiums if p > min_premium]),
            "discount_count": len([p for p in all_premiums if p < -min_premium]),
        }

        return make_success_response({
            "funds": filtered,
            "stats": stats,
            "data_source": data_source,
            "market_status": determine_market_status(),
            "usdcny_rate": usdcny_rate,
            "hkdcny_rate": hkdcny_rate,
            "filters": {
                "min_premium": min_premium,
                "min_amount": min_amount,
                "direction": direction,
                "holding_days": holding_days,
            },
        })

    except Exception as e:
        logger.error(f"扫描套利机会失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"扫描失败: {str(e)}")


@router.get("/fund/{fund_code}")
def get_fund_detail(fund_code: str, holding_days: int = Query(30)):
    """获取单只基金的详细套利分析

    包含：计算过程、持仓明细、底层资产行情、套利建议
    """
    fund_code = validate_stock_code(fund_code)
    try:
        config = get_fund_config(fund_code)
        if not config:
            raise HTTPException(status_code=404, detail=f"未找到基金 {fund_code} 的配置")

        # 获取底层资产价格
        underlying_symbols = get_underlying_symbols()
        underlying_data = get_sina_realtime(list(underlying_symbols))

        # 获取汇率
        usdcny_rate = get_usdcny_rate()

        # 获取官方净值
        nav_data = get_fund_nav_batch([fund_code])
        nav_info = nav_data.get(fund_code, {})
        official_nav = nav_info.get("nav", 0)
        official_nav_date = nav_info.get("nav_date", "")

        # 获取集思录数据（标准化后含 turnover/apply_limit）
        jisilu_funds = [
            n for n in (FundService._normalize_fund(c) for c in FundService._fetch_jisilu_lof())
            if n
        ]
        fund_data = next((f for f in jisilu_funds if f.get("fund_id") == fund_code), {})

        fund_price = _safe_float(fund_data.get("price"))
        if fund_price <= 0:
            raise HTTPException(status_code=404, detail=f"未找到基金 {fund_code} 的场内价格")

        # 计算EST
        est = calc_fund_est(
            fund_code=fund_code,
            fund_price=fund_price,
            underlying_data=underlying_data,
            usdcny_rate=usdcny_rate,
            official_nav=official_nav,
            official_nav_date=official_nav_date,
        )

        if not est:
            raise HTTPException(status_code=500, detail=f"计算基金 {fund_code} 的EST失败")

        # 解析实际费率
        actual_apply_fee = _parse_fee_value(fund_data.get("apply_fee"))
        actual_redeem_fee = _parse_fee_value(fund_data.get("redeem_fee"))
        underlying_type = config.get("underlying_type", "unknown")
        position = config.get("position", 0.95)

        # 套利评估
        arb_eval = evaluate_arbitrage(
            est_result=est,
            turnover=fund_data.get("turnover", 0),
            apply_status=fund_data.get("apply_status", ""),
            holding_days=holding_days,
            apply_fee=actual_apply_fee,
            redeem_fee=actual_redeem_fee,
            underlying_type=underlying_type,
            position=position,
        )

        return make_success_response({
            "fund": {
                "fund_code": fund_code,
                "fund_name": config["name"],
                "fund_price": fund_price,
                "fund_change_pct": fund_data.get("increase_rt", 0),
                "official_nav": official_nav,
                "official_nav_date": official_nav_date,
                "turnover": fund_data.get("turnover", 0),
                "apply_status": fund_data.get("apply_status", ""),
                "apply_limit": fund_data.get("apply_limit", ""),
            },
            "est": est,
            "arb_eval": arb_eval,
            "config": {
                "underlying_type": config["underlying_type"],
                "position": config.get("position", 0.95),
                "calibration": config.get("calibration"),
            },
            "usdcny_rate": usdcny_rate,
            "market_status": determine_market_status(),
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取基金 {fund_code} 详情失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取详情失败: {str(e)}")


@router.get("/t-opportunities")
def get_t_opportunities():
    """扫描QDII基金的做T机会 (V2)

    V2改进：
    - 多因子信号：开盘缺口 + 底层资产方向 + 溢价率 + 成交量
    - 完整费用计算：佣金 + 过户费 + 滑点
    - 风险控制：止损线、仓位上限、期望收益
    - LOF套利联动：集成EST净值和溢价率

    Returns:
        {
            "opportunities": [...],
            "total": int,
            "update_time": str,
            "strategy_info": dict,
        }
    """
    try:
        opportunities = scan_t_opportunities(include_details=True)

        return make_success_response({
            "opportunities": opportunities,
            "total": len(opportunities),
            "strategy_info": {
                "version": "V2",
                "high_open_threshold": 2.0,
                "strong_high_open_threshold": 3.0,
                "low_open_threshold": -1.0,
                "strong_low_open_threshold": -3.0,
                "high_open_fall_prob": "35%-75%",
                "low_open_bounce_prob": "65%-70%",
                "fee_structure": {
                    "commission": "万2.5(双边)",
                    "transfer_fee": "万0.2",
                    "slippage": "0.02%-0.08%",
                },
                "risk_controls": {
                    "stop_loss": "信号幅度的50%",
                    "take_profit": "信号幅度的60%",
                    "max_position": "日均成交额的5%",
                },
            },
        })

    except Exception as e:
        logger.error(f"扫描做T机会失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"扫描失败: {str(e)}")


@router.get("/t-backtest/{fund_code}")
def get_t_backtest(fund_code: str, days: int = Query(60, ge=10, le=250)):
    """回测做T策略历史表现

    通过历史K线数据模拟做T信号，统计胜率和收益。

    Args:
        fund_code: 基金代码
        days: 回测天数（默认60，范围10-250）

    Returns:
        回测结果（胜率、收益、信号明细等）
    """
    fund_code = validate_stock_code(fund_code)
    try:
        result = backtest_t_strategy(fund_code, days=days)
        return make_success_response(result)
    except Exception as e:
        logger.error(f"回测 {fund_code} 失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"回测失败: {str(e)}")


# ==================== 集思录登录（合并自 funds.py）====================


class LoginRequest(BaseModel):
    user_name: str
    password: str


@router.post("/login")
def login(req: LoginRequest):
    """登录集思录"""
    result = FundService.login(req.user_name, req.password)
    if not result['success']:
        raise HTTPException(status_code=400, detail=result['error'])
    return result


@router.get("/login_status")
def login_status():
    """获取登录状态"""
    return FundService.get_login_status()


@router.get("/refresh")
def refresh_data():
    """强制刷新数据"""
    result = FundService.refresh_data()
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@router.get("/legacy-arbitrage")
def get_legacy_arbitrage(
    min_threshold: float = Query(0.0, ge=0, description="最低折溢价率阈值(%)"),
    direction: str = Query("all", description="筛选方向: all/溢价/折价"),
    min_turnover: float = Query(300.0, ge=0, description="最低成交额(万元)"),
    open_subscribe_only: bool = Query(True, description="仅显示开放申购"),
):
    """获取当前套利机会（旧版，基于集思录数据）"""
    if direction not in ("all", "溢价", "折价"):
        raise HTTPException(status_code=400, detail="direction 必须是 all/溢价/折价")

    result = FundService.get_arbitrage_opportunities(
        min_threshold=min_threshold,
        direction=direction,
        min_turnover=min_turnover,
        open_subscribe_only=open_subscribe_only,
    )

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return result


# ==================== 基金EST净值估算（合并自 fund_est.py）====================

# 合法代码集合（用于标准化）
_EST_VALID_CODES = set(LOF_FUND_CONFIG.keys()) | set(MULTI_UNDERLYING_FUNDS.keys())


@router.get("/est-list")
def get_fund_est_list():
    """获取所有LOF基金的EST净值估算列表（校准值法）

    批量获取底层资产价格，减少HTTP请求数。
    支持多标的基金（如海外科技LOF），通过持仓数据计算加权涨跌幅。
    """
    try:
        # 获取集思录申购状态（开放/暂停/限购），失败不影响EST计算
        # 注意：LOF_FUND_CONFIG 键带 SH/SZ 前缀，集思录 fund_id 为裸6位代码，统一按裸代码建索引；
        # 经 _normalize_fund 标准化以补齐 apply_limit（从 min_amt/apply_status 解析）
        apply_status_map: dict = {}
        try:
            for _c in FundService._fetch_jisilu_lof():
                _f = FundService._normalize_fund(_c)
                if not _f:
                    continue
                _fid = _f.get("fund_id", "")
                if _fid:
                    apply_status_map[_fid] = {
                        "apply_status": _f.get("apply_status", ""),
                        "apply_limit": _f.get("apply_limit", ""),
                        "redeem_status": _f.get("redeem_status", ""),
                    }
        except Exception as _e:
            logger.warning(f"获取集思录申购状态失败(不影响EST): {_e}")

        # 兜底：天天基金(akshare)申购状态，补齐集思录未覆盖的基金（匿名仅返回各列表前20条）
        try:
            for _code, _v in FundService.get_em_purchase_status_map().items():
                apply_status_map.setdefault(_code, _v)
        except Exception as _e:
            logger.warning(f"天天基金申购状态兜底失败(不影响EST): {_e}")

        # 批量收集所有底层资产代码
        underlying_symbols = set()
        for config in LOF_FUND_CONFIG.values():
            underlying_symbols.add(config["underlying"])
            if "underlying_alt" in config:
                underlying_symbols.add(config["underlying_alt"])

        for config in MULTI_UNDERLYING_FUNDS.values():
            for holding in config.get("holdings", []):
                underlying_symbols.add(holding["code"])

        # 批量获取基金实时价格（包括A股LOF）
        all_fund_codes = list(LOF_FUND_CONFIG.keys()) + list(MULTI_UNDERLYING_FUNDS.keys())
        # 添加A股LOF基金代码
        for bare_code, cfg in FUND_CONFIG.items():
            if cfg.get("underlying_type") in ("a_index", "active"):
                prefixed = f"{'SH' if bare_code.startswith('5') else 'SZ'}{bare_code}"
                if prefixed not in LOF_FUND_CONFIG and prefixed not in MULTI_UNDERLYING_FUNDS:
                    all_fund_codes.append(prefixed)
        fund_symbols = [get_sina_fund_code(s) for s in all_fund_codes]
        fund_data = get_sina_realtime(fund_symbols)

        # 批量获取底层资产价格
        underlying_data = get_sina_realtime(list(underlying_symbols))

        usdcny_rate = get_usdcny_rate()
        hkdcny_rate = get_hkdcny_rate()
        market_status = determine_market_status()

        results = []
        for fund_code, config in LOF_FUND_CONFIG.items():
            item = _process_single_fund(
                fund_code, config, fund_data, underlying_data, usdcny_rate,
                is_multi_underlying=False
            )
            if item:
                # 从统一配置中补充 underlying_type（LOF_FUND_CONFIG 用 SH/SZ 前缀，FUND_CONFIG 用纯数字）
                bare_code = fund_code[2:] if fund_code[:2] in ('SH', 'SZ') else fund_code
                unified_cfg = FUND_CONFIG.get(bare_code, {})
                item["underlying_type"] = unified_cfg.get("underlying_type", "unknown")
                _ast = apply_status_map.get(bare_code, {})
                item["apply_status"] = _ast.get("apply_status", "")
                item["apply_limit"] = _ast.get("apply_limit", "")
                item["redeem_status"] = _ast.get("redeem_status", "")
                results.append(item)

        for fund_code, config in MULTI_UNDERLYING_FUNDS.items():
            item = _process_single_fund(
                fund_code, config, fund_data, underlying_data, usdcny_rate,
                is_multi_underlying=True
            )
            if item:
                item["underlying_type"] = "multi"
                _bare3 = fund_code[2:] if fund_code[:2] in ('SH', 'SZ') else fund_code
                _ast3 = apply_status_map.get(_bare3, {})
                item["apply_status"] = _ast3.get("apply_status", "")
                item["apply_limit"] = _ast3.get("apply_limit", "")
                item["redeem_status"] = _ast3.get("redeem_status", "")
                results.append(item)

        # A股LOF参考数据（无EST，仅价格和涨跌幅）
        a_share_funds = []
        for bare_code, cfg in FUND_CONFIG.items():
            if cfg.get("underlying_type") not in ("a_index", "active"):
                continue
            # 跳过已在 QDII 列表中的
            prefixed = f"{'SH' if bare_code.startswith('5') else 'SZ'}{bare_code}"
            if prefixed in LOF_FUND_CONFIG or prefixed in MULTI_UNDERLYING_FUNDS:
                continue
            # 查找已获取的基金数据
            sina_code = get_sina_fund_code(prefixed)
            fund_info = fund_data.get(sina_code, [])
            if not fund_info or len(fund_info) < 10:
                continue
            price = _safe_float_orig(fund_info[3], 0)
            change_pct = _safe_float_orig(fund_info[32], 0) if len(fund_info) > 32 else 0
            if price <= 0:
                continue
            _ast2 = apply_status_map.get(bare_code, {})
            a_share_funds.append({
                "fund_code": prefixed,
                "fund_name": cfg["name"],
                "fund_price": price,
                "fund_change_pct": round(change_pct, 2),
                "underlying_type": cfg.get("underlying_type", "unknown"),
                "underlying_code": cfg.get("underlying", ""),
                "turnover": round(_safe_float_orig(fund_info[9], 0) / 10000, 2) if len(fund_info) > 9 else 0,
                "apply_status": _ast2.get("apply_status", ""),
                "apply_limit": _ast2.get("apply_limit", ""),
            })

        return make_success_response({
            "funds": results,
            "total": len(results),
            "a_share_funds": a_share_funds,
            "a_share_total": len(a_share_funds),
            "usdcny_rate": usdcny_rate,
            "hkdcny_rate": hkdcny_rate,
            "market_status": market_status,
        })
    except Exception as e:
        logger.error(f"获取LOF基金EST列表失败: {e}")
        raise HTTPException(status_code=500, detail="获取基金EST列表失败，请稍后重试")


@router.get("/est/{fund_code}")
def get_fund_est(fund_code: str):
    """获取单只LOF基金的EST净值估算（校准值法）"""
    normalized = normalize_fund_code(fund_code, _EST_VALID_CODES)
    if not normalized:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的基金代码: {fund_code}",
        )

    is_multi = normalized in MULTI_UNDERLYING_FUNDS
    config = MULTI_UNDERLYING_FUNDS[normalized] if is_multi else LOF_FUND_CONFIG.get(normalized)

    if not config:
        raise HTTPException(status_code=404, detail=f"未找到基金 {fund_code} 的配置")

    try:
        sina_fund_code = get_sina_fund_code(normalized)
        fund_data = get_sina_realtime([sina_fund_code])
        fund_info = fund_data.get(sina_fund_code, [])

        if len(fund_info) < 10:
            raise HTTPException(status_code=404, detail="获取基金价格失败，请稍后重试")

        fund_price = _safe_float_orig(fund_info[3], 0)
        fund_change_pct = _safe_float_orig(fund_info[32], 0) if len(fund_info) > 32 else 0

        if fund_price <= 0:
            raise HTTPException(status_code=404, detail="基金价格数据异常")

        fund_nav_code = normalized[2:]
        nav_info = get_fund_nav_from_eastmoney(fund_nav_code)
        official_nav = _safe_float_orig(nav_info.get("nav"), 0)
        usdcny_rate = get_usdcny_rate()

        if is_multi:
            underlying_symbols = [h["code"] for h in config.get("holdings", [])]
            underlying_data = get_sina_realtime(underlying_symbols)
            multi_result = _calc_multi_underlying_est_nav(
                config, underlying_data, usdcny_rate, official_nav
            )
            if multi_result:
                est_nav = multi_result["est_nav"]
                premium = round((fund_price - est_nav) / est_nav * 100, 2) if est_nav > 0 else 0
                return make_success_response({
                    "fund_code": normalized,
                    "fund_name": config["name"],
                    "fund_price": fund_price,
                    "fund_change_pct": round(fund_change_pct, 2),
                    "est_nav": round(est_nav, 4),
                    "premium": premium,
                    "official_nav": official_nav,
                    "official_nav_date": nav_info.get("nav_date", ""),
                    "holdings_detail": multi_result["holdings_detail"],
                    "is_multi_underlying": True,
                })
            else:
                raise HTTPException(status_code=404, detail="计算多标的基金净值失败")

        underlying_code = config["underlying"]
        underlying_data = get_sina_realtime([underlying_code])
        underlying_info = underlying_data.get(underlying_code, [])

        if not underlying_info and "underlying_alt" in config:
            underlying_code = config["underlying_alt"]
            underlying_data = get_sina_realtime([underlying_code])
            underlying_info = underlying_data.get(underlying_code, [])

        if not underlying_info:
            raise HTTPException(status_code=404, detail=f"获取底层资产 {underlying_code} 价格失败")

        parsed = parse_underlying_price(underlying_code, underlying_info)
        if not parsed or parsed["price"] <= 0:
            raise HTTPException(status_code=404, detail=f"底层资产 {underlying_code} 价格数据异常")

        est_nav = _calc_est_nav(
            underlying_code, parsed["price"], usdcny_rate, config["position"], config["calibration"]
        )
        premium = round((fund_price - est_nav) / est_nav * 100, 2) if est_nav > 0 else 0

        return make_success_response({
            "fund_code": normalized,
            "fund_name": config["name"],
            "fund_price": fund_price,
            "fund_change_pct": round(fund_change_pct, 2),
            "underlying_code": underlying_code,
            "underlying_price": parsed["price"],
            "underlying_change_pct": parsed["change_pct"],
            "est_nav": round(est_nav, 4),
            "premium": premium,
            "official_nav": official_nav,
            "official_nav_date": nav_info.get("nav_date", ""),
            "position": config["position"],
            "usdcny_rate": usdcny_rate,
            "is_multi_underlying": False,
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取基金 {fund_code} EST失败: {e}")
        raise HTTPException(status_code=500, detail="获取基金EST数据失败，请稍后重试")


# ==================== EST详情（合并自 fund_est_detail.py）====================

_DETAIL_VALID_CODES = set(LOF_FUND_CONFIG.keys())


@router.get("/est-detail-list")
def get_fund_est_detail_list():
    """获取所有QDII LOF基金的EST净值估算列表（动态比率法）

    同时返回动态比率法和传统校准值法的结果用于对比。
    """
    try:
        underlying_symbols = set()
        for config in LOF_FUND_CONFIG.values():
            underlying_symbols.add(config["underlying"])

        fund_symbols = [get_sina_fund_code(s) for s in LOF_FUND_CONFIG.keys()]
        fund_data = get_sina_realtime(fund_symbols)
        underlying_data = get_sina_realtime(list(underlying_symbols))

        usdcny_rate = get_usdcny_rate()
        market_status = determine_market_status()

        fund_nav_codes = [fund_code[2:] for fund_code in LOF_FUND_CONFIG.keys()]
        nav_data_batch = get_fund_nav_batch(fund_nav_codes)

        results = []
        for fund_code, config in LOF_FUND_CONFIG.items():
            try:
                sina_fund_code = get_sina_fund_code(fund_code)
                fund_info = fund_data.get(sina_fund_code, [])
                if len(fund_info) < 10:
                    continue

                fund_price = _safe_float_orig(fund_info[3], 0)
                fund_change_pct = _safe_float_orig(fund_info[32], 0) if len(fund_info) > 32 else 0

                if fund_price <= 0:
                    continue

                underlying_code = config["underlying"]
                underlying_info = underlying_data.get(underlying_code, [])
                if not underlying_info:
                    continue

                parsed = parse_underlying_price(underlying_code, underlying_info)
                if not parsed or parsed["price"] <= 0 or parsed["prev_close"] <= 0:
                    continue

                fund_nav_code = fund_code[2:]
                nav_info = nav_data_batch.get(fund_nav_code, {})
                official_nav = _safe_float_orig(nav_info.get("nav"), 0)
                nav_date = nav_info.get("nav_date", "")

                if official_nav <= 0:
                    continue

                position = config["position"]
                price_ratio = parsed["price"] / parsed["prev_close"]
                est_nav_dynamic = official_nav * price_ratio

                calibration = config.get("calibration", 0)
                est_nav_traditional = _calc_est_nav(
                    underlying_code, parsed["price"], usdcny_rate, position, calibration
                )

                premium = (
                    round((fund_price - est_nav_dynamic) / est_nav_dynamic * 100, 2)
                    if est_nav_dynamic > 0 else 0
                )

                results.append({
                    "fund_code": fund_code,
                    "fund_name": config["name"],
                    "fund_price": fund_price,
                    "fund_change_pct": round(fund_change_pct, 2),
                    "underlying_code": underlying_code,
                    "underlying_price": parsed["price"],
                    "underlying_prev_close": parsed["prev_close"],
                    "underlying_change_pct": parsed["change_pct"],
                    "est_nav": round(est_nav_dynamic, 4),
                    "est_nav_traditional": round(est_nav_traditional, 4),
                    "premium": premium,
                    "official_nav": official_nav,
                    "official_nav_date": nav_date,
                    "position": position,
                    "usdcny_rate": usdcny_rate,
                    "price_ratio": round(price_ratio, 6),
                    "calculation_method": "dynamic_ratio",
                })
            except Exception as e:
                logger.warning(f"处理基金 {fund_code} 失败: {e}")
                continue

        results.sort(key=lambda x: x["premium"], reverse=True)

        return make_success_response({
            "funds": results,
            "total": len(results),
            "usdcny_rate": usdcny_rate,
            "market_status": market_status,
        })
    except Exception as e:
        logger.error(f"获取QDII基金EST列表失败: {e}")
        raise HTTPException(status_code=500, detail="获取基金EST列表失败，请稍后重试")


@router.get("/est-detail/{fund_code}")
def get_fund_est_detail(fund_code: str):
    """获取单只QDII LOF基金的详细EST净值估算（动态比率法）"""
    normalized = normalize_fund_code(fund_code, _DETAIL_VALID_CODES)
    if not normalized:
        raise HTTPException(status_code=400, detail=f"不支持的基金代码: {fund_code}")

    config = LOF_FUND_CONFIG[normalized]

    try:
        fund_nav_code = normalized[2:]
        nav_info = get_fund_nav_from_eastmoney(fund_nav_code)
        official_nav = _safe_float_orig(nav_info.get("nav"), 0)
        nav_date = nav_info.get("nav_date", "")

        if official_nav <= 0:
            raise HTTPException(status_code=404, detail="获取基金官方净值失败")

        underlying_code = config["underlying"]
        underlying_raw = get_sina_realtime([underlying_code])
        underlying_info = underlying_raw.get(underlying_code, [])

        if not underlying_info or len(underlying_info) < 2:
            raise HTTPException(status_code=404, detail=f"获取 {underlying_code} 价格失败")

        parsed = parse_underlying_price(underlying_code, underlying_info)
        if not parsed or parsed["price"] <= 0:
            raise HTTPException(status_code=404, detail=f"{underlying_code} 价格数据异常")

        usdcny_rate = get_usdcny_rate()
        hkdcny_rate = get_hkdcny_rate()

        sina_fund_code = get_sina_fund_code(normalized)
        fund_data_raw = get_sina_realtime([sina_fund_code])
        fund_info = fund_data_raw.get(sina_fund_code, [])

        a_share_price = 0.0
        a_share_change_pct = 0.0
        a_share_volume = 0
        a_share_amount = 0.0

        if fund_info and len(fund_info) > 10:
            a_share_price = _safe_float_orig(fund_info[3], 0)
            a_share_change_pct = _safe_float_orig(fund_info[32], 0) if len(fund_info) > 32 else 0
            a_share_volume = int(_safe_float_orig(fund_info[8], 0))
            a_share_amount = _safe_float_orig(fund_info[9], 0)

        position = config["position"]
        underlying_price = parsed["price"]
        underlying_prev_close = parsed["prev_close"]

        if underlying_prev_close > 0:
            price_ratio = underlying_price / underlying_prev_close
            est_nav_dynamic = official_nav * price_ratio
        else:
            price_ratio = 1.0
            est_nav_dynamic = official_nav

        calibration = config.get("calibration", 0)
        est_nav_traditional = _calc_est_nav(
            underlying_code, underlying_price, usdcny_rate, position, calibration
        )

        premium_pct = (
            round((a_share_price - est_nav_dynamic) / est_nav_dynamic * 100, 2)
            if a_share_price > 0 and est_nav_dynamic > 0 else 0
        )

        return make_success_response({
            "fund_code": normalized,
            "fund_name": config["name"],
            "est_nav": round(est_nav_dynamic, 4),
            "est_nav_traditional": round(est_nav_traditional, 4),
            "a_share_price": a_share_price,
            "a_share_change_pct": round(a_share_change_pct, 2),
            "a_share_volume": a_share_volume,
            "a_share_amount": round(a_share_amount, 2),
            "premium_pct": premium_pct,
            "official_nav": official_nav,
            "official_nav_date": nav_date,
            "underlying_code": underlying_code,
            "underlying_name": parsed["name"],
            "underlying_price": underlying_price,
            "underlying_prev_close": underlying_prev_close,
            "underlying_change_pct": parsed["change_pct"],
            "underlying_open": parsed["open"],
            "underlying_high": parsed["high"],
            "underlying_low": parsed["low"],
            "usdcny_rate": usdcny_rate,
            "hkdcny_rate": hkdcny_rate,
            "position_ratio": position,
            "calibration": round(calibration, 6),
            "price_ratio": round(price_ratio, 6),
            "calculation_method": "dynamic_ratio",
            "market_status": determine_market_status(),
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取基金 {fund_code} 详细EST失败: {e}")
        raise HTTPException(status_code=500, detail="获取基金EST数据失败，请稍后重试")


@router.get("/stock-quotes")
def get_stock_quotes(codes: str = Query(..., description="逗号分隔的股票代码，如 sh600519,sz000858")):
    """批量获取A股股票实时行情（用于基金持仓股票价格查询）"""
    if not codes or not codes.strip():
        raise HTTPException(status_code=400, detail="codes参数不能为空")

    code_list = [c.strip().lower() for c in codes.split(",") if c.strip()]
    if not code_list:
        raise HTTPException(status_code=400, detail="未提供有效的股票代码")
    if len(code_list) > 50:
        raise HTTPException(status_code=400, detail="单次最多查询50个股票代码")

    cache_key = f"stock_quotes:{','.join(sorted(code_list))}"
    cached_data = get_cache(cache_key, 30)
    if cached_data is not None:
        return make_success_response({"quotes": cached_data})

    try:
        raw_data = get_sina_realtime(code_list)
        quotes = {}
        for code in code_list:
            fields = raw_data.get(code, [])
            if not fields or len(fields) < 32:
                continue

            name = fields[0] if fields[0] else code
            price = _safe_float_orig(fields[3], 0)
            prev_close = _safe_float_orig(fields[2], 0)

            if price <= 0 or prev_close <= 0:
                continue

            change_pct = round((price - prev_close) / prev_close * 100, 2)
            quotes[code] = {
                "code": code, "name": name, "price": price,
                "change_pct": change_pct, "prev_close": prev_close,
                "open": _safe_float_orig(fields[1], 0),
                "high": _safe_float_orig(fields[4], 0),
                "low": _safe_float_orig(fields[5], 0),
                "volume": int(_safe_float_orig(fields[8], 0)),
                "amount": _safe_float_orig(fields[9], 0),
            }

        if quotes:
            set_cache(cache_key, quotes)

        return make_success_response({"quotes": quotes})
    except Exception as e:
        logger.error(f"批量获取股票行情失败 ({len(code_list)}个代码): {e}")
        raise HTTPException(status_code=500, detail="获取股票行情失败，请稍后重试")


# ==================== EST准确度回测（新增）====================


@router.get("/est-accuracy")
def get_est_accuracy(fund_code: str = Query("", description="基金代码，空则返回全部汇总")):
    """获取EST估算净值的历史准确度统计

    用于评估EST估算方法的可靠性：
    - 平均偏差：反映EST的系统性偏高或偏低
    - 平均绝对偏差：反映EST的精度
    - 准确率：偏差<0.5%的记录占比
    """
    try:
        stats = get_est_accuracy_stats(fund_code)
        return make_success_response({
            "accuracy": stats,
            "fund_code": fund_code or "all",
        })
    except Exception as e:
        logger.error(f"获取EST准确度统计失败: {e}")
        raise HTTPException(status_code=500, detail="获取准确度统计失败")


@router.get("/exchange-rates")
def get_exchange_rates():
    """获取当前汇率信息（USD/CNY和HKD/CNY）"""
    try:
        usdcny = get_usdcny_rate()
        hkdcny = get_hkdcny_rate()
        return make_success_response({
            "usdcny": usdcny,
            "hkdcny": hkdcny,
            "hkdcny_source": "dynamic",  # 标记为动态获取
        })
    except Exception as e:
        logger.error(f"获取汇率失败: {e}")
        raise HTTPException(status_code=500, detail="获取汇率失败")
