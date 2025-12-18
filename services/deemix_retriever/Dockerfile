"""Deemix Retriever Service Dockerfile

Provides a service container that:
1. Watches for Deezer download requests
2. Downloads music using Deemix (multi-threaded)
3. Produces standardized job bundles for the pipeline
4. Hands off to simple_runner via /queues/other/

Usage:
  docker build -t instrumental-deemix-retriever .
  docker run -it \
    -v /path/to/queues:/queues \
    -v /path/to/pipeline-data:/data \
    -e DEEMIX_QUALITY=FLAC \
    -e MAX_CONCURRENT_DEEMIX=2 \
    instrumental-deemix-retriever

Environment variables:
  - DEEMIX_QUALITY: Download quality (FLAC, MP3_320, MP3_128, etc.)
  - MAX_CONCURRENT_DEEMIX: Number of parallel downloads
  - WATCH_INTERVAL: Seconds between checking for new requests
  - DEEMIX_DOWNLOAD_TIMEOUT: Max seconds per download (default 1800)
  - LOG_LEVEL: Python logging level (DEBUG, INFO, WARNING, ERROR)
"""

FROM python:3.11-slim

LABEL maintainer="instrumental-maker"
LABEL description="Deemix Retriever Service for Deezer downloads"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy service files
COPY requirements.txt .
COPY config.py .
COPY retriever.py .
COPY job_producer.py .
COPY main.py .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create directories for runtime
RUN mkdir -p /queues/other /tmp/deemix_retriever /home/deemix/.cache/deemix /home/deemix/.config/deemix

# Set environment defaults
ENV LOG_LEVEL=INFO
ENV DEEMIX_QUALITY=FLAC
ENV MAX_CONCURRENT_DEEMIX=2
ENV WATCH_INTERVAL=10
ENV DEEMIX_DOWNLOAD_TIMEOUT=1800
ENV QUEUE_OTHER=/queues/other/
ENV DEEMIX_WORKING_DIR=/tmp/deemix_retriever

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import socket; socket.create_connection(('localhost', 9000), timeout=2)" || exit 1

# Run the service
CMD ["python", "-u", "main.py"]
