from dotenv import load_dotenv
load_dotenv()

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.api import stocks, cb, scraper, bonds, index_valuation, dividend, cigar_butt, cross_analysis, value_investing, reit, macro, futures, jc_screener, polymarket, export_champions, grid, national_team, right_side, fund_holdings, decision, t_trading, backtest, fund_arb, futu_options, drawdown_control, daily_info, tractor, cb_backtest, valuation, quantdinger, portfolio, sector_valuation, crypto_master, quant_backtest, airdrop_scanner, crypto_crawler
from app.core.exceptions import register_exception_handlers
from app.core.security_middleware import ApiKeyMiddleware, SENSITIVE_PREFIXES

logger = logging.getLogger(__name__)

# 请求超时中间件 - 防止单个请求阻塞服务器过久
class RequestTimeoutMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await asyncio.wait_for(call_next(request), timeout=60)
        except asyncio.TimeoutError:
            logger.warning(f"请求超时: {request.method} {request.url.path}")
            return JSONResponse(
                status_code=504,
                content={"error": "请求处理超时，请稍后重试", "type": "RequestTimeout"}
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown hooks."""
    # Startup
    import threading
    from app.core.database import init_db
    from app.services.fund_service import FundService
    from app.services.akshare_service import AKShareService

    # 初始化 SQLite 数据库（建表 + 迁移旧 JSON 数据）
    try:
        init_db()
        logger.info("SQLite 数据库初始化完成")
    except Exception as e:
        logger.error(f"SQLite 数据库初始化失败: {e}")

    # 恢复集思录登录态
    try:
        FundService.restore_login()
        logger.info("集思录登录态恢复完成")
    except Exception as e:
        logger.warning(f"集思录登录态恢复失败: {e}")

    # 异步并行预热缓存
    def _warm():
        from concurrent.futures import ThreadPoolExecutor, as_completed
        try:
            svc = AKShareService()
            logger.info("开始预热缓存...")
            warmup_tasks = [
                svc.get_gdp_data,
                svc.get_cpi_data,
                svc.get_pmi_data,
                svc.get_lpr_data,
                svc.get_money_supply,
                svc.get_us_fed_rate,
                svc.get_us_gdp,
                svc.get_us_ism_pmi,
                svc.get_yield_curve,
            ]
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {executor.submit(fn): fn.__name__ for fn in warmup_tasks}
                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        logger.debug(f"预热 {futures[future]} 失败: {e}")
            logger.info("缓存预热完成")
        except Exception as e:
            logger.warning(f"缓存预热失败: {e}")

    threading.Thread(target=_warm, daemon=True).start()

    # 启动币圈情报定时搜集器
    try:
        from app.services.crypto_scheduler import start_crypto_crawler_scheduler
        start_crypto_crawler_scheduler(interval_minutes=30)
        logger.info("币圈情报搜集器已启动")
    except Exception as e:
        logger.warning(f"币圈情报搜集器启动失败: {e}")

    yield

    # Shutdown (if needed)


app = FastAPI(title="新源的Invest工具", version="1.0.0", lifespan=lifespan)

# 注册全局异常处理器
register_exception_handlers(app)

# 请求超时中间件（60秒）
app.add_middleware(RequestTimeoutMiddleware)

# CORS 配置 - 白名单模式，支持环境变量覆盖
_default_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]
_allowed_origins = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()
] or _default_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# API Key 认证中间件 - 保护敏感端点（tractor交易、portfolio组合等）
# 未设置 API_KEY 环境变量时不启用认证（本地开发零配置）
app.add_middleware(ApiKeyMiddleware, api_key=os.getenv("API_KEY", ""))

app.include_router(stocks.router, prefix="/api/stocks", tags=["stocks"])
app.include_router(cb.router, prefix="/api/cb", tags=["cb"])
app.include_router(scraper.router, prefix="/api/scraper", tags=["scraper"])
app.include_router(bonds.router, prefix="/api/bonds", tags=["bonds"])
app.include_router(index_valuation.router, prefix="/api/index-valuation", tags=["index-valuation"])

app.include_router(dividend.router, prefix="/api/dividend", tags=["dividend"])
app.include_router(cigar_butt.router, prefix="/api/cigar-butt", tags=["cigar-butt"])
app.include_router(cross_analysis.router, prefix="/api/cross-analysis", tags=["cross-analysis"])
app.include_router(value_investing.router, prefix="/api/value-investing", tags=["value-investing"])
app.include_router(valuation.router, prefix="/api/valuation", tags=["估值分析"])
app.include_router(reit.router, prefix="/api/reit", tags=["reit"])

app.include_router(macro.router, prefix="/api/macro", tags=["macro"])
app.include_router(futures.router, prefix="/api/futures", tags=["futures"])
app.include_router(jc_screener.router, prefix="/api/jc", tags=["金渐成体系"])
app.include_router(polymarket.router, prefix="/api/polymarket", tags=["Polymarket"])
app.include_router(export_champions.router, prefix="/api/export-champions", tags=["出口冠军"])
app.include_router(grid.router, prefix="/api/grid", tags=["网格交易"])

app.include_router(national_team.router, prefix="/api/national-team", tags=["国家队监控"])
app.include_router(right_side.router, prefix="/api/right-side", tags=["右侧交易"])
app.include_router(fund_holdings.router, prefix="/api/fund-holdings", tags=["基金持仓"])
app.include_router(decision.router, prefix="/api/decision", tags=["决策卫士"])
app.include_router(t_trading.router, prefix="/api/t-trading", tags=["做T交易系统"])
app.include_router(backtest.router, prefix="/api/backtest", tags=["策略回测"])
app.include_router(fund_arb.router, prefix="/api/fund-arb", tags=["LOF套利"])
app.include_router(futu_options.router, prefix="/api/futu-options", tags=["期权轮动(实战)"])
app.include_router(drawdown_control.router, prefix="/api/drawdown", tags=["回撤控制"])
app.include_router(daily_info.router, prefix="/api/daily-info", tags=["每日信息"])
app.include_router(tractor.router, prefix="/api/tractor", tags=["拖拉机套利"])
app.include_router(cb_backtest.router, prefix="/api/cb-backtest", tags=["可转债回测"])
app.include_router(quantdinger.router, tags=["QuantDinger AI分析"])
app.include_router(portfolio.router, prefix="/api/portfolio", tags=["组合管理"])
app.include_router(sector_valuation.router, prefix="/api/sector-valuation", tags=["行业估值"])
app.include_router(crypto_master.router, prefix="/api/crypto-master", tags=["币圈大师"])
app.include_router(quant_backtest.router, prefix="/api/quant", tags=["量化回测"])
app.include_router(airdrop_scanner.router, prefix="/api/airdrop-scanner", tags=["空投扫描器"])
app.include_router(crypto_crawler.router, prefix="/api/crypto-crawler", tags=["币圈情报搜集"])


@app.get("/")
async def root():
    return {"message": "新源的Invest工具 API"}


@app.get("/health")
async def health_check():
    """健康检查端点，用于移动端APP测试连接"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "service": "新源Invest API",
    }
