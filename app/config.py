import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "J-TEC Downloader API"
    VERSION: str = "1.0.0"
    TEMP_DIR: str = os.path.join(os.getcwd(), "temp_downloads")
    
settings = Settings()

# Ensure temp directory exists on startup
os.makedirs(settings.TEMP_DIR, exist_ok=True)
