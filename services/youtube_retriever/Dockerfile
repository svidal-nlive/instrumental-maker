FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
    yt-dlp

# Copy application code
COPY config.py retriever.py job_producer.py main.py ./

# Create directories
RUN mkdir -p /data/logs /data/requests /tmp/ytdl_work \
    && mkdir -p /queues/youtube_audio /queues/youtube_video

# Set Python unbuffered for logging
ENV PYTHONUNBUFFERED=1

# Default to daemon mode (watch requests)
CMD ["python3", "main.py", "--daemon"]
