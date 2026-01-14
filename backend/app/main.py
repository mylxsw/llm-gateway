"""
LLM Gateway Application Entry Point

FastAPI application main entry, including router registration and application configuration.
"""

from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.routing import APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.logging_config import setup_logging
from app.db.session import init_db
from app.common.errors import AppError
from app.api.proxy import openai_router, anthropic_router
from app.api.admin import providers_router, models_router, api_keys_router, logs_router
from app.api.auth import router as auth_router
from app.scheduler import start_scheduler, shutdown_scheduler


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
    start_scheduler()
    yield
    # Shutdown
    shutdown_scheduler()


# Create FastAPI application
settings = get_settings()
app = FastAPI(
    title=settings.APP_NAME,
    description="LLM Proxy Gateway Service compatible with OpenAI/Anthropic",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Should restrict specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global Exception Handler
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    """
    Handle application custom exceptions
    """
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Handle uncaught exceptions
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
    
    Returns basic service information.
    """
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


repo_root = Path(__file__).resolve().parents[3]
default_frontend_dist = repo_root / "frontend" / "out"
frontend_dist_dir = Path(os.getenv("FRONTEND_DIST_DIR", str(default_frontend_dist)))

if frontend_dist_dir.exists() and (frontend_dist_dir / "index.html").exists():
    app.mount("/", FrontendStaticFiles(directory=str(frontend_dist_dir), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
