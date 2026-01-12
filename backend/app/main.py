"""
LLM Gateway Application Entry Point

FastAPI application main entry, including router registration and application configuration.
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

# Auth Router
app.include_router(auth_router)

# Register Admin Routers
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