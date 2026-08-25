"""FastAPI application entry point for the Autonomous Agentic Commerce Engine."""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from backend.database import init_db
from backend.routes import inventory, checkout
from backend.models import ErrorResponse
from backend.services.guardrails import SpendingLimitExceeded

# Resolve path to frontend directory
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'frontend')


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler — initializes DB on startup."""
    init_db()
    yield


app = FastAPI(
    title="Autonomous Agentic Commerce Engine",
    version="1.0.0",
    description="Headless M2M commerce engine allowing autonomous agents to make purchases within safety guardrails.",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(SpendingLimitExceeded)
async def spending_limit_exception_handler(request: Request, exc: SpendingLimitExceeded):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            error="SpendingLimitExceeded",
            detail=str(exc),
            max_allowed_paise=exc.max_paise,
            attempted_paise=exc.amount_paise
        ).model_dump()
    )


# ── API Routes ────────────────────────────────
app.include_router(inventory.router)
app.include_router(checkout.router)


# ── API Root ──────────────────────────────────
@app.get("/api")
def api_root():
    """API metadata endpoint for machine discovery."""
    return {
        "status": "online",
        "service": "Autonomous Agentic Commerce Engine",
        "version": "1.0.0",
        "endpoints": {
            "/api/inventory": "GET - Agent-readable product catalog",
            "/api/checkout": "POST - Execute purchase transaction",
            "/api/ledger": "GET - View audit trail"
        }
    }


# ── Frontend ──────────────────────────────────
@app.get("/")
def serve_dashboard():
    """Serve the dashboard frontend."""
    return FileResponse(os.path.join(FRONTEND_DIR, 'index.html'))


# Mount static files for any future assets (CSS, JS, images)
if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
