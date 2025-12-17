"""
Queue consumer: watches holding folders and dispatches jobs to the processor.

Replaces the old file-watcher approach. Retrieval services place job bundles in:
  /queues/youtube_audio/
  /queues/youtube_video/
  /queues/other/

This consumer discovers, validates, and dispatches them.
"""

from pathlib import Path
from typing import Optional, Dict, Any
import json
import time
import shutil
from datetime import datetime
import logging

from .job_bundle import JobBundle

logger = logging.getLogger(__name__)


class QueueConsumer:
    """Watches queue folders and yields ready jobs."""
    
    def __init__(self, queue_folders: Dict[str, Path]):
        """
        Args:
            queue_folders: dict mapping queue_type -> Path
                e.g. {"youtube_audio": Path("/queues/youtube_audio"), ...}
        """
        self.queue_folders = queue_folders
    
    def _is_job_ready(self, job_folder: Path) -> bool:
        """
        Check if a job folder is ready to process.
        A job is ready if:
        - job.json exists and is readable
        - No .tmp suffix (indicates still being written)
        """
        if job_folder.name.endswith(".tmp"):
            return False
        
        job_json = job_folder / "job.json"
        return job_json.exists() and job_json.is_file()
    
    def discover_jobs(self) -> Dict[str, list]:
        """
        Scan all queue folders and return a dict of discovered jobs.
        
        Returns:
            {queue_type: [job_folder_path, ...], ...}
        """
        discovered = {}
        
        for queue_type, queue_path in self.queue_folders.items():
            jobs = []
            
            if not queue_path.exists():
                logger.warning(f"Queue folder does not exist: {queue_path}")
                continue
            
            # Find all job_<id>/ folders (not .tmp)
            for item in queue_path.iterdir():
                if item.is_dir() and item.name.startswith("job_"):
                    if self._is_job_ready(item):
                        jobs.append(item)
            
            # Sort by mtime (oldest first) to process in order
            jobs.sort(key=lambda p: p.stat().st_mtime)
            discovered[queue_type] = jobs
        
        return discovered
    
    def load_job_bundle(self, job_folder: Path) -> Optional[JobBundle]:
        """
        Load a job.json and reconstruct a JobBundle.
        Returns None if the bundle is invalid.
        """
        job_json = job_folder / "job.json"
        
        if not job_json.exists():
            logger.error(f"job.json missing in {job_folder}")
            return None
        
        try:
            with open(job_json, "r") as f:
                data = json.load(f)
            
            # Reconstruct paths (they are relative to job_folder)
            audio_path = None
            if "audio_path" in data and data["audio_path"]:
                audio_path = job_folder / data["audio_path"]
            
            video_path = None
            if "video_path" in data and data["video_path"]:
                video_path = job_folder / data["video_path"]
            
            cover_path = None
            if "cover_path" in data and data["cover_path"]:
                cover_path = job_folder / data["cover_path"]
            
            bundle = JobBundle(
                job_id=data.get("job_id"),
                source_type=data.get("source_type"),
                title=data.get("title"),
                artist=data.get("artist"),
                album=data.get("album"),
                audio_path=audio_path,
                video_path=video_path,
                cover_path=cover_path,
            )
            
            return bundle
        
        except Exception as e:
            logger.error(f"Failed to load job bundle from {job_folder}: {e}")
            return None
    
    def claim_job(self, job_folder: Path, working_folder: Path) -> Optional[Path]:
        """
        Move a job from queue to working folder (atomic rename).
        Returns the new path under working_folder, or None if failed.
        """
        job_id = job_folder.name.replace("job_", "")
        working_job = working_folder / f"job_{job_id}"
        
        try:
            job_folder.rename(working_job)
            logger.info(f"Claimed job {job_id} -> {working_job}")
            return working_job
        
        except Exception as e:
            logger.error(f"Failed to claim job {job_folder}: {e}")
            return None
    
    def archive_job(self, job_folder: Path, archive_folder: Path, status: str) -> bool:
        """
        Move job to archive (success or fail).
        """
        success_folder = archive_folder / status
        success_folder.mkdir(parents=True, exist_ok=True)
        
        dest = success_folder / job_folder.name
        
        try:
            # Remove if exists (shouldn't happen, but be safe)
            if dest.exists():
                shutil.rmtree(dest)
            
            job_folder.rename(dest)
            logger.info(f"Archived job to {status}: {job_folder.name}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to archive job {job_folder} to {status}: {e}")
            return False
