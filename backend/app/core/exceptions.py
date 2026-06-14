"""Custom exceptions and global exception handler for the API."""

import logging
import traceback
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


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
        logger.error(f"Unhandled error: {exc} path={request.url.path}\n{traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content={"error": "服务器内部错误，请稍后重试", "type": "InternalServerError"},
        )
