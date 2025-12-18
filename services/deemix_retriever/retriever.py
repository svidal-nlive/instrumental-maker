"""Deemix retriever: downloads music from Deezer and produces job bundles."""

import subprocess
import json
import logging
from pathlib import Path
from typing import Dict, Optional, List, Tuple
from datetime import datetime
import shutil
import time
from dataclasses import dataclass

from config import Config

logger = logging.getLogger(__name__)


@dataclass
class DeemixTrackInfo:
    """Information about a Deezer track."""
    track_id: str
    title: str
    artist: str
    album: str
    duration_sec: float
    url: str


class DeemixDownloadError(Exception):
    """Raised when Deemix download fails."""
    pass


class DeemixRetriever:
    """Downloads from Deezer using Deemix and produces standardized job bundles."""
    
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.work_dir = Path(cfg.WORKING_DIR)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.deemix_cache = Path(cfg.DEEMIX_CACHE_DIR)
        self.deemix_config = Path(cfg.DEEMIX_CONFIG_DIR)
    
    def download_and_validate(self, deezer_url: str) -> Dict:
        """
        Download from Deezer using Deemix and validate.
        
        Supports:
        - Track URLs: https://www.deezer.com/track/123456789
        - Album URLs: https://www.deezer.com/album/123456789
        - Playlist URLs: https://www.deezer.com/playlist/123456789
        
        Returns dict with:
        {
            "job_id": "dz_<id>",
            "url": url,
            "title": str,
            "artist": str,
            "album": str,
            "duration": float,
            "tracks": [
                {
                    "track_id": str,
                    "title": str,
                    "artist": str,
                    "album": str,
                    "duration_sec": float,
                    "file_path": Path,
                },
                ...
            ],
            "cover_path": Path or None,
        }
        """
        job_id = None
        temp_dir = None
        
        try:
            # Step 1: Parse URL and get metadata
            logger.info(f"Fetching Deezer metadata: {deezer_url}")
            metadata = self._fetch_metadata(deezer_url)
            
            if not metadata:
                raise DeemixDownloadError(f"Failed to fetch metadata from {deezer_url}")
            
            url_type = metadata.get("type", "unknown")  # track, album, playlist
            
            # Step 2: Create temp directory
            job_id = f"dz_{metadata['id']}"
            temp_dir = self.work_dir / f"{job_id}.tmp"
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            result = {
                "job_id": job_id,
                "url": deezer_url,
                "url_type": url_type,
                "title": metadata.get("title", "Unknown"),
                "artist": metadata.get("artist", "Unknown"),
                "album": metadata.get("album", "Unknown"),
                "duration": metadata.get("duration", 0.0),
                "tracks": [],
                "cover_path": None,
            }
            
            # Step 3: Download using deemix CLI
            logger.info(f"Downloading from Deezer ({url_type}): {metadata.get('title', 'Unknown')}")
            download_dir = temp_dir / "downloads"
            self._run_deemix_download(deezer_url, download_dir)
            
            # Step 4: Collect downloaded tracks
            if download_dir.exists():
                result["tracks"] = self._collect_tracks(download_dir, metadata)
            
            if not result["tracks"]:
                raise DeemixDownloadError(f"No tracks were downloaded from {deezer_url}")
            
            logger.info(f"Downloaded {len(result['tracks'])} track(s)")
            
            # Step 5: Find and copy cover art
            cover_path = self._find_cover_art(download_dir)
            if cover_path:
                dst_cover = temp_dir / cover_path.name
                shutil.copy2(cover_path, dst_cover)
                result["cover_path"] = dst_cover
                logger.info(f"Found cover art: {cover_path.name}")
            
            return result
        
        except Exception as e:
            logger.error(f"Download failed: {e}")
            # Cleanup on error
            if temp_dir and temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                except Exception:
                    pass
            raise
    
    def _fetch_metadata(self, deezer_url: str) -> Optional[Dict]:
        """Extract metadata from Deezer URL without downloading."""
        # Parse URL to extract resource type and ID
        parts = deezer_url.rstrip('/').split('/')
        
        if 'deezer.com' not in deezer_url:
            logger.error(f"Not a valid Deezer URL: {deezer_url}")
            return None
        
        try:
            resource_type = None
            resource_id = None
            
            # Extract type and ID from URL
            # https://www.deezer.com/track/123456789
            # https://www.deezer.com/album/123456789
            # https://www.deezer.com/playlist/123456789
            for i, part in enumerate(parts):
                if part in ("track", "album", "playlist"):
                    resource_type = part
                    if i + 1 < len(parts):
                        resource_id = parts[i + 1].split("?")[0]
                        break
            
            if not resource_type or not resource_id:
                logger.error(f"Could not parse Deezer URL: {deezer_url}")
                return None
            
            logger.info(f"Parsed URL: type={resource_type}, id={resource_id}")
            
            # Use deemix CLI to get metadata
            # Note: This is a simplified approach - in production, you'd use the Deezer API
            # or deemix's Python library for more detailed metadata extraction
            result = {
                "id": resource_id,
                "type": resource_type,
                "title": "Unknown",
                "artist": "Unknown",
                "album": "Unknown",
                "duration": 0.0,
            }
            
            return result
        
        except Exception as e:
            logger.error(f"Failed to parse metadata: {e}")
            return None
    
    def _run_deemix_download(self, deezer_url: str, output_dir: Path):
        """Execute deemix CLI to download."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Build deemix command
        cmd = [
            "deemix",
            "-p", str(output_dir),  # output path
            "--quality", self.cfg.DEEMIX_QUALITY,
            deezer_url,
        ]
        
        logger.info(f"Running: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                timeout=self.cfg.DEEMIX_DOWNLOAD_TIMEOUT,
                capture_output=True,
                text=True,
                check=False,
            )
            
            if result.returncode != 0:
                logger.error(f"Deemix error (code {result.returncode}): {result.stderr}")
                if not self.cfg.SKIP_ON_ERROR:
                    raise DeemixDownloadError(f"Deemix failed: {result.stderr}")
                else:
                    logger.warning("Continuing despite error (SKIP_ON_ERROR=true)")
            else:
                logger.info(f"Deemix output: {result.stdout}")
        
        except subprocess.TimeoutExpired:
            raise DeemixDownloadError(
                f"Deemix download timed out after {self.cfg.DEEMIX_DOWNLOAD_TIMEOUT}s"
            )
        except Exception as e:
            raise DeemixDownloadError(f"Failed to run deemix: {e}")
    
    def _collect_tracks(self, download_dir: Path, metadata: Dict) -> List[Dict]:
        """Collect downloaded audio files and metadata."""
        tracks = []
        
        # Recursively search for audio files
        audio_extensions = {".mp3", ".flac", ".m4a", ".wav", ".aac"}
        
        for audio_file in download_dir.rglob("*"):
            if audio_file.suffix.lower() in audio_extensions:
                # Extract metadata from filename or use defaults
                track_info = {
                    "track_id": audio_file.stem,
                    "title": audio_file.stem,
                    "artist": metadata.get("artist", "Unknown"),
                    "album": metadata.get("album", "Unknown"),
                    "duration_sec": self._get_audio_duration(audio_file),
                    "file_path": audio_file,
                }
                tracks.append(track_info)
        
        # Sort by modification time (oldest first = natural download order)
        tracks.sort(key=lambda t: t["file_path"].stat().st_mtime)
        
        return tracks
    
    def _get_audio_duration(self, audio_file: Path) -> float:
        """Get audio duration using ffprobe."""
        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "json",
                str(audio_file),
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                duration = float(data.get("format", {}).get("duration", 0))
                return duration
        except Exception as e:
            logger.warning(f"Could not get duration for {audio_file}: {e}")
        
        return 0.0
    
    def _find_cover_art(self, search_dir: Path) -> Optional[Path]:
        """Find cover art image in downloaded files."""
        image_extensions = {".jpg", ".jpeg", ".png", ".gif"}
        
        # Look for common cover art names first
        common_names = ["cover", "folder", "albumart", "front"]
        
        for img_file in search_dir.rglob("*"):
            if img_file.suffix.lower() in image_extensions:
                stem = img_file.stem.lower()
                if any(name in stem for name in common_names):
                    return img_file
        
        # Return first image found
        for img_file in search_dir.rglob("*"):
            if img_file.suffix.lower() in image_extensions:
                return img_file
        
        return None
    
    def cleanup_temp(self, temp_dir: Path):
        """Clean up temporary directory."""
        try:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
                logger.info(f"Cleaned up temp dir: {temp_dir}")
        except Exception as e:
            logger.error(f"Failed to cleanup temp dir: {e}")
