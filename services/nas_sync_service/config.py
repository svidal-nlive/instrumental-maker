"""
Configuration for NAS Sync service.

Reads environment variables to configure:
- What to watch (outputs directory)
- How to sync (rsync, S3, SCP, etc.)
- Where to route artifacts (by kind + variant)
"""

import os
from typing import Dict, Any, List
import json
import logging

logger = logging.getLogger(__name__)

# Core paths
OUTPUTS_DIR = os.getenv("OUTPUTS_DIR", "/data/outputs")
WORK_DIR = os.getenv("NAS_SYNC_WORK_DIR", "/data/nas-sync-work")
LOG_FILE = os.getenv("NAS_SYNC_LOG_FILE", "/data/logs/nas-sync.jsonl")

# Sync mechanism
SYNC_METHOD = os.getenv("NAS_SYNC_METHOD", "rsync")  # "rsync", "s3", "scp", "local"

# Remote root paths (base directories for each artifact kind)
REMOTE_ROOTS = {
    "audio": os.getenv("NAS_REMOTE_ROOT_AUDIO", ""),
    "video": os.getenv("NAS_REMOTE_ROOT_VIDEO", ""),
    "stems": os.getenv("NAS_REMOTE_ROOT_STEMS", ""),
}

# Route definitions: JSON string with list of route dicts
# Example: '[{"kind": "audio", "variant": "instrumental", "to": "${remoteRoots.audio}/Instrumental"}]'
ROUTES_JSON = os.getenv(
    "NAS_SYNC_ROUTES",
    json.dumps([
        {
            "kind": "audio",
            "variant": "instrumental",
            "to": "${remoteRoots.audio}/Instrumental",
        }
    ])
)

try:
    ROUTES = json.loads(ROUTES_JSON)
except json.JSONDecodeError as e:
    logger.error(f"Failed to parse NAS_SYNC_ROUTES JSON: {e}")
    ROUTES = []

# Sync mechanism specifics
# === RSYNC (for local or SSH-mounted NAS) ===
RSYNC_BW_LIMIT = os.getenv("NAS_RSYNC_BW_LIMIT", "0")  # KB/s, 0 = unlimited
RSYNC_COMPRESS = os.getenv("NAS_RSYNC_COMPRESS", "true").lower() == "true"

# === S3 (for cloud storage) ===
S3_BUCKET = os.getenv("NAS_S3_BUCKET", "")
S3_PREFIX = os.getenv("NAS_S3_PREFIX", "instrumental-maker")
S3_REGION = os.getenv("NAS_S3_REGION", "us-east-1")
S3_ENDPOINT = os.getenv("NAS_S3_ENDPOINT", "")  # For MinIO/custom S3

# === SCP (for remote servers) ===
SCP_HOST = os.getenv("NAS_SCP_HOST", "")
SCP_USER = os.getenv("NAS_SCP_USER", "")
SCP_KEY = os.getenv("NAS_SCP_KEY", "/home/user/.ssh/id_rsa")

# Behavior
SKIP_ON_MISSING_REMOTE = os.getenv("NAS_SKIP_ON_MISSING_REMOTE", "true").lower() == "true"
DRY_RUN = os.getenv("NAS_DRY_RUN", "false").lower() == "true"
POLL_INTERVAL_SEC = float(os.getenv("NAS_POLL_INTERVAL_SEC", "5"))
WATCH_PATTERN = os.getenv("NAS_WATCH_PATTERN", "manifest.json")

# Logging
LOG_LEVEL = os.getenv("NAS_LOG_LEVEL", "INFO")

# Daemon mode
DAEMON_MODE = os.getenv("NAS_DAEMON_MODE", "true").lower() == "true"


def validate_config() -> List[str]:
    """
    Validate configuration. Returns list of warnings (empty = all good).
    """
    warnings = []
    
    if not OUTPUTS_DIR:
        warnings.append("OUTPUTS_DIR not set")
    
    if SYNC_METHOD not in ["rsync", "s3", "scp", "local"]:
        warnings.append(f"Unknown NAS_SYNC_METHOD: {SYNC_METHOD}")
    
    if not any(REMOTE_ROOTS.values()):
        warnings.append("No NAS_REMOTE_ROOT_* variables set - artifacts will not be synced")
    
    if SYNC_METHOD == "s3" and not S3_BUCKET:
        warnings.append("S3 method selected but NAS_S3_BUCKET not set")
    
    if SYNC_METHOD == "scp" and (not SCP_HOST or not SCP_USER):
        warnings.append("SCP method selected but NAS_SCP_HOST or NAS_SCP_USER not set")
    
    if DRY_RUN:
        warnings.append("DRY_RUN mode enabled - no artifacts will actually be synced")
    
    return warnings


def log_config():
    """Log active configuration."""
    logger.info(f"NAS Sync Configuration:")
    logger.info(f"  OUTPUTS_DIR: {OUTPUTS_DIR}")
    logger.info(f"  SYNC_METHOD: {SYNC_METHOD}")
    logger.info(f"  REMOTE_ROOTS: {REMOTE_ROOTS}")
    logger.info(f"  Routes: {len(ROUTES)} defined")
    logger.info(f"  DRY_RUN: {DRY_RUN}")
    logger.info(f"  DAEMON_MODE: {DAEMON_MODE}")
    
    warnings = validate_config()
    for w in warnings:
        logger.warning(f"Config warning: {w}")
