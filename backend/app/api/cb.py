"""可转债双低轮动策略API路由（机构级增强版）"""

from fastapi import APIRouter, HTTPException, Query
from app.services.cb_service import CBService

router = APIRouter()


@router.get("/double-low")
def get_double_low(
    max_double_low: float = Query(130.0, ge=0, description="双低值上限"),
    min_rating: str = Query('A', description="最低信用评级: A/A+/AA-/AA/AA+/AAA"),
    min_year_left: float = Query(1.0, ge=0, description="最低剩余年限(年)"),
    min_turnover: float = Query(100.0, ge=0, description="最低成交额(万元)"),
    min_ytm: float = Query(-999, description="最低到期收益率(%)，如0表示只看正收益"),
    top_n: int = Query(20, ge=1, le=100, description="返回前N只"),
    sort_by: str = Query('double_low', description="排序方式: double_low/quality_score/ytm/triple_low/ytm_after_tax/pure_bond_value"),
    exclude_st: bool = Query(True, description="排除ST"),
    exclude_force_redeem: bool = Query(True, description="排除已公告强赎"),
):
    """获取可转债双低排名（机构级增强版：5维度评分+纯债价值+税后YTM+多源容错）"""
    result = CBService.get_double_low_list(
        max_double_low=max_double_low,
        min_rating=min_rating,
        min_year_left=min_year_left,
        min_turnover=min_turnover,
        min_ytm=min_ytm,
        top_n=top_n,
        sort_by=sort_by,
        exclude_st=exclude_st,
        exclude_force_redeem=exclude_force_redeem,
    )

    if result.get('soft_error'):
        return result
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return result


@router.get("/master-strategy")
def get_master_strategy(
    strategy: str = Query('andaoquan', description="策略名称: andaoquan/dual_low/triple_low/negative_premium/pancake/ytm_defense/revision_game/redeem_game"),
    top_n: int = Query(20, ge=1, le=100, description="返回前N只"),
):
    """获取大师策略筛选结果（新增三低策略和负溢价套利策略）"""
    result = CBService.get_master_strategy(
        strategy=strategy,
        top_n=top_n,
    )

    if result.get('soft_error'):
        return result
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return result


@router.get("/strategies")
def get_strategies():
    """获取所有策略定义（含八大战法完整详情）

    返回每个策略的对外公开信息（剔除 lambda），以及 eight_order——
    《可转债：从入门到精通的八大战法》的权威八战法顺序。
    """
    strategies = {}
    for key in CBService.STRATEGIES.keys():
        strategies[key] = CBService.get_strategy_public(key)
    return {
        'strategies': strategies,
        'eight_order': CBService.EIGHT_STRATEGIES,
    }


@router.get("/refresh")
def refresh_data():
    """强制刷新可转债数据"""
    result = CBService.refresh_data()
    if result.get('soft_error'):
        return result
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result
