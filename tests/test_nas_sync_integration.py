"""
Integration tests for NAS Sync Service (Phase 5).

Tests:
1. Route resolution (artifact matching)
2. Manifest loading and parsing
3. Sync backend initialization
4. Single manifest processing
5. Daemon mode discovery
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys

# Add services to path
sys.path.insert(0, str(Path(__file__).parent.parent / "services/nas_sync_service"))

from manifest_processor import (
    RouteResolver,
    ManifestWatcher,
    ManifestProcessor,
    RouteMatch,
)
from syncer import RsyncBackend, LocalBackend, S3Backend


@pytest.fixture
def temp_outputs_dir():
    """Create temporary outputs directory with test structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        outputs = Path(tmpdir) / "outputs"
        outputs.mkdir(parents=True)
        yield outputs


@pytest.fixture
def sample_manifest():
    """Sample manifest.json content."""
    return {
        "job_id": "youtube_test_20250101",
        "source_type": "youtube",
        "artist": "Test Channel",
        "album": "YTDL",
        "title": "Test Song",
        "processed_at": "2025-01-01T12:00:00Z",
        "artifacts": [
            {
                "kind": "audio",
                "variant": "instrumental",
                "label": "Instrumental",
                "path": "files/instrumental.m4a",
                "codec": "aac",
                "container": "m4a",
                "duration_sec": 180.5,
            },
            {
                "kind": "audio",
                "variant": "no_drums",
                "label": "Instrumental (no drums)",
                "path": "files/no_drums.m4a",
                "codec": "aac",
                "container": "m4a",
                "duration_sec": 180.5,
            },
            {
                "kind": "audio",
                "variant": "drums_only",
                "label": "Drums only",
                "path": "files/drums_only.m4a",
                "codec": "aac",
                "container": "m4a",
                "duration_sec": 180.5,
            },
        ],
        "youtube": {
            "video_id": "test123",
            "url": "https://www.youtube.com/watch?v=test123",
            "channel": "Test Channel",
            "title": "Test Song",
            "online_duration_sec": 185.0,
        },
        "stems_generated": True,
        "stems_preserved": False,
    }


@pytest.fixture
def sample_routes():
    """Sample route definitions."""
    return [
        {
            "kind": "audio",
            "variant": "instrumental",
            "to": "${remoteRoots.audio}/Instrumental",
        },
        {
            "kind": "audio",
            "variant": "no_drums",
            "to": "${remoteRoots.audio}/Instrumental (no drums)",
        },
        {
            "kind": "audio",
            "variant": "drums_only",
            "to": "${remoteRoots.audio}/Drums only",
        },
    ]


@pytest.fixture
def sample_remote_roots():
    """Sample remote root paths."""
    return {
        "audio": "/mnt/nas/Instrumentals",
        "video": "/mnt/nas/Videos",
        "stems": "/mnt/nas/Stems",
    }


class TestRouteResolver:
    """Test route resolution (artifact matching)."""
    
    def test_resolve_artifact_exact_match(self, sample_routes, sample_remote_roots):
        """Test resolving an artifact with exact kind+variant match."""
        resolver = RouteResolver(sample_routes, sample_remote_roots)
        
        artifact = {
            "kind": "audio",
            "variant": "instrumental",
            "label": "Instrumental",
            "path": "files/instrumental.m4a",
        }
        
        remote_path = resolver.resolve_artifact(artifact)
        assert remote_path == "/mnt/nas/Instrumentals/Instrumental"
    
    def test_resolve_artifact_partial_match(self, sample_routes, sample_remote_roots):
        """Test resolving with only kind specified in route."""
        routes = [{"kind": "audio", "to": "${remoteRoots.audio}"}]
        resolver = RouteResolver(routes, sample_remote_roots)
        
        artifact = {"kind": "audio", "variant": "any_variant"}
        remote_path = resolver.resolve_artifact(artifact)
        assert remote_path == "/mnt/nas/Instrumentals"
    
    def test_resolve_artifact_no_match(self, sample_routes, sample_remote_roots):
        """Test artifact with no matching route."""
        resolver = RouteResolver(sample_routes, sample_remote_roots)
        
        artifact = {"kind": "video", "variant": "source"}
        remote_path = resolver.resolve_artifact(artifact)
        assert remote_path is None
    
    def test_expand_variables(self, sample_routes, sample_remote_roots):
        """Test variable expansion in paths."""
        resolver = RouteResolver(sample_routes, sample_remote_roots)
        
        result = resolver._expand_variables("${remoteRoots.audio}/Test/${remoteRoots.video}")
        assert result == "/mnt/nas/Instrumentals/Test//mnt/nas/Videos"
    
    def test_resolve_all_artifacts(self, sample_routes, sample_remote_roots, sample_manifest):
        """Test resolving all artifacts in a manifest."""
        resolver = RouteResolver(sample_routes, sample_remote_roots)
        
        matches = resolver.resolve_all_artifacts(
            sample_manifest,
            skip_on_missing=False,
        )
        
        assert len(matches) == 3
        assert all(isinstance(m, RouteMatch) for m in matches)
        assert matches[0].remote_path == "/mnt/nas/Instrumentals/Instrumental"
        assert matches[1].remote_path == "/mnt/nas/Instrumentals/Instrumental (no drums)"
        assert matches[2].remote_path == "/mnt/nas/Instrumentals/Drums only"


class TestManifestWatcher:
    """Test manifest discovery and loading."""
    
    def test_discover_manifests(self, temp_outputs_dir, sample_manifest):
        """Test discovering manifest.json files."""
        # Create test manifests
        job1 = temp_outputs_dir / "job_001"
        job1.mkdir()
        manifest1 = job1 / "manifest.json"
        manifest1.write_text(json.dumps(sample_manifest))
        
        job2 = temp_outputs_dir / "job_002"
        job2.mkdir()
        manifest2 = job2 / "manifest.json"
        manifest2.write_text(json.dumps(sample_manifest))
        
        watcher = ManifestWatcher(temp_outputs_dir)
        manifests = watcher.discover_manifests()
        
        assert len(manifests) == 2
        assert manifest1 in manifests
        assert manifest2 in manifests
    
    def test_load_manifest(self, temp_outputs_dir, sample_manifest):
        """Test loading manifest.json."""
        job = temp_outputs_dir / "job_001"
        job.mkdir()
        manifest_path = job / "manifest.json"
        manifest_path.write_text(json.dumps(sample_manifest))
        
        watcher = ManifestWatcher(temp_outputs_dir)
        loaded = watcher.load_manifest(manifest_path)
        
        assert loaded["job_id"] == sample_manifest["job_id"]
        assert len(loaded["artifacts"]) == 3
    
    def test_load_manifest_invalid_json(self, temp_outputs_dir):
        """Test loading corrupted manifest."""
        job = temp_outputs_dir / "job_001"
        job.mkdir()
        manifest_path = job / "manifest.json"
        manifest_path.write_text("{invalid json")
        
        watcher = ManifestWatcher(temp_outputs_dir)
        loaded = watcher.load_manifest(manifest_path)
        
        assert loaded is None
    
    def test_get_job_directory(self, temp_outputs_dir):
        """Test getting job directory from manifest path."""
        job = temp_outputs_dir / "job_001"
        job.mkdir()
        manifest_path = job / "manifest.json"
        manifest_path.touch()
        
        watcher = ManifestWatcher(temp_outputs_dir)
        job_dir = watcher.get_job_directory(manifest_path)
        
        assert job_dir == job


class TestSyncBackends:
    """Test sync backend implementations."""
    
    def test_rsync_backend_init(self):
        """Test rsync backend initialization."""
        backend = RsyncBackend(bw_limit="1000", compress=True)
        assert backend.bw_limit == "1000"
        assert backend.compress is True
    
    def test_local_backend_sync(self, temp_outputs_dir):
        """Test local backend sync (copy)."""
        src = temp_outputs_dir / "source.txt"
        src.write_text("test content")
        
        dest = temp_outputs_dir / "dest" / "source.txt"
        dest.parent.mkdir(parents=True)
        
        backend = LocalBackend()
        ok = backend.sync(src, str(dest.parent), "test file", dry_run=False)
        
        assert ok is True
        assert dest.exists()
        assert dest.read_text() == "test content"
    
    def test_local_backend_sync_dry_run(self, temp_outputs_dir):
        """Test local backend dry run (no actual sync)."""
        src = temp_outputs_dir / "source.txt"
        src.write_text("test content")
        
        dest = temp_outputs_dir / "dest" / "source.txt"
        
        backend = LocalBackend()
        ok = backend.sync(src, str(dest), "test file", dry_run=True)
        
        assert ok is True
        assert not dest.exists()  # Not actually synced
    
    @patch("syncer.subprocess.run")
    def test_rsync_backend_sync(self, mock_run, temp_outputs_dir):
        """Test rsync backend sync."""
        src = temp_outputs_dir / "source.txt"
        src.write_text("test content")
        
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        
        backend = RsyncBackend(bw_limit="1000", compress=True)
        ok = backend.sync(src, "/remote/path", "test file", dry_run=False)
        
        assert ok is True
        mock_run.assert_called_once()


class TestManifestProcessor:
    """Test end-to-end manifest processing."""
    
    def test_process_manifest_with_local_backend(
        self,
        temp_outputs_dir,
        sample_manifest,
        sample_routes,
        sample_remote_roots,
    ):
        """Test processing a manifest with local sync backend."""
        # Create job directory with artifacts
        job = temp_outputs_dir / "job_001"
        job.mkdir()
        files = job / "files"
        files.mkdir()
        
        # Create dummy artifact files
        for artifact in sample_manifest["artifacts"]:
            artifact_path = job / artifact["path"]
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_bytes(b"dummy audio data")
        
        # Write manifest
        manifest_path = job / "manifest.json"
        manifest_path.write_text(json.dumps(sample_manifest))
        
        # Create remote directory
        remote = temp_outputs_dir / "remote"
        remote.mkdir()
        
        # Update remote roots to use temp directory
        remote_roots = {
            "audio": str(remote / "Instrumentals"),
            "video": str(remote / "Videos"),
            "stems": str(remote / "Stems"),
        }
        
        # Process
        resolver = RouteResolver(sample_routes, remote_roots)
        backend = LocalBackend()
        processor = ManifestProcessor(resolver, backend, temp_outputs_dir)
        
        success, skipped = processor.process_manifest(manifest_path, dry_run=False)
        
        assert success == 3
        assert skipped == 0
        
        # Verify files were synced
        # Routes create: {remoteRoot}/{variant_label}/filename
        assert (remote / "Instrumentals" / "Instrumental" / "instrumental.m4a").exists()
        assert (remote / "Instrumentals" / "Instrumental (no drums)" / "no_drums.m4a").exists()
        assert (remote / "Instrumentals" / "Drums only" / "drums_only.m4a").exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
