"""
SynthQuant API - Main Application Entry Point

A FastAPI-based synthetic market data generation service.
Uses Geometric Brownian Motion (GBM) to generate realistic price paths.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import APP_NAME, APP_VERSION, APP_DESCRIPTION
from app.routers import v1, admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    # Startup
    print(f"🚀 {APP_NAME} v{APP_VERSION} starting up...")
    print("📊 Synthetic market data generation service ready.")
    print("📖 API documentation available at /docs")
    yield
    # Shutdown
    print(f"👋 {APP_NAME} shutting down...")


# Create FastAPI application
app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=APP_DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(v1.router)
app.include_router(admin.router)


@app.get("/", tags=["root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": APP_NAME,
        "version": APP_VERSION,
        "description": APP_DESCRIPTION,
        "docs": "/docs",
        "health": "/v1/status",
    }


@app.get("/health", tags=["root"])
async def health_check():
    """Simple health check endpoint."""
    return {"status": "healthy"}
