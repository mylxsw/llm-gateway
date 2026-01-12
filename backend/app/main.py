"""
LLM Gateway 应用入口

FastAPI 应用主入口，包含路由注册和应用配置。
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.logging_config import setup_logging
from app.db.session import init_db
from app.common.errors import AppError
from app.api.proxy import openai_router, anthropic_router
from app.api.admin import providers_router, models_router, api_keys_router, logs_router
from app.scheduler import start_scheduler, shutdown_scheduler


# 初始化日志配置
setup_logging()


# 应用生命周期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理

    启动时初始化数据库，关闭时清理资源。
    """
    # 启动时
    await init_db()
    start_scheduler()
    yield
    # 关闭时
    shutdown_scheduler()


# 创建 FastAPI 应用
settings = get_settings()
app = FastAPI(
    title=settings.APP_NAME,
    description="兼容 OpenAI/Anthropic 的 LLM 代理网关服务",
    version="0.1.0",
    lifespan=lifespan,
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 全局异常处理
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    """
    处理应用自定义异常
    """
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    处理未捕获的异常
    """
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": "Internal server error",
                "type": "internal_error",
                "code": "internal_error",
            }
        },
    )


# 健康检查端点
@app.get("/health", tags=["Health"])
async def health_check():
    """
    健康检查
    
    用于服务存活探测。
    """
    return {"status": "healthy"}


@app.get("/", tags=["Health"])
async def root():
    """
    根路径
    
    返回服务基本信息。
    """
    return {
        "name": settings.APP_NAME,
        "version": "0.1.0",
        "description": "LLM Gateway - 模型路由与代理服务",
    }


# 注册代理路由
app.include_router(openai_router)
app.include_router(anthropic_router)

# 注册管理路由
app.include_router(providers_router)
app.include_router(models_router)
app.include_router(api_keys_router)
app.include_router(logs_router)


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
