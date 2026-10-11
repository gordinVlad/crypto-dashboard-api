"""
Application entry point: creates the FastAPI app, registers routers,
sets up CORS and global error handling.
"""

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import auth, cryptocurrencies, watchlist
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestContextLogMiddleware

configure_logging()
logger = get_logger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "A backend API for a cryptocurrency dashboard: browse current rates, "
        "manage a personal watchlist, and view historical price data. "
        "Data is sourced from CoinGecko."
    ),
    version="1.0.0",
)

logger.info(
    "application starting",
    extra={"app_name": settings.APP_NAME, "environment": settings.ENVIRONMENT},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# Registered after CORSMiddleware so it becomes the outermost layer (Starlette
# applies middleware in reverse-registration order), ensuring every request -
# including CORS-rejected ones - gets a request id and an access-log line.
app.add_middleware(RequestContextLogMiddleware)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return a consistent, readable JSON body for validation (422) errors."""
    logger.warning(
        "request validation failed",
        extra={"method": request.method, "path": request.url.path, "errors": exc.errors()},
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Validation error", "errors": exc.errors()},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Return a consistent JSON body for all HTTPExceptions raised in routes."""
    level = logger.error if exc.status_code >= 500 else logger.warning
    level(
        "http exception raised",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": exc.status_code,
            "detail": exc.detail,
        },
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all for unexpected errors so clients always get valid JSON back."""
    logger.exception(
        "unhandled exception while processing request",
        extra={"method": request.method, "path": request.url.path},
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An unexpected error occurred. Please try again later.",
            "request_id": getattr(request.state, "request_id", None),
        },
    )


app.include_router(auth.router)
app.include_router(cryptocurrencies.router)
app.include_router(watchlist.router)


@app.get("/", tags=["health"])
def root():
    """Basic health check / welcome endpoint."""
    return {
        "status": "ok",
        "name": settings.APP_NAME,
        "docs": "/docs",
    }


@app.get("/health", tags=["health"])
def health():
    """Health check endpoint, useful for deployment platforms."""
    return {"status": "healthy"}
