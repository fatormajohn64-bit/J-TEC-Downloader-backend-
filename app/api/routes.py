"""
J TEC Downloader
API routes.
"""

import threading
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl

from app.services.downloader import (
    DownloaderError,
    downloader_service,
)


router = APIRouter()


# =========================================================
# DOWNLOAD JOB STORAGE
# =========================================================

DOWNLOAD_JOBS: dict[str, dict[str, Any]] = {}

JOBS_LOCK = threading.Lock()


# =========================================================
# REQUEST MODEL
# =========================================================

class DownloadRequest(BaseModel):
    url: HttpUrl
    type: str = "video"
    quality: Optional[str] = "best"


# =========================================================
# HEALTH
# =========================================================

@router.get("/health")
async def api_health():
    return {
        "status": "healthy",
        "service": "J TEC Downloader API",
    }


# =========================================================
# MEDIA INFO
# =========================================================

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


# =========================================================
# START DOWNLOAD
# =========================================================

@router.post("/download")
def start_download(request: DownloadRequest):
    """
    Start a background download job.

    Returns immediately with a job ID that the frontend
    can use to monitor progress.
    """

    if request.type not in {"video", "audio"}:
        raise HTTPException(
            status_code=400,
            detail="Download type must be 'video' or 'audio'.",
        )

    job_id = uuid.uuid4().hex

    with JOBS_LOCK:
        DOWNLOAD_JOBS[job_id] = {
            "id": job_id,
            "status": "queued",
            "progress": 0.0,
            "downloaded_bytes": 0,
            "total_bytes": None,
            "speed": None,
            "eta": None,
            "file_path": None,
            "error": None,
        }

    thread = threading.Thread(
        target=_run_download_job,
        args=(
            job_id,
            str(request.url),
            request.type,
            request.quality or "best",
        ),
        daemon=True,
    )

    thread.start()

    return {
        "success": True,
        "job_id": job_id,
        "status": "queued",
    }


# =========================================================
# DOWNLOAD STATUS / PROGRESS
# =========================================================

@router.get("/download/{job_id}")
def download_status(job_id: str):
    """
    Return the current progress of a download job.
    """

    with JOBS_LOCK:
        job = DOWNLOAD_JOBS.get(job_id)

        if job is None:
            raise HTTPException(
                status_code=404,
                detail="Download job not found.",
            )

        return {
            "success": True,
            "data": {
                "id": job["id"],
                "status": job["status"],
                "progress": job["progress"],
                "downloaded_bytes":
                    job["downloaded_bytes"],
                "total_bytes":
                    job["total_bytes"],
                "speed":
                    job["speed"],
                "eta":
                    job["eta"],
                "error":
                    job["error"],
                "ready":
                    job["status"] == "finished",
            },
        }


# =========================================================
# DOWNLOAD FILE
# =========================================================

@router.get("/download/{job_id}/file")
def download_file(job_id: str):
    """
    Return the completed downloaded file.
    """

    with JOBS_LOCK:
        job = DOWNLOAD_JOBS.get(job_id)

        if job is None:
            raise HTTPException(
                status_code=404,
                detail="Download job not found.",
            )

        if job["status"] != "finished":
            raise HTTPException(
                status_code=409,
                detail="Download is not finished yet.",
            )

        file_path_value = job["file_path"]

    if not file_path_value:
        raise HTTPException(
            status_code=404,
            detail="Downloaded file could not be found.",
        )

    file_path = Path(file_path_value)

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Downloaded file no longer exists.",
        )

    media_type = _get_media_type(file_path)

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=file_path.name,
    )


# =========================================================
# BACKGROUND DOWNLOAD WORKER
# =========================================================

def _run_download_job(
    job_id: str,
    url: str,
    download_type: str,
    quality: str,
) -> None:
    """
    Execute a download in the background.
    """

    _update_job(
        job_id,
        status="downloading",
    )

    def progress_callback(data: dict[str, Any]) -> None:
        status = data.get("status")

        if status == "downloading":
            _update_job(
                job_id,
                status="downloading",
                progress=_safe_float(
                    data.get("progress"),
                    0.0,
                ),
                downloaded_bytes=data.get(
                    "downloaded_bytes"
                ),
                total_bytes=data.get(
                    "total_bytes"
                ),
                speed=data.get("speed"),
                eta=data.get("eta"),
            )

        elif status == "finished":
            _update_job(
                job_id,
                progress=100.0,
                downloaded_bytes=data.get(
                    "downloaded_bytes"
                ),
                total_bytes=data.get(
                    "total_bytes"
                ),
                speed=data.get("speed"),
                eta=0,
            )

    try:
        file_path = downloader_service.download(
            url=url,
            download_type=download_type,
            quality=quality,
            progress_callback=progress_callback,
        )

        if not file_path.exists():
            raise DownloaderError(
                "Downloaded file could not be found."
            )

        _update_job(
            job_id,
            status="finished",
            progress=100.0,
            file_path=str(file_path),
            error=None,
        )

    except DownloaderError as exc:
        _update_job(
            job_id,
            status="error",
            error=str(exc),
        )

    except Exception:
        _update_job(
            job_id,
            status="error",
            error=(
                "Unable to download this media."
            ),
        )


# =========================================================
# JOB STATE HELPER
# =========================================================

def _update_job(
    job_id: str,
    **updates: Any,
) -> None:
    """
    Safely update a download job.
    """

    with JOBS_LOCK:
        job = DOWNLOAD_JOBS.get(job_id)

        if job is None:
            return

        job.update(updates)


# =========================================================
# SAFE FLOAT
# =========================================================

def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """
    Convert a value to float safely.
    """

    try:
        return float(value)
    except (
        TypeError,
        ValueError,
    ):
        return default


# =========================================================
# MIME TYPE
# =========================================================

def _get_media_type(
    file_path: Path,
) -> str:
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
