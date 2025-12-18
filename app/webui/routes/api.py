"""API routes for status and configuration endpoints."""
from flask import Blueprint, jsonify, request, current_app
from pathlib import Path
from datetime import datetime, timezone
import os
import json

bp = Blueprint('api', __name__, url_prefix='/api')

def _count_queue_items(queue_path: str) -> int:
    """Count items in a queue directory."""
    path = Path(queue_path)
    if not path.exists():
        return 0
    return len([f for f in path.iterdir() if f.is_file() and f.name.endswith('.json')])

def _get_outputs_info() -> dict:
    """Get information about completed outputs."""
    outputs_dir = Path(os.environ.get('OUTPUTS_DIR', '/data/outputs'))
    if not outputs_dir.exists():
        return {'total': 0, 'recent': []}
    
    manifests = sorted(outputs_dir.glob('*/manifest.json'), key=lambda p: p.stat().st_mtime, reverse=True)
    recent = []
    
    for manifest_file in manifests[:20]:
        try:
            with open(manifest_file) as f:
                manifest = json.load(f)
                recent.append({
                    'job_id': manifest.get('job_id'),
                    'source': manifest.get('source'),
                    'job_type': manifest.get('job_type'),
                    'completed_at': manifest.get('timestamp'),
                    'artifacts_count': len(manifest.get('artifacts', []))
                })
        except (json.JSONDecodeError, IOError):
            pass
    
    return {
        'total': len(manifests),
        'recent': recent
    }

@bp.route('/status', methods=['GET'])
def get_status():
    """Get current pipeline status including queue counts and recent jobs."""
    try:
        queue_enabled = os.environ.get('QUEUE_ENABLED', 'false').lower() == 'true'
        
        status = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'queue_enabled': queue_enabled,
            'queues': {}
        }
        
        if queue_enabled:
            # Get queue paths
            youtube_audio_queue = os.environ.get('QUEUE_YOUTUBE_AUDIO', '/queues/youtube_audio')
            youtube_video_queue = os.environ.get('QUEUE_YOUTUBE_VIDEO', '/queues/youtube_video')
            other_queue = os.environ.get('QUEUE_OTHER', '/queues/other')
            
            status['queues'] = {
                'youtube_audio': _count_queue_items(youtube_audio_queue),
                'youtube_video': _count_queue_items(youtube_video_queue),
                'other': _count_queue_items(other_queue)
            }
            status['queues']['total'] = sum(status['queues'].values())
        
        # Get outputs info
        outputs_info = _get_outputs_info()
        status['outputs'] = outputs_info
        
        # Get processing state (from simple_runner if available)
        pid_file = Path('/data/db/simple_runner.pid')
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                status['processing'] = {
                    'pid': pid,
                    'running': os.path.exists(f'/proc/{pid}')
                }
            except (ValueError, IOError):
                status['processing'] = {'pid': None, 'running': False}
        else:
            status['processing'] = {'pid': None, 'running': False}
        
        return jsonify(status), 200
    
    except Exception as e:
        return jsonify({
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 500

@bp.route('/config', methods=['GET'])
def get_config():
    """Get all configuration values."""
    try:
        db = current_app.config.get('CONFIG_DB')
        if db is None:
            return jsonify({'error': 'Database not initialized'}), 500
        
        config = db.get_all_config()
        return jsonify(config), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/config/<key>', methods=['GET'])
def get_config_item(key: str):
    """Get a specific configuration value."""
    try:
        db = current_app.config.get('CONFIG_DB')
        if db is None:
            return jsonify({'error': 'Database not initialized'}), 500
        
        config = db.get_config(key)
        if config is None:
            return jsonify({'error': f'Configuration key not found: {key}'}), 404
        
        return jsonify(config), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/config/<key>', methods=['PUT'])
def set_config_item(key: str):
    """Update a configuration value."""
    try:
        db = current_app.config.get('CONFIG_DB')
        if db is None:
            return jsonify({'error': 'Database not initialized'}), 500
        
        data = request.get_json()
        if data is None:
            return jsonify({'error': 'Request body must be JSON'}), 400
        
        if 'value' not in data:
            return jsonify({'error': 'Missing required field: value'}), 400
        
        # Get current config to preserve metadata
        current = db.get_config(key)
        if current is None:
            return jsonify({'error': f'Configuration key not found: {key}'}), 404
        
        # Update the value
        db.set_config(
            key=key,
            value=data['value'],
            data_type=current['data_type'],
            description=current['description'],
            is_default=current['is_default']
        )
        
        updated = db.get_config(key)
        return jsonify({
            'success': True,
            'config': updated,
            'message': f'Configuration updated: {key}'
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/config/<key>/reset', methods=['POST'])
def reset_config_item(key: str):
    """Reset a configuration value to its default."""
    try:
        db = current_app.config.get('CONFIG_DB')
        if db is None:
            return jsonify({'error': 'Database not initialized'}), 500
        
        success = db.reset_to_default(key)
        if not success:
            return jsonify({'error': f'Could not reset {key} to default'}), 400
        
        config = db.get_config(key)
        return jsonify({
            'success': True,
            'config': config,
            'message': f'Configuration reset to default: {key}'
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/jobs/recent', methods=['GET'])
def get_recent_jobs():
    """Get recently completed jobs."""
    try:
        db = current_app.config.get('CONFIG_DB')
        if db is None:
            return jsonify({'error': 'Database not initialized'}), 500
        
        limit = request.args.get('limit', 20, type=int)
        if limit > 100:
            limit = 100
        
        jobs = db.get_recent_jobs(limit)
        return jsonify({'jobs': jobs}), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }), 200
@bp.route('/jobs/<job_id>/manifest', methods=['GET'])
def get_job_manifest(job_id):
    """Get manifest for a specific job."""
    try:
        outputs_dir = Path(os.environ.get('OUTPUTS_DIR', '/data/outputs'))
        manifest_path = outputs_dir / job_id / 'manifest.json'
        
        if not manifest_path.exists():
            return jsonify({'error': f'Job {job_id} not found'}), 404
        
        try:
            with open(manifest_path) as f:
                manifest = json.load(f)
            return jsonify(manifest), 200
        except json.JSONDecodeError:
            return jsonify({'error': 'Invalid manifest JSON'}), 500
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/jobs/<job_id>/artifacts', methods=['GET'])
def get_job_artifacts(job_id):
    """Get list of artifacts for a job with metadata."""
    try:
        outputs_dir = Path(os.environ.get('OUTPUTS_DIR', '/data/outputs'))
        job_dir = outputs_dir / job_id
        
        if not job_dir.exists():
            return jsonify({'error': f'Job {job_id} not found'}), 404
        
        # Get manifest
        manifest_path = job_dir / 'manifest.json'
        manifest = {}
        if manifest_path.exists():
            try:
                with open(manifest_path) as f:
                    manifest = json.load(f)
            except json.JSONDecodeError:
                pass
        
        # Collect artifact information
        artifacts = []
        for artifact_dir in job_dir.iterdir():
            if artifact_dir.is_dir() and artifact_dir.name != '.tmp':
                artifact_info = {
                    'name': artifact_dir.name,
                    'type': None,
                    'files': [],
                    'total_size': 0
                }
                
                # Scan for files
                for file_path in artifact_dir.rglob('*'):
                    if file_path.is_file():
                        size = file_path.stat().st_size
                        artifact_info['files'].append({
                            'name': file_path.name,
                            'path': str(file_path.relative_to(job_dir)),
                            'size': size
                        })
                        artifact_info['total_size'] += size
                
                # Determine artifact type
                if any(f['name'].endswith('.mp3') for f in artifact_info['files']):
                    artifact_info['type'] = 'audio'
                elif any(f['name'].endswith('.json') for f in artifact_info['files']):
                    artifact_info['type'] = 'metadata'
                elif any(f['name'].endswith(('.png', '.jpg', '.jpeg')) for f in artifact_info['files']):
                    artifact_info['type'] = 'image'
                else:
                    artifact_info['type'] = 'other'
                
                artifacts.append(artifact_info)
        
        # Sort by type, then name
        artifacts.sort(key=lambda a: (a['type'], a['name']))
        
        return jsonify({
            'job_id': job_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'total_artifacts': len(artifacts),
            'manifest': manifest,
            'artifacts': artifacts
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500