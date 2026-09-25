# Dockerfile for TUTUCO CLIP MINER (Unified Cloud & Local Container)
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8765 \
    ALLOW_REMOTE=true

WORKDIR /app

# Install system dependencies (FFmpeg, FFprobe, curl for healthchecks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project code
COPY . .

# Ensure runtime directories exist
RUN mkdir -p data/edited data/preview_cache logs config/campaigns

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8765/api/health || exit 1

EXPOSE 8765

# Launch app factory with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8765", "--workers", "1", "--threads", "8", "--timeout", "180", "app:create_app()"]
