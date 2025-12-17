"""Produces standardized job bundles from downloaded media."""

import json
import logging
from pathlib import Path
from typing import Dict, Optional

from config import Config

logger = logging.getLogger(__name__)


class JobBundleProducer:
    """Converts retriever output to standardized job bundles."""
    
    def __init__(self, cfg: Config):
        self.cfg = cfg
    
    def produce_bundle(self, download_result: Dict) -> Optional[Path]:
        """
        Create a job bundle from download result.
        
        Returns path to the finalized job bundle (renamed from .tmp).
        """
        job_id = download_result["job_id"]
        url = download_result["url"]
        title = download_result["title"]
        channel = download_result["channel"]
        online_duration = download_result["online_duration"]
        audio_path = download_result["audio_path"]
        video_path = download_result["video_path"]
        cover_path = download_result["cover_path"]
        
        # Determine which queue(s) to write to
        should_queue_audio = audio_path is not None
        should_queue_video = video_path is not None
        
        if not (should_queue_audio or should_queue_video):
            logger.error("No audio or video to enqueue")
            return None
        
        bundles_created = []
        
        # Create audio job bundle if audio exists
        if should_queue_audio and self.cfg.MODE in ("audio", "both"):
            audio_bundle = self._create_audio_bundle(
                job_id, title, channel, url, online_duration,
                audio_path, cover_path
            )
            if audio_bundle:
                bundles_created.append(("audio", audio_bundle))
        
        # Create video job bundle if video exists
        if should_queue_video and self.cfg.MODE in ("video", "both"):
            video_bundle = self._create_video_bundle(
                job_id, title, channel, url, online_duration,
                video_path, cover_path
            )
            if video_bundle:
                bundles_created.append(("video", video_bundle))
        
        if not bundles_created:
            logger.error("Failed to create any job bundles")
            return None
        
        logger.info(f"Created {len(bundles_created)} job bundle(s)")
        
        # Return the first bundle (or whichever is more important)
        return bundles_created[0][1]
    
    def _create_audio_bundle(
        self, job_id: str, title: str, channel: str, url: str, online_duration: float,
        audio_path: Path, cover_path: Optional[Path]
    ) -> Optional[Path]:
        """Create audio job bundle in youtube_audio queue."""
        queue_dir = Path(self.cfg.QUEUE_AUDIO)
        queue_dir.mkdir(parents=True, exist_ok=True)
        
        # Create bundle in temporary folder
        bundle_id = f"{job_id}_audio"
        tmp_bundle = queue_dir / f"job_{bundle_id}.tmp"
        tmp_bundle.mkdir(parents=True, exist_ok=True)
        
        try:
            # Write job.json
            job_json = {
                "job_id": bundle_id,
                "source_type": "youtube",
                "artist": channel,
                "album": "YTDL",
                "title": title,
                "audio_path": audio_path.name,
            }
            
            if cover_path:
                job_json["cover_path"] = cover_path.name
            
            job_json["youtube"] = {
                "video_id": job_id.replace("yt_", ""),
                "url": url,
                "channel": channel,
                "title": title,
                "online_duration_sec": online_duration,
            }
            
            (tmp_bundle / "job.json").write_text(json.dumps(job_json, indent=2))
            
            # Move files into bundle
            import shutil
            shutil.copy2(audio_path, tmp_bundle / audio_path.name)
            
            if cover_path and cover_path.exists():
                shutil.copy2(cover_path, tmp_bundle / cover_path.name)
            
            # Atomically rename to final location
            final_bundle = queue_dir / f"job_{bundle_id}"
            tmp_bundle.rename(final_bundle)
            
            logger.info(f"Audio bundle created: {final_bundle}")
            return final_bundle
        
        except Exception as e:
            logger.error(f"Failed to create audio bundle: {e}")
            # Cleanup on error
            if tmp_bundle.exists():
                import shutil
                shutil.rmtree(tmp_bundle, ignore_errors=True)
            return None
    
    def _create_video_bundle(
        self, job_id: str, title: str, channel: str, url: str, online_duration: float,
        video_path: Path, cover_path: Optional[Path]
    ) -> Optional[Path]:
        """Create video job bundle in youtube_video queue."""
        queue_dir = Path(self.cfg.QUEUE_VIDEO)
        queue_dir.mkdir(parents=True, exist_ok=True)
        
        # Create bundle in temporary folder
        bundle_id = f"{job_id}_video"
        tmp_bundle = queue_dir / f"job_{bundle_id}.tmp"
        tmp_bundle.mkdir(parents=True, exist_ok=True)
        
        try:
            # Write job.json
            job_json = {
                "job_id": bundle_id,
                "source_type": "youtube",
                "artist": channel,
                "album": "YTDL",
                "title": title,
                "video_path": video_path.name,
            }
            
            if cover_path:
                job_json["cover_path"] = cover_path.name
            
            job_json["youtube"] = {
                "video_id": job_id.replace("yt_", ""),
                "url": url,
                "channel": channel,
                "title": title,
                "online_duration_sec": online_duration,
            }
            
            (tmp_bundle / "job.json").write_text(json.dumps(job_json, indent=2))
            
            # Move files into bundle
            import shutil
            shutil.copy2(video_path, tmp_bundle / video_path.name)
            
            if cover_path and cover_path.exists():
                shutil.copy2(cover_path, tmp_bundle / cover_path.name)
            
            # Atomically rename to final location
            final_bundle = queue_dir / f"job_{bundle_id}"
            tmp_bundle.rename(final_bundle)
            
            logger.info(f"Video bundle created: {final_bundle}")
            return final_bundle
        
        except Exception as e:
            logger.error(f"Failed to create video bundle: {e}")
            # Cleanup on error
            if tmp_bundle.exists():
                import shutil
                shutil.rmtree(tmp_bundle, ignore_errors=True)
            return None
