"""Produces standardized job bundles from Deemix downloads."""

import json
import logging
from pathlib import Path
from typing import Dict, Optional, List
import shutil

from config import Config

logger = logging.getLogger(__name__)


class JobBundleProducer:
    """Converts Deemix retriever output to standardized job bundles."""
    
    def __init__(self, cfg: Config):
        self.cfg = cfg
    
    def produce_bundle(self, download_result: Dict) -> Optional[Path]:
        """
        Create a job bundle from Deemix download result.
        
        Returns path to the finalized job bundle (renamed from .tmp).
        """
        job_id = download_result["job_id"]
        url = download_result["url"]
        url_type = download_result["url_type"]
        title = download_result["title"]
        artist = download_result["artist"]
        album = download_result["album"]
        tracks = download_result["tracks"]
        cover_path = download_result.get("cover_path")
        
        if not tracks:
            logger.error("No tracks in download result")
            return None
        
        logger.info(f"Creating job bundle for {len(tracks)} track(s)")
        
        # Create single bundle for all tracks
        bundle = self._create_job_bundle(
            job_id, url, url_type, title, artist, album,
            tracks, cover_path
        )
        
        if bundle:
            logger.info(f"Job bundle created: {bundle}")
        
        return bundle
    
    def _create_job_bundle(
        self,
        job_id: str,
        url: str,
        url_type: str,
        title: str,
        artist: str,
        album: str,
        tracks: List[Dict],
        cover_path: Optional[Path]
    ) -> Optional[Path]:
        """Create job bundle in /queues/other/."""
        queue_dir = Path(self.cfg.QUEUE_OTHER)
        queue_dir.mkdir(parents=True, exist_ok=True)
        
        # Create bundle in temporary folder
        bundle_id = f"{job_id}_deemix"
        tmp_bundle = queue_dir / f"job_{bundle_id}.tmp"
        tmp_bundle.mkdir(parents=True, exist_ok=True)
        
        try:
            # Step 1: Create files/ subdirectory
            files_dir = tmp_bundle / "files"
            files_dir.mkdir(parents=True, exist_ok=True)
            
            # Step 2: Copy audio tracks into files/
            audio_files = []
            for i, track in enumerate(tracks):
                src_path = track["file_path"]
                if not src_path.exists():
                    logger.warning(f"Track file not found: {src_path}")
                    continue
                
                # Preserve original filename or create indexed name
                dst_filename = f"{i+1:02d}_{src_path.name}" if len(tracks) > 1 else src_path.name
                dst_path = files_dir / dst_filename
                
                shutil.copy2(src_path, dst_path)
                audio_files.append(dst_filename)
                logger.info(f"Copied track: {dst_filename}")
            
            if not audio_files:
                logger.error("No audio files were copied")
                return None
            
            # Step 3: Copy cover art if present
            cover_filename = None
            if cover_path and cover_path.exists():
                cover_filename = cover_path.name
                dst_cover = files_dir / cover_filename
                shutil.copy2(cover_path, dst_cover)
                logger.info(f"Copied cover: {cover_filename}")
            
            # Step 4: Create job.json manifest
            job_json = {
                "job_id": bundle_id,
                "source_type": "deemix",
                "artist": artist,
                "album": album,
                "title": title,
                "audio_files": audio_files,  # List of filenames in files/
            }
            
            if cover_filename:
                job_json["cover_path"] = cover_filename
            
            # Add Deezer-specific metadata
            job_json["deemix"] = {
                "url": url,
                "url_type": url_type,
                "job_id": job_id.replace("dz_", ""),
                "track_count": len(tracks),
            }
            
            # Include track details for reference
            job_json["tracks"] = [
                {
                    "title": t["title"],
                    "artist": t["artist"],
                    "album": t["album"],
                    "duration_sec": t["duration_sec"],
                    "filename": audio_files[i] if i < len(audio_files) else None,
                }
                for i, t in enumerate(tracks)
            ]
            
            job_json_path = tmp_bundle / "job.json"
            job_json_path.write_text(json.dumps(job_json, indent=2))
            logger.info(f"Created job.json in {bundle_id}")
            
            # Step 5: Atomically rename to final location
            final_bundle = queue_dir / f"job_{bundle_id}"
            
            # Remove if it already exists (for test idempotency)
            if final_bundle.exists():
                shutil.rmtree(final_bundle)
            
            tmp_bundle.rename(final_bundle)
            
            logger.info(f"Deemix bundle finalized: {final_bundle}")
            return final_bundle
        
        except Exception as e:
            logger.error(f"Failed to create job bundle: {e}")
            # Cleanup on error
            try:
                shutil.rmtree(tmp_bundle)
            except Exception:
                pass
            return None
