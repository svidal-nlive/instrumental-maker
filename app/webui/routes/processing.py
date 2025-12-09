"""Processing control routes."""
import signal
import os
import time
import json
from pathlib import Path
from flask import Blueprint, jsonify, current_app, request

bp = Blueprint('processing', __name__, url_prefix='/api/processing')


def get_processor_status():
    """Check if the processor is running."""
    pid_file = current_app.config['DB_PATH'] / 'simple_runner.pid'
    
    if not pid_file.exists():
        return {
            'running': False,
            'status': 'stopped',
            'pid': None
        }
    
    try:
        with open(pid_file, 'r') as f:
            pid_info = f.read().strip()
            # Format is "hostname:pid"
            if ':' in pid_info:
                hostname, pid = pid_info.split(':', 1)
                pid = int(pid)
            else:
                pid = int(pid_info)
                hostname = 'unknown'
        
        # Check if process is actually running
        try:
            # Sending signal 0 checks if process exists
            import os
            os.kill(pid, 0)
            running = True
        except (OSError, ProcessLookupError):
            running = False
        
        return {
            'running': running,
            'status': 'active' if running else 'stale',
            'pid': pid,
            'hostname': hostname if ':' in pid_info else None
        }
    except (ValueError, FileNotFoundError):
        return {
            'running': False,
            'status': 'error',
            'pid': None
        }


def get_current_job():
    """Get detailed information about the currently processing job."""
    working_dir = current_app.config['WORKING_DIR']
    
    # Look for job directories (format: simple_<timestamp>)
    try:
        job_dirs = [d for d in working_dir.iterdir() if d.is_dir() and d.name.startswith('simple_')]
        if not job_dirs:
            return None
        
        # Get the most recent job directory
        latest_job = max(job_dirs, key=lambda x: x.stat().st_mtime)
        
        # Count chunks and demucs outputs
        chunks = list(latest_job.glob('chunk_*.wav'))
        demucs_dirs = list(latest_job.glob('demucs_*'))
        
        # Check which chunks have completed
        completed_chunks = []
        for demucs_dir in demucs_dirs:
            # Check if it has output files
            output_files = list(demucs_dir.rglob('*.wav'))
            if output_files:
                # Extract chunk number from directory name
                chunk_num = int(demucs_dir.name.split('_')[1])
                completed_chunks.append(chunk_num)
        
        # Calculate progress
        total_chunks = len(chunks)
        completed = len(completed_chunks)
        
        # Get the source file from incoming directory
        incoming_dir = current_app.config['INCOMING_DIR']
        source_file = None
        for audio_file in incoming_dir.rglob('*.mp3'):
            source_file = str(audio_file.relative_to(incoming_dir))
            break
        
        if not source_file:
            for audio_file in incoming_dir.rglob('*.flac'):
                source_file = str(audio_file.relative_to(incoming_dir))
                break
        
        # Get timing info
        start_time = latest_job.stat().st_ctime
        elapsed = time.time() - start_time
        
        # Determine current stage
        stage = 'preparing'
        if chunks:
            if completed == 0:
                stage = 'separating'
                current_chunk = 0
            elif completed < total_chunks:
                stage = 'separating'
                current_chunk = completed
            elif (latest_job / 'instrumental.wav').exists():
                stage = 'encoding'
            else:
                stage = 'merging'
        
        # Get most recent file modification time to detect activity
        all_files = list(latest_job.rglob('*'))
        if all_files:
            latest_mod = max(f.stat().st_mtime for f in all_files if f.is_file())
            idle_time = time.time() - latest_mod
        else:
            idle_time = 0
        
        return {
            'job_id': latest_job.name,
            'path': str(latest_job),
            'started': start_time,
            'elapsed': elapsed,
            'source_file': source_file,
            'total_chunks': total_chunks,
            'completed_chunks': completed,
            'progress_percent': int((completed / total_chunks * 100)) if total_chunks > 0 else 0,
            'current_chunk': min(completed_chunks) if completed_chunks else (0 if total_chunks > 0 else None),
            'stage': stage,
            'idle_seconds': idle_time,
            'is_active': idle_time < 120,  # Consider active if modified within last 2 minutes
            'is_stale': idle_time > 600  # Mark as stale if idle for more than 10 minutes
        }
    except Exception as e:
        current_app.logger.error(f"Error getting current job: {e}")
        return None


@bp.route('/cleanup-stale', methods=['POST'])
def cleanup_stale_jobs():
    """Manually clean up stale working directories."""
    import shutil
    working_dir = current_app.config['WORKING_DIR']
    
    cleaned = []
    errors = []
    
    try:
        for d in working_dir.iterdir():
            if not d.is_dir() or not d.name.startswith('simple_'):
                continue
            
            try:
                # Check the last modification time
                all_files = list(d.rglob('*'))
                if not all_files:
                    shutil.rmtree(d, ignore_errors=True)
                    cleaned.append(d.name)
                    continue
                
                latest_mtime = max(f.stat().st_mtime for f in all_files if f.is_file())
                idle_time = time.time() - latest_mtime
                
                # Only clean up if idle for more than 10 minutes
                if idle_time > 600:
                    shutil.rmtree(d, ignore_errors=True)
                    cleaned.append(d.name)
            except Exception as e:
                errors.append({'dir': d.name, 'error': str(e)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    
    return jsonify({
        'success': True,
        'cleaned': cleaned,
        'errors': errors
    })


@bp.route('/status')
def get_status():
    """Get current processing status."""
    processor_status = get_processor_status()
    current_job = get_current_job()
    
    # Check for album lock
    album_lock_file = current_app.config['DB_PATH'] / 'album_active.txt'
    album_locked = album_lock_file.exists()
    
    current_album = None
    if album_locked:
        try:
            with open(album_lock_file, 'r') as f:
                current_album = f.read().strip()
        except Exception:
            pass
    
    return jsonify({
        'processor': processor_status,
        'current_job': current_job,
        'album_locked': album_locked,
        'current_album': current_album
    })


@bp.route('/config')
def get_config():
    """Get current processing configuration."""
    import os
    
    config = {
        'model': os.environ.get('MODEL', 'htdemucs'),
        'device': os.environ.get('DEMUCS_DEVICE', 'cpu'),
        'jobs': int(os.environ.get('DEMUCS_JOBS', '1')),
        'mp3_encoding': os.environ.get('MP3_ENCODING', 'v0'),
        'chunking_enabled': os.environ.get('CHUNKING_ENABLED', 'true').lower() == 'true',
        'chunk_max': int(os.environ.get('CHUNK_MAX', '16')),
        'chunk_overlap_sec': float(os.environ.get('CHUNK_OVERLAP_SEC', '0.5')),
        'crossfade_ms': int(os.environ.get('CROSSFADE_MS', '200')),
        'corrupt_dest': os.environ.get('CORRUPT_DEST', 'archive'),
        'timeout_sec': int(os.environ.get('DEMUCS_CHUNK_TIMEOUT_SEC', '3600')),
        'max_retries': int(os.environ.get('DEMUCS_MAX_RETRIES', '2'))
    }
    
    return jsonify(config)


@bp.route('/history')
def get_history():
    """Get processing history from logs."""
    log_dir = current_app.config['LOG_DIR']
    log_file = log_dir / 'simple_runner.jsonl'
    
    limit = int(request.args.get('limit', 50))
    
    history = []
    try:
        if log_file.exists():
            with open(log_file, 'r') as f:
                lines = f.readlines()
                for line in lines[-limit:]:
                    try:
                        event = json.loads(line.strip())
                        if event.get('event') == 'processed':
                            history.append({
                                'timestamp': event.get('timestamp'),
                                'source': event.get('source'),
                                'output': event.get('output'),
                                'artist': event.get('artist'),
                                'album': event.get('album'),
                                'title': event.get('title'),
                                'duration_sec': event.get('duration_sec'),
                                'processing_time_sec': event.get('processing_time_sec'),
                                'chunk_count': event.get('chunk_count'),
                                'model': event.get('model'),
                                'encoding': event.get('encoding')
                            })
                    except (json.JSONDecodeError, KeyError):
                        continue
    except Exception as e:
        current_app.logger.error(f"Error reading history: {e}")
    
    return jsonify(history[::-1])  # Reverse to show most recent first


@bp.route('/clear-history', methods=['POST'])
def clear_history():
    """Clear processing history."""
    try:
        log_dir = current_app.config['LOG_DIR']
        log_file = log_dir / 'simple_runner.jsonl'
        
        if log_file.exists():
            log_file.write_text('')
            return jsonify({
                'success': True,
                'message': 'Processing history cleared successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Log file not found'
            }), 404
    except Exception as e:
        current_app.logger.error(f"Error clearing history: {e}")
        return jsonify({
            'success': False,
            'message': f'Error clearing history: {str(e)}'
        }), 500

