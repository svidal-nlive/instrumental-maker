"""
Integration test for queue-based pipeline (Phase 2).

Tests:
1. JobBundle creation and serialization
2. QueueConsumer job discovery and claiming
3. ManifestGenerator artifact list generation
4. Full queue→process→archive workflow
"""

import tempfile
import json
from pathlib import Path
import shutil
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.job_bundle import JobBundle, JobManifest, ArtifactMetadata, YouTubeMetadata
from app.queue_consumer import QueueConsumer
from app.manifest_generator import ManifestGenerator


def test_job_bundle_creation():
    """Test JobBundle creation and serialization."""
    print("\n✓ Test: JobBundle creation")
    
    bundle = JobBundle(
        job_id="test_001",
        source_type="youtube",
        title="Test Song",
        artist="Test Artist",
        album="Test Album",
        audio_path=Path("/tmp/audio.m4a"),
        video_path=Path("/tmp/video.mp4"),
    )
    
    # Convert to job.json dict
    job_dict = bundle.to_job_json()
    assert job_dict["job_id"] == "test_001"
    assert job_dict["source_type"] == "youtube"
    assert job_dict["title"] == "Test Song"
    assert "audio_path" in job_dict
    print("  ✓ JobBundle.to_job_json() works")


def test_queue_consumer():
    """Test QueueConsumer discover, load, and archive."""
    print("\n✓ Test: QueueConsumer operations")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        queue_dir = tmpdir / "queues" / "youtube_audio"
        queue_dir.mkdir(parents=True)
        
        # Create a test job bundle
        job_id = "yt_test_001"
        job_folder = queue_dir / f"job_{job_id}"
        job_folder.mkdir()
        
        # Write a test job.json
        job_json = {
            "job_id": job_id,
            "source_type": "youtube",
            "artist": "Test Channel",
            "album": "YTDL",
            "title": "Test Video",
            "audio_path": "audio.m4a",
        }
        (job_folder / "job.json").write_text(json.dumps(job_json))
        
        # Create dummy audio file
        (job_folder / "audio.m4a").write_text("fake audio data")
        
        # Test QueueConsumer
        consumer = QueueConsumer({
            "youtube_audio": queue_dir,
        })
        
        # Discover jobs
        discovered = consumer.discover_jobs()
        assert "youtube_audio" in discovered
        assert len(discovered["youtube_audio"]) == 1
        print("  ✓ QueueConsumer.discover_jobs() works")
        
        # Load job bundle
        bundle = consumer.load_job_bundle(job_folder)
        assert bundle is not None
        assert bundle.job_id == job_id
        assert bundle.artist == "Test Channel"
        print("  ✓ QueueConsumer.load_job_bundle() works")
        
        # Archive job
        archive_dir = tmpdir / "archive"
        archive_dir.mkdir()
        success = consumer.archive_job(job_folder, archive_dir, "success")
        assert success
        assert (archive_dir / "success" / f"job_{job_id}").exists()
        assert not job_folder.exists()
        print("  ✓ QueueConsumer.archive_job() works")


def test_manifest_generation():
    """Test ManifestGenerator artifact list creation."""
    print("\n✓ Test: ManifestGenerator")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "outputs" / "test_001"
        output_dir.mkdir(parents=True)
        
        # Generate manifest
        manifest = ManifestGenerator.generate_for_job(
            job_id="test_001",
            source_type="youtube",
            artist="Test Artist",
            album="Test Album",
            title="Test Song",
            output_dir=output_dir,
            audio_variants=[
                {
                    "variant": "instrumental",
                    "label": "Instrumental",
                    "filename": "Test Artist - Test Song.m4a",
                    "codec": "aac",
                    "duration_sec": 180.5,
                }
            ],
            stems_preserved=False,
        )
        
        assert manifest.job_id == "test_001"
        assert len(manifest.artifacts) == 1
        assert manifest.artifacts[0].kind == "audio"
        assert manifest.artifacts[0].variant == "instrumental"
        print("  ✓ ManifestGenerator.generate_for_job() works")
        
        # Save manifest
        manifest_path = manifest.save(output_dir)
        assert manifest_path.exists()
        print("  ✓ JobManifest.save() works")
        
        # Load manifest
        loaded = JobManifest.load(manifest_path)
        assert loaded.job_id == "test_001"
        assert len(loaded.artifacts) == 1
        print("  ✓ JobManifest.load() works")


def test_full_queue_workflow():
    """Test complete queue → process → archive workflow."""
    print("\n✓ Test: Full queue workflow")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Setup directories
        queue_dir = tmpdir / "queues" / "youtube_audio"
        queue_dir.mkdir(parents=True)
        archive_dir = tmpdir / "archive"
        archive_dir.mkdir(parents=True)
        output_dir = tmpdir / "outputs"
        output_dir.mkdir()
        
        # Create a job bundle in queue
        job_id = "yt_workflow_001"
        job_folder = queue_dir / f"job_{job_id}"
        job_folder.mkdir()
        
        job_json = {
            "job_id": job_id,
            "source_type": "youtube",
            "artist": "Workflow Test",
            "album": "YTDL",
            "title": "Workflow Song",
            "audio_path": "source.m4a",
        }
        (job_folder / "job.json").write_text(json.dumps(job_json))
        (job_folder / "source.m4a").write_text("fake audio")
        
        # Step 1: Discover
        consumer = QueueConsumer({"youtube_audio": queue_dir})
        discovered = consumer.discover_jobs()
        assert len(discovered["youtube_audio"]) == 1
        print("  ✓ Step 1: Job discovered")
        
        # Step 2: Load
        job = discovered["youtube_audio"][0]
        bundle = consumer.load_job_bundle(job)
        assert bundle.job_id == job_id
        print("  ✓ Step 2: Bundle loaded")
        
        # Step 3: Claim
        working_dir = tmpdir / "working"
        working_dir.mkdir()
        claimed = consumer.claim_job(job, working_dir)
        assert claimed.exists()
        assert not job.exists()
        print("  ✓ Step 3: Job claimed (moved to working)")
        
        # Step 4: Process (simulated - create output)
        job_output = output_dir / job_id
        job_output.mkdir()
        (job_output / "files" / "audio").mkdir(parents=True)
        (job_output / "files" / "audio" / "output.m4a").write_text("fake instrumental")
        
        # Step 5: Generate manifest
        manifest = ManifestGenerator.generate_for_job(
            job_id=job_id,
            source_type=bundle.source_type,
            artist=bundle.artist,
            album=bundle.album,
            title=bundle.title,
            output_dir=job_output,
            audio_variants=[
                {
                    "variant": "instrumental",
                    "label": "Instrumental",
                    "filename": "output.m4a",
                    "codec": "aac",
                }
            ],
        )
        manifest.save(job_output)
        assert (job_output / "manifest.json").exists()
        print("  ✓ Step 4: Processing complete, manifest generated")
        
        # Step 6: Archive
        consumer.archive_job(claimed, archive_dir, "success")
        assert (archive_dir / "success" / f"job_{job_id}").exists()
        print("  ✓ Step 5: Job archived")
        
        # Verify manifest
        manifest_loaded = JobManifest.load(job_output / "manifest.json")
        assert manifest_loaded.job_id == job_id
        assert len(manifest_loaded.artifacts) > 0
        print("  ✓ Step 6: Manifest verified")
        
        print("\n✓ FULL WORKFLOW SUCCESS")


if __name__ == "__main__":
    print("=" * 60)
    print("Queue-Based Pipeline Integration Tests")
    print("=" * 60)
    
    test_job_bundle_creation()
    test_queue_consumer()
    test_manifest_generation()
    test_full_queue_workflow()
    
    print("\n" + "=" * 60)
    print("✓ ALL TESTS PASSED")
    print("=" * 60)
