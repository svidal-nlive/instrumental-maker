"""Settings route for configuration management."""
from flask import Blueprint, jsonify, current_app, render_template_string

bp = Blueprint('settings', __name__, url_prefix='/settings')

# Configuration categories for organizing settings in the UI
CONFIG_CATEGORIES = {
    'Variant Generation': {
        'description': 'Audio variant generation settings',
        'variables': [
            'GENERATE_NO_DRUMS_VARIANT',
            'GENERATE_DRUMS_ONLY_VARIANT',
            'PRESERVE_STEMS'
        ]
    },
    'Demucs': {
        'description': 'Source separation model configuration',
        'variables': [
            'MODEL',
            'DEMUCS_DEVICE',
            'DEMUCS_JOBS',
            'DEMUCS_CHUNK_TIMEOUT_SEC',
            'DEMUCS_MAX_RETRIES'
        ]
    },
    'Audio Processing': {
        'description': 'Audio output and mixing settings',
        'variables': [
            'SAMPLE_RATE',
            'CHUNK_OVERLAP_SEC',
            'CROSSFADE_MS',
            'MP3_ENCODING'
        ]
    },
    'YouTube Download': {
        'description': 'YouTube video download settings',
        'variables': [
            'YTDL_MODE',
            'YTDL_AUDIO_FORMAT',
            'YTDL_DURATION_TOL_SEC',
            'YTDL_DURATION_TOL_PCT',
            'YTDL_FAIL_ON_DURATION_MISMATCH'
        ]
    },
    'NAS Synchronization': {
        'description': 'Network storage sync configuration',
        'variables': [
            'NAS_SYNC_METHOD',
            'NAS_DRY_RUN',
            'NAS_SKIP_ON_MISSING_REMOTE',
            'NAS_POLL_INTERVAL_SEC'
        ]
    },
    'Queue Processing': {
        'description': 'Job queue settings',
        'variables': [
            'QUEUE_ENABLED'
        ]
    }
}

def get_config_by_category():
    """Get all configurations organized by category."""
    db = current_app.config.get('CONFIG_DB')
    if db is None:
        return {}
    
    all_config = db.get_all_config()
    categorized = {}
    
    for category, info in CONFIG_CATEGORIES.items():
        categorized[category] = {
            'description': info['description'],
            'variables': {}
        }
        
        for var_name in info['variables']:
            if var_name in all_config:
                config_item = all_config[var_name]
                categorized[category]['variables'][var_name] = {
                    'value': config_item['value'],
                    'data_type': config_item['data_type'],
                    'description': config_item['description'],
                    'is_default': config_item['is_default']
                }
    
    return categorized

@bp.route('/api/config-categories', methods=['GET'])
def get_config_categories():
    """Get configuration categories with current values."""
    try:
        categorized = get_config_by_category()
        return jsonify(categorized), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/')
def settings_page():
    """Render the settings page."""
    return render_template_string("""
    <!-- Settings Page will be injected by JavaScript -->
    <div id="page-settings" class="page-content hidden">
        <div class="space-y-6 md:space-y-8">
            <!-- Settings Header -->
            <div class="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-4 md:p-6 border border-gray-200 dark:border-gray-700">
                <h2 class="text-xl md:text-2xl font-bold mb-2">System Configuration</h2>
                <p class="text-gray-600 dark:text-gray-400 text-sm md:text-base">
                    Manage pipeline settings. Changes apply immediately without restarting services.
                </p>
            </div>

            <!-- Settings Tabs -->
            <div class="flex flex-wrap gap-2 border-b border-gray-200 dark:border-gray-700">
                <button class="settings-tab-btn px-4 py-3 font-medium border-b-2 border-primary-600 text-primary-600 dark:text-primary-400" data-tab="variant-generation">
                    Variant Generation
                </button>
                <button class="settings-tab-btn px-4 py-3 font-medium border-b-2 border-transparent hover:border-gray-300 dark:hover:border-gray-600 text-gray-600 dark:text-gray-400" data-tab="demucs">
                    Demucs
                </button>
                <button class="settings-tab-btn px-4 py-3 font-medium border-b-2 border-transparent hover:border-gray-300 dark:hover:border-gray-600 text-gray-600 dark:text-gray-400" data-tab="audio">
                    Audio
                </button>
                <button class="settings-tab-btn px-4 py-3 font-medium border-b-2 border-transparent hover:border-gray-300 dark:hover:border-gray-600 text-gray-600 dark:text-gray-400" data-tab="youtube">
                    YouTube
                </button>
                <button class="settings-tab-btn px-4 py-3 font-medium border-b-2 border-transparent hover:border-gray-300 dark:hover:border-gray-600 text-gray-600 dark:text-gray-400" data-tab="nas-sync">
                    NAS Sync
                </button>
                <button class="settings-tab-btn px-4 py-3 font-medium border-b-2 border-transparent hover:border-gray-300 dark:hover:border-gray-600 text-gray-600 dark:text-gray-400" data-tab="queue">
                    Queue
                </button>
            </div>

            <!-- Settings Content -->
            <div id="settings-content">
                <!-- Loading state -->
                <div class="flex items-center justify-center py-12">
                    <div class="text-center">
                        <svg class="w-8 h-8 mx-auto mb-3 text-gray-400 animate-spin" fill="none" viewBox="0 0 24 24">
                            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        <p class="text-gray-600 dark:text-gray-400">Loading configuration...</p>
                    </div>
                </div>
            </div>

            <!-- Settings Help -->
            <div class="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                <p class="text-sm text-blue-800 dark:text-blue-300">
                    <strong>💡 Configuration Tips:</strong> All settings are loaded from your .env file on startup. 
                    Changes you make here are saved to the database and persist across restarts. 
                    You can reset any setting to its original default value.
                </p>
            </div>
        </div>
    </div>
    """)
