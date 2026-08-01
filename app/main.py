"""
Application entry point: creates the FastAPI app, registers routers,
sets up CORS and global error handling, and creates DB tables on startup.
"""

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import auth, cryptocurrencies, watchlist
from app.core.config import settings
from app.db.database import Base, engine

# Create all tables on startup if they don't exist yet (fine for SQLite /
# a take-home assignment; a real production app would use migrations).
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "A backend API for a cryptocurrency dashboard: browse current rates, "
        "manage a personal watchlist, and view historical price data. "
        "Data is sourced from CoinGecko."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return a consistent, readable JSON body for validation (422) errors."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Validation error", "errors": exc.errors()},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Return a consistent JSON body for all HTTPExceptions raised in routes."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all for unexpected errors so clients always get valid JSON back."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred. Please try again later."},
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
