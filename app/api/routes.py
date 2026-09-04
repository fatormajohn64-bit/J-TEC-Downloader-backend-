import os
import tempfile
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl

from app.config import settings
from app.services.downloader import extract_video_info, process_download
from app.utils.cleanup import remove_temp_folder

router = APIRouter()

class DownloadRequest(BaseModel):
    url: HttpUrl

@router.get("/health")
def health_check():
    return {"status": "online", "app": settings.APP_NAME, "version": settings.VERSION}

@router.post("/info")
def get_info(request: DownloadRequest):
    try:
        info = extract_video_info(str(request.url))
        return {
            "title": info.get("title"),
            "duration": info.get("duration"),
            "thumbnail": info.get("thumbnail"),
            "uploader": info.get("uploader"),
            "platform": info.get("extractor_key")
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch metadata: {str(e)}")

@router.post("/download")
def download_media(request: DownloadRequest, background_tasks: BackgroundTasks):
    # Unique sub-folder per request to prevent file collision
    request_temp_dir = tempfile.mkdtemp(dir=settings.TEMP_DIR)
    
    try:
        file_path = process_download(str(request.url), request_temp_dir)
        file_name = os.path.basename(file_path)

        # Cleanup isolated folder after streaming finishes
        background_tasks.add_task(remove_temp_folder, request_temp_dir)

        return FileResponse(
            path=file_path,
            filename=file_name,
            media_type="application/octet-stream"
        )
    except Exception as e:
        remove_temp_folder(request_temp_dir)
        raise HTTPException(status_code=400, detail=f"Download failed: {str(e)}")
      
