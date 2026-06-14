"""行业特异性估值 API"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from ..services.sector_valuation import analyze_bank_valuation, analyze_insurance_valuation

router = APIRouter()


class BankValuationRequest(BaseModel):
    current_price: float
    total_shares: float
    total_equity: float
    goodwill: float = 0
    intangible_assets: float = 0
    total_assets: float = 0
    net_interest_income: float = 0
    operating_income: float = 0
    net_profit: float = 0
    operating_expense: float = 0
    non_performing_loans: float = 0
    total_loans: float = 0
    loan_provisions: float = 0


class InsuranceValuationRequest(BaseModel):
    current_price: float
    total_shares: float
    embedded_value: float = 0
    new_business_value: float = 0
    net_profit: float = 0
    earned_premium: float = 0
    underwriting_expense: float = 0
    claims_expense: float = 0
    total_equity: float = 0


@router.post("/bank")
def bank_valuation(req: BankValuationRequest):
    """银行估值分析"""
    result = analyze_bank_valuation(
        current_price=req.current_price,
        total_shares=req.total_shares,
        total_equity=req.total_equity,
        goodwill=req.goodwill,
        intangible_assets=req.intangible_assets,
        total_assets=req.total_assets,
        net_interest_income=req.net_interest_income,
        operating_income=req.operating_income,
        net_profit=req.net_profit,
        operating_expense=req.operating_expense,
        non_performing_loans=req.non_performing_loans,
        total_loans=req.total_loans,
        loan_provisions=req.loan_provisions,
    )
    return result


@router.post("/insurance")
def insurance_valuation(req: InsuranceValuationRequest):
    """保险估值分析"""
    result = analyze_insurance_valuation(
        current_price=req.current_price,
        total_shares=req.total_shares,
        embedded_value=req.embedded_value,
        new_business_value=req.new_business_value,
        net_profit=req.net_profit,
        earned_premium=req.earned_premium,
        underwriting_expense=req.underwriting_expense,
        claims_expense=req.claims_expense,
        total_equity=req.total_equity,
    )
    return result
