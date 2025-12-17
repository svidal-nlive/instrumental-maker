"""Database models for WebUI configuration and state persistence."""
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional

class ConfigDB:
    """SQLite database for storing user configuration changes."""
    
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS config (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        data_type TEXT NOT NULL,
        description TEXT,
        is_default INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    
    CREATE TABLE IF NOT EXISTS queue_status (
        queue_name TEXT PRIMARY KEY,
        job_count INTEGER DEFAULT 0,
        last_checked TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    
    CREATE TABLE IF NOT EXISTS completed_jobs (
        job_id TEXT PRIMARY KEY,
        source TEXT NOT NULL,
        job_type TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        completed_at TEXT NOT NULL,
        manifest_path TEXT
    );
    """
    
    def __init__(self, db_path: Path):
        """Initialize database connection and create schema."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_schema(self):
        """Initialize database schema."""
        conn = self._get_connection()
        try:
            conn.executescript(self.SCHEMA)
            conn.commit()
        finally:
            conn.close()
    
    def set_config(
        self,
        key: str,
        value: Any,
        data_type: str,
        description: str = "",
        is_default: bool = False
    ) -> None:
        """
        Set or update a configuration value.
        
        Args:
            key: Configuration key
            value: Configuration value (will be JSON serialized)
            data_type: Type of value (str, int, float, bool, json)
            description: Human-readable description
            is_default: Whether this is a default value from .env
        """
        conn = self._get_connection()
        try:
            now = datetime.utcnow().isoformat()
            # Always JSON serialize for consistency, handles all types
            json_value = json.dumps(value)
            
            # Check if key exists
            cursor = conn.execute("SELECT key FROM config WHERE key = ?", (key,))
            exists = cursor.fetchone() is not None
            
            if exists:
                conn.execute(
                    """UPDATE config SET value = ?, data_type = ?, description = ?, 
                       is_default = ?, updated_at = ? WHERE key = ?""",
                    (json_value, data_type, description, int(is_default), now, key)
                )
            else:
                conn.execute(
                    """INSERT INTO config (key, value, data_type, description, is_default, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (key, json_value, data_type, description, int(is_default), now, now)
                )
            
            conn.commit()
        finally:
            conn.close()
    
    def get_config(self, key: str) -> Optional[Dict[str, Any]]:
        """Get a configuration value by key."""
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT * FROM config WHERE key = ?", (key,))
            row = cursor.fetchone()
            
            if row is None:
                return None
            
            return {
                'key': row['key'],
                'value': json.loads(row['value']),
                'data_type': row['data_type'],
                'description': row['description'],
                'is_default': bool(row['is_default']),
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            }
        finally:
            conn.close()
    
    def get_all_config(self) -> Dict[str, Dict[str, Any]]:
        """Get all configuration values."""
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT * FROM config ORDER BY key")
            result = {}
            
            for row in cursor.fetchall():
                result[row['key']] = {
                    'value': json.loads(row['value']),
                    'data_type': row['data_type'],
                    'description': row['description'],
                    'is_default': bool(row['is_default']),
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at']
                }
            
            return result
        finally:
            conn.close()
    
    def reset_to_default(self, key: str) -> bool:
        """Reset a configuration to its default value."""
        conn = self._get_connection()
        try:
            # Get the original default value (where is_default should be 1 initially)
            # Since we don't track the original default separately, we need a different approach
            # For now, we'll restore from environment variables if possible
            cursor = conn.execute("SELECT * FROM config WHERE key = ?", (key,))
            current_row = cursor.fetchone()
            
            if current_row is None:
                return False
            
            # Re-initialize from environment
            import os
            from app.webui.app import _env_bool
            
            # Map environment variable names to default values
            env_defaults = {
                'GENERATE_NO_DRUMS_VARIANT': (lambda: _env_bool('GENERATE_NO_DRUMS_VARIANT', False), 'bool'),
                'GENERATE_DRUMS_ONLY_VARIANT': (lambda: _env_bool('GENERATE_DRUMS_ONLY_VARIANT', False), 'bool'),
                'PRESERVE_STEMS': (lambda: _env_bool('PRESERVE_STEMS', False), 'bool'),
                'DEMUCS_DEVICE': (lambda: os.environ.get('DEMUCS_DEVICE', 'cpu'), 'str'),
                'DEMUCS_JOBS': (lambda: int(os.environ.get('DEMUCS_JOBS', '1')), 'int'),
                'DEMUCS_CHUNK_TIMEOUT_SEC': (lambda: int(os.environ.get('DEMUCS_CHUNK_TIMEOUT_SEC', '3600')), 'int'),
                'DEMUCS_MAX_RETRIES': (lambda: int(os.environ.get('DEMUCS_MAX_RETRIES', '2')), 'int'),
                'MODEL': (lambda: os.environ.get('MODEL', 'htdemucs'), 'str'),
                'SAMPLE_RATE': (lambda: int(os.environ.get('SAMPLE_RATE', '44100')), 'int'),
                'CHUNK_OVERLAP_SEC': (lambda: int(os.environ.get('CHUNK_OVERLAP_SEC', '10')), 'int'),
                'CROSSFADE_MS': (lambda: int(os.environ.get('CROSSFADE_MS', '1000')), 'int'),
                'MP3_ENCODING': (lambda: os.environ.get('MP3_ENCODING', 'cbr320'), 'str'),
                'YTDL_MODE': (lambda: os.environ.get('YTDL_MODE', 'audio'), 'str'),
                'YTDL_AUDIO_FORMAT': (lambda: os.environ.get('YTDL_AUDIO_FORMAT', 'm4a'), 'str'),
                'YTDL_DURATION_TOL_SEC': (lambda: float(os.environ.get('YTDL_DURATION_TOL_SEC', '2.0')), 'float'),
                'YTDL_DURATION_TOL_PCT': (lambda: float(os.environ.get('YTDL_DURATION_TOL_PCT', '0.01')), 'float'),
                'YTDL_FAIL_ON_DURATION_MISMATCH': (lambda: _env_bool('YTDL_FAIL_ON_DURATION_MISMATCH', True), 'bool'),
                'NAS_SYNC_METHOD': (lambda: os.environ.get('NAS_SYNC_METHOD', 'rsync'), 'str'),
                'NAS_DRY_RUN': (lambda: _env_bool('NAS_DRY_RUN', False), 'bool'),
                'NAS_SKIP_ON_MISSING_REMOTE': (lambda: _env_bool('NAS_SKIP_ON_MISSING_REMOTE', True), 'bool'),
                'NAS_POLL_INTERVAL_SEC': (lambda: int(os.environ.get('NAS_POLL_INTERVAL_SEC', '5')), 'int'),
                'QUEUE_ENABLED': (lambda: _env_bool('QUEUE_ENABLED', False), 'bool'),
            }
            
            if key not in env_defaults:
                return False
            
            default_getter, data_type = env_defaults[key]
            default_value = default_getter()
            
            now = datetime.utcnow().isoformat()
            json_value = json.dumps(default_value)
            
            conn.execute(
                "UPDATE config SET value = ?, updated_at = ? WHERE key = ?",
                (json_value, now, key)
            )
            conn.commit()
            return True
        finally:
            conn.close()
    
    def update_queue_status(self, queue_name: str, job_count: int) -> None:
        """Update queue status information."""
        conn = self._get_connection()
        try:
            now = datetime.utcnow().isoformat()
            
            cursor = conn.execute("SELECT queue_name FROM queue_status WHERE queue_name = ?", (queue_name,))
            exists = cursor.fetchone() is not None
            
            if exists:
                conn.execute(
                    """UPDATE queue_status SET job_count = ?, last_checked = ?, updated_at = ?
                       WHERE queue_name = ?""",
                    (job_count, now, now, queue_name)
                )
            else:
                conn.execute(
                    """INSERT INTO queue_status (queue_name, job_count, last_checked, updated_at)
                       VALUES (?, ?, ?, ?)""",
                    (queue_name, job_count, now, now)
                )
            
            conn.commit()
        finally:
            conn.close()
    
    def get_queue_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status for all queues."""
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT * FROM queue_status ORDER BY queue_name")
            result = {}
            
            for row in cursor.fetchall():
                result[row['queue_name']] = {
                    'job_count': row['job_count'],
                    'last_checked': row['last_checked'],
                    'updated_at': row['updated_at']
                }
            
            return result
        finally:
            conn.close()
    
    def add_completed_job(
        self,
        job_id: str,
        source: str,
        job_type: str,
        status: str,
        manifest_path: Optional[str] = None
    ) -> None:
        """
        Add a completed job record.
        
        Args:
            job_id: Unique job identifier
            source: Source of job (youtube, deemix, other)
            job_type: Type of job (audio, video)
            status: Final status (success, failed, skipped)
            manifest_path: Path to manifest.json file
        """
        conn = self._get_connection()
        try:
            now = datetime.utcnow().isoformat()
            
            conn.execute(
                """INSERT OR REPLACE INTO completed_jobs 
                   (job_id, source, job_type, status, created_at, completed_at, manifest_path)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (job_id, source, job_type, status, now, now, manifest_path)
            )
            
            conn.commit()
        finally:
            conn.close()
    
    def get_recent_jobs(self, limit: int = 20) -> list[Dict[str, Any]]:
        """Get recently completed jobs."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """SELECT * FROM completed_jobs 
                   ORDER BY completed_at DESC LIMIT ?""",
                (limit,)
            )
            result = []
            
            for row in cursor.fetchall():
                result.append({
                    'job_id': row['job_id'],
                    'source': row['source'],
                    'job_type': row['job_type'],
                    'status': row['status'],
                    'created_at': row['created_at'],
                    'completed_at': row['completed_at'],
                    'manifest_path': row['manifest_path']
                })
            
            return result
        finally:
            conn.close()
