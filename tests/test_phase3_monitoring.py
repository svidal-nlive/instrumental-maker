"""Phase 3 WebUI Tests: NAS Sync Monitoring & Job Manifest Viewer"""
import json
import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock

# Import Flask app and models
from app.webui.app import create_app
from app.webui.models import ConfigDB


@pytest.fixture
def app():
    """Create Flask app with test configuration."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Set up environment for test
        import os
        os.environ['DB_PATH'] = tmpdir
        os.environ['OUTPUTS_DIR'] = tmpdir
        os.environ['NAS_SYNC_LOG'] = str(Path(tmpdir) / 'nas_sync.jsonl')
        
        app = create_app()
        app.config['TESTING'] = True
        
        yield app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def nas_log_file(app):
    """Create sample NAS sync log."""
    log_path = Path(app.config['NAS_SYNC_LOG'])
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write sample events
    events = [
        {
            'timestamp': (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
            'event_type': 'manifest_processed',
            'status': 'success',
            'sync_method': 'rsync',
            'files_synced': 3,
            'bytes_synced': 1024 * 1024 * 50  # 50 MB
        },
        {
            'timestamp': (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
            'event_type': 'artifact_synced',
            'status': 'success',
            'artifact_id': 'art_001',
            'job_id': 'job_001',
            'artifact_kind': 'instrumental',
            'sync_method': 's3',
            'bytes_synced': 1024 * 1024 * 30  # 30 MB
        },
        {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'event_type': 'manifest_processed',
            'status': 'failed',
            'sync_method': 'rsync',
            'files_synced': 0,
            'bytes_synced': 0,
            'message': 'Connection timeout'
        }
    ]
    
    with open(log_path, 'w') as f:
        for event in events:
            f.write(json.dumps(event) + '\n')
    
    return log_path


@pytest.fixture
def sample_job(app):
    """Create sample job with artifacts."""
    import os
    # Make sure OUTPUTS_DIR env var is set
    outputs_dir = Path(os.environ.get('OUTPUTS_DIR', tempfile.gettempdir() + '/outputs'))
    outputs_dir.mkdir(parents=True, exist_ok=True)
    
    # Temporarily set the env var for the API routes
    old_env = os.environ.get('OUTPUTS_DIR')
    os.environ['OUTPUTS_DIR'] = str(outputs_dir)
    
    job_id = 'test_job_001'
    job_dir = outputs_dir / job_id
    
    # Create job directory structure
    (job_dir / 'instrumental').mkdir(parents=True, exist_ok=True)
    (job_dir / 'no_drums').mkdir(parents=True, exist_ok=True)
    
    # Create manifest
    manifest = {
        'job_id': job_id,
        'source': 'youtube',
        'job_type': 'instrumental_extraction',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'artifacts': [
            {
                'kind': 'instrumental',
                'filename': 'instrumental.mp3'
            },
            {
                'kind': 'no_drums',
                'filename': 'no_drums.mp3'
            }
        ]
    }
    
    with open(job_dir / 'manifest.json', 'w') as f:
        json.dump(manifest, f)
    
    # Create dummy artifact files
    (job_dir / 'instrumental' / 'instrumental.mp3').touch()
    (job_dir / 'instrumental' / 'metadata.json').write_text('{}')
    (job_dir / 'no_drums' / 'no_drums.mp3').touch()
    
    yield job_id, job_dir
    
    # Cleanup: restore old env var
    import os
    if old_env is None:
        os.environ.pop('OUTPUTS_DIR', None)
    else:
        os.environ['OUTPUTS_DIR'] = old_env


class TestNASSyncStatus:
    """Tests for NAS sync status endpoint."""
    
    def test_get_sync_status(self, client, nas_log_file):
        """Test getting sync status and statistics."""
        response = client.get('/api/nas-sync/status')
        assert response.status_code == 200
        
        data = response.get_json()
        assert 'timestamp' in data
        assert 'current_method' in data
        assert 'statistics' in data
        assert 'recent_events' in data
        
        stats = data['statistics']
        assert stats['total_syncs'] >= 0
        assert stats['successful_syncs'] >= 0
        assert stats['failed_syncs'] >= 0
        assert stats['skipped_syncs'] >= 0
        assert stats['total_files'] >= 0
        assert stats['total_bytes'] >= 0
    
    def test_sync_statistics_accuracy(self, client, nas_log_file):
        """Test that statistics are calculated correctly."""
        response = client.get('/api/nas-sync/status')
        data = response.get_json()
        stats = data['statistics']
        
        # Should have at least one successful and one failed sync
        assert stats['successful_syncs'] > 0
        assert stats['failed_syncs'] > 0
        assert stats['total_syncs'] > 0
        
        # Total should be sum of results
        assert stats['total_syncs'] >= stats['successful_syncs'] + stats['failed_syncs']


class TestArtifactSyncStatus:
    """Tests for artifact sync status endpoint."""
    
    def test_get_artifact_sync_status(self, client, nas_log_file):
        """Test getting artifact sync status."""
        response = client.get('/api/nas-sync/artifacts')
        assert response.status_code == 200
        
        data = response.get_json()
        assert 'timestamp' in data
        assert 'total_artifacts' in data
        assert 'artifacts' in data
        assert isinstance(data['artifacts'], list)


class TestSyncLogs:
    """Tests for sync logs endpoint."""
    
    def test_get_sync_logs(self, client, nas_log_file):
        """Test retrieving sync logs."""
        response = client.get('/api/nas-sync/logs')
        assert response.status_code == 200
        
        data = response.get_json()
        assert 'timestamp' in data
        assert 'total' in data
        assert 'returned' in data
        assert 'logs' in data
        assert isinstance(data['logs'], list)
    
    def test_sync_logs_with_limit(self, client, nas_log_file):
        """Test retrieving limited number of logs."""
        response = client.get('/api/nas-sync/logs?limit=2')
        data = response.get_json()
        
        # Should return at most 2 items
        assert len(data['logs']) <= 2
    
    def test_sync_logs_status_filter(self, client, nas_log_file):
        """Test filtering logs by status."""
        response = client.get('/api/nas-sync/logs?status=success')
        data = response.get_json()
        
        # All returned logs should have success status
        for log in data['logs']:
            if 'status' in log:
                assert log['status'] == 'success'


class TestSyncHealth:
    """Tests for sync health endpoint."""
    
    def test_sync_health(self, client, nas_log_file):
        """Test sync health status."""
        response = client.get('/api/nas-sync/health')
        assert response.status_code == 200
        
        data = response.get_json()
        assert 'timestamp' in data
        assert 'status' in data
        assert data['status'] in ['healthy', 'warning', 'unknown', 'error']
        assert 'total_events' in data
    
    def test_sync_health_status_calculation(self, client, nas_log_file):
        """Test that health status is calculated correctly."""
        response = client.get('/api/nas-sync/health')
        data = response.get_json()
        
        # With recent events, should be healthy or warning
        assert data['status'] in ['healthy', 'warning']
        assert data['total_events'] > 0


class TestConnectivityTest:
    """Tests for connectivity testing endpoint."""
    
    def test_connectivity_test_endpoint(self, client):
        """Test connectivity test endpoint exists."""
        response = client.post('/api/nas-sync/test-connectivity')
        assert response.status_code == 200
        
        data = response.get_json()
        assert 'timestamp' in data
        assert 'method' in data
        assert 'available' in data
        assert 'message' in data
        assert isinstance(data['available'], bool)


class TestJobManifest:
    """Tests for job manifest endpoint."""
    
    def test_get_job_manifest(self, client, sample_job):
        """Test retrieving job manifest."""
        job_id, _ = sample_job
        response = client.get(f'/api/jobs/{job_id}/manifest')
        assert response.status_code == 200
        
        data = response.get_json()
        assert 'job_id' in data
        assert 'source' in data
        assert 'job_type' in data
        assert 'artifacts' in data
    
    def test_get_nonexistent_job_manifest(self, client):
        """Test retrieving manifest for nonexistent job."""
        response = client.get('/api/jobs/nonexistent_job/manifest')
        assert response.status_code == 404


class TestJobArtifacts:
    """Tests for job artifacts endpoint."""
    
    def test_get_job_artifacts(self, client, sample_job):
        """Test retrieving job artifacts."""
        job_id, _ = sample_job
        response = client.get(f'/api/jobs/{job_id}/artifacts')
        assert response.status_code == 200
        
        data = response.get_json()
        assert 'job_id' in data
        assert 'timestamp' in data
        assert 'total_artifacts' in data
        assert 'manifest' in data
        assert 'artifacts' in data
        assert isinstance(data['artifacts'], list)
    
    def test_artifact_metadata(self, client, sample_job):
        """Test artifact metadata is correct."""
        job_id, _ = sample_job
        response = client.get(f'/api/jobs/{job_id}/artifacts')
        data = response.get_json()
        
        # Should have at least 2 artifacts (instrumental, no_drums)
        assert len(data['artifacts']) >= 2
        
        # Check artifact structure
        for artifact in data['artifacts']:
            assert 'name' in artifact
            assert 'type' in artifact
            assert 'files' in artifact
            assert 'total_size' in artifact
            assert isinstance(artifact['files'], list)
    
    def test_get_nonexistent_job_artifacts(self, client):
        """Test retrieving artifacts for nonexistent job."""
        response = client.get('/api/jobs/nonexistent_job/artifacts')
        assert response.status_code == 404
    
    def test_artifact_file_listing(self, client, sample_job):
        """Test that artifact files are properly listed."""
        job_id, _ = sample_job
        response = client.get(f'/api/jobs/{job_id}/artifacts')
        data = response.get_json()
        
        for artifact in data['artifacts']:
            # Each artifact should have files listed
            assert len(artifact['files']) > 0
            
            # Check file structure
            for file_info in artifact['files']:
                assert 'name' in file_info
                assert 'path' in file_info
                assert 'size' in file_info
                assert isinstance(file_info['size'], int)


class TestBlueprintRegistration:
    """Tests for proper blueprint registration."""
    
    def test_nas_monitor_blueprint_registered(self, app):
        """Test that nas_monitor blueprint is registered."""
        assert 'nas_monitor' in app.blueprints
    
    def test_nas_monitor_routes_exist(self, app, client):
        """Test that all nas_monitor routes are accessible."""
        routes = [
            '/api/nas-sync/status',
            '/api/nas-sync/artifacts',
            '/api/nas-sync/logs',
            '/api/nas-sync/health'
        ]
        
        for route in routes:
            response = client.get(route)
            # Should not be 404 (route not found)
            assert response.status_code != 404


class TestMonitoringIntegration:
    """Integration tests for monitoring features."""
    
    def test_status_endpoint_includes_method(self, client):
        """Test that status includes current sync method."""
        response = client.get('/api/nas-sync/status')
        data = response.get_json()
        
        assert 'current_method' in data
        # Should be one of the valid methods
        assert data['current_method'] in ['rsync', 's3', 'scp', 'local', 'unknown']
    
    def test_all_monitoring_endpoints_are_json(self, client, nas_log_file):
        """Test that all monitoring endpoints return JSON."""
        endpoints = [
            '/api/nas-sync/status',
            '/api/nas-sync/artifacts',
            '/api/nas-sync/logs',
            '/api/nas-sync/health'
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.content_type == 'application/json'


class TestErrorHandling:
    """Tests for error handling in monitoring."""
    
    def test_sync_status_with_missing_log(self, app, client):
        """Test sync status when log file doesn't exist."""
        # This should not crash - just return empty statistics
        response = client.get('/api/nas-sync/status')
        assert response.status_code == 200
        data = response.get_json()
        assert 'statistics' in data
    
    def test_connectivity_test_with_invalid_method(self, client, app):
        """Test connectivity with invalid method configured."""
        # Even with invalid method, should return valid JSON
        response = client.post('/api/nas-sync/test-connectivity')
        assert response.status_code == 200
        data = response.get_json()
        assert 'message' in data


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
