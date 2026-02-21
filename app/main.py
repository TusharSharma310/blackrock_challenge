"""
BlackRock Retirement Savings API
Main application entry point with FastAPI configuration,
middleware setup, security headers, and router registration.
"""
import time
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import uvicorn

from app.routers import transactions, returns, performance
from app.services.performance_service import performance_tracker


# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Application Lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    logger.info("Retirement Savings API starting up...")
    logger.info(f"Listening on port {os.getenv('PORT', '5477')}")
    yield
    logger.info("Retirement Savings API shutting down...")


# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="BlackRock Retirement Savings API",
    description=(
        "Production-grade API for automated retirement savings through "
        "expense-based micro-investments. Supports NPS and NIFTY 50 Index Fund "
        "investment vehicles with tax benefit calculations and inflation adjustments."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Middleware Stack
# ---------------------------------------------------------------------------

# CORS: Allow all origins for API usage (configure as needed for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip compression for large responses (threshold: 1KB)
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def performance_tracking_middleware(request: Request, call_next):
    """Track request performance metrics and add security headers."""
    start_time = time.time()

    response = await call_next(request)

    duration = time.time() - start_time
    performance_tracker.record_request(duration)

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Response-Time"] = f"{duration * 1000:.2f}ms"

    return response


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Log all incoming requests with method, path, and response time."""
    start = time.time()
    logger.info(f"{request.method} {request.url.path}")
    response = await call_next(request)
    elapsed = (time.time() - start) * 1000
    logger.info(f"{request.method} {request.url.path} → {response.status_code} ({elapsed:.2f}ms)")
    return response


# ---------------------------------------------------------------------------
# Exception Handlers
# ---------------------------------------------------------------------------

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors with clear error messages."""
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error["loc"])
        errors.append({
            "field": field,
            "message": error["msg"],
            "type": error["type"],
        })

    logger.warning(f"Validation error on {request.url.path}: {errors}")
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Request validation failed",
            "errors": errors,
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions gracefully."""
    logger.error(f"Unhandled exception on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal server error occurred. Please try again.",
        },
    )


# ---------------------------------------------------------------------------
# Router Registration
# ---------------------------------------------------------------------------

app.include_router(transactions.router)
app.include_router(returns.router)
app.include_router(performance.router)


# ---------------------------------------------------------------------------
# Health & Root Endpoints
# ---------------------------------------------------------------------------

@app.get("/", tags=["Health"])
async def root():
    """API root - health check endpoint."""
    return {
        "service": "BlackRock Retirement Savings API",
        "version": "1.0.0",
        "status": "healthy",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Detailed health check with system status."""
    metrics = performance_tracker.get_metrics()
    return {
        "status": "healthy",
        "memory": metrics["memory"],
        "threads": metrics["threads"],
        "uptime_seconds": time.time() - performance_tracker.start_time,
    }


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5477"))
    workers = int(os.getenv("WORKERS", "1"))

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        workers=workers,
        log_level="info",
        access_log=True,
        reload=False,
    )
