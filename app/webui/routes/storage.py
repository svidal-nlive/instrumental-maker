"""Storage management routes."""
import os
import shutil
from pathlib import Path
from flask import Blueprint, jsonify, current_app, request
import subprocess

bp = Blueprint('storage', __name__, url_prefix='/api/storage')


def get_directory_size(path: Path) -> int:
    """Calculate total size of a directory in bytes."""
    total = 0
    try:
        if not path.exists():
            return 0
        for entry in path.rglob('*'):
            if entry.is_file():
                try:
                    total += entry.stat().st_size
                except (OSError, FileNotFoundError):
                    continue
    except Exception as e:
        current_app.logger.error(f"Error calculating directory size {path}: {e}")
    return total


def get_disk_usage(path: Path) -> dict:
    """Get disk usage for a path using df command."""
    try:
        result = subprocess.run(
            ['df', '-B1', str(path)],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if len(lines) >= 2:
                parts = lines[1].split()
                if len(parts) >= 4:
                    return {
                        'total': int(parts[1]),
                        'used': int(parts[2]),
                        'available': int(parts[3])
                    }
    except Exception as e:
        current_app.logger.error(f"Error getting disk usage: {e}")
    return {'total': 0, 'used': 0, 'available': 0}


def format_bytes(bytes_val: int) -> str:
    """Format bytes to human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_val < 1024:
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.2f} PB"


@bp.route('/stats')
def get_storage_stats():
    """Get storage statistics for all pipeline directories."""
    incoming_dir = current_app.config['INCOMING_DIR']
    output_dir = current_app.config['OUTPUT_DIR']
    working_dir = current_app.config['WORKING_DIR']
    archive_dir = current_app.config['ARCHIVE_DIR']
    quarantine_dir = current_app.config['QUARANTINE_DIR']
    
    # Calculate directory sizes
    incoming_size = get_directory_size(incoming_dir)
    output_size = get_directory_size(output_dir)
    working_size = get_directory_size(working_dir)
    archive_size = get_directory_size(archive_dir)
    quarantine_size = get_directory_size(quarantine_dir)
    
    total_pipeline_size = (
        incoming_size + output_size + working_size + 
        archive_size + quarantine_size
    )
    
    # Get disk usage for the main pipeline directory
    pipeline_parent = incoming_dir.parent
    disk_usage = get_disk_usage(pipeline_parent)
    
    # Count files in each directory
    def count_files(path: Path) -> int:
        try:
            if not path.exists():
                return 0
            return sum(1 for _ in path.rglob('*') if _.is_file())
        except Exception:
            return 0
    
    return jsonify({
        'directories': {
            'incoming': {
                'size_bytes': incoming_size,
                'size_human': format_bytes(incoming_size),
                'file_count': count_files(incoming_dir),
                'path': str(incoming_dir)
            },
            'output': {
                'size_bytes': output_size,
                'size_human': format_bytes(output_size),
                'file_count': count_files(output_dir),
                'path': str(output_dir)
            },
            'working': {
                'size_bytes': working_size,
                'size_human': format_bytes(working_size),
                'file_count': count_files(working_dir),
                'path': str(working_dir)
            },
            'archive': {
                'size_bytes': archive_size,
                'size_human': format_bytes(archive_size),
                'file_count': count_files(archive_dir),
                'path': str(archive_dir)
            },
            'quarantine': {
                'size_bytes': quarantine_size,
                'size_human': format_bytes(quarantine_size),
                'file_count': count_files(quarantine_dir),
                'path': str(quarantine_dir)
            }
        },
        'disk': {
            'total_bytes': disk_usage['total'],
            'total_human': format_bytes(disk_usage['total']),
            'used_bytes': disk_usage['used'],
            'used_human': format_bytes(disk_usage['used']),
            'available_bytes': disk_usage['available'],
            'available_human': format_bytes(disk_usage['available']),
            'percent_used': round((disk_usage['used'] / disk_usage['total'] * 100), 2) if disk_usage['total'] > 0 else 0
        },
        'pipeline': {
            'total_bytes': total_pipeline_size,
            'total_human': format_bytes(total_pipeline_size),
            'percent_of_disk': round((total_pipeline_size / disk_usage['total'] * 100), 2) if disk_usage['total'] > 0 else 0
        }
    })


@bp.route('/cleanup', methods=['POST'])
def cleanup_working_directory():
    """Clean up the working directory."""
    try:
        working_dir = current_app.config['WORKING_DIR']
        
        if not working_dir.exists():
            return jsonify({
                'success': True,
                'message': 'Working directory does not exist',
                'cleaned_size': 0
            })
        
        # Calculate size before cleanup
        size_before = get_directory_size(working_dir)
        
        # Remove all files in working directory
        for item in working_dir.iterdir():
            try:
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
            except Exception as e:
                current_app.logger.error(f"Error removing {item}: {e}")
        
        size_after = get_directory_size(working_dir)
        cleaned_size = size_before - size_after
        
        return jsonify({
            'success': True,
            'message': 'Working directory cleaned successfully',
            'cleaned_size': cleaned_size,
            'cleaned_human': format_bytes(cleaned_size)
        })
    except Exception as e:
        current_app.logger.error(f"Error cleaning working directory: {e}")
        return jsonify({
            'success': False,
            'message': f'Error cleaning working directory: {str(e)}'
        }), 500


@bp.route('/empty-quarantine', methods=['POST'])
def empty_quarantine():
    """Empty the quarantine directory."""
    try:
        quarantine_dir = current_app.config['QUARANTINE_DIR']
        
        if not quarantine_dir.exists():
            return jsonify({
                'success': True,
                'message': 'Quarantine directory does not exist',
                'removed_size': 0
            })
        
        # Calculate size before cleanup
        size_before = get_directory_size(quarantine_dir)
        
        # Remove all files in quarantine
        for item in quarantine_dir.iterdir():
            try:
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
            except Exception as e:
                current_app.logger.error(f"Error removing {item}: {e}")
        
        size_after = get_directory_size(quarantine_dir)
        removed_size = size_before - size_after
        
        return jsonify({
            'success': True,
            'message': 'Quarantine emptied successfully',
            'removed_size': removed_size,
            'removed_human': format_bytes(removed_size)
        })
    except Exception as e:
        current_app.logger.error(f"Error emptying quarantine: {e}")
        return jsonify({
            'success': False,
            'message': f'Error emptying quarantine: {str(e)}'
        }), 500
