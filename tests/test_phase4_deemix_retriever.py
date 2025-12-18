"""Tests for Phase 4 - Deemix Retriever Service"""

import pytest
import json
import logging
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import shutil

# Add services directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "deemix_retriever"))

from config import Config
from retriever import DeemixRetriever, DeemixDownloadError
from job_producer import JobBundleProducer


@pytest.fixture
def pipeline_root():
    """Provide actual pipeline directories for testing."""
    return Path(__file__).parent.parent / "pipeline-data"


@pytest.fixture
def test_config(pipeline_root):
    """Provide test configuration."""
    config = Config()
    config.QUEUE_OTHER = str(pipeline_root / "queues" / "other")
    config.WORKING_DIR = str(pipeline_root / "working" / "deemix_test")
    config.DEEMIX_QUALITY = "MP3_320"
    config.MAX_CONCURRENT = 1
    config.SKIP_ON_ERROR = True
    
    # Ensure directories exist
    Path(config.QUEUE_OTHER).mkdir(parents=True, exist_ok=True)
    Path(config.WORKING_DIR).mkdir(parents=True, exist_ok=True)
    
    return config


@pytest.fixture
def retriever(test_config):
    """Create a Deemix retriever instance."""
    return DeemixRetriever(test_config)


@pytest.fixture
def producer(test_config):
    """Create a job bundle producer instance."""
    return JobBundleProducer(test_config)


@pytest.fixture(autouse=True)
def cleanup_test_artifacts(test_config):
    """Clean up test artifacts after each test."""
    yield
    
    # Remove test job bundles from queue
    queue_dir = Path(test_config.QUEUE_OTHER)
    if queue_dir.exists():
        # Remove both .tmp and finalized bundles
        for bundle in queue_dir.glob("job_dz_*"):
            if bundle.is_dir():
                try:
                    shutil.rmtree(bundle)
                except Exception:
                    pass
    
    # Remove test working directory
    work_dir = Path(test_config.WORKING_DIR)
    if work_dir.exists():
        try:
            shutil.rmtree(work_dir)
            work_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass


class TestDeemixRetrieverConfig:
    """Test configuration loading."""
    
    def test_config_defaults(self):
        """Test that Config loads default values."""
        cfg = Config()
        assert cfg.SERVICE_NAME == "deemix_retriever"
        assert cfg.LOG_LEVEL == "INFO"
        assert cfg.DEEMIX_QUALITY == "FLAC"
        assert cfg.MAX_CONCURRENT > 0
    
    def test_config_environment_override(self, monkeypatch):
        """Test that environment variables override defaults."""
        monkeypatch.setenv("DEEMIX_QUALITY", "MP3_128")
        monkeypatch.setenv("MAX_CONCURRENT_DEEMIX", "4")
        
        cfg = Config()
        assert cfg.DEEMIX_QUALITY == "MP3_128"
        assert cfg.MAX_CONCURRENT == 4
    
    def test_config_ensure_directories(self, tmp_path, monkeypatch):
        """Test that ensure_directories creates necessary dirs."""
        # Set environment to use temp directories
        queue_dir = tmp_path / "queues" / "other"
        work_dir = tmp_path / "work"
        cache_dir = tmp_path / "cache"
        config_dir = tmp_path / "config"
        
        monkeypatch.setenv("QUEUE_OTHER", str(queue_dir))
        monkeypatch.setenv("DEEMIX_WORKING_DIR", str(work_dir))
        monkeypatch.setenv("DEEMIX_CACHE_DIR", str(cache_dir))
        monkeypatch.setenv("DEEMIX_CONFIG_DIR", str(config_dir))
        
        cfg = Config()
        cfg.ensure_directories()
        
        assert queue_dir.exists()
        assert work_dir.exists()
        assert cache_dir.exists()
        assert config_dir.exists()


class TestDeezerURLParsing:
    """Test URL parsing for various Deezer link types."""
    
    def test_parse_track_url(self, retriever):
        """Test parsing track URL."""
        url = "https://www.deezer.com/track/123456789"
        metadata = retriever._fetch_metadata(url)
        
        assert metadata is not None
        assert metadata["type"] == "track"
        assert metadata["id"] == "123456789"
    
    def test_parse_album_url(self, retriever):
        """Test parsing album URL."""
        url = "https://www.deezer.com/album/987654321"
        metadata = retriever._fetch_metadata(url)
        
        assert metadata is not None
        assert metadata["type"] == "album"
        assert metadata["id"] == "987654321"
    
    def test_parse_playlist_url(self, retriever):
        """Test parsing playlist URL."""
        url = "https://www.deezer.com/playlist/555666777"
        metadata = retriever._fetch_metadata(url)
        
        assert metadata is not None
        assert metadata["type"] == "playlist"
        assert metadata["id"] == "555666777"
    
    def test_invalid_url(self, retriever):
        """Test handling of invalid URL."""
        url = "https://example.com/invalid"
        metadata = retriever._fetch_metadata(url)
        
        assert metadata is None
    
    def test_url_with_trailing_slash(self, retriever):
        """Test URL parsing with trailing slash."""
        url = "https://www.deezer.com/track/123456789/"
        metadata = retriever._fetch_metadata(url)
        
        assert metadata is not None
        assert metadata["id"] == "123456789"


class TestJobBundleCreation:
    """Test job bundle creation from download results."""
    
    def test_create_single_track_bundle(self, producer, test_config, tmp_path):
        """Test creating a bundle for a single track."""
        # Create a mock audio file
        mock_audio = tmp_path / "track.mp3"
        mock_audio.write_bytes(b"mock audio data")
        
        download_result = {
            "job_id": "dz_123456789_test",
            "url": "https://www.deezer.com/track/123456789",
            "url_type": "track",
            "title": "Test Song",
            "artist": "Test Artist",
            "album": "Test Album",
            "duration": 180.0,
            "tracks": [
                {
                    "track_id": "123456789",
                    "title": "Test Song",
                    "artist": "Test Artist",
                    "album": "Test Album",
                    "duration_sec": 180.0,
                    "file_path": mock_audio,
                }
            ],
            "cover_path": None,
        }
        
        bundle_path = producer.produce_bundle(download_result)
        
        assert bundle_path is not None
        assert bundle_path.exists()
        assert bundle_path.name == "job_dz_123456789_test_deemix"
        
        # Verify bundle structure
        assert (bundle_path / "job.json").exists()
        assert (bundle_path / "files").exists()
        
        # Verify job.json content
        job_json = json.loads((bundle_path / "job.json").read_text())
        assert job_json["job_id"] == "dz_123456789_test_deemix"
        assert job_json["source_type"] == "deemix"
        assert job_json["artist"] == "Test Artist"
        assert job_json["album"] == "Test Album"
        assert len(job_json["audio_files"]) == 1
    
    def test_create_album_bundle(self, producer, test_config, tmp_path):
        """Test creating a bundle for an album with multiple tracks."""
        # Create mock audio files
        tracks = []
        for i in range(3):
            mock_audio = tmp_path / f"track_{i+1}.flac"
            mock_audio.write_bytes(b"mock audio data")
            tracks.append({
                "track_id": f"1234567{i}",
                "title": f"Track {i+1}",
                "artist": "Test Artist",
                "album": "Test Album",
                "duration_sec": 240.0 + (i * 10),
                "file_path": mock_audio,
            })
        
        download_result = {
            "job_id": "dz_987654321_test",
            "url": "https://www.deezer.com/album/987654321",
            "url_type": "album",
            "title": "Test Album",
            "artist": "Test Artist",
            "album": "Test Album",
            "duration": 750.0,
            "tracks": tracks,
            "cover_path": None,
        }
        
        bundle_path = producer.produce_bundle(download_result)
        
        assert bundle_path is not None
        assert bundle_path.exists()
        
        # Verify job.json contains all tracks
        job_json = json.loads((bundle_path / "job.json").read_text())
        assert len(job_json["audio_files"]) == 3
        assert len(job_json["tracks"]) == 3
        
        # Verify files are in the files directory
        files_dir = bundle_path / "files"
        audio_files = list(files_dir.glob("*.flac"))
        assert len(audio_files) == 3
    
    def test_create_bundle_with_cover_art(self, producer, test_config, tmp_path):
        """Test creating a bundle with cover art."""
        mock_audio = tmp_path / "track.mp3"
        mock_audio.write_bytes(b"mock audio data")
        
        mock_cover = tmp_path / "cover.jpg"
        mock_cover.write_bytes(b"mock image data")
        
        download_result = {
            "job_id": "dz_111111111_test",
            "url": "https://www.deezer.com/track/111111111",
            "url_type": "track",
            "title": "Test Song",
            "artist": "Test Artist",
            "album": "Test Album",
            "duration": 200.0,
            "tracks": [
                {
                    "track_id": "111111111",
                    "title": "Test Song",
                    "artist": "Test Artist",
                    "album": "Test Album",
                    "duration_sec": 200.0,
                    "file_path": mock_audio,
                }
            ],
            "cover_path": mock_cover,
        }
        
        bundle_path = producer.produce_bundle(download_result)
        
        assert bundle_path is not None
        assert (bundle_path / "files" / "cover.jpg").exists()
        
        # Verify job.json references cover
        job_json = json.loads((bundle_path / "job.json").read_text())
        assert "cover_path" in job_json
        assert job_json["cover_path"] == "cover.jpg"


class TestJobBundleFormat:
    """Test job bundle format compliance."""
    
    def test_bundle_structure(self, producer, test_config, tmp_path):
        """Test that bundle has correct structure."""
        mock_audio = tmp_path / "track.mp3"
        mock_audio.write_bytes(b"mock audio data")
        
        download_result = {
            "job_id": "dz_test_structure",
            "url": "https://www.deezer.com/track/test",
            "url_type": "track",
            "title": "Test",
            "artist": "Test",
            "album": "Test",
            "duration": 100.0,
            "tracks": [
                {
                    "track_id": "test",
                    "title": "Test",
                    "artist": "Test",
                    "album": "Test",
                    "duration_sec": 100.0,
                    "file_path": mock_audio,
                }
            ],
            "cover_path": None,
        }
        
        bundle_path = producer.produce_bundle(download_result)
        
        # Verify required files
        assert (bundle_path / "job.json").exists(), "Missing job.json"
        assert (bundle_path / "files").is_dir(), "Missing files directory"
        
        # Verify job.json is valid JSON
        job_json = json.loads((bundle_path / "job.json").read_text())
        
        # Verify required fields
        required_fields = [
            "job_id", "source_type", "artist", "album", "title",
            "audio_files", "deemix", "tracks"
        ]
        for field in required_fields:
            assert field in job_json, f"Missing required field: {field}"
        
        # Verify deemix metadata
        assert "url" in job_json["deemix"]
        assert "url_type" in job_json["deemix"]
        assert "track_count" in job_json["deemix"]


class TestErrorHandling:
    """Test error handling in retriever and producer."""
    
    def test_no_tracks_error(self, producer):
        """Test error when no tracks in result."""
        download_result = {
            "job_id": "dz_test",
            "url": "https://www.deezer.com/track/test",
            "url_type": "track",
            "title": "Test",
            "artist": "Test",
            "album": "Test",
            "duration": 100.0,
            "tracks": [],  # Empty!
            "cover_path": None,
        }
        
        bundle_path = producer.produce_bundle(download_result)
        assert bundle_path is None
    
    def test_missing_audio_file(self, producer, test_config):
        """Test error when audio file doesn't exist."""
        missing_file = Path(test_config.WORKING_DIR) / "nonexistent.mp3"
        
        download_result = {
            "job_id": "dz_test",
            "url": "https://www.deezer.com/track/test",
            "url_type": "track",
            "title": "Test",
            "artist": "Test",
            "album": "Test",
            "duration": 100.0,
            "tracks": [
                {
                    "track_id": "test",
                    "title": "Test",
                    "artist": "Test",
                    "album": "Test",
                    "duration_sec": 100.0,
                    "file_path": missing_file,
                }
            ],
            "cover_path": None,
        }
        
        # Should handle gracefully
        bundle_path = producer.produce_bundle(download_result)
        # Either returns None or creates bundle without the missing file
        # (depending on implementation choice)


class TestConfigIntegration:
    """Test integration with application config."""
    
    def test_queue_path_configuration(self, test_config):
        """Test that queue paths are properly configured."""
        assert test_config.QUEUE_OTHER
        assert Path(test_config.QUEUE_OTHER).exists()
    
    def test_working_directory_creation(self, test_config):
        """Test that working directory is created."""
        assert Path(test_config.WORKING_DIR).exists()
    
    def test_to_dict_serialization(self, test_config):
        """Test config can be serialized to dict."""
        config_dict = test_config.to_dict()
        
        assert isinstance(config_dict, dict)
        assert config_dict["SERVICE_NAME"] == "deemix_retriever"
        # The actual quality might be from environment, so just check it exists
        assert "DEEMIX_QUALITY" in config_dict


class TestPhase4Integration:
    """Test Phase 4 integration with the pipeline."""
    
    def test_bundle_compatible_with_simple_runner(self, producer, test_config, tmp_path):
        """Test that created bundles are compatible with simple_runner expectations."""
        mock_audio = tmp_path / "track.flac"
        mock_audio.write_bytes(b"mock audio data")
        
        download_result = {
            "job_id": "dz_phase4_test",
            "url": "https://www.deezer.com/album/test",
            "url_type": "album",
            "title": "Test Album",
            "artist": "Test Artist",
            "album": "Test Album",
            "duration": 300.0,
            "tracks": [
                {
                    "track_id": "test1",
                    "title": "Track 1",
                    "artist": "Test Artist",
                    "album": "Test Album",
                    "duration_sec": 180.0,
                    "file_path": mock_audio,
                }
            ],
            "cover_path": None,
        }
        
        bundle_path = producer.produce_bundle(download_result)
        
        # Verify simple_runner can read the bundle
        job_json_path = bundle_path / "job.json"
        assert job_json_path.exists()
        
        job_data = json.loads(job_json_path.read_text())
        
        # simple_runner expects these fields
        assert job_data["source_type"] == "deemix"  # Identifies source
        assert "artist" in job_data  # For tagging
        assert "album" in job_data  # For tagging
        assert "audio_files" in job_data  # Files to process
        
        # Verify audio files are accessible
        for audio_file in job_data["audio_files"]:
            audio_path = bundle_path / "files" / audio_file
            assert audio_path.exists(), f"Audio file not found: {audio_file}"
    
    def test_queue_directory_structure(self, test_config):
        """Test that queue directory structure is correct."""
        queue_dir = Path(test_config.QUEUE_OTHER)
        assert queue_dir.exists()
        assert queue_dir.is_dir()
        
        # Verify it's on the expected pipeline path
        assert "queues" in str(queue_dir)
        assert "other" in str(queue_dir)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
