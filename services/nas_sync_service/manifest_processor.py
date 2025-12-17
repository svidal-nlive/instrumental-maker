"""
Manifest watcher and router for NAS Sync service.

Watches the /outputs directory for manifest.json files and routes
artifacts to configured remote paths based on kind + variant matching.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RouteMatch:
    """Result of matching an artifact against routes."""
    artifact: Dict[str, Any]
    remote_path: Optional[str]  # None if no match


class ManifestWatcher:
    """Watches /outputs for manifest.json and processes them."""
    
    def __init__(self, outputs_dir: Path):
        """
        Args:
            outputs_dir: Root /outputs directory to watch
        """
        self.outputs_dir = Path(outputs_dir)
    
    def discover_manifests(self) -> List[Path]:
        """
        Find all manifest.json files in /outputs that haven't been processed yet.
        
        Returns:
            List of paths to manifest.json files.
        """
        manifests = []
        
        if not self.outputs_dir.exists():
            logger.debug(f"Outputs directory does not exist: {self.outputs_dir}")
            return manifests
        
        # Look for manifest.json in any job subdirectory
        for manifest_path in self.outputs_dir.glob("*/manifest.json"):
            manifests.append(manifest_path)
        
        return sorted(manifests)
    
    def load_manifest(self, manifest_path: Path) -> Optional[Dict[str, Any]]:
        """
        Load and parse manifest.json.
        
        Args:
            manifest_path: Path to manifest.json
        
        Returns:
            Parsed manifest dict, or None if error.
        """
        try:
            with open(manifest_path, "r") as f:
                manifest = json.load(f)
            return manifest
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse manifest: {manifest_path}: {e}")
            return None
        except FileNotFoundError:
            logger.debug(f"Manifest disappeared: {manifest_path}")
            return None
        except Exception as e:
            logger.error(f"Error loading manifest: {manifest_path}: {e}")
            return None
    
    def get_job_directory(self, manifest_path: Path) -> Path:
        """
        Get the directory containing this manifest (the job output directory).
        """
        return manifest_path.parent


class RouteResolver:
    """Resolves which artifacts should go where."""
    
    def __init__(self, routes: List[Dict[str, Any]], remote_roots: Dict[str, str]):
        """
        Args:
            routes: List of route definitions from config:
                [
                    {
                        "kind": "audio",
                        "variant": "instrumental",
                        "to": "${remoteRoots.audio}/Instrumental"
                    },
                    ...
                ]
            remote_roots: Dict of remote root paths:
                {
                    "audio": "/mnt/nas/Instrumentals",
                    "video": "/mnt/nas/Videos",
                    ...
                }
        """
        self.routes = routes
        self.remote_roots = remote_roots
    
    def resolve_artifact(self, artifact: Dict[str, Any]) -> Optional[str]:
        """
        Find matching remote path for an artifact.
        
        Args:
            artifact: Artifact dict from manifest["artifacts"] with:
                - kind: "audio", "video", "stems"
                - variant: "instrumental", "no_drums", "drums_only", etc.
                - label: Human-readable
                - path: Relative path
        
        Returns:
            Remote path string, or None if no match found.
        """
        artifact_kind = artifact.get("kind")
        artifact_variant = artifact.get("variant")
        
        for route in self.routes:
            route_kind = route.get("kind")
            route_variant = route.get("variant")
            
            # Check if this route matches the artifact
            if route_kind and artifact_kind != route_kind:
                continue
            if route_variant and artifact_variant != route_variant:
                continue
            
            # Found a match - expand variables and return
            remote_path_template = route.get("to", "")
            return self._expand_variables(remote_path_template)
        
        # No match found
        return None
    
    def _expand_variables(self, path_template: str) -> str:
        """Replace ${remoteRoots.key} with actual paths."""
        result = path_template
        
        for key, value in self.remote_roots.items():
            placeholder = f"${{remoteRoots.{key}}}"
            result = result.replace(placeholder, value)
        
        return result
    
    def resolve_all_artifacts(
        self,
        manifest: Dict[str, Any],
        skip_on_missing: bool = True,
    ) -> List[RouteMatch]:
        """
        Resolve all artifacts in a manifest.
        
        Args:
            manifest: Parsed manifest.json
            skip_on_missing: If True, skip artifacts with no matching route
        
        Returns:
            List of RouteMatch objects (including skipped ones if not skip_on_missing).
        """
        results = []
        artifacts = manifest.get("artifacts", [])
        
        for artifact in artifacts:
            remote_path = self.resolve_artifact(artifact)
            
            if not remote_path and skip_on_missing:
                artifact_label = artifact.get("label", artifact.get("variant", "unknown"))
                logger.warning(
                    f"No route found for artifact {artifact_label} "
                    f"(kind={artifact.get('kind')}, variant={artifact.get('variant')})"
                )
                continue
            
            results.append(RouteMatch(artifact=artifact, remote_path=remote_path))
        
        return results


class ManifestProcessor:
    """High-level manifest processing: load, route, sync."""
    
    def __init__(
        self,
        route_resolver: RouteResolver,
        sync_backend,  # SyncBackend instance
        outputs_dir: Path,
    ):
        """
        Args:
            route_resolver: RouteResolver instance
            sync_backend: SyncBackend implementation (rsync, s3, etc.)
            outputs_dir: Root /outputs directory
        """
        self.resolver = route_resolver
        self.backend = sync_backend
        self.outputs_dir = Path(outputs_dir)
        self.watcher = ManifestWatcher(outputs_dir)
    
    def process_manifest(
        self,
        manifest_path: Path,
        dry_run: bool = False,
        skip_on_missing: bool = True,
    ) -> Tuple[int, int]:
        """
        Process a manifest: load it, route artifacts, sync them.
        
        Args:
            manifest_path: Path to manifest.json
            dry_run: If True, log but don't sync
            skip_on_missing: If True, skip unrouted artifacts
        
        Returns:
            (success_count, skip_count)
        """
        # Load manifest
        manifest = self.watcher.load_manifest(manifest_path)
        if not manifest:
            return (0, 0)
        
        # Get job directory (parent of manifest.json)
        job_dir = self.watcher.get_job_directory(manifest_path)
        
        # Resolve all artifacts
        matches = self.resolver.resolve_all_artifacts(manifest, skip_on_missing)
        
        success_count = 0
        skip_count = 0
        
        for match in matches:
            artifact = match.artifact
            artifact_path = artifact.get("path")
            artifact_label = artifact.get("label", artifact.get("variant", "unknown"))
            
            if not artifact_path:
                logger.warning(f"Artifact has no path: {artifact_label}")
                skip_count += 1
                continue
            
            if not match.remote_path:
                logger.warning(f"Artifact {artifact_label} has no remote path")
                skip_count += 1
                continue
            
            # Construct full local path
            local_artifact_path = job_dir / artifact_path
            
            if not local_artifact_path.exists():
                logger.error(
                    f"Artifact not found: {artifact_label} at {local_artifact_path}"
                )
                skip_count += 1
                continue
            
            # Sync the artifact
            ok = self.backend.sync(
                local_artifact_path,
                match.remote_path,
                artifact_label,
                dry_run=dry_run,
            )
            
            if ok:
                success_count += 1
            else:
                logger.warning(f"Failed to sync {artifact_label}")
        
        return (success_count, skip_count)
