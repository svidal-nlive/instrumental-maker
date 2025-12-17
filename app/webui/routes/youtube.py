"""YouTube download routes using yt-dlp."""
import os
import re
import threading
import uuid
from urllib.parse import urlparse, parse_qs
from pathlib import Path
from flask import Blueprint, jsonify, request, current_app
import yt_dlp

bp = Blueprint('youtube', __name__, url_prefix='/api/youtube')

# Store download status in memory (for simplicity)
download_status = {}

# Default cookies file path (can be mounted via Docker volume)
COOKIES_FILE_PATH = Path(os.environ.get('YTDLP_COOKIES_FILE', '/data/config/cookies.txt'))

# PO Token provider URL (bgutil-ytdlp-pot-provider HTTP server)
POT_PROVIDER_URL = os.environ.get('YTDLP_POT_PROVIDER_URL', 'http://instrumental-bgutil:4416')


def get_cookies_option() -> dict:
    """
    Get the cookies option for yt-dlp if a cookies file exists.
    Returns a dict with 'cookiefile' key if cookies are available.
    """
    if COOKIES_FILE_PATH.exists() and COOKIES_FILE_PATH.stat().st_size > 0:
        return {'cookiefile': str(COOKIES_FILE_PATH)}
    return {}


def get_pot_provider_option() -> dict:
    """
    Get the PO Token provider extractor args for yt-dlp.
    This configures yt-dlp to use the bgutil HTTP server for PO token generation,
    which bypasses YouTube's bot detection automatically.
    """
    if POT_PROVIDER_URL:
        return {
            'extractor_args': {
                'youtubepot-bgutilhttp': {
                    'base_url': [POT_PROVIDER_URL]
                }
            }
        }
    return {}


def clean_youtube_url(url: str) -> str:
    """
    Clean a YouTube URL by removing playlist and radio mix parameters.
    This prevents yt-dlp from trying to process entire playlists which causes stalls.
    """
    parsed = urlparse(url)
    
    # Handle youtu.be short URLs
    if 'youtu.be' in parsed.netloc:
        # Extract video ID from path
        video_id = parsed.path.strip('/')
        if video_id:
            return 'https://www.youtube.com/watch?v={}'.format(video_id)
        return url
    
    # Handle youtube.com URLs
    if 'youtube.com' in parsed.netloc:
        query_params = parse_qs(parsed.query)
        
        # Get video ID
        video_id = query_params.get('v', [None])[0]
        
        if video_id:
            # Return clean URL with only the video ID
            return 'https://www.youtube.com/watch?v={}'.format(video_id)
    
    # Return original if we can't parse it
    return url


def sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename."""
    # Remove or replace invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '', name)
    # Replace multiple spaces with single space
    sanitized = re.sub(r'\s+', ' ', sanitized)
    # Trim and limit length
    return sanitized.strip()[:200]


def extract_info(url: str) -> dict:
    """Extract video info without downloading."""
    # Clean the URL to remove playlist parameters
    clean_url = clean_youtube_url(url)
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'noplaylist': True,  # Only get single video, not playlist
        'socket_timeout': 60,  # Timeout after 60 seconds for info extraction
        'retries': 5,  # Retry up to 5 times
        'ignoreerrors': False,
        # Skip live streams to avoid hanging
        'match_filter': yt_dlp.utils.match_filter_func('!is_live'),
        # Add cookies if available (fallback for bot detection)
        **get_cookies_option(),
        # Add PO Token provider for automatic bot detection bypass
        **get_pot_provider_option(),
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(clean_url, download=False)
        return ydl.sanitize_info(info)


def download_audio(url: str, download_id: str, incoming_dir: Path):
    """Download audio from YouTube URL in a background thread."""
    # Clean URL to remove playlist parameters
    clean_url = clean_youtube_url(url)
    
    try:
        download_status[download_id] = {
            'status': 'extracting',
            'progress': 0,
            'message': 'Extracting video information...',
            'error': None,
            'filename': None
        }
        
        # First extract info to get metadata (uses clean URL internally)
        info = extract_info(clean_url)
        
        title = info.get('title', 'Unknown Title')
        channel = info.get('channel', info.get('uploader', 'Unknown Channel'))
        
        # Create sanitized filename: "Title - YTDL.mp3"
        safe_title = sanitize_filename(title)
        output_filename = "{} - YTDL.mp3".format(safe_title)
        output_path = incoming_dir / output_filename
        
        # Handle duplicate filenames
        counter = 1
        while output_path.exists():
            output_filename = "{} - YTDL ({}).mp3".format(safe_title, counter)
            output_path = incoming_dir / output_filename
            counter += 1
        
        download_status[download_id] = {
            'status': 'downloading',
            'progress': 10,
            'message': 'Downloading: {}'.format(title),
            'error': None,
            'filename': output_filename,
            'title': title,
            'channel': channel
        }
        
        def progress_hook(d):
            """Update download progress."""
            if d['status'] == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                downloaded = d.get('downloaded_bytes', 0)
                if total > 0:
                    percent = min(90, 10 + int((downloaded / total) * 80))
                    download_status[download_id]['progress'] = percent
                    download_status[download_id]['message'] = f'Downloading: {percent}%'
            elif d['status'] == 'finished':
                download_status[download_id]['progress'] = 90
                download_status[download_id]['message'] = 'Converting to MP3...'
        
        # yt-dlp options for audio extraction with metadata
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': str(output_path.with_suffix('.%(ext)s')),
            # Download thumbnail for embedding as album art
            'writethumbnail': True,
            'postprocessors': [
                {
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                },
                {
                    'key': 'FFmpegMetadata',
                    'add_metadata': True,
                },
                {
                    # Embed YouTube thumbnail as album artwork
                    'key': 'EmbedThumbnail',
                    'already_have_thumbnail': False,
                },
            ],
            # Set metadata: title as song, channel as album, YTDL as artist
            'parse_metadata': [
                'title:%(title)s',
            ],
            'postprocessor_args': {
                'ffmpeg': [
                    '-metadata', 'title={}'.format(title),
                    '-metadata', 'album={}'.format(channel),
                    '-metadata', 'artist=YTDL',
                ]
            },
            'progress_hooks': [progress_hook],
            'quiet': False,  # Enable output for debugging truncation issues
            'no_warnings': False,
            'verbose': False,  # Set to True for detailed debugging
            # Prevent playlist processing and add timeouts
            'noplaylist': True,
            'socket_timeout': 300,  # 5 minute timeout for longer videos
            'retries': 5,  # More retries for reliability
            'fragment_retries': 10,  # Retry fragments that fail
            'skip_unavailable_fragments': False,  # Don't skip - fail if fragments missing
            # Buffer settings to prevent stalls
            'buffersize': 1024 * 64,  # 64KB buffer (larger for stability)
            'http_chunk_size': 10485760,  # 10MB chunks (larger for faster downloads)
            # Add cookies if available (fallback for bot detection)
            **get_cookies_option(),
            # Add PO Token provider for automatic bot detection bypass
            **get_pot_provider_option(),
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([clean_url])
        
        # Verify the file was created
        # The actual file will have .mp3 extension after conversion
        final_path = output_path.with_suffix('.mp3')
        if not final_path.exists():
            # Try the original path if suffix wasn't replaced correctly
            final_path = output_path
        
        if final_path.exists():
            download_status[download_id] = {
                'status': 'completed',
                'progress': 100,
                'message': 'Download complete! Added to processing queue.',
                'error': None,
                'filename': final_path.name,
                'title': title,
                'channel': channel,
                'filepath': str(final_path)
            }
        else:
            raise FileNotFoundError("Downloaded file not found at expected path")
            
    except (yt_dlp.utils.DownloadError, FileNotFoundError, OSError) as e:
        download_status[download_id] = {
            'status': 'error',
            'progress': 0,
            'message': 'Download failed: {}'.format(str(e)),
            'error': str(e),
            'filename': None
        }


@bp.route('/info', methods=['POST'])
def get_video_info():
    """Get information about a YouTube video without downloading."""
    data = request.get_json()
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({'error': 'No URL provided'}), 400
    
    # Basic URL validation
    if not any(domain in url.lower() for domain in ['youtube.com', 'youtu.be', 'youtube']):
        return jsonify({'error': 'Invalid YouTube URL'}), 400
    
    try:
        info = extract_info(url)
        return jsonify({
            'success': True,
            'info': {
                'title': info.get('title', 'Unknown'),
                'channel': info.get('channel', info.get('uploader', 'Unknown')),
                'duration': info.get('duration'),
                'duration_string': info.get('duration_string'),
                'thumbnail': info.get('thumbnail'),
                'view_count': info.get('view_count'),
                'upload_date': info.get('upload_date'),
                'description': info.get('description', '')[:500],  # Limit description length
            }
        })
    except (yt_dlp.utils.DownloadError, yt_dlp.utils.ExtractorError) as e:
        return jsonify({'error': 'Failed to extract video info: {}'.format(str(e))}), 400


@bp.route('/download', methods=['POST'])
def start_download():
    """Start a YouTube audio download."""
    data = request.get_json()
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({'error': 'No URL provided'}), 400
    
    # Basic URL validation
    if not any(domain in url.lower() for domain in ['youtube.com', 'youtu.be', 'youtube']):
        return jsonify({'error': 'Invalid YouTube URL'}), 400
    
    # Get incoming directory
    incoming_dir = current_app.config['INCOMING_DIR']
    
    # Ensure directory exists
    incoming_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate download ID
    download_id = str(uuid.uuid4())
    
    # Start download in background thread
    thread = threading.Thread(
        target=download_audio,
        args=(url, download_id, incoming_dir)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'success': True,
        'download_id': download_id,
        'message': 'Download started'
    })


@bp.route('/status/<download_id>')
def get_download_status(download_id):
    """Get the status of a download."""
    if download_id not in download_status:
        return jsonify({'error': 'Download not found'}), 404
    
    return jsonify(download_status[download_id])


@bp.route('/history')
def get_download_history():
    """Get recent download history."""
    # Return last 20 downloads
    history = []
    for download_id, status in list(download_status.items())[-20:]:
        history.append({
            'id': download_id,
            **status
        })
    return jsonify({'downloads': history})


@bp.route('/cookies/status')
def get_cookies_status():
    """Check if a cookies file is configured and valid."""
    cookies_exist = COOKIES_FILE_PATH.exists()
    cookies_size = COOKIES_FILE_PATH.stat().st_size if cookies_exist else 0
    cookies_valid = False
    
    if cookies_exist and cookies_size > 0:
        # Check if it looks like a valid Netscape cookies file
        try:
            with open(COOKIES_FILE_PATH, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
                cookies_valid = first_line.startswith('# Netscape HTTP Cookie File') or \
                               first_line.startswith('# HTTP Cookie File')
        except (IOError, UnicodeDecodeError):
            cookies_valid = False
    
    return jsonify({
        'configured': cookies_exist and cookies_size > 0,
        'valid': cookies_valid,
        'path': str(COOKIES_FILE_PATH),
        'size': cookies_size
    })


@bp.route('/cookies/upload', methods=['POST'])
def upload_cookies():
    """Upload a cookies.txt file for YouTube authentication."""
    if 'file' not in request.files:
        # Try to get cookies from form data (text paste)
        cookies_text = request.form.get('cookies_text', '').strip()
        if not cookies_text:
            data = request.get_json(silent=True) or {}
            cookies_text = data.get('cookies_text', '').strip()
        
        if not cookies_text:
            return jsonify({'error': 'No cookies file or text provided'}), 400
        
        # Validate the cookies text
        first_line = cookies_text.split('\n')[0].strip()
        if not (first_line.startswith('# Netscape HTTP Cookie File') or 
                first_line.startswith('# HTTP Cookie File')):
            return jsonify({
                'error': 'Invalid cookies format. Must be Netscape/Mozilla format. '
                        'First line should be "# Netscape HTTP Cookie File"'
            }), 400
        
        # Ensure directory exists
        COOKIES_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        # Save the cookies
        with open(COOKIES_FILE_PATH, 'w', encoding='utf-8') as f:
            f.write(cookies_text)
        
        return jsonify({
            'success': True,
            'message': 'Cookies saved successfully',
            'size': len(cookies_text)
        })
    
    # Handle file upload
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Read and validate
    content = file.read().decode('utf-8', errors='ignore')
    first_line = content.split('\n')[0].strip()
    
    if not (first_line.startswith('# Netscape HTTP Cookie File') or 
            first_line.startswith('# HTTP Cookie File')):
        return jsonify({
            'error': 'Invalid cookies format. Must be Netscape/Mozilla format. '
                    'First line should be "# Netscape HTTP Cookie File"'
        }), 400
    
    # Ensure directory exists
    COOKIES_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # Save the cookies
    with open(COOKIES_FILE_PATH, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return jsonify({
        'success': True,
        'message': 'Cookies file uploaded successfully',
        'filename': file.filename,
        'size': len(content)
    })


@bp.route('/cookies/delete', methods=['POST', 'DELETE'])
def delete_cookies():
    """Delete the cookies file."""
    if COOKIES_FILE_PATH.exists():
        COOKIES_FILE_PATH.unlink()
        return jsonify({'success': True, 'message': 'Cookies deleted'})
    return jsonify({'success': True, 'message': 'No cookies file to delete'})


@bp.route('/pot-provider/status')
def pot_provider_status():
    """Check the status of the PO Token provider (bgutil HTTP server)."""
    import urllib.request
    import urllib.error
    
    status = {
        'available': False,
        'url': POT_PROVIDER_URL,
        'message': 'Checking...',
        'error': None
    }
    
    if not POT_PROVIDER_URL:
        status['message'] = 'PO Token provider URL not configured'
        status['error'] = 'YTDLP_POT_PROVIDER_URL environment variable not set'
        return jsonify(status)
    
    try:
        # Try to connect to the bgutil provider
        # The provider responds to GET requests at the root
        req = urllib.request.Request(
            POT_PROVIDER_URL,
            method='GET',
            headers={'User-Agent': 'instrumental-maker/1.0'}
        )
        
        with urllib.request.urlopen(req, timeout=5):
            # Any successful response means the provider is running
            status['available'] = True
            status['message'] = 'PO Token provider is running and ready'
            
    except urllib.error.HTTPError as e:
        # HTTP errors can indicate the server is running but returned an error
        # For the bgutil provider, some endpoints may return errors for GET
        # We consider it "available" if we got any HTTP response
        if e.code in (400, 404, 405):
            status['available'] = True
            status['message'] = 'PO Token provider is running'
        else:
            status['message'] = f'PO Token provider returned HTTP {e.code}'
            status['error'] = str(e)
            
    except urllib.error.URLError as e:
        status['message'] = 'Cannot connect to PO Token provider'
        status['error'] = f'Connection failed: {e.reason}'
        
    except TimeoutError:
        status['message'] = 'PO Token provider connection timed out'
        status['error'] = 'Request timed out after 5 seconds'
        
    except (OSError, ValueError) as e:
        status['message'] = 'Error checking PO Token provider'
        status['error'] = str(e)
    
    return jsonify(status)
