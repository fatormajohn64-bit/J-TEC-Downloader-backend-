# J TEC Downloader

J TEC Downloader is a mobile-first media downloading service designed to
retrieve supported online video and audio content.

## Features

- Video downloads
- Audio-only downloads
- Best available video quality
- Video and audio stream merging
- FFmpeg media processing
- Temporary file cleanup
- FastAPI REST API
- Docker deployment
- Render-ready backend

## Project Structure

```text
j-tec-downloader/
│
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   └── downloader.py
│   │
│   └── utils/
│       ├── __init__.py
│       └── cleanup.py
│
├── temp_downloads/
├── requirements.txt
├── Dockerfile
└── README.md
