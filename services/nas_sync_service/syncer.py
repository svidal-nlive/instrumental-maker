"""
Sync implementation for different backends: rsync, S3, SCP, local.
"""

import subprocess
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class SyncBackend(ABC):
    """Abstract base for sync backends."""
    
    @abstractmethod
    def sync(
        self,
        local_path: Path,
        remote_path: str,
        artifact_label: str,
        dry_run: bool = False,
    ) -> bool:
        """
        Sync a file/folder to remote.
        
        Args:
            local_path: Local file or folder
            remote_path: Remote destination (backend-specific format)
            artifact_label: Human-readable label for logging
            dry_run: If True, log but don't execute
        
        Returns:
            True if successful, False otherwise.
        """
        pass


class RsyncBackend(SyncBackend):
    """Sync using rsync (for local NAS or SSH-mounted paths)."""
    
    def __init__(self, bw_limit: str = "0", compress: bool = True):
        """
        Args:
            bw_limit: Bandwidth limit in KB/s (0 = unlimited)
            compress: Whether to compress during transfer
        """
        self.bw_limit = bw_limit
        self.compress = compress
    
    def sync(
        self,
        local_path: Path,
        remote_path: str,
        artifact_label: str,
        dry_run: bool = False,
    ) -> bool:
        """Sync with rsync."""
        if not local_path.exists():
            logger.error(f"Local path does not exist: {local_path}")
            return False
        
        # Build rsync command
        cmd = ["rsync", "-av"]
        
        if self.compress:
            cmd.append("-z")
        
        if self.bw_limit != "0":
            cmd.extend(["--bwlimit", self.bw_limit])
        
        if dry_run:
            cmd.append("--dry-run")
        
        # Add trailing slash if local is directory (sync contents)
        local_str = str(local_path)
        if local_path.is_dir():
            local_str += "/"
        
        cmd.extend([local_str, remote_path])
        
        try:
            logger.info(f"[RSYNC] {artifact_label}: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,  # 1 hour timeout
            )
            
            if result.returncode == 0:
                logger.info(f"[RSYNC OK] {artifact_label}")
                return True
            else:
                logger.error(
                    f"[RSYNC FAIL] {artifact_label}: {result.stderr}"
                )
                return False
        
        except subprocess.TimeoutExpired:
            logger.error(f"[RSYNC TIMEOUT] {artifact_label}")
            return False
        except Exception as e:
            logger.error(f"[RSYNC ERROR] {artifact_label}: {e}")
            return False


class S3Backend(SyncBackend):
    """Sync to S3-compatible storage (AWS S3, MinIO, etc.)."""
    
    def __init__(
        self,
        bucket: str,
        prefix: str = "",
        region: str = "us-east-1",
        endpoint: Optional[str] = None,
    ):
        """
        Args:
            bucket: S3 bucket name
            prefix: S3 key prefix (e.g., "instrumental-maker/")
            region: AWS region
            endpoint: Custom S3 endpoint (for MinIO, etc.)
        """
        self.bucket = bucket
        self.prefix = prefix.rstrip("/")
        self.region = region
        self.endpoint = endpoint
        
        # Check if boto3 is available
        try:
            import boto3
            self.boto3 = boto3
        except ImportError:
            logger.warning("boto3 not available - S3 sync will fail")
            self.boto3 = None
    
    def sync(
        self,
        local_path: Path,
        remote_path: str,
        artifact_label: str,
        dry_run: bool = False,
    ) -> bool:
        """Sync to S3."""
        if not self.boto3:
            logger.error("boto3 required for S3 sync - not installed")
            return False
        
        if not local_path.exists():
            logger.error(f"Local path does not exist: {local_path}")
            return False
        
        try:
            # Create S3 client
            s3_kwargs = {"region_name": self.region}
            if self.endpoint:
                s3_kwargs["endpoint_url"] = self.endpoint
            
            s3 = self.boto3.client("s3", **s3_kwargs)
            
            # Build S3 key
            s3_key = f"{self.prefix}/{remote_path.lstrip('/')}"
            
            if dry_run:
                logger.info(
                    f"[S3 DRY RUN] {artifact_label}: "
                    f"s3://{self.bucket}/{s3_key}"
                )
                return True
            
            # Upload file or folder
            if local_path.is_file():
                logger.info(
                    f"[S3] Uploading {artifact_label}: "
                    f"{local_path} -> s3://{self.bucket}/{s3_key}"
                )
                s3.upload_file(str(local_path), self.bucket, s3_key)
                return True
            else:
                # Upload directory recursively
                logger.info(
                    f"[S3] Uploading folder {artifact_label}: "
                    f"{local_path} -> s3://{self.bucket}/{s3_key}/"
                )
                for file_path in local_path.rglob("*"):
                    if file_path.is_file():
                        rel_path = file_path.relative_to(local_path)
                        file_s3_key = f"{s3_key}/{rel_path}"
                        s3.upload_file(str(file_path), self.bucket, file_s3_key)
                return True
        
        except Exception as e:
            logger.error(f"[S3 ERROR] {artifact_label}: {e}")
            return False


class ScpBackend(SyncBackend):
    """Sync via SCP to remote server."""
    
    def __init__(self, host: str, user: str, key: str = "/home/user/.ssh/id_rsa"):
        """
        Args:
            host: Remote hostname or IP
            user: Remote username
            key: Path to SSH private key
        """
        self.host = host
        self.user = user
        self.key = key
    
    def sync(
        self,
        local_path: Path,
        remote_path: str,
        artifact_label: str,
        dry_run: bool = False,
    ) -> bool:
        """Sync via SCP."""
        if not local_path.exists():
            logger.error(f"Local path does not exist: {local_path}")
            return False
        
        # Build SCP target
        scp_target = f"{self.user}@{self.host}:{remote_path}"
        
        # Build command
        cmd = [
            "scp",
            "-r",  # Recursive for folders
            "-i", self.key,
            str(local_path),
            scp_target,
        ]
        
        try:
            if dry_run:
                logger.info(f"[SCP DRY RUN] {artifact_label}: {' '.join(cmd)}")
                return True
            
            logger.info(f"[SCP] {artifact_label}: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,
            )
            
            if result.returncode == 0:
                logger.info(f"[SCP OK] {artifact_label}")
                return True
            else:
                logger.error(f"[SCP FAIL] {artifact_label}: {result.stderr}")
                return False
        
        except subprocess.TimeoutExpired:
            logger.error(f"[SCP TIMEOUT] {artifact_label}")
            return False
        except Exception as e:
            logger.error(f"[SCP ERROR] {artifact_label}: {e}")
            return False


class LocalBackend(SyncBackend):
    """Local filesystem copy (for testing or local NAS paths)."""
    
    def sync(
        self,
        local_path: Path,
        remote_path: str,
        artifact_label: str,
        dry_run: bool = False,
    ) -> bool:
        """Copy to local path (like rsync: copies file INTO directory)."""
        if not local_path.exists():
            logger.error(f"Local path does not exist: {local_path}")
            return False
        
        remote_base = Path(remote_path)
        
        try:
            if dry_run:
                logger.info(
                    f"[LOCAL DRY RUN] {artifact_label}: {local_path} -> {remote_base}/"
                )
                return True
            
            import shutil
            
            # Create target directory
            remote_base.mkdir(parents=True, exist_ok=True)
            
            # Copy file or folder INTO the target directory (like rsync with trailing slash)
            if local_path.is_file():
                target = remote_base / local_path.name
                logger.info(
                    f"[LOCAL COPY] {artifact_label}: {local_path} -> {target}"
                )
                shutil.copy2(local_path, target)
            else:
                # Copy directory INTO the target
                target = remote_base / local_path.name
                if target.exists():
                    shutil.rmtree(target)
                logger.info(
                    f"[LOCAL COPY] {artifact_label}: {local_path} -> {target}/"
                )
                shutil.copytree(local_path, target)
            
            logger.info(f"[LOCAL OK] {artifact_label}")
            return True
        
        except Exception as e:
            logger.error(f"[LOCAL ERROR] {artifact_label}: {e}")
            return False
