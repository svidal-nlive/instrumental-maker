"""NAS synchronization routes."""
import os
import json
from pathlib import Path
from datetime import datetime
from flask import Blueprint, jsonify, current_app
import subprocess

bp = Blueprint('nas', __name__, url_prefix='/api/nas')


def parse_nas_sync_log():
    """Parse NAS sync log file to extract sync history."""
    log_file = current_app.config.get('NAS_SYNC_LOG')
    if not log_file or not Path(log_file).exists():
        return []
    
    syncs = []
    try:
        with open(log_file, 'r') as f:
            for line in f:
                try:
                    event = json.loads(line.strip())
                    syncs.append({
                        'timestamp': event.get('timestamp'),
                        'status': event.get('status'),
                        'files_synced': event.get('files_synced', 0),
                        'bytes_synced': event.get('bytes_synced', 0),
                        'duration_sec': event.get('duration_sec', 0),
                        'error': event.get('error')
                    })
                except (json.JSONDecodeError, ValueError):
                    continue
    except Exception as e:
        current_app.logger.error(f"Error parsing NAS sync log: {e}")
    
    return syncs[::-1]  # Reverse to show most recent first


def get_nas_sync_status():
    """Get current NAS sync status."""
    syncs = parse_nas_sync_log()
    
    if not syncs:
        return {
            'enabled': True,
            'status': 'never',
            'last_sync': None,
            'last_sync_relative': 'Never synced',
            'files_synced_total': 0,
            'bytes_synced_total': 0,
            'success_rate': 0,
            'total_syncs': 0
        }
    
    # Get last sync
    last_sync = syncs[0]
    
    # Calculate statistics
    successful_syncs = len([s for s in syncs if s['status'] == 'success'])
    total_syncs = len(syncs)
    success_rate = (successful_syncs / total_syncs * 100) if total_syncs > 0 else 0
    
    # Calculate totals
    total_files = sum(s['files_synced'] for s in syncs)
    total_bytes = sum(s['bytes_synced'] for s in syncs)
    
    # Calculate relative time
    try:
        last_sync_time = datetime.fromisoformat(
            last_sync['timestamp'].replace('Z', '+00:00')
        )
        now = datetime.utcnow().replace(tzinfo=last_sync_time.tzinfo)
        delta = now - last_sync_time
        
        if delta.days > 0:
            relative = f"{delta.days}d ago"
        elif delta.seconds > 3600:
            relative = f"{delta.seconds // 3600}h ago"
        elif delta.seconds > 60:
            relative = f"{delta.seconds // 60}m ago"
        else:
            relative = "Just now"
    except Exception:
        relative = "Unknown"
    
    return {
        'enabled': True,
        'status': last_sync['status'],
        'last_sync': last_sync['timestamp'],
        'last_sync_relative': relative,
        'files_synced_last': last_sync['files_synced'],
        'bytes_synced_last': last_sync['bytes_synced'],
        'duration_sec_last': last_sync['duration_sec'],
        'files_synced_total': total_files,
        'bytes_synced_total': total_bytes,
        'success_rate': round(success_rate, 2),
        'total_syncs': total_syncs,
        'recent_error': last_sync.get('error') if last_sync['status'] == 'failed' else None
    }


def format_bytes(bytes_val: int) -> str:
    """Format bytes to human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_val < 1024:
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.2f} PB"


@bp.route('/status')
def get_sync_status():
    """Get NAS sync status and statistics."""
    status = get_nas_sync_status()
    
    # Add formatted sizes (handling missing keys when no syncs exist)
    status['bytes_synced_last_human'] = format_bytes(status.get('bytes_synced_last', 0))
    status['bytes_synced_total_human'] = format_bytes(status.get('bytes_synced_total', 0))
    status['last_sync_time'] = status.get('last_sync_relative', 'Never')
    status['last_sync_success'] = status.get('status') == 'success'
    
    return jsonify(status)


@bp.route('/history')
def get_sync_history():
    """Get NAS sync history."""
    syncs = parse_nas_sync_log()
    
    # Format and add human-readable sizes
    for sync in syncs:
        sync['bytes_synced_human'] = format_bytes(sync['bytes_synced'])
        sync['duration_human'] = f"{sync['duration_sec']:.1f}s"
    
    # Return last 20 syncs
    return jsonify(syncs[:20])


@bp.route('/trigger-sync', methods=['POST'])
def trigger_sync():
    """Trigger a manual NAS sync by creating a trigger file."""
    try:
        # Create the trigger file that the sync script watches for
        # This path is shared between webui container and nas-sync container via the output volume
        trigger_file = Path(os.environ.get('SYNC_TRIGGER_FILE', '/app/pipeline-data/output/.sync_trigger'))
        trigger_file.touch()
        
        return jsonify({
            'success': True,
            'message': 'NAS sync triggered - files will be synced shortly',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })
    except Exception as e:
        current_app.logger.error(f"Error triggering NAS sync: {e}")
        return jsonify({
            'success': False,
            'message': f'Error triggering sync: {str(e)}'
        }), 500


@bp.route('/config')
def get_sync_config():
    """Get NAS sync configuration (non-sensitive values)."""
    sync_mode = os.environ.get('SYNC_MODE', 'manual')
    delete_after = os.environ.get('DELETE_AFTER_SYNC', 'false').lower() == 'true'
    sync_interval = int(os.environ.get('SYNC_INTERVAL', '300'))
    
    # Determine schedule description based on mode
    if sync_mode == 'continuous':
        schedule = f"Every {sync_interval} seconds"
    elif sync_mode == 'scheduled':
        schedule = "Scheduled (cron)"
    else:
        schedule = "On-demand"
    
    # Check if target is configured by looking at environment
    nas_host = os.environ.get('NAS_HOST', '')
    nas_user = os.environ.get('NAS_USER', '')
    if nas_host and nas_user:
        target = f"{nas_user}@{nas_host}"
    else:
        target = "Not configured"
    
    config = {
        'enabled': sync_mode != 'disabled',
        'mode': sync_mode,
        'target': target,
        'cleanup_enabled': delete_after,
        'schedule': schedule,
        'sync_interval': sync_interval,
    }
    
    return jsonify(config)
