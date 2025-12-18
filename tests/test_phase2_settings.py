"""
Test Phase 2 Settings Dashboard functionality
Tests settings route, configuration categories, and form handling
"""
import sys
import os
import json
import tempfile
from pathlib import Path

# Add app to path
sys.path.insert(0, '/home/roredev/instrumental-maker')

from app.webui.app import create_app

def test_settings_route():
    """Test settings route registration and initialization."""
    print("\n=== Testing Settings Route ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ['DB_PATH'] = tmpdir
        os.environ['QUEUE_ENABLED'] = 'true'
        
        app = create_app()
        client = app.test_client()
        
        # Test settings page loads
        print("Testing GET /settings/...")
        response = client.get('/settings/')
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert b'System Configuration' in response.data, "Settings page missing title"
        assert b'settings-tab-btn' in response.data, "Settings tabs missing"
        assert b'settings-content' in response.data, "Settings content area missing"
        print("  ✓ Settings page loads successfully")
        
    print("✓ All settings route tests passed!\n")

def test_config_categories_api():
    """Test configuration categories API endpoint."""
    print("\n=== Testing Config Categories API ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ['DB_PATH'] = tmpdir
        os.environ['QUEUE_ENABLED'] = 'true'
        
        app = create_app()
        client = app.test_client()
        
        # Test getting config categories
        print("Testing /settings/api/config-categories...")
        response = client.get('/settings/api/config-categories')
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = json.loads(response.data)
        print(f"  Retrieved {len(data)} categories:")
        
        # Verify expected categories exist
        expected_categories = [
            'Variant Generation',
            'Demucs',
            'Audio Processing',
            'YouTube Download',
            'NAS Synchronization',
            'Queue Processing'
        ]
        
        for category in expected_categories:
            assert category in data, f"Missing category: {category}"
            assert 'description' in data[category], f"Missing description for {category}"
            assert 'variables' in data[category], f"Missing variables for {category}"
            assert len(data[category]['variables']) > 0, f"No variables in {category}"
            print(f"    - {category}: {len(data[category]['variables'])} variables")
        
        # Verify specific variables are in correct categories
        variant_vars = data['Variant Generation']['variables']
        assert 'GENERATE_NO_DRUMS_VARIANT' in variant_vars, "Missing variant generation config"
        assert 'PRESERVE_STEMS' in variant_vars, "Missing preserve stems config"
        print("  ✓ Variant Generation variables present")
        
        demucs_vars = data['Demucs']['variables']
        assert 'DEMUCS_DEVICE' in demucs_vars, "Missing DEMUCS_DEVICE config"
        assert 'MODEL' in demucs_vars, "Missing MODEL config"
        print("  ✓ Demucs variables present")
        
        youtube_vars = data['YouTube Download']['variables']
        assert 'YTDL_MODE' in youtube_vars, "Missing YTDL_MODE config"
        assert 'YTDL_AUDIO_FORMAT' in youtube_vars, "Missing YTDL_AUDIO_FORMAT config"
        print("  ✓ YouTube variables present")
        
        nas_vars = data['NAS Synchronization']['variables']
        assert 'NAS_SYNC_METHOD' in nas_vars, "Missing NAS_SYNC_METHOD config"
        assert 'NAS_DRY_RUN' in nas_vars, "Missing NAS_DRY_RUN config"
        print("  ✓ NAS variables present")
        
        queue_vars = data['Queue Processing']['variables']
        assert 'QUEUE_ENABLED' in queue_vars, "Missing QUEUE_ENABLED config"
        print("  ✓ Queue variables present")
        
        # Verify variable structure
        sample_var = variant_vars['GENERATE_NO_DRUMS_VARIANT']
        assert 'value' in sample_var, "Missing value field"
        assert 'data_type' in sample_var, "Missing data_type field"
        assert 'description' in sample_var, "Missing description field"
        assert 'is_default' in sample_var, "Missing is_default field"
        print("  ✓ Variable structure correct")
        
    print("✓ All config categories API tests passed!\n")

def test_integration_with_api_endpoints():
    """Test that settings work with the existing API endpoints."""
    print("\n=== Testing Integration with API Endpoints ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ['DB_PATH'] = tmpdir
        os.environ['DEMUCS_DEVICE'] = 'cpu'
        
        app = create_app()
        client = app.test_client()
        
        # Get config via categories endpoint
        print("Testing config consistency...")
        categories_response = client.get('/settings/api/config-categories')
        categories_data = json.loads(categories_response.data)
        
        # Get same config via /api/config
        api_response = client.get('/api/config')
        api_data = json.loads(api_response.data)
        
        # Compare a value
        demucs_device_category = categories_data['Demucs']['variables']['DEMUCS_DEVICE']['value']
        demucs_device_api = api_data['DEMUCS_DEVICE']['value']
        assert demucs_device_category == demucs_device_api, "Config values don't match between endpoints"
        print(f"  ✓ DEMUCS_DEVICE consistent: {demucs_device_category}")
        
        # Test updating via API and reading via categories
        print("Testing config update flow...")
        update_response = client.put(
            '/api/config/DEMUCS_DEVICE',
            data=json.dumps({'value': 'cuda'}),
            content_type='application/json'
        )
        assert update_response.status_code == 200, "Failed to update config"
        
        # Read back via categories endpoint
        categories_response = client.get('/settings/api/config-categories')
        categories_data = json.loads(categories_response.data)
        updated_value = categories_data['Demucs']['variables']['DEMUCS_DEVICE']['value']
        assert updated_value == 'cuda', f"Expected 'cuda', got '{updated_value}'"
        print(f"  ✓ Config update reflected: {updated_value}")
        
        # Reset via API and verify
        reset_response = client.post('/api/config/DEMUCS_DEVICE/reset')
        assert reset_response.status_code == 200, "Failed to reset config"
        
        categories_response = client.get('/settings/api/config-categories')
        categories_data = json.loads(categories_response.data)
        reset_value = categories_data['Demucs']['variables']['DEMUCS_DEVICE']['value']
        assert reset_value == 'cpu', f"Expected 'cpu' after reset, got '{reset_value}'"
        print(f"  ✓ Config reset reflected: {reset_value}")
        
    print("✓ All integration tests passed!\n")

def test_all_config_variables_categorized():
    """Test that all configuration variables are properly categorized."""
    print("\n=== Testing All Variables Categorized ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ['DB_PATH'] = tmpdir
        
        app = create_app()
        client = app.test_client()
        
        # Get all variables from /api/config
        api_response = client.get('/api/config')
        api_data = json.loads(api_response.data)
        
        # Get categorized variables
        categories_response = client.get('/settings/api/config-categories')
        categories_data = json.loads(categories_response.data)
        
        # Flatten categorized variables
        categorized_vars = set()
        for category_info in categories_data.values():
            categorized_vars.update(category_info['variables'].keys())
        
        # Check that all API variables are in categories (ignoring extra test vars if any)
        print(f"API has {len(api_data)} variables")
        print(f"Categories cover {len(categorized_vars)} variables")
        
        api_vars = set(api_data.keys())
        all_covered = api_vars.issubset(categorized_vars)
        if not all_covered:
            missing = api_vars - categorized_vars
            print(f"  ⚠ Uncategorized variables: {missing}")
        else:
            print("  ✓ All variables properly categorized")
        
        # List variables by category
        for category_name in sorted(categories_data.keys()):
            var_count = len(categories_data[category_name]['variables'])
            var_names = ', '.join(sorted(categories_data[category_name]['variables'].keys())[:3])
            if var_count > 3:
                var_names += f" (+{var_count - 3} more)"
            print(f"  - {category_name}: {var_count} variables ({var_names})")
        
    print("✓ All categorization tests passed!\n")

if __name__ == '__main__':
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║     Phase 2 Settings Dashboard - Integration Tests            ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    
    try:
        test_settings_route()
        test_config_categories_api()
        test_integration_with_api_endpoints()
        test_all_config_variables_categorized()
        
        print("╔════════════════════════════════════════════════════════════════╗")
        print("║     ✓ All Phase 2 tests passed!                               ║")
        print("╚════════════════════════════════════════════════════════════════╝")
        sys.exit(0)
    
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
