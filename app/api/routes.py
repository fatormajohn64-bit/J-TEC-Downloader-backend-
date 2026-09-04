"""
J TEC Downloader
API routes.
"""

from enum import Enum
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl


router = APIRouter()


# ---------------------------------------------------------
# DOWNLOAD TYPES
# ---------------------------------------------------------

class DownloadType(str, Enum):
    VIDEO = "video"
    AUDIO = "audio"


# ---------------------------------------------------------
# REQUEST MODELS
# ---------------------------------------------------------

class DownloadRequest(BaseModel):
    url: HttpUrl
    type: DownloadType = DownloadType.VIDEO
    quality: Optional[str] = "best"


# ---------------------------------------------------------
# HEALTH
# ---------------------------------------------------------

@router.get("/health")
async def api_health():
    return {
        "status": "healthy",
        "service": "J TEC Downloader API",
    }


# ---------------------------------------------------------
# MEDIA INFORMATION
# ---------------------------------------------------------

@router.post("/info")
async def media_info(request: DownloadRequest):
    """
    Retrieve information about the supplied media URL.

    The actual extraction logic will be implemented in
    services/downloader.py.
    """

    raise HTTPException(
        status_code=501,
        detail="Media information service is not implemented yet.",
    )


# ---------------------------------------------------------
# DOWNLOAD
# ---------------------------------------------------------

@router.post("/download")
async def download_media(request: DownloadRequest):
    """
    Start a media download.

    Supported modes:
        - video
        - audio
    """

    raise HTTPException(
        status_code=501,
        detail="Download service is not implemented yet.",
    )
