"""Configuration for Deemix Retriever service."""

import os
from pathlib import Path


class Config:
    """Load and provide access to configuration from environment."""
    
    def __init__(self):
        """Initialize config from environment variables."""
        # Service identity
        self.SERVICE_NAME = "deemix_retriever"
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        
        # Queue paths (mount points for job bundles)
        self.QUEUE_OTHER = os.getenv("QUEUE_OTHER", "/queues/other/")
        
        # Working directory for downloads and temporary files
        self.WORKING_DIR = os.getenv("DEEMIX_WORKING_DIR", "/tmp/deemix_retriever")
        
        # Deemix configuration
        self.DEEMIX_CACHE_DIR = os.getenv("DEEMIX_CACHE_DIR", "/home/deemix/.cache/deemix")
        self.DEEMIX_CONFIG_DIR = os.getenv("DEEMIX_CONFIG_DIR", "/home/deemix/.config/deemix")
        
        # Download settings
        self.DEEMIX_QUALITY = os.getenv("DEEMIX_QUALITY", "FLAC")  # FLAC, MP3_320, MP3_128, etc.
        self.DEEMIX_DOWNLOAD_TIMEOUT = int(os.getenv("DEEMIX_DOWNLOAD_TIMEOUT", "1800"))  # 30 min
        
        # Polling
        self.WATCH_INTERVAL = int(os.getenv("WATCH_INTERVAL", "10"))  # seconds
        self.MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT_DEEMIX", "2"))
        
        # Error handling
        self.SKIP_ON_ERROR = os.getenv("SKIP_ON_ERROR", "true").lower() == "true"
        self.MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
        
        # Optional: Artist/album metadata enrichment
        self.ENRICH_METADATA = os.getenv("ENRICH_METADATA", "true").lower() == "true"
        
        # Optional: Metadata enrichment from MusicBrainz
        self.MUSICBRAINZ_ENABLED = os.getenv("MUSICBRAINZ_ENABLED", "false").lower() == "true"
        self.MUSICBRAINZ_TIMEOUT = int(os.getenv("MUSICBRAINZ_TIMEOUT", "10"))
    
    def ensure_directories(self):
        """Create necessary directories."""
        dirs = [
            self.QUEUE_OTHER,
            self.WORKING_DIR,
            self.DEEMIX_CACHE_DIR,
            self.DEEMIX_CONFIG_DIR,
        ]
        for d in dirs:
            Path(d).mkdir(parents=True, exist_ok=True)
    
    def to_dict(self):
        """Return config as dict for logging."""
        return {
            "SERVICE_NAME": self.SERVICE_NAME,
            "LOG_LEVEL": self.LOG_LEVEL,
            "QUEUE_OTHER": self.QUEUE_OTHER,
            "WORKING_DIR": self.WORKING_DIR,
            "DEEMIX_QUALITY": self.DEEMIX_QUALITY,
            "MAX_CONCURRENT": self.MAX_CONCURRENT,
            "ENRICH_METADATA": self.ENRICH_METADATA,
            "MUSICBRAINZ_ENABLED": self.MUSICBRAINZ_ENABLED,
        }
