# =========================================================
# J TEC DOWNLOADER
# Docker configuration
# =========================================================

FROM python:3.12-slim

# ---------------------------------------------------------
# SYSTEM DEPENDENCIES
# ---------------------------------------------------------

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------
# WORKING DIRECTORY
# ---------------------------------------------------------

WORKDIR /app

# ---------------------------------------------------------
# PYTHON SETTINGS
# ---------------------------------------------------------

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# ---------------------------------------------------------
# INSTALL PYTHON DEPENDENCIES
# ---------------------------------------------------------

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------
# COPY APPLICATION
# ---------------------------------------------------------

COPY app ./app

# Create temporary download directory
RUN mkdir -p temp_downloads

# ---------------------------------------------------------
# PORT
# ---------------------------------------------------------

EXPOSE 8000

# ---------------------------------------------------------
# START SERVER
# ---------------------------------------------------------

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
