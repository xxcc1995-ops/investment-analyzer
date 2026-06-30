"""Input validation utilities for API parameters."""

import re
from fastapi import HTTPException

# 股票代码格式：6位数字（A股）、HK.XXXXXX（港股）、US.XXXXXX（美股）
_STOCK_CODE_PATTERN = re.compile(r"^[A-Za-z]{0,3}\.?[A-Za-z0-9]{1,10}$")
# 搜索关键词：允许中英文、数字、字母、点号，最多30字符
_KEYWORD_PATTERN = re.compile(r"^[\u4e00-\u9fa5A-Za-z0-9.\s]+$")


def validate_stock_code(code: str) -> str:
    """验证股票代码格式，防止注入攻击。"""
    if not code or len(code) > 20:
        raise HTTPException(status_code=400, detail="股票代码格式无效")
    if not _STOCK_CODE_PATTERN.match(code):
        raise HTTPException(status_code=400, detail="股票代码包含非法字符")
    return code


def validate_keyword(keyword: str) -> str:
    """验证搜索关键词格式。"""
    if not keyword or len(keyword) > 30:
        raise HTTPException(status_code=400, detail="关键词格式无效")
    if not _KEYWORD_PATTERN.match(keyword):
        raise HTTPException(status_code=400, detail="关键词包含非法字符")
    return keyword
