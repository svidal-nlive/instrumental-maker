"""NAS Synchronization monitoring and status routes."""
import os
import json
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta
from flask import Blueprint, jsonify, current_app

bp = Blueprint('nas_monitor', __name__, url_prefix='/api/nas-sync')

def parse_nas_sync_log():
    """Parse NAS sync log file (JSONL format)."""
    log_path = Path(os.environ.get('NAS_SYNC_LOG', '/data/logs/nas_sync.jsonl'))
    events = []
    
    if not log_path.exists():
        return events
    
    try:
        with open(log_path, 'r') as f:
            for line in f:
                if line.strip():
                    try:
                        event = json.loads(line)
                        events.append(event)
                    except json.JSONDecodeError:
                        pass
    except IOError:
        pass
    
    return events

def get_sync_statistics():
    """Calculate sync statistics from log."""
    events = parse_nas_sync_log()
    stats = {
        'total_syncs': 0,
        'successful_syncs': 0,
        'failed_syncs': 0,
        'skipped_syncs': 0,
        'total_files': 0,
        'total_bytes': 0,
        'last_sync': None,
        'sync_methods': {}
    }
    
    for event in events:
        if event.get('event_type') == 'manifest_processed':
            stats['total_syncs'] += 1
            status = event.get('status', 'unknown')
            
            if status == 'success':
                stats['successful_syncs'] += 1
            elif status == 'failed':
                stats['failed_syncs'] += 1
            elif status == 'skipped':
                stats['skipped_syncs'] += 1
            
            # Track files and bytes
            stats['total_files'] += event.get('files_synced', 0)
            stats['total_bytes'] += event.get('bytes_synced', 0)
            
            # Track methods
            method = event.get('sync_method', 'unknown')
            if method not in stats['sync_methods']:
                stats['sync_methods'][method] = {'count': 0, 'success': 0}
            stats['sync_methods'][method]['count'] += 1
            if status == 'success':
                stats['sync_methods'][method]['success'] += 1
            
            # Track last sync
            if not stats['last_sync']:
                stats['last_sync'] = event.get('timestamp')
    
    # Sort events by timestamp (newest first)
    events.sort(key=lambda e: e.get('timestamp', ''), reverse=True)
    
    return stats, events[:50]  # Return last 50 events

def get_sync_status_by_artifact():
    """Get sync status grouped by artifact/job."""
    events = parse_nas_sync_log()
    artifacts = {}
    
    for event in events:
        if event.get('event_type') == 'artifact_synced':
            artifact_id = event.get('artifact_id', 'unknown')
            if artifact_id not in artifacts:
                artifacts[artifact_id] = {
                    'artifact_id': artifact_id,
                    'job_id': event.get('job_id'),
                    'kind': event.get('artifact_kind'),
                    'syncs': []
                }
            
            artifacts[artifact_id]['syncs'].append({
                'timestamp': event.get('timestamp'),
                'method': event.get('sync_method'),
                'status': event.get('status'),
                'message': event.get('message'),
                'bytes': event.get('bytes_synced', 0)
            })
    
    return artifacts

@bp.route('/status', methods=['GET'])
def get_nas_sync_status():
    """Get overall NAS sync status and statistics."""
    try:
        stats, recent_events = get_sync_statistics()
        
        # Get current sync method from config
        db = current_app.config.get('CONFIG_DB')
        sync_method_config = db.get_config('NAS_SYNC_METHOD') if db else None
        current_method = sync_method_config['value'] if sync_method_config else 'unknown'
        
        response = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'current_method': current_method,
            'statistics': stats,
            'recent_events': recent_events
        }
        
        return jsonify(response), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/artifacts', methods=['GET'])
def get_artifact_sync_status():
    """Get sync status for all artifacts."""
    try:
        artifacts = get_sync_status_by_artifact()
        
        # Return as array, sorted by most recent first
        artifact_list = list(artifacts.values())
        artifact_list.sort(
            key=lambda a: a['syncs'][0]['timestamp'] if a['syncs'] else '',
            reverse=True
        )
        
        return jsonify({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'total_artifacts': len(artifact_list),
            'artifacts': artifact_list[:50]  # Return last 50 artifacts
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/test-connectivity', methods=['POST'])
def test_connectivity():
    """Test NAS connectivity for current sync method."""
    try:
        from services.nas_sync_service.syncer import (
            RsyncBackend, S3Backend, ScpBackend, LocalBackend
        )
        
        db = current_app.config.get('CONFIG_DB')
        if not db:
            return jsonify({'error': 'Database not initialized'}), 500
        
        sync_method_config = db.get_config('NAS_SYNC_METHOD')
        if not sync_method_config:
            return jsonify({'error': 'NAS_SYNC_METHOD not configured'}), 400
        
        method = sync_method_config['value']
        
        # Test based on method type
        if method == 'rsync':
            # Test rsync connectivity
            import subprocess
            try:
                result = subprocess.run(
                    ['rsync', '--version'],
                    capture_output=True,
                    timeout=5,
                    text=True
                )
                is_available = result.returncode == 0
                message = 'rsync is installed and available' if is_available else 'rsync not available'
            except Exception as e:
                is_available = False
                message = f'Error testing rsync: {str(e)}'
        
        elif method == 's3':
            # Test S3 connectivity
            try:
                import boto3
                s3 = boto3.client('s3', endpoint_url='http://minio:9000')
                s3.list_buckets()
                is_available = True
                message = 'S3/MinIO connection successful'
            except Exception as e:
                is_available = False
                message = f'S3 connection failed: {str(e)}'
        
        elif method == 'scp':
            # SCP requires SSH, can't fully test without credentials
            is_available = True
            message = 'SCP method requires SSH credentials configured'
        
        elif method == 'local':
            # Test local path accessibility
            output_dir = Path(os.environ.get('OUTPUTS_DIR', '/data/outputs'))
            is_available = output_dir.exists()
            message = f'Local output directory {"exists" if is_available else "not found"}: {output_dir}'
        
        else:
            is_available = False
            message = f'Unknown sync method: {method}'
        
        return jsonify({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'method': method,
            'available': is_available,
            'message': message
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e), 'timestamp': datetime.now(timezone.utc).isoformat()}), 500

@bp.route('/logs', methods=['GET'])
def get_sync_logs():
    """Get NAS sync logs with filtering."""
    try:
        from flask import request
        
        limit = request.args.get('limit', 100, type=int)
        if limit > 500:
            limit = 500
        
        event_type = request.args.get('event_type')
        status = request.args.get('status')
        method = request.args.get('method')
        
        events = parse_nas_sync_log()
        
        # Filter events
        if event_type:
            events = [e for e in events if e.get('event_type') == event_type]
        if status:
            events = [e for e in events if e.get('status') == status]
        if method:
            events = [e for e in events if e.get('sync_method') == method]
        
        # Sort by timestamp (newest first)
        events.sort(key=lambda e: e.get('timestamp', ''), reverse=True)
        
        return jsonify({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'total': len(events),
            'returned': min(len(events), limit),
            'logs': events[:limit]
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/health', methods=['GET'])
def nas_sync_health():
    """Check NAS sync service health."""
    try:
        # Check if NAS sync is enabled
        db = current_app.config.get('CONFIG_DB')
        
        # Get latest sync event
        events = parse_nas_sync_log()
        last_event = events[0] if events else None
        
        # Calculate time since last sync
        time_since_last = None
        if last_event and last_event.get('timestamp'):
            try:
                last_time = datetime.fromisoformat(last_event['timestamp'].replace('Z', '+00:00'))
                now = datetime.now(timezone.utc)
                time_since_last = (now - last_time).total_seconds()
            except:
                pass
        
        # Determine health status
        status = 'healthy'
        if time_since_last and time_since_last > 3600:  # More than 1 hour
            status = 'warning'  # Haven't synced in over an hour
        if not events:
            status = 'unknown'  # No sync events yet
        
        return jsonify({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'status': status,
            'last_sync': last_event.get('timestamp') if last_event else None,
            'seconds_since_last_sync': time_since_last,
            'total_events': len(events)
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 500
