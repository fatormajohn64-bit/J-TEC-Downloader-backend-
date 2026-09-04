"""
J TEC Downloader
Main FastAPI application entry point.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router


# ---------------------------------------------------------
# APPLICATION
# ---------------------------------------------------------

app = FastAPI(
    title="J TEC Downloader API",
    description=(
        "Media downloader API for supported video and audio sources."
    ),
    version="1.0.0",
)


# ---------------------------------------------------------
# CORS
# ---------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# ROUTES
# ---------------------------------------------------------

app.include_router(
    router,
    prefix="/api",
)


# ---------------------------------------------------------
# ROOT
# ---------------------------------------------------------

@app.get("/")
async def root():
    return {
        "name": "J TEC Downloader",
        "status": "online",
        "version": "1.0.0",
    }


# ---------------------------------------------------------
# HEALTH CHECK
# ---------------------------------------------------------

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
    }
