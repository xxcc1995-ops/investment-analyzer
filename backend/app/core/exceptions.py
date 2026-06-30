"""Custom exceptions and global exception handler for the API."""

import logging
import re
import traceback
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# 敏感信息过滤正则
_SENSITIVE_PATTERNS = [
    (re.compile(r'(password|passwd|secret|token|api_key|apikey)["\s]*[:=]\s*[^\s,}]+', re.IGNORECASE), r'\1=***'),
    (re.compile(r'(Bearer)\s+[A-Za-z0-9\-._~+/]+=*', re.IGNORECASE), r'\1 ***'),
]


def _sanitize_text(text: str) -> str:
    """过滤日志中的敏感信息。"""
    for pattern, replacement in _SENSITIVE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class AppError(Exception):
    """Base application error."""

    def __init__(self, message: str, status_code: int = 500, detail: str = None):
        self.message = message
        self.status_code = status_code
        self.detail = detail or message
        super().__init__(self.message)


class NotFoundError(AppError):
    """Resource not found."""

    def __init__(self, message: str = "资源未找到"):
        super().__init__(message, status_code=404)


class ValidationError(AppError):
    """Input validation error."""

    def __init__(self, message: str = "输入数据无效"):
        super().__init__(message, status_code=400)


class ExternalServiceError(AppError):
    """External API or service error."""

    def __init__(self, message: str = "外部服务调用失败", service: str = None):
        self.service = service
        super().__init__(message, status_code=502)


class AuthenticationError(AppError):
    """Authentication error."""

    def __init__(self, message: str = "认证失败"):
        super().__init__(message, status_code=401)


class RateLimitError(AppError):
    """Rate limit exceeded."""

    def __init__(self, message: str = "请求过于频繁，请稍后再试"):
        super().__init__(message, status_code=429)


def register_exception_handlers(app: FastAPI):
    """Register global exception handlers on the FastAPI app."""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        """Handle custom application errors."""
        logger.warning(f"AppError: {exc.message} (status={exc.status_code}) path={request.url.path}")
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.detail, "type": type(exc).__name__},
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Handle all unhandled exceptions."""
        safe_traceback = _sanitize_text(traceback.format_exc())
        logger.error(f"Unhandled error: {exc} path={request.url.path}\n{safe_traceback}")
        return JSONResponse(
            status_code=500,
            content={"error": "服务器内部错误，请稍后重试", "type": "InternalServerError"},
        )
