"""
LLM Gateway Application Entry Point

FastAPI application main entry, including router registration and application configuration.
"""

import logging
import os
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.routing import APIRouter
from fastapi.staticfiles import StaticFiles

from app.api.admin import api_keys_router, logs_router, models_router, providers_router
from app.api.auth import router as auth_router
from app.api.proxy import anthropic_router, openai_router
from app.common.errors import AppError
from app.config import get_settings
from app.db.redis import close_redis, init_redis
from app.db.session import init_db
from app.logging_config import setup_logging
from app.middleware.rate_limit import RateLimitMiddleware
from app.scheduler import shutdown_scheduler, start_scheduler

logger = logging.getLogger(__name__)

# Initialize logging configuration
setup_logging()


# Application Lifecycle Management
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application Lifecycle Management

    Initialize database on startup, clean up resources on shutdown.
    """
    # Startup
    await init_db()
    settings = get_settings()
    if settings.KV_STORE_TYPE == "redis":
        await init_redis()
    start_scheduler()
    yield
    # Shutdown
    shutdown_scheduler()
    if settings.KV_STORE_TYPE == "redis":
        await close_redis()


# Create FastAPI application
settings = get_settings()

repo_root = Path(__file__).resolve().parents[3]
default_frontend_dist = repo_root / "frontend" / "out"
frontend_dist_dir = Path(os.getenv("FRONTEND_DIST_DIR", str(default_frontend_dist)))
frontend_enabled = (
    frontend_dist_dir.exists() and (frontend_dist_dir / "index.html").exists()
)

app = FastAPI(
    title=settings.APP_NAME,
    description="LLM Proxy Gateway Service compatible with OpenAI/Anthropic",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
# Parse ALLOWED_ORIGINS from comma-separated string to list
allowed_origins_str = settings.ALLOWED_ORIGINS.strip()
if allowed_origins_str:
    allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",") if origin.strip()]
else:
    # In development mode with DEBUG=True, allow localhost origins
    # In production, empty list means no CORS
    if settings.DEBUG:
        allowed_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
    else:
        allowed_origins = []

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add Rate Limit Middleware (should be added after CORS)
app.add_middleware(RateLimitMiddleware)
logger.info(f"Rate limiting enabled: {settings.RATE_LIMIT_ENABLED}")


# Global Exception Handler
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    """
    Handle application custom exceptions

    In production mode, error details are hidden to prevent information leakage.
    """
    settings = get_settings()
    # Hide details in production mode
    include_details = settings.DEBUG
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(include_details=include_details),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Handle uncaught exceptions

    In production mode, stack traces and error details are logged but not returned to clients.
    """
    settings = get_settings()
    # Log the full error for debugging
    logger.error(
        "Uncaught exception: %s\nPath: %s\nTraceback:\n%s",
        str(exc),
        request.url.path,
        traceback.format_exc(),
    )

    # In debug mode, return detailed error information
    if settings.DEBUG:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "message": str(exc),
                    "type": type(exc).__name__,
                    "code": "internal_error",
                    "traceback": traceback.format_exc().split("\n"),
                }
            },
        )

    # In production, return generic error message
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


# Health Check Endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health Check

    Used for service liveness probe.
    """
    return {"status": "healthy"}


@app.get("/", tags=["Health"])
async def root():
    """
    Root Path

    When the frontend static bundle exists, serve the dashboard homepage.
    Otherwise, return basic service information (API-only mode).
    """
    if frontend_enabled:
        return FileResponse(frontend_dist_dir / "index.html")
    return {
        "name": settings.APP_NAME,
        "version": "0.1.0",
        "description": "LLM Gateway - Model Routing & Proxy Service",
    }


# Register Proxy Routers
app.include_router(openai_router)
app.include_router(anthropic_router)

# Admin/Auth API (prefixed) — keep proxy endpoints (/v1/...) unchanged.
api_router = APIRouter(prefix="/api")
api_router.include_router(auth_router)
api_router.include_router(providers_router)
api_router.include_router(models_router)
api_router.include_router(api_keys_router)
api_router.include_router(logs_router)
app.include_router(api_router)


class FrontendStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if response.status_code != 404:
            return response

        # Never serve SPA fallback for API/proxy paths.
        if path == "api" or path.startswith("api/"):
            return response
        if path == "v1" or path.startswith("v1/"):
            return response

        # Serve /foo as /foo.html (Next static export).
        if path and "." not in Path(path).name:
            html_path = Path(self.directory) / f"{path}.html"
            if html_path.exists():
                return await super().get_response(f"{path}.html", scope)

        # Serve /foo as /foo/index.html when exporting directories.
        if path and "." not in Path(path).name:
            index_path = Path(self.directory) / path / "index.html"
            if index_path.exists():
                return await super().get_response(f"{path}/index.html", scope)

        # SPA fallback (keeps the dashboard usable on refresh / direct-link).
        return await super().get_response("index.html", scope)


if frontend_enabled:
    app.mount(
        "/",
        FrontendStaticFiles(directory=str(frontend_dist_dir), html=True),
        name="frontend",
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
