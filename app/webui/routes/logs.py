"""Log streaming and viewing routes."""
import json
from pathlib import Path
from flask import Blueprint, jsonify, Response, current_app, stream_with_context, request
import time

bp = Blueprint('logs', __name__, url_prefix='/api/logs')


@bp.route('/clear', methods=['POST'])
def clear_logs():
    """Clear all processing logs."""
    try:
        log_dir = current_app.config['LOG_DIR']
        log_file = log_dir / 'simple_runner.jsonl'
        
        if log_file.exists():
            log_file.write_text('')
            return jsonify({
                'success': True,
                'message': 'Processing logs cleared successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Log file not found'
            }), 404
    except Exception as e:
        current_app.logger.error(f"Error clearing logs: {e}")
        return jsonify({
            'success': False,
            'message': f'Error clearing logs: {str(e)}'
        }), 500


@bp.route('/recent')
def get_recent_logs():
    """Get recent log entries."""
    log_dir = current_app.config['LOG_DIR']
    log_file = log_dir / 'simple_runner.jsonl'
    
    limit = int(request.args.get('limit', 100))
    
    logs = []
    try:
        if log_file.exists():
            with open(log_file, 'r') as f:
                # Read all lines and take the last N
                lines = f.readlines()
                for line in lines[-limit:]:
                    try:
                        event = json.loads(line.strip())
                        logs.append(event)
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        current_app.logger.error(f"Error reading logs: {e}")
    
    return jsonify(logs)


@bp.route('/stream')
def stream_logs():
    """Stream logs using Server-Sent Events."""
    log_dir = current_app.config['LOG_DIR']
    log_file = log_dir / 'simple_runner.jsonl'
    
    def generate():
        """Generate SSE events from log file."""
        # First, send existing logs
        try:
            if log_file.exists():
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    for line in lines[-50:]:  # Send last 50 lines
                        try:
                            event = json.loads(line.strip())
                            yield f"data: {json.dumps(event)}\n\n"
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        # Then, watch for new logs
        last_position = log_file.stat().st_size if log_file.exists() else 0
        
        while True:
            try:
                if log_file.exists():
                    current_size = log_file.stat().st_size
                    if current_size > last_position:
                        with open(log_file, 'r') as f:
                            f.seek(last_position)
                            new_lines = f.readlines()
                            for line in new_lines:
                                try:
                                    event = json.loads(line.strip())
                                    yield f"data: {json.dumps(event)}\n\n"
                                except json.JSONDecodeError:
                                    continue
                        last_position = current_size
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            
            # Send heartbeat
            yield f": heartbeat\n\n"
            time.sleep(2)
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )
