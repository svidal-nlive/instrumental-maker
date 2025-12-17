"""YouTube retriever: downloads media from YouTube and produces job bundles."""

import subprocess
import json
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple
from datetime import datetime
import shutil
import time

from config import Config

logger = logging.getLogger(__name__)


class DurationMismatchError(Exception):
    """Raised when online and downloaded durations don't match."""
    pass


class YouTubeRetriever:
    """Downloads from YouTube and produces standardized job bundles."""
    
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.work_dir = Path(cfg.WORKING_DIR)
        self.work_dir.mkdir(parents=True, exist_ok=True)
    
    def download_and_validate(self, url: str) -> Dict:
        """
        Download from YouTube and validate.
        
        Returns dict with:
        {
            "job_id": "yt_<id>",
            "url": url,
            "title": str,
            "channel": str,
            "online_duration": float,
            "audio_path": Path or None,
            "video_path": Path or None,
            "cover_path": Path or None,
        }
        """
        job_id = None
        temp_dir = None
        
        try:
            # Step 1: Get metadata
            logger.info(f"Fetching metadata: {url}")
            metadata = self._fetch_metadata(url)
            
            if not metadata:
                raise RuntimeError(f"Failed to fetch metadata from {url}")
            
            job_id = f"yt_{metadata['id'][:11]}"
            online_duration = float(metadata.get('duration', 0))
            title = metadata.get('title', 'Unknown')
            channel = metadata.get('uploader', 'Unknown')
            
            logger.info(f"Title: {title}")
            logger.info(f"Channel: {channel}")
            logger.info(f"Online duration: {online_duration:.1f}s")
            
            # Step 2: Create temp directory for downloads
            temp_dir = self.work_dir / f"{job_id}.tmp"
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            result = {
                "job_id": job_id,
                "url": url,
                "title": title,
                "channel": channel,
                "online_duration": online_duration,
                "audio_path": None,
                "video_path": None,
                "cover_path": None,
            }
            
            # Step 3: Download based on mode
            if self.cfg.MODE in ("audio", "both"):
                audio_path = self._download_audio(url, temp_dir, online_duration)
                if audio_path:
                    result["audio_path"] = audio_path
                    logger.info(f"Downloaded audio: {audio_path.name}")
            
            if self.cfg.MODE in ("video", "both"):
                video_path = self._download_video(url, temp_dir, online_duration)
                if video_path:
                    result["video_path"] = video_path
                    logger.info(f"Downloaded video: {video_path.name}")
            
            # Step 4: Download thumbnail (cover art)
            cover_path = self._download_cover(url, temp_dir)
            if cover_path:
                result["cover_path"] = cover_path
                logger.info(f"Downloaded cover: {cover_path.name}")
            
            # Step 5: Tag audio if present
            if result["audio_path"] and result["audio_path"].exists():
                self._tag_audio(
                    result["audio_path"],
                    artist=channel,
                    album="YTDL",
                    title=title
                )
                logger.info("Tagged audio file")
            
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
    
    def _fetch_metadata(self, url: str) -> Optional[Dict]:
        """Fetch JSON metadata from YouTube using yt-dlp."""
        cmd = [
            "yt-dlp",
            "--dump-json",
            "--no-playlist",
        ]
        
        if self.cfg.YTDL_QUIET:
            cmd.append("-q")
        if self.cfg.YTDL_NO_WARNINGS:
            cmd.append("--no-warnings")
        if self.cfg.YTDL_COOKIES_FILE and Path(self.cfg.YTDL_COOKIES_FILE).exists():
            cmd.extend(["--cookies", self.cfg.YTDL_COOKIES_FILE])
        
        cmd.append(url)
        
        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self.cfg.YTDL_SOCKET_TIMEOUT,
                check=False
            )
            
            if proc.returncode != 0:
                logger.error(f"yt-dlp error: {proc.stderr}")
                return None
            
            return json.loads(proc.stdout)
        
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout fetching metadata from {url}")
            return None
        except json.JSONDecodeError:
            logger.error("Failed to parse yt-dlp JSON output")
            return None
        except Exception as e:
            logger.error(f"Metadata fetch error: {e}")
            return None
    
    def _download_audio(self, url: str, work_dir: Path, online_duration: float) -> Optional[Path]:
        """Download best audio, convert to desired format, and validate duration."""
        output_pattern = str(work_dir / "audio.%(ext)s")
        
        cmd = [
            "yt-dlp",
            "-f", "ba/bestaudio",  # best audio
            "--no-playlist",
            "-o", output_pattern,
        ]
        
        if self.cfg.YTDL_QUIET:
            cmd.append("-q")
        if self.cfg.YTDL_COOKIES_FILE and Path(self.cfg.YTDL_COOKIES_FILE).exists():
            cmd.extend(["--cookies", self.cfg.YTDL_COOKIES_FILE])
        
        cmd.append(url)
        
        try:
            logger.info("Downloading audio...")
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=3600,  # 1 hour timeout
                check=False
            )
            
            if proc.returncode != 0:
                logger.error(f"Download failed: {proc.stderr}")
                return None
            
            # Find downloaded file
            audio_files = list(work_dir.glob("audio.*"))
            if not audio_files:
                logger.error("No audio file found after download")
                return None
            
            downloaded_file = audio_files[0]
            logger.info(f"Downloaded to: {downloaded_file.name}")
            
            # Validate duration
            downloaded_duration = self._probe_duration(downloaded_file)
            logger.info(f"Downloaded duration: {downloaded_duration:.1f}s")
            
            if not self._validate_duration(online_duration, downloaded_duration):
                msg = f"Duration mismatch: online {online_duration:.1f}s vs downloaded {downloaded_duration:.1f}s"
                if self.cfg.FAIL_ON_DURATION_MISMATCH:
                    raise DurationMismatchError(msg)
                else:
                    logger.warning(msg)
            
            # Convert to target format if needed
            output_audio = self._convert_audio(downloaded_file, work_dir)
            
            # Validate converted duration
            if output_audio and output_audio != downloaded_file:
                converted_duration = self._probe_duration(output_audio)
                logger.info(f"Converted duration: {converted_duration:.1f}s")
                
                if not self._validate_duration(downloaded_duration, converted_duration):
                    msg = f"Duration mismatch after conversion: {downloaded_duration:.1f}s vs {converted_duration:.1f}s"
                    if self.cfg.FAIL_ON_DURATION_MISMATCH:
                        raise DurationMismatchError(msg)
                    else:
                        logger.warning(msg)
            
            return output_audio or downloaded_file
        
        except Exception as e:
            logger.error(f"Audio download failed: {e}")
            return None
    
    def _download_video(self, url: str, work_dir: Path, online_duration: float) -> Optional[Path]:
        """Download best video (merged with audio), validate duration."""
        output_pattern = str(work_dir / "video.%(ext)s")
        
        cmd = [
            "yt-dlp",
            "-f", "bv*+ba/b",  # best video + best audio, merged
            "--no-playlist",
            "-o", output_pattern,
        ]
        
        if self.cfg.YTDL_QUIET:
            cmd.append("-q")
        if self.cfg.YTDL_COOKIES_FILE and Path(self.cfg.YTDL_COOKIES_FILE).exists():
            cmd.extend(["--cookies", self.cfg.YTDL_COOKIES_FILE])
        
        cmd.append(url)
        
        try:
            logger.info("Downloading video...")
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=3600,  # 1 hour timeout
                check=False
            )
            
            if proc.returncode != 0:
                logger.error(f"Download failed: {proc.stderr}")
                return None
            
            # Find downloaded file
            video_files = list(work_dir.glob("video.*"))
            if not video_files:
                logger.error("No video file found after download")
                return None
            
            video_file = video_files[0]
            logger.info(f"Downloaded to: {video_file.name}")
            
            # Validate duration
            video_duration = self._probe_duration(video_file)
            logger.info(f"Downloaded video duration: {video_duration:.1f}s")
            
            if not self._validate_duration(online_duration, video_duration):
                msg = f"Duration mismatch: online {online_duration:.1f}s vs video {video_duration:.1f}s"
                if self.cfg.FAIL_ON_DURATION_MISMATCH:
                    raise DurationMismatchError(msg)
                else:
                    logger.warning(msg)
            
            return video_file
        
        except Exception as e:
            logger.error(f"Video download failed: {e}")
            return None
    
    def _download_cover(self, url: str, work_dir: Path) -> Optional[Path]:
        """Download video thumbnail as cover art."""
        output_pattern = str(work_dir / "cover.%(ext)s")
        
        cmd = [
            "yt-dlp",
            "--write-thumbnail",
            "--no-playlist",
            "-o", output_pattern,
            "-q",
            url,
        ]
        
        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=60,
                check=False
            )
            
            # Find thumbnail file (usually .jpg or .webp)
            cover_files = list(work_dir.glob("cover.*"))
            if cover_files:
                return cover_files[0]
            
            return None
        
        except Exception as e:
            logger.warning(f"Failed to download cover: {e}")
            return None
    
    def _convert_audio(self, audio_file: Path, work_dir: Path) -> Optional[Path]:
        """Convert audio to target format if needed."""
        target_format = self.cfg.AUDIO_FORMAT
        current_ext = audio_file.suffix.lstrip(".").lower()
        
        # Map common formats
        format_map = {
            "m4a": "aac",
            "aac": "aac",
            "mp3": "libmp3lame",
            "flac": "flac",
            "wav": "pcm_s16le",
        }
        
        # If already in target format, no conversion needed
        if current_ext == target_format:
            return audio_file
        
        codec = format_map.get(target_format, "aac")
        output_file = work_dir / f"audio.{target_format}"
        
        cmd = [
            "ffmpeg", "-y",
            "-i", str(audio_file),
            "-vn",  # no video
            "-c:a", codec,
        ]
        
        # Add format-specific options
        if target_format == "mp3":
            cmd.extend(["-b:a", "192k"])
        elif target_format == "aac":
            cmd.extend(["-b:a", "192k"])
        
        cmd.append(str(output_file))
        
        try:
            logger.info(f"Converting audio to {target_format}...")
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=3600,
                check=False
            )
            
            if proc.returncode != 0:
                logger.warning(f"Conversion failed: {proc.stderr}")
                return audio_file  # Return original
            
            # Remove original if conversion succeeded
            try:
                audio_file.unlink()
            except Exception:
                pass
            
            return output_file
        
        except Exception as e:
            logger.warning(f"Conversion error: {e}")
            return audio_file
    
    def _tag_audio(self, audio_file: Path, artist: str, album: str, title: str):
        """Tag audio file with metadata."""
        cmd = [
            "ffmpeg", "-y",
            "-i", str(audio_file),
            "-c:a", "copy",
            "-metadata", f"artist={artist}",
            "-metadata", f"album={album}",
            "-metadata", f"title={title}",
            str(audio_file.parent / f"tagged.{audio_file.suffix.lstrip('.')}")
        ]
        
        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=600,
                check=False
            )
            
            if proc.returncode == 0:
                # Replace original with tagged version
                tagged = audio_file.parent / f"tagged.{audio_file.suffix.lstrip('.')}"
                audio_file.unlink()
                tagged.rename(audio_file)
        
        except Exception as e:
            logger.warning(f"Failed to tag audio: {e}")
    
    def _probe_duration(self, file_path: Path) -> float:
        """Get file duration using ffprobe."""
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(file_path),
        ]
        
        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=60,
                check=False
            )
            
            if proc.returncode == 0:
                duration_str = proc.stdout.strip()
                return float(duration_str)
            
            return 0.0
        
        except Exception as e:
            logger.error(f"Failed to probe duration: {e}")
            return 0.0
    
    def _validate_duration(self, expected: float, actual: float) -> bool:
        """Check if actual duration matches expected within tolerance."""
        if expected == 0:
            return True  # Skip validation if online duration unknown
        
        abs_diff = abs(expected - actual)
        pct_diff = abs_diff / expected if expected > 0 else 0
        
        abs_ok = abs_diff <= self.cfg.DURATION_TOL_SEC
        pct_ok = pct_diff <= self.cfg.DURATION_TOL_PCT
        
        return abs_ok or pct_ok
