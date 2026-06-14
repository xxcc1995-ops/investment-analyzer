"""
决策卫士 API
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from ..services.decision_service import (
    analyze_decision, submit_diagnosis, get_history, record_outcome, quick_scan,
    get_prefrontal_warmup, get_calibration_question, submit_calibration_answer,
    get_calibration_stats, get_base_rates, get_decision_stats,
)

router = APIRouter()


class AnalyzeRequest(BaseModel):
    decision_type: str  # buy / sell / hold
    target: str  # 标的名称或代码
    reason: str  # 决策理由
    trigger: str = ""  # 触发原因
    position_pct: str = ""  # 仓位比例
    time_horizon: str = ""  # 持有时间框架


class AnswerItem(BaseModel):
    id: int
    answer: str


class DiagnoseRequest(BaseModel):
    decision_id: str
    answers: list[AnswerItem]


class OutcomeRequest(BaseModel):
    decision_id: str
    outcome: str  # profit / loss / breakeven
    profit_pct: Optional[float] = None
    lesson: str = ""


class QuickScanRequest(BaseModel):
    intention: str  # buy / sell / adjust
    thought: str = ""  # 用户当前想法


class CalibrationSubmitRequest(BaseModel):
    question_id: str
    user_answer: float
    confidence: int  # 60/70/80/90


class PrefrontalWarmupRequest(BaseModel):
    decision_type: str = ""
    target: str = ""
    thought: str = ""


@router.post("/quick-scan")
async def api_quick_scan(req: QuickScanRequest):
    """快速情绪扫描（理性门卫用）"""
    result = quick_scan(
        intention=req.intention,
        thought=req.thought,
    )
    return result


@router.post("/analyze")
async def api_analyze(req: AnalyzeRequest):
    """提交决策，返回检出的偏误和质问"""
    if not req.target.strip():
        raise HTTPException(400, "请填写投资标的")
    if not req.reason.strip():
        raise HTTPException(400, "请填写决策理由")

    result = analyze_decision(
        decision_type=req.decision_type,
        target=req.target,
        reason=req.reason,
        trigger=req.trigger,
        position_pct=req.position_pct,
        time_horizon=req.time_horizon,
    )
    return result


@router.post("/diagnose")
async def api_diagnose(req: DiagnoseRequest):
    """提交质问回答，返回诊断报告"""
    result = submit_diagnosis(
        decision_id=req.decision_id,
        answers=[a.model_dump() for a in req.answers],
    )
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.get("/history")
async def api_history(limit: int = 50):
    """获取决策日志"""
    return get_history(limit)


@router.post("/outcome")
async def api_outcome(req: OutcomeRequest):
    """补填决策结果"""
    result = record_outcome(
        decision_id=req.decision_id,
        outcome=req.outcome,
        profit_pct=req.profit_pct,
        lesson=req.lesson,
    )
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/prefrontal-warmup")
async def api_prefrontal_warmup(req: PrefrontalWarmupRequest):
    """获取前额叶热身问题"""
    return get_prefrontal_warmup(
        decision_type=req.decision_type,
        target=req.target,
        thought=req.thought,
    )


@router.get("/calibration-question")
async def api_calibration_question(index: int = None):
    """获取一道校准训练题"""
    return get_calibration_question(index)


@router.post("/calibration-submit")
async def api_calibration_submit(req: CalibrationSubmitRequest):
    """提交校准训练答案"""
    result = submit_calibration_answer(
        question_id=req.question_id,
        user_answer=req.user_answer,
        confidence=req.confidence,
    )
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.get("/calibration-stats")
async def api_calibration_stats():
    """获取校准训练统计"""
    return get_calibration_stats()


@router.get("/base-rates")
async def api_base_rates():
    """获取个人基准率"""
    return get_base_rates()


@router.get("/stats")
async def api_decision_stats():
    """获取决策系统综合统计（仪表盘）"""
    return get_decision_stats()
