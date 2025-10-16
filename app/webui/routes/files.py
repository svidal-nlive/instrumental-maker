"""File management routes."""
import os
import shutil
import mimetypes
from pathlib import Path
from flask import Blueprint, jsonify, request, send_file, current_app, Response
from werkzeug.utils import secure_filename

bp = Blueprint('files', __name__, url_prefix='/api/files')


def get_directory_tree(path, max_depth=3, current_depth=0):
    """Get directory tree structure."""
    audio_extensions = {'.mp3', '.flac', '.wav', '.m4a', '.ogg', '.opus', '.aac'}
    
    tree = {
        'name': path.name,
        'path': str(path),
        'type': 'directory',
        'children': []
    }
    
    if current_depth >= max_depth:
        return tree
    
    try:
        for item in sorted(path.iterdir()):
            if item.is_dir():
                tree['children'].append(get_directory_tree(item, max_depth, current_depth + 1))
            elif item.suffix.lower() in audio_extensions:
                tree['children'].append({
                    'name': item.name,
                    'path': str(item),
                    'type': 'file',
                    'size': item.stat().st_size,
                    'modified': item.stat().st_mtime
                })
    except PermissionError:
        pass
    
    return tree


@bp.route('/incoming')
def list_incoming():
    """List files in the incoming directory."""
    incoming_dir = current_app.config['INCOMING_DIR']
    tree = get_directory_tree(incoming_dir, max_depth=2)
    return jsonify(tree)


@bp.route('/output')
def list_output():
    """List files in the output directory (music library)."""
    output_dir = current_app.config['OUTPUT_DIR']
    tree = get_directory_tree(output_dir, max_depth=3)
    return jsonify(tree)


@bp.route('/upload', methods=['POST'])
def upload_file():
    """Upload a file to the incoming directory."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400
    
    # Get optional album folder from form data
    album_folder = request.form.get('album', '').strip()
    
    incoming_dir = current_app.config['INCOMING_DIR']
    
    try:
        # Secure the filename
        filename = secure_filename(file.filename)
        
        # Determine save path
        if album_folder:
            album_path = incoming_dir / secure_filename(album_folder)
            album_path.mkdir(exist_ok=True)
            save_path = album_path / filename
        else:
            save_path = incoming_dir / filename
        
        # Save the file
        file.save(save_path)
        
        return jsonify({
            'success': True,
            'filename': filename,
            'path': str(save_path)
        })
    except Exception as e:
        current_app.logger.error(f"Upload error: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/download/<path:filepath>')
def download_file(filepath):
    """Download a file from the output directory."""
    output_dir = current_app.config['OUTPUT_DIR']
    file_path = output_dir / filepath
    
    if not file_path.exists() or not file_path.is_file():
        return jsonify({'error': 'File not found'}), 404
    
    # Security check: ensure file is within output directory
    try:
        file_path.resolve().relative_to(output_dir.resolve())
    except ValueError:
        return jsonify({'error': 'Invalid file path'}), 403
    
    return send_file(file_path, as_attachment=True)


@bp.route('/delete', methods=['POST'])
def delete_file():
    """Delete a file from incoming or output directory."""
    data = request.get_json()
    file_path_str = data.get('path')
    
    if not file_path_str:
        return jsonify({'error': 'No path provided'}), 400
    
    file_path = Path(file_path_str)
    
    # Security: only allow deletion from incoming, output, archive, or quarantine
    allowed_dirs = [
        current_app.config['INCOMING_DIR'],
        current_app.config['OUTPUT_DIR'],
        current_app.config['ARCHIVE_DIR'],
        current_app.config['QUARANTINE_DIR']
    ]
    
    allowed = False
    for allowed_dir in allowed_dirs:
        try:
            file_path.resolve().relative_to(allowed_dir.resolve())
            allowed = True
            break
        except ValueError:
            continue
    
    if not allowed:
        return jsonify({'error': 'Path not allowed'}), 403
    
    try:
        if file_path.is_file():
            file_path.unlink()
        elif file_path.is_dir():
            shutil.rmtree(file_path)
        else:
            return jsonify({'error': 'Path not found'}), 404
        
        return jsonify({'success': True})
    except Exception as e:
        current_app.logger.error(f"Delete error: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/archive')
def list_archive():
    """List files in the archive directory."""
    archive_dir = current_app.config['ARCHIVE_DIR']
    tree = get_directory_tree(archive_dir, max_depth=2)
    return jsonify(tree)


@bp.route('/quarantine')
def list_quarantine():
    """List files in the quarantine directory."""
    quarantine_dir = current_app.config['QUARANTINE_DIR']
    tree = get_directory_tree(quarantine_dir, max_depth=2)
    return jsonify(tree)


@bp.route('/library')
def list_library():
    """List all audio files in the library with metadata."""
    output_dir = current_app.config['OUTPUT_DIR']
    audio_extensions = {'.mp3', '.flac', '.wav', '.m4a', '.ogg', '.opus', '.aac'}
    
    files = []
    try:
        for audio_file in output_dir.rglob('*'):
            if audio_file.is_file() and audio_file.suffix.lower() in audio_extensions:
                rel_path = audio_file.relative_to(output_dir)
                # Try to extract artist/album from path structure
                parts = rel_path.parts
                artist = parts[0] if len(parts) > 0 else 'Unknown'
                album = parts[1] if len(parts) > 1 else 'Unknown'
                title = audio_file.stem
                
                files.append({
                    'path': str(rel_path),
                    'name': audio_file.name,
                    'artist': artist,
                    'album': album,
                    'title': title,
                    'size': audio_file.stat().st_size,
                    'modified': audio_file.stat().st_mtime,
                    'extension': audio_file.suffix.lower()
                })
        
        # Sort by modification time, most recent first
        files.sort(key=lambda x: x['modified'], reverse=True)
    except Exception as e:
        current_app.logger.error(f"Error listing library: {e}")
        return jsonify({'error': str(e)}), 500
    
    return jsonify(files)


@bp.route('/stream/<path:filepath>')
def stream_audio(filepath):
    """Stream an audio file from the output directory."""
    output_dir = current_app.config['OUTPUT_DIR']
    file_path = output_dir / filepath
    
    if not file_path.exists() or not file_path.is_file():
        return jsonify({'error': 'File not found'}), 404
    
    # Security check: ensure file is within output directory
    try:
        file_path.resolve().relative_to(output_dir.resolve())
    except ValueError:
        return jsonify({'error': 'Invalid file path'}), 403
    
    # Get the mimetype
    mimetype, _ = mimetypes.guess_type(str(file_path))
    if not mimetype:
        mimetype = 'audio/mpeg' if file_path.suffix.lower() == '.mp3' else 'application/octet-stream'
    
    # Support range requests for seeking
    range_header = request.headers.get('Range', None)
    file_size = file_path.stat().st_size
    
    if not range_header:
        # No range request, send entire file
        return send_file(
            file_path,
            mimetype=mimetype,
            as_attachment=False,
            download_name=file_path.name
        )
    
    # Handle range request
    byte_range = range_header.replace('bytes=', '').split('-')
    start = int(byte_range[0]) if byte_range[0] else 0
    end = int(byte_range[1]) if len(byte_range) > 1 and byte_range[1] else file_size - 1
    length = end - start + 1
    
    with open(file_path, 'rb') as f:
        f.seek(start)
        data = f.read(length)
    
    response = Response(
        data,
        206,  # Partial Content
        mimetype=mimetype,
        direct_passthrough=True
    )
    response.headers.add('Content-Range', f'bytes {start}-{end}/{file_size}')
    response.headers.add('Accept-Ranges', 'bytes')
    response.headers.add('Content-Length', str(length))
    
    return response
