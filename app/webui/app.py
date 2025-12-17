"""Flask application for Instrumental Maker Web UI."""
import os
import json
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, jsonify, request, send_file, Response
from werkzeug.utils import secure_filename
import mimetypes

# Import routes
from app.webui.routes import dashboard, files, processing, logs, storage, nas, youtube

# Try to import youtube_auth (requires google-auth-oauthlib)
try:
    from app.webui.routes import youtube_auth
    HAS_OAUTH = True
except ImportError:
    HAS_OAUTH = False

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
    
    # Register blueprints
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(files.bp)
    app.register_blueprint(processing.bp)
    app.register_blueprint(logs.bp)
    app.register_blueprint(storage.bp)
    app.register_blueprint(nas.bp)
    app.register_blueprint(youtube.bp)
    
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
