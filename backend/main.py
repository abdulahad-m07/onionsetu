# backend/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.config.settings import settings
from backend.app.config.database import init_db
from backend.app.middleware.error_handler import (
    http_exception_handler,
    validation_exception_handler,
    generic_exception_handler,
)
from backend.app.routes import health, auth, scans, reports, disputes, sync, audit, admin, inference, batch, verify

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables on startup
    await init_db()
    yield

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="FastAPI Backend for OnionSetu AI Quality Assessment, Offline Sync, SHA-256 Audit Trail, and APMC Procurement Management.",
    lifespan=lifespan,
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception Handlers
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Include Routers with /v1 Prefix
app.include_router(health.router, prefix="/v1")
app.include_router(auth.router, prefix="/v1")
app.include_router(scans.router, prefix="/v1")
app.include_router(reports.router, prefix="/v1")
app.include_router(disputes.router, prefix="/v1")
app.include_router(sync.router, prefix="/v1")
app.include_router(audit.router, prefix="/v1")
app.include_router(admin.router, prefix="/v1")
app.include_router(inference.router, prefix="/v1")
app.include_router(batch.router, prefix="/v1")
app.include_router(verify.router, prefix="/v1")

# Root health alias for localhost smoke tests (the versioned
# GET /v1/health from the health router is preserved).
@app.get("/health", tags=["Health"])
async def root_health():
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
