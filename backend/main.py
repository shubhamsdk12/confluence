"""
US Healthcare EDI Parser & X12 File Validator
FastAPI Application Entry Point
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from database.connection import init_db
from routes.parse import router as parse_router
from routes.validate import router as validate_router
from routes.ai import router as ai_router
from routes.reconcile import router as reconcile_router
from routes.delta import router as delta_router


# ---------------------------------------------------------------------------
# Startup / Shutdown lifecycle
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the database on startup."""
    await init_db()
    yield


app = FastAPI(
    title="US Healthcare EDI Parser & AI Validator",
    description="High-performance X12 EDI parser supporting 837P/I, 835, and 834 transactions",
    version="2.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS – allow React dev server
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "detail": str(exc),
            "code": "INTERNAL_SERVER_ERROR",
        },
    )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(parse_router, prefix="/api", tags=["Parsing"])
app.include_router(validate_router, prefix="/api", tags=["Validation"])
app.include_router(ai_router, prefix="/api", tags=["AI Intelligence"])
app.include_router(reconcile_router, prefix="/api", tags=["Reconciliation"])
app.include_router(delta_router, prefix="/api", tags=["Delta Engine"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "edi-parser", "version": "2.0.0"}
