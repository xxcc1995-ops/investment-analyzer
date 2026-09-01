"""Security middleware: API Key authentication for sensitive endpoints."""

import hmac
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# 需要认证的敏感路由前缀（交易、组合管理、写操作、爬虫等）
# 注意：仅当 API_KEY 环境变量已设置时才生效；本地零配置默认跳过。
SENSITIVE_PREFIXES = (
    "/api/portfolio",
    "/api/futu-options",
    "/api/grid",
    "/api/cb",
    "/api/fund-arb",
    "/api/scraper",
    "/api/t-trading",
    "/api/decision",
    "/api/cb-backtest",
    "/api/airdrop-scanner",
    "/api/crypto-master",
    "/api/national-team",
    "/api/right-side",
    "/api/fund-holdings",
    "/api/relative-valuation",
    "/api/polymarket",
    "/api/crypto-crawler",
    "/api/t-realtime",
)

# 始终放行的路径（健康检查、根路径、OPTIONS预检、API文档）
PUBLIC_PATHS = frozenset({"/", "/health", "/docs", "/openapi.json", "/redoc"})


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """
    轻量级 API Key 认证中间件。

    工作方式:
    - 当 api_key 为空时（未设置环境变量），中间件不做任何拦截，零配置即可本地开发。
    - 当 api_key 已设置时，访问 SENSITIVE_PREFIXES 中的路径必须在请求头
      `X-API-Key` 中携带正确的 key，否则返回 401。
    - 公开路径（健康检查、文档等）始终放行。
    - OPTIONS 预检请求始终放行。
    - 使用 hmac.compare_digest 进行常数时间比较，避免计时攻击。
    """

    def __init__(self, app, api_key: str = ""):
        super().__init__(app)
        self.api_key = api_key
        if api_key:
            logger.info("API Key 认证已启用，保护路径: %s", ", ".join(SENSITIVE_PREFIXES))
        else:
            logger.info("API Key 未设置，敏感端点认证已跳过（仅本地开发安全）")

    async def dispatch(self, request: Request, call_next):
        # 未配置 key → 直接放行
        if not self.api_key:
            return await call_next(request)

        path = request.url.path

        # 公开路径 & OPTIONS 预检 → 放行
        if path in PUBLIC_PATHS or request.method == "OPTIONS":
            return await call_next(request)

        # 非敏感路径 → 放行
        if not path.startswith(SENSITIVE_PREFIXES):
            return await call_next(request)

        # 敏感路径 → 校验 API Key（常数时间比较，防计时攻击）
        provided_key = request.headers.get("X-API-Key", "")
        if hmac.compare_digest(provided_key, self.api_key):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        logger.warning("API Key 认证失败: path=%s, ip=%s", path, client_ip)
        return JSONResponse(
            status_code=401,
            content={"error": "未授权：缺少或错误的 API Key", "type": "Unauthorized"},
        )
