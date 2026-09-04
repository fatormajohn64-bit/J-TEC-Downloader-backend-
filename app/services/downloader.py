import os
import glob
import yt_dlp
from app.config import settings

def extract_video_info(url: str) -> dict:
    """Extract metadata without downloading the file."""
    ydl_opts = {'quiet': True, 'no_warnings': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)

def process_download(url: str, output_dir: str) -> str:
    """Downloads media stream and returns the absolute local file path."""
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    downloaded_files = glob.glob(os.path.join(output_dir, "*"))
    if not downloaded_files:
        raise Exception("File extraction failed.")
        
    return downloaded_files[0]
  
