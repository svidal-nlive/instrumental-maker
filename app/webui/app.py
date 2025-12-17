"""Flask application for Instrumental Maker Web UI."""
import os
import json
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, jsonify, request, send_file, Response
from werkzeug.utils import secure_filename
import mimetypes

# Import routes
from app.webui.routes import dashboard, files, processing, logs, storage, nas, youtube, api
from app.webui.models import ConfigDB

# Try to import youtube_auth (requires google-auth-oauthlib)
try:
    from app.webui.routes import youtube_auth
    HAS_OAUTH = True
except ImportError:
    HAS_OAUTH = False

def _env_bool(key: str, default: bool = False) -> bool:
    """Parse environment variable as boolean."""
    value = os.environ.get(key, str(default)).lower()
    return value in ('true', '1', 'yes', 'on')

def _init_config_db(db_path: Path) -> ConfigDB:
    """Initialize configuration database with defaults from environment."""
    db = ConfigDB(db_path)
    
    # Define all configuration variables with their types and descriptions
    config_vars = {
        # Variant generation settings
        'GENERATE_NO_DRUMS_VARIANT': {
            'value': _env_bool('GENERATE_NO_DRUMS_VARIANT', False),
            'type': 'bool',
            'description': 'Generate no drums variant during audio processing'
        },
        'GENERATE_DRUMS_ONLY_VARIANT': {
            'value': _env_bool('GENERATE_DRUMS_ONLY_VARIANT', False),
            'type': 'bool',
            'description': 'Generate drums only variant during audio processing'
        },
        'PRESERVE_STEMS': {
            'value': _env_bool('PRESERVE_STEMS', False),
            'type': 'bool',
            'description': 'Keep individual stem files in output'
        },
        
        # Demucs settings
        'DEMUCS_DEVICE': {
            'value': os.environ.get('DEMUCS_DEVICE', 'cpu'),
            'type': 'str',
            'description': 'Device for demucs processing (cpu or cuda)'
        },
        'DEMUCS_JOBS': {
            'value': int(os.environ.get('DEMUCS_JOBS', '1')),
            'type': 'int',
            'description': 'Number of parallel demucs jobs'
        },
        'DEMUCS_CHUNK_TIMEOUT_SEC': {
            'value': int(os.environ.get('DEMUCS_CHUNK_TIMEOUT_SEC', '3600')),
            'type': 'int',
            'description': 'Timeout in seconds for demucs chunk processing'
        },
        'DEMUCS_MAX_RETRIES': {
            'value': int(os.environ.get('DEMUCS_MAX_RETRIES', '2')),
            'type': 'int',
            'description': 'Maximum retries for failed demucs jobs'
        },
        'MODEL': {
            'value': os.environ.get('MODEL', 'htdemucs'),
            'type': 'str',
            'description': 'Demucs model to use for source separation'
        },
        
        # Audio processing settings
        'SAMPLE_RATE': {
            'value': int(os.environ.get('SAMPLE_RATE', '44100')),
            'type': 'int',
            'description': 'Output sample rate in Hz'
        },
        'CHUNK_OVERLAP_SEC': {
            'value': int(os.environ.get('CHUNK_OVERLAP_SEC', '10')),
            'type': 'int',
            'description': 'Overlap duration between audio chunks in seconds'
        },
        'CROSSFADE_MS': {
            'value': int(os.environ.get('CROSSFADE_MS', '1000')),
            'type': 'int',
            'description': 'Crossfade duration in milliseconds'
        },
        'MP3_ENCODING': {
            'value': os.environ.get('MP3_ENCODING', 'cbr320'),
            'type': 'str',
            'description': 'MP3 encoding (cbr320, cbr256, vbr9, etc)'
        },
        
        # YouTube settings
        'YTDL_MODE': {
            'value': os.environ.get('YTDL_MODE', 'audio'),
            'type': 'str',
            'description': 'YouTube download mode (audio, video, or both)'
        },
        'YTDL_AUDIO_FORMAT': {
            'value': os.environ.get('YTDL_AUDIO_FORMAT', 'm4a'),
            'type': 'str',
            'description': 'Preferred audio format (m4a, flac, mp3, wav)'
        },
        'YTDL_DURATION_TOL_SEC': {
            'value': float(os.environ.get('YTDL_DURATION_TOL_SEC', '2.0')),
            'type': 'float',
            'description': 'Duration tolerance in seconds'
        },
        'YTDL_DURATION_TOL_PCT': {
            'value': float(os.environ.get('YTDL_DURATION_TOL_PCT', '0.01')),
            'type': 'float',
            'description': 'Duration tolerance as percentage'
        },
        'YTDL_FAIL_ON_DURATION_MISMATCH': {
            'value': _env_bool('YTDL_FAIL_ON_DURATION_MISMATCH', True),
            'type': 'bool',
            'description': 'Fail job if duration mismatch detected'
        },
        
        # NAS Sync settings
        'NAS_SYNC_METHOD': {
            'value': os.environ.get('NAS_SYNC_METHOD', 'rsync'),
            'type': 'str',
            'description': 'NAS sync method (rsync, s3, scp, local)'
        },
        'NAS_DRY_RUN': {
            'value': _env_bool('NAS_DRY_RUN', False),
            'type': 'bool',
            'description': 'Perform dry run without actually syncing'
        },
        'NAS_SKIP_ON_MISSING_REMOTE': {
            'value': _env_bool('NAS_SKIP_ON_MISSING_REMOTE', True),
            'type': 'bool',
            'description': 'Skip sync if remote destination is not available'
        },
        'NAS_POLL_INTERVAL_SEC': {
            'value': int(os.environ.get('NAS_POLL_INTERVAL_SEC', '5')),
            'type': 'int',
            'description': 'Poll interval in seconds for manifest watching'
        },
        
        # Queue settings
        'QUEUE_ENABLED': {
            'value': _env_bool('QUEUE_ENABLED', False),
            'type': 'bool',
            'description': 'Enable queue-based job processing'
        },
    }
    
    # Set all config values as defaults
    for key, config in config_vars.items():
        db.set_config(
            key=key,
            value=config['value'],
            data_type=config['type'],
            description=config['description'],
            is_default=True
        )
    
    return db

def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size
    
    # Data paths from environment or defaults
    app.config['INCOMING_DIR'] = Path(os.environ.get('INCOMING_DIR', '/data/incoming'))
    app.config['OUTPUT_DIR'] = Path(os.environ.get('MUSIC_LIBRARY', '/data/output'))
    app.config['WORKING_DIR'] = Path(os.environ.get('WORKING_DIR', '/data/working'))
    app.config['LOG_DIR'] = Path(os.environ.get('LOG_DIR', '/data/logs'))
    app.config['ARCHIVE_DIR'] = Path(os.environ.get('ARCHIVE_DIR', '/data/archive'))
    app.config['QUARANTINE_DIR'] = Path(os.environ.get('QUARANTINE_DIR', '/data/quarantine'))
    app.config['DB_PATH'] = Path(os.environ.get('DB_PATH', '/data/db'))
    app.config['NAS_SYNC_LOG'] = Path(os.environ.get('NAS_SYNC_LOG', '/data/logs/nas_sync.jsonl'))
    
    # Initialize configuration database
    db_path = app.config['DB_PATH'] / 'webui_config.db'
    app.config['CONFIG_DB'] = _init_config_db(db_path)
    
    # Register blueprints
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(files.bp)
    app.register_blueprint(processing.bp)
    app.register_blueprint(logs.bp)
    app.register_blueprint(storage.bp)
    app.register_blueprint(nas.bp)
    app.register_blueprint(youtube.bp)
    app.register_blueprint(api.bp)
    
    # Register OAuth blueprint if available
    if HAS_OAUTH:
        app.register_blueprint(youtube_auth.bp)
    
    @app.route('/')
    def index():
        """Render the main dashboard."""
        return render_template('index.html')
    
    @app.route('/health')
    def health():
        """Health check endpoint."""
        return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})
    
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)
