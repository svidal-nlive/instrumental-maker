"""YouTube retriever service configuration."""

import os
from typing import Optional


def _env_clean(key: str, default: Optional[str] = None) -> str:
    """Return env var value with inline comments stripped and whitespace trimmed."""
    val = os.getenv(key, default)
    if val is None:
        return ""
    s = str(val)
    if "#" in s:
        s = s.split("#", 1)[0]
    return s.strip()


def env_bool(key: str, default: str = "false") -> bool:
    """Parse environment variable as boolean."""
    s = _env_clean(key, default).lower()
    return s in ("1", "true", "yes", "on")


class Config:
    """YouTube retriever configuration."""
    
    # Operating mode
    MODE = _env_clean("YTDL_MODE", "audio").lower()  # audio | video | both
    
    # Output queues (must be mounted)
    QUEUE_AUDIO = _env_clean("QUEUE_YOUTUBE_AUDIO", "/queues/youtube_audio")
    QUEUE_VIDEO = _env_clean("QUEUE_YOUTUBE_VIDEO", "/queues/youtube_video")
    
    # Audio format for extraction
    AUDIO_FORMAT = _env_clean("YTDL_AUDIO_FORMAT", "m4a").lower()  # m4a | flac | mp3 | wav
    
    # Duration validation (online vs downloaded)
    DURATION_TOL_SEC = float(_env_clean("YTDL_DURATION_TOL_SEC", "2.0") or 2.0)
    DURATION_TOL_PCT = float(_env_clean("YTDL_DURATION_TOL_PCT", "0.01") or 0.01)
    FAIL_ON_DURATION_MISMATCH = env_bool("YTDL_FAIL_ON_DURATION_MISMATCH", "true")
    
    # yt-dlp options
    YTDL_QUIET = env_bool("YTDL_QUIET", "false")
    YTDL_NO_WARNINGS = env_bool("YTDL_NO_WARNINGS", "false")
    YTDL_SOCKET_TIMEOUT = int(_env_clean("YTDL_SOCKET_TIMEOUT", "30") or 30)
    
    # Cookie file for authentication (optional)
    YTDL_COOKIES_FILE = _env_clean("YTDL_COOKIES_FILE", "")
    
    # Logging
    LOG_DIR = _env_clean("LOG_DIR", "/data/logs")
    LOG_LEVEL = _env_clean("LOG_LEVEL", "info").lower()
    
    # Work directory
    WORKING_DIR = _env_clean("WORKING_DIR", "/tmp/ytdl_work")
    
    # Request handling: watch a folder for download requests
    REQUESTS_DIR = _env_clean("REQUESTS_DIR", "/data/requests")
    
    # Metadata tags
    ARTIST_FALLBACK = _env_clean("ARTIST_FALLBACK", "Unknown")
    ALBUM_FALLBACK = _env_clean("ALBUM_FALLBACK", "YTDL")
