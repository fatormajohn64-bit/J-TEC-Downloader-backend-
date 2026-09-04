"""
J TEC Downloader
API routes.
"""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl

from app.services.downloader import (
    DownloaderError,
    downloader_service,
)


router = APIRouter()


class DownloadRequest(BaseModel):
    url: HttpUrl
    type: str = "video"
    quality: Optional[str] = "best"


@router.get("/health")
async def api_health():
    return {
        "status": "healthy",
        "service": "J TEC Downloader API",
    }


@router.post("/info")
def media_info(request: DownloadRequest):
    """
    Get information about a supported media URL.
    """

    try:
        info = downloader_service.get_info(
            str(request.url)
        )

        return {
            "success": True,
            "data": info,
        }

    except DownloaderError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Unable to process this media URL.",
        ) from exc


@router.post("/download")
def download_media(
    request: DownloadRequest,
    background_tasks: BackgroundTasks,
):
    """
    Download the requested media and return the file.
    """

    if request.type not in {"video", "audio"}:
        raise HTTPException(
            status_code=400,
            detail="Download type must be 'video' or 'audio'.",
        )

    try:
        file_path = downloader_service.download(
            url=str(request.url),
            download_type=request.type,
            quality=request.quality or "best",
        )

    except DownloaderError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Unable to download this media.",
        ) from exc

    if not file_path.exists():
        raise HTTPException(
            status_code=500,
            detail="Downloaded file could not be found.",
        )

    media_type = _get_media_type(file_path)

    # Remove the temporary file after it has been sent.
    background_tasks.add_task(
        _delete_file,
        file_path,
    )

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=file_path.name,
        background=background_tasks,
    )


def _get_media_type(file_path: Path) -> str:
    """
    Determine the response MIME type.
    """

    extension = file_path.suffix.lower()

    media_types = {
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".mkv": "video/x-matroska",
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".aac": "audio/aac",
        ".wav": "audio/wav",
        ".ogg": "audio/ogg",
    }

    return media_types.get(
        extension,
        "application/octet-stream",
    )


def _delete_file(file_path: Path) -> None:
    """
    Safely remove a temporary downloaded file.
    """

    try:
        if file_path.exists():
            file_path.unlink()
    except (FileNotFoundError, PermissionError, OSError):
        pass
