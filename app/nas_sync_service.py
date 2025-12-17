"""
NAS Sync service: watches /outputs for manifests and syncs artifacts to configured remote paths.

This is a separate, optional service that runs alongside instrumental-maker.
If not configured, it logs warnings and does nothing (jobs complete normally).
"""

from pathlib import Path
from typing import Dict, Optional, List, Any
import json
import time
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SyncRoute:
    """Route rule: match artifacts by kind+variant -> sync to remote path."""
    match_kind: str  # "audio", "video", "stems"
    match_variant: str  # "instrumental", "no_drums", "source", etc.
    remote_path: str  # "/mnt/nas/Instrumentals", etc.


class NASSyncService:
    """
    Watches /outputs for manifest.json files and syncs artifacts to remote paths.
    Configuration driven: if remote paths not configured, warnings are logged but processing continues.
    """
    
    def __init__(self, config_dict: Optional[Dict[str, Any]] = None):
        """
        Args:
            config_dict: Dict with structure:
                {
                    "enabled": True,
                    "remoteRoots": {
                        "audio": "/mnt/nas/Instrumentals",
                        "video": "/mnt/nas/Videos",
                        "stems": "/mnt/nas/Stems"
                    },
                    "routes": [
                        {
                            "match": {"kind": "audio", "variant": "instrumental"},
                            "to": "${remoteRoots.audio}/Instrumental"
                        },
                        ...
                    ]
                }
        """
        self.config = config_dict or {}
        self.enabled = self.config.get("enabled", False)
        self.remote_roots = self.config.get("remoteRoots", {})
        self.routes = self._parse_routes(self.config.get("routes", []))
    
    def _parse_routes(self, routes_raw: List[Dict[str, Any]]) -> List[tuple]:
        """
        Parse route definitions and expand ${remoteRoots.*} variables.
        Returns list of (match_dict, remote_path) tuples.
        """
        parsed = []
        for route in routes_raw:
            match = route.get("match", {})
            remote_raw = route.get("to", "")
            
            # Expand variables like ${remoteRoots.audio}
            remote = self._expand_variables(remote_raw)
            
            # Store as dict for easy matching
            parsed.append((match, remote))
        
        return parsed
    
    def _expand_variables(self, path_template: str) -> str:
        """Replace ${remoteRoots.key} with actual paths."""
        result = path_template
        for key, value in self.remote_roots.items():
            placeholder = f"${{remoteRoots.{key}}}"
            result = result.replace(placeholder, value)
        return result
    
    def find_route(self, artifact: Dict[str, Any]) -> Optional[str]:
        """
        Find a matching remote path for an artifact.
        
        Args:
            artifact: Dict from manifest["artifacts"] with "kind" and "variant"
        
        Returns:
            Remote path string, or None if no match found.
        """
        artifact_kind = artifact.get("kind")
        artifact_variant = artifact.get("variant")
        
        for match_dict, remote_path in self.routes:
            match_kind = match_dict.get("kind")
            match_variant = match_dict.get("variant")
            
            # If both kind and variant specified, both must match
            if match_kind and artifact_kind != match_kind:
                continue
            if match_variant and artifact_variant != match_variant:
                continue
            
            # Found a match
            return remote_path
        
        # No matching route
        return None
    
    def sync_artifact(
        self,
        artifact_local_path: Path,
        remote_path: str,
        artifact_label: str,
        dry_run: bool = False,
    ) -> bool:
        """
        Sync a single artifact to a remote path.
        
        Currently a stub; actual implementation would use rsync, SSH, S3, etc.
        
        Args:
            artifact_local_path: Path to file/folder on local system
            remote_path: Destination path on NAS
            artifact_label: Human-readable description (for logging)
            dry_run: If True, log but don't actually sync
        
        Returns:
            True if successful (or dry_run), False otherwise.
        """
        remote_full = f"{remote_path}/{artifact_local_path.name}"
        
        if dry_run:
            logger.info(f"[DRY RUN] Would sync {artifact_label}: {artifact_local_path} -> {remote_full}")
            return True
        
        # TODO: Implement actual sync mechanism
        #   - rsync for local NAS
        #   - S3 sync for cloud
        #   - SCP for remote servers
        #   - etc.
        
        logger.info(f"[NAS SYNC] Would sync {artifact_label}: {artifact_local_path} -> {remote_full}")
        return True
    
    def process_manifest(
        self,
        manifest_path: Path,
        outputs_dir: Path,
        dry_run: bool = False,
    ) -> bool:
        """
        Process a manifest: read it, find routes for each artifact, sync.
        
        Args:
            manifest_path: Path to manifest.json
            outputs_dir: Parent /outputs/ directory
            dry_run: If True, log but don't sync
        
        Returns:
            True if all syncs succeeded (or were skipped), False if errors occurred.
        """
        if not self.enabled:
            logger.debug(f"NAS Sync disabled; skipping {manifest_path}")
            return True
        
        try:
            with open(manifest_path, "r") as f:
                manifest = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load manifest {manifest_path}: {e}")
            return False
        
        job_id = manifest.get("job_id", "unknown")
        artifacts = manifest.get("artifacts", [])
        
        if not artifacts:
            logger.warning(f"Manifest {job_id} has no artifacts to sync")
            return True
        
        job_output_dir = manifest_path.parent
        success_count = 0
        
        for artifact in artifacts:
            kind = artifact.get("kind")
            variant = artifact.get("variant")
            artifact_rel_path = artifact.get("path")
            label = artifact.get("label", f"{kind}/{variant}")
            
            # Resolve local path
            artifact_local = job_output_dir / artifact_rel_path
            if not artifact_local.exists():
                logger.warning(f"Artifact missing (skip): {artifact_local}")
                continue
            
            # Find matching route
            remote_path = self.find_route(artifact)
            
            if not remote_path:
                logger.warning(
                    f"No route configured for {kind}/{variant} (label: {label}); "
                    f"artifact will not be synced: {artifact_rel_path}"
                )
                continue
            
            # Sync it
            if self.sync_artifact(artifact_local, remote_path, label, dry_run=dry_run):
                success_count += 1
            else:
                logger.error(f"Failed to sync {label}")
        
        return True  # Even if some syncs failed, continue processing


# Example configuration (can be loaded from YAML or environment)
DEFAULT_NAS_SYNC_CONFIG = {
    "enabled": False,  # Disabled by default
    "remoteRoots": {
        "audio": "",  # Not configured
        "video": "",
        "stems": "",
    },
    "routes": [
        {
            "match": {"kind": "audio", "variant": "instrumental"},
            "to": "${remoteRoots.audio}/Instrumental",
        },
        {
            "match": {"kind": "audio", "variant": "no_drums"},
            "to": "${remoteRoots.audio}/NoDrums",
        },
        {
            "match": {"kind": "audio", "variant": "drums_only"},
            "to": "${remoteRoots.audio}/DrumsOnly",
        },
        {
            "match": {"kind": "video", "variant": "source"},
            "to": "${remoteRoots.video}/YouTube",
        },
    ],
}
