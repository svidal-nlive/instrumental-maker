"""Dashboard routes and statistics."""
import os
import json
from pathlib import Path
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, current_app, request
from collections import defaultdict

bp = Blueprint('dashboard', __name__, url_prefix='/api/dashboard')


def get_audio_files(directory):
    """Get list of audio files in a directory."""
    audio_extensions = {'.mp3', '.flac', '.wav', '.m4a', '.ogg', '.opus', '.aac'}
    files = []
    try:
        for item in Path(directory).rglob('*'):
            if item.is_file() and item.suffix.lower() in audio_extensions:
                files.append(item)
    except Exception as e:
        current_app.logger.error(f"Error scanning directory {directory}: {e}")
    return files


def parse_log_events(log_file, hours=24):
    """Parse JSONL log file and return recent events."""
    events = []
    cutoff_time = datetime.utcnow() - timedelta(hours=hours)
    
    try:
        if not Path(log_file).exists():
            return events
            
        with open(log_file, 'r') as f:
            for line in f:
                try:
                    event = json.loads(line.strip())
                    # Parse timestamp
                    event_time = datetime.fromisoformat(event.get('timestamp', '').replace('Z', '+00:00'))
                    if event_time >= cutoff_time:
                        events.append(event)
                except (json.JSONDecodeError, ValueError) as e:
                    continue
    except Exception as e:
        current_app.logger.error(f"Error reading log file: {e}")
    
    return events


@bp.route('/stats')
def get_stats():
    """Get overall statistics for the dashboard."""
    incoming_dir = current_app.config['INCOMING_DIR']
    output_dir = current_app.config['OUTPUT_DIR']
    working_dir = current_app.config['WORKING_DIR']
    log_dir = current_app.config['LOG_DIR']
    archive_dir = current_app.config['ARCHIVE_DIR']
    quarantine_dir = current_app.config['QUARANTINE_DIR']
    
    # Count files in various directories
    incoming_files = get_audio_files(incoming_dir)
    output_files = get_audio_files(output_dir)
    
    # Get album folders in incoming
    album_folders = []
    try:
        for item in incoming_dir.iterdir():
            if item.is_dir():
                audio_in_folder = [f for f in item.rglob('*') if f.is_file() and f.suffix.lower() in {'.mp3', '.flac', '.wav', '.m4a', '.ogg'}]
                if audio_in_folder:
                    album_folders.append({
                        'name': item.name,
                        'tracks': len(audio_in_folder),
                        'path': str(item)
                    })
    except Exception as e:
        current_app.logger.error(f"Error scanning albums: {e}")
    
    # Parse recent log events
    log_file = log_dir / 'simple_runner.jsonl'
    recent_events = parse_log_events(log_file, hours=24)
    
    # Calculate statistics
    processed_count = len([e for e in recent_events if e.get('event') == 'processed'])
    failed_count = len([e for e in recent_events if e.get('event') == 'skipped_corrupt'])
    
    # Check if processor is running
    pid_file = current_app.config['DB_PATH'] / 'simple_runner.pid'
    processor_running = pid_file.exists()
    
    stats = {
        'queue': {
            'singles': len([f for f in incoming_files if f.parent == incoming_dir]),
            'albums': len(album_folders),
            'total_tracks': len(incoming_files)
        },
        'library': {
            'total_instrumentals': len(output_files)
        },
        'recent': {
            'processed_24h': processed_count,
            'failed_24h': failed_count
        },
        'processor': {
            'running': processor_running,
            'status': 'active' if processor_running else 'stopped'
        },
        'album_folders': album_folders[:10]  # Top 10 album folders
    }
    
    return jsonify(stats)


@bp.route('/activity')
def get_activity():
    """Get recent processing activity."""
    log_dir = current_app.config['LOG_DIR']
    log_file = log_dir / 'simple_runner.jsonl'
    
    events = parse_log_events(log_file, hours=168)  # Last 7 days
    
    # Group events by hour for chart data
    hourly_stats = defaultdict(lambda: {'processed': 0, 'failed': 0})
    
    for event in events:
        try:
            timestamp = datetime.fromisoformat(event.get('timestamp', '').replace('Z', '+00:00'))
            hour_key = timestamp.strftime('%Y-%m-%d %H:00')
            
            if event.get('event') == 'processed':
                hourly_stats[hour_key]['processed'] += 1
            elif event.get('event') == 'skipped_corrupt':
                hourly_stats[hour_key]['failed'] += 1
        except Exception:
            continue
    
    # Convert to sorted list
    activity_data = [
        {
            'timestamp': key,
            'processed': value['processed'],
            'failed': value['failed']
        }
        for key, value in sorted(hourly_stats.items())
    ]
    
    return jsonify(activity_data)


@bp.route('/recent-jobs')
def get_recent_jobs():
    """Get list of recently processed jobs."""
    log_dir = current_app.config['LOG_DIR']
    log_file = log_dir / 'simple_runner.jsonl'
    
    
    events = parse_log_events(log_file, hours=168)
    
    # Get recent processed and failed items
    jobs = []
    for event in events:
        if event.get('event') in ['processed', 'skipped_corrupt']:
            jobs.append({
                'timestamp': event.get('timestamp'),
                'status': 'completed' if event.get('event') == 'processed' else 'failed',
                'filename': event.get('title', 'Unknown'),
                'artist': event.get('artist', 'Unknown'),
                'album': event.get('album', 'Unknown'),
                'duration': event.get('duration_sec'),
                'output_path': event.get('output_path', '')
            })
    
    # Sort by timestamp descending
    jobs.sort(key=lambda x: x['timestamp'], reverse=True)
    
    
    return jsonify(jobs[:50])  # Return last 50 jobs

