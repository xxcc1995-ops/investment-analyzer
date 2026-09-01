"""临期可转债筛选 API 路由（税后保本价安全垫）

独立功能，移植自 cb-bond-screener 技能；返回 JSON 供前端 NearMaturityPage 渲染。
"""
from fastapi import APIRouter, HTTPException, Query

from app.services.cb_near_mature_service import get_near_mature_list

router = APIRouter()


@router.get("/near-mature")
def get_near_mature(
    include_elasticity: bool = Query(False, description="是否计算正股弹性（近20日涨幅/振幅），较慢"),
    max_remain_years: float = Query(1.0, ge=0, description="剩余期限上限（年）"),
    price_tol: float = Query(1.0, ge=0, description="保本价容忍度（元）：|现价-税后保本价| <= 该值 视为钝化"),
    max_premium: float = Query(20.0, ge=0, description="转股溢价率上限（%），双条件精选阈值"),
):
    """获取临期可转债筛选结果

    返回三张表：
    - double_condition：双条件精选（钝化区 + 溢价率<=阈值 + 未公告强赎）——主表
    - floor_zone：钝化区（现价贴税后保本价 ±price_tol 元）
    - all_linqi：临期债全表（剩余<max_remain_years 年的全部在交易转债，观察区）
    """
    result = get_near_mature_list(
        include_elasticity=include_elasticity,
        max_remain_years=max_remain_years,
        price_tol=price_tol,
        max_premium=max_premium,
    )
    if result.get("error"):
        raise HTTPException(status_code=502, detail=result["error"])
    return result
