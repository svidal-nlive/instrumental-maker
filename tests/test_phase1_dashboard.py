"""
Test Phase 1 Dashboard functionality
Tests database initialization, API endpoints, and configuration loading
"""
import sys
import os
import json
import tempfile
from pathlib import Path
from datetime import datetime

# Add app to path
sys.path.insert(0, '/home/roredev/instrumental-maker')

from app.webui.models import ConfigDB
from app.webui.app import create_app, _init_config_db

def test_config_db():
    """Test ConfigDB initialization and basic operations."""
    print("\n=== Testing ConfigDB ===")
    
    # Use actual pipeline directories for consistency
    pipeline_root = Path('/home/roredev/instrumental-maker/pipeline-data')
    db_dir = pipeline_root / 'db'
    db_dir.mkdir(parents=True, exist_ok=True)
    
    db_path = db_dir / 'test_phase1.db'
    db = ConfigDB(db_path)
    
    try:
        # Test setting config
        print("Testing set_config...")
        db.set_config('TEST_BOOL', True, 'bool', 'Test boolean', is_default=True)
        db.set_config('TEST_INT', 42, 'int', 'Test integer', is_default=True)
        db.set_config('TEST_STR', 'hello', 'str', 'Test string', is_default=False)
        
        # Test getting config
        print("Testing get_config...")
        config = db.get_config('TEST_BOOL')
        assert config is not None, "Failed to get config"
        assert config['value'] is True, f"Expected True, got {config['value']}"
        assert config['is_default'] is True, "is_default should be True"
        print(f"  ✓ Retrieved config: {config}")
        
        
        # Test get_all_config
        print("Testing get_all_config...")
        all_config = db.get_all_config()
        assert len(all_config) >= 3, f"Expected at least 3 configs, got {len(all_config)}"
        print(f"  ✓ Retrieved {len(all_config)} configuration items")
        
        # Test update
        print("Testing update...")
        db.set_config('TEST_INT', 100, 'int', 'Test integer', is_default=True)
        updated = db.get_config('TEST_INT')
        assert updated['value'] == 100, f"Expected 100, got {updated['value']}"
        print(f"  ✓ Updated TEST_INT to {updated['value']}")
        
        # Test queue status
        print("Testing queue_status...")
        db.update_queue_status('youtube_audio', 5)
        db.update_queue_status('youtube_video', 3)
        db.update_queue_status('other', 1)
        status = db.get_queue_status()
        assert status['youtube_audio']['job_count'] == 5, "Queue count mismatch"
        print(f"  ✓ Queue status: {status}")
        
        # Test completed jobs
        print("Testing completed_jobs...")
        db.add_completed_job(
            'job-001',
            'youtube',
            'audio',
            'success',
            '/outputs/job-001/manifest.json'
        )
        jobs = db.get_recent_jobs(10)
        assert len(jobs) >= 1, "Failed to retrieve completed jobs"
        assert jobs[0]['job_id'] == 'job-001', "Job ID mismatch"
        print(f"  ✓ Added completed job: {jobs[0]}")
    finally:
        # Cleanup: Remove test database
        if db_path.exists():
            db_path.unlink()
        
    print("✓ All ConfigDB tests passed!\n")

def test_flask_app_initialization():
    """Test Flask app initialization with database using actual pipeline directories."""
    print("\n=== Testing Flask App Initialization ===")
    
    # Use actual pipeline directories for consistency
    pipeline_root = Path('/home/roredev/instrumental-maker/pipeline-data')
    db_dir = pipeline_root / 'db'
    db_dir.mkdir(parents=True, exist_ok=True)
    
    os.environ['DB_PATH'] = str(db_dir)
    os.environ['QUEUE_ENABLED'] = 'true'
    
    try:
        app = create_app()
        print("✓ Flask app created successfully")
        
        # Check that database is initialized
        config_db = app.config.get('CONFIG_DB')
        assert config_db is not None, "CONFIG_DB not initialized"
        print("✓ CONFIG_DB initialized")
        
        # Check some configuration values
        config = config_db.get_all_config()
        assert 'GENERATE_NO_DRUMS_VARIANT' in config, "Missing variant config"
        assert 'DEMUCS_DEVICE' in config, "Missing demucs config"
        assert 'NAS_SYNC_METHOD' in config, "Missing NAS config"
        print(f"✓ Configuration loaded ({len(config)} items)")
        
        # List some config items
        print("  Sample configurations:")
        for key in ['GENERATE_NO_DRUMS_VARIANT', 'DEMUCS_DEVICE', 'NAS_SYNC_METHOD']:
            item = config[key]
            print(f"    - {key}: {item['value']} ({item['data_type']})")
    
    except Exception as e:
        print(f"✗ Failed to initialize Flask app: {e}")
        raise
    
    print("✓ All Flask app tests passed!\n")

def test_api_endpoints():
    """Test API endpoints in test client using actual pipeline directories."""
    print("\n=== Testing API Endpoints ===")
    
    # Use actual pipeline directories for consistency
    pipeline_root = Path('/home/roredev/instrumental-maker/pipeline-data')
    db_dir = pipeline_root / 'db'
    db_dir.mkdir(parents=True, exist_ok=True)
    
    os.environ['DB_PATH'] = str(db_dir)
    os.environ['QUEUE_ENABLED'] = 'true'
    
    app = create_app()
    client = app.test_client()
    
    # Test /api/health
    print("Testing /api/health...")
    response = client.get('/api/health')
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = json.loads(response.data)
    assert data['status'] == 'healthy', "Health check failed"
    print(f"  ✓ Health check: {data['status']}")
    
    # Test /api/status
    print("Testing /api/status...")
    response = client.get('/api/status')
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = json.loads(response.data)
    assert 'queue_enabled' in data, "Missing queue_enabled field"
    assert 'queues' in data, "Missing queues field"
    assert 'outputs' in data, "Missing outputs field"
    print(f"  ✓ Status: queue_enabled={data['queue_enabled']}, queues={data['queues']}")
    
    # Test /api/config (GET all)
    print("Testing /api/config...")
    response = client.get('/api/config')
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    config = json.loads(response.data)
    assert 'GENERATE_NO_DRUMS_VARIANT' in config, "Missing variant config"
    print(f"  ✓ Retrieved {len(config)} configuration items")
    
    # Test /api/config/<key> (GET)
    print("Testing /api/config/DEMUCS_DEVICE...")
    response = client.get('/api/config/DEMUCS_DEVICE')
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = json.loads(response.data)
    assert data['key'] == 'DEMUCS_DEVICE', "Config key mismatch"
    print(f"  ✓ Retrieved: {data['key']} = {data['value']}")
    
    # Test /api/config/<key> (PUT)
    print("Testing /api/config/DEMUCS_DEVICE (PUT)...")
    response = client.put(
        '/api/config/DEMUCS_DEVICE',
        data=json.dumps({'value': 'cuda'}),
        content_type='application/json'
    )
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = json.loads(response.data)
    assert data['config']['value'] == 'cuda', f"Expected 'cuda', got {data['config']['value']}"
    print(f"  ✓ Updated DEMUCS_DEVICE to: {data['config']['value']}")
    
    # Test /api/config/<key>/reset
    print("Testing /api/config/DEMUCS_DEVICE/reset...")
    response = client.post('/api/config/DEMUCS_DEVICE/reset')
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = json.loads(response.data)
    # Should be reset to original default (cpu in test environment)
    print(f"  ✓ Reset DEMUCS_DEVICE to: {data['config']['value']}")
    
    # Test /api/jobs/recent
    print("Testing /api/jobs/recent...")
    response = client.get('/api/jobs/recent')
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = json.loads(response.data)
    assert 'jobs' in data, "Missing jobs field"
    print(f"  ✓ Retrieved {len(data['jobs'])} recent jobs")
    
    print("✓ All API endpoint tests passed!\n")

if __name__ == '__main__':
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║     Phase 1 Dashboard - Integration Tests                      ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    
    try:
        test_config_db()
        test_flask_app_initialization()
        test_api_endpoints()
        
        print("╔════════════════════════════════════════════════════════════════╗")
        print("║     ✓ All Phase 1 tests passed!                               ║")
        print("╚════════════════════════════════════════════════════════════════╝")
        sys.exit(0)
    
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
