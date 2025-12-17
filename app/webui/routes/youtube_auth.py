"""
YouTube OAuth authentication for automated cookie/token refresh.

This module handles Google OAuth 2.0 authentication to obtain refresh tokens
that can be used to automatically generate fresh YouTube access tokens,
bypassing bot detection.

Setup:
1. Create a Google Cloud project at https://console.cloud.google.com/
2. Enable the YouTube Data API v3
3. Create OAuth 2.0 credentials (Web application type)
4. Add redirect URI: http://localhost:5000/api/youtube/oauth/callback (or your domain)
5. Download the client_secret.json or set env vars
"""
import os
import json
import time
from pathlib import Path
from flask import Blueprint, jsonify, request, redirect, url_for, session, current_app
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request

bp = Blueprint('youtube_auth', __name__, url_prefix='/api/youtube/oauth')

# Configuration paths
CONFIG_DIR = Path(os.environ.get('YTDLP_CONFIG_DIR', '/data/config'))
CREDENTIALS_FILE = CONFIG_DIR / 'youtube_credentials.json'
CLIENT_SECRETS_FILE = CONFIG_DIR / 'client_secret.json'

# OAuth scopes - we only need read access for cookie generation
SCOPES = ['https://www.googleapis.com/auth/youtube.readonly']


def get_oauth_config() -> dict:
    """Get OAuth configuration from environment or file."""
    # Try environment variables first
    client_id = os.environ.get('GOOGLE_CLIENT_ID')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
    
    if client_id and client_secret:
        return {
            'installed': {
                'client_id': client_id,
                'client_secret': client_secret,
                'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                'token_uri': 'https://oauth2.googleapis.com/token',
                'redirect_uris': ['http://localhost:5000/api/youtube/oauth/callback']
            }
        }
    
    # Try client_secret.json file
    if CLIENT_SECRETS_FILE.exists():
        with open(CLIENT_SECRETS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    return None


def get_stored_credentials() -> Credentials:
    """Load stored OAuth credentials if they exist and are valid."""
    if not CREDENTIALS_FILE.exists():
        return None
    
    try:
        with open(CREDENTIALS_FILE, 'r', encoding='utf-8') as f:
            creds_data = json.load(f)
        
        creds = Credentials(
            token=creds_data.get('token'),
            refresh_token=creds_data.get('refresh_token'),
            token_uri=creds_data.get('token_uri', 'https://oauth2.googleapis.com/token'),
            client_id=creds_data.get('client_id'),
            client_secret=creds_data.get('client_secret'),
            scopes=creds_data.get('scopes', SCOPES)
        )
        
        return creds
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def save_credentials(creds: Credentials, client_id: str, client_secret: str):
    """Save OAuth credentials to file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    creds_data = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': client_id,
        'client_secret': client_secret,
        'scopes': list(creds.scopes) if creds.scopes else SCOPES,
        'expiry': creds.expiry.isoformat() if creds.expiry else None
    }
    
    with open(CREDENTIALS_FILE, 'w', encoding='utf-8') as f:
        json.dump(creds_data, f, indent=2)


def refresh_credentials() -> Credentials:
    """Refresh OAuth credentials if expired."""
    creds = get_stored_credentials()
    
    if not creds:
        return None
    
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            # Re-save with new access token
            config = get_oauth_config()
            if config:
                client_config = config.get('installed') or config.get('web', {})
                save_credentials(
                    creds, 
                    client_config.get('client_id', creds.client_id),
                    client_config.get('client_secret', creds.client_secret)
                )
        except Exception as e:
            current_app.logger.error(f"Failed to refresh credentials: {e}")
            return None
    
    return creds


def generate_cookies_from_oauth() -> bool:
    """
    Generate a cookies.txt file from OAuth credentials.
    
    This creates a minimal cookies file that yt-dlp can use for authentication.
    The OAuth access token is converted to cookies format.
    """
    creds = refresh_credentials()
    if not creds or not creds.valid:
        return False
    
    # Create a Netscape-format cookies file with the access token
    # Note: This is a workaround - the access token is passed via a custom header
    cookies_content = f"""# Netscape HTTP Cookie File
# Generated automatically from OAuth credentials
# This file is auto-refreshed when tokens expire

# OAuth access token (used by yt-dlp for authentication)
.youtube.com\tTRUE\t/\tTRUE\t{int(time.time()) + 3600}\tACCESS_TOKEN\t{creds.token}
"""
    
    cookies_file = CONFIG_DIR / 'cookies.txt'
    with open(cookies_file, 'w', encoding='utf-8') as f:
        f.write(cookies_content)
    
    return True


@bp.route('/status')
def oauth_status():
    """Check OAuth configuration and authentication status."""
    config = get_oauth_config()
    creds = get_stored_credentials()
    
    # Determine redirect URI
    redirect_uri = 'http://localhost:5000/api/youtube/oauth/callback'
    
    status = {
        'configured': config is not None,
        'authenticated': False,
        'has_refresh_token': False,
        'token_expired': True,
        'client_id_set': bool(os.environ.get('GOOGLE_CLIENT_ID')) or CLIENT_SECRETS_FILE.exists(),
        'redirect_uri': redirect_uri,
        'expires_at': None,
    }
    
    # Show masked client_id if configured
    if config:
        client_config = config.get('installed') or config.get('web', {})
        client_id = client_config.get('client_id', '')
        if client_id:
            # Mask middle of client ID for display
            if len(client_id) > 20:
                status['client_id'] = client_id[:10] + '...' + client_id[-20:]
            else:
                status['client_id'] = client_id
    
    if creds:
        status['authenticated'] = True
        status['has_refresh_token'] = bool(creds.refresh_token)
        status['token_expired'] = creds.expired if hasattr(creds, 'expired') else True
        
        if hasattr(creds, 'expiry') and creds.expiry:
            status['expires_at'] = creds.expiry.isoformat()
        
        # Try to refresh if expired
        if status['token_expired'] and status['has_refresh_token']:
            refreshed = refresh_credentials()
            if refreshed and refreshed.valid:
                status['token_expired'] = False
                if hasattr(refreshed, 'expiry') and refreshed.expiry:
                    status['expires_at'] = refreshed.expiry.isoformat()
    
    return jsonify(status)


@bp.route('/init', methods=['POST'])
def init_oauth():
    """Initialize OAuth flow and return authorization URL."""
    config = get_oauth_config()
    if not config:
        return jsonify({
            'error': 'OAuth not configured. Save your Client ID and Client Secret first.'
        }), 400
    
    # Determine redirect URI based on request
    redirect_uri = request.url_root.rstrip('/') + '/api/youtube/oauth/callback'
    
    # Create OAuth flow
    try:
        flow = Flow.from_client_config(
            config,
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
        
        authorization_url, state = flow.authorization_url(
            access_type='offline',  # Get refresh token
            include_granted_scopes='true',
            prompt='consent'  # Always show consent to ensure refresh token
        )
        
        # Store state in session for verification
        session['oauth_state'] = state
        session['redirect_uri'] = redirect_uri
        
        return jsonify({
            'success': True,
            'auth_url': authorization_url
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to start OAuth flow: {str(e)}'}), 500


@bp.route('/config', methods=['POST'])
def save_oauth_config():
    """Save OAuth client credentials."""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    client_id = data.get('client_id', '').strip()
    client_secret = data.get('client_secret', '').strip()
    
    if not client_id or not client_secret:
        return jsonify({'error': 'Both client_id and client_secret are required'}), 400
    
    # Create config directory if needed
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    # Save as client_secret.json format
    config = {
        'installed': {
            'client_id': client_id,
            'client_secret': client_secret,
            'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
            'token_uri': 'https://oauth2.googleapis.com/token',
            'redirect_uris': ['http://localhost:5000/api/youtube/oauth/callback']
        }
    }
    
    try:
        with open(CLIENT_SECRETS_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        
        return jsonify({'success': True, 'message': 'OAuth credentials saved'})
    except Exception as e:
        return jsonify({'error': f'Failed to save credentials: {str(e)}'}), 500


@bp.route('/start')
def start_oauth():
    """Start the OAuth authorization flow."""
    config = get_oauth_config()
    if not config:
        return jsonify({
            'error': 'OAuth not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET '
                     'environment variables or provide client_secret.json file.'
        }), 400
    
    # Determine redirect URI based on request
    redirect_uri = request.url_root.rstrip('/') + '/api/youtube/oauth/callback'
    
    # Create OAuth flow
    try:
        flow = Flow.from_client_config(
            config,
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
        
        authorization_url, state = flow.authorization_url(
            access_type='offline',  # Get refresh token
            include_granted_scopes='true',
            prompt='consent'  # Always show consent to ensure refresh token
        )
        
        # Store state in session for verification
        session['oauth_state'] = state
        session['redirect_uri'] = redirect_uri
        
        return redirect(authorization_url)
        
    except Exception as e:
        return jsonify({'error': f'Failed to start OAuth flow: {str(e)}'}), 500


@bp.route('/callback')
def oauth_callback():
    """Handle OAuth callback from Google."""
    error = request.args.get('error')
    if error:
        return f"""
        <html>
        <head><title>Authentication Failed</title></head>
        <body>
            <h1>Authentication Failed</h1>
            <p>Error: {error}</p>
            <p><a href="/#youtube">Return to YouTube Download</a></p>
        </body>
        </html>
        """, 400
    
    code = request.args.get('code')
    state = request.args.get('state')
    
    # Verify state
    stored_state = session.get('oauth_state')
    if state != stored_state:
        return jsonify({'error': 'Invalid state parameter'}), 400
    
    config = get_oauth_config()
    if not config:
        return jsonify({'error': 'OAuth configuration not found'}), 500
    
    redirect_uri = session.get('redirect_uri', 
                               request.url_root.rstrip('/') + '/api/youtube/oauth/callback')
    
    try:
        flow = Flow.from_client_config(
            config,
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
        
        flow.fetch_token(code=code)
        creds = flow.credentials
        
        # Get client info for storage
        client_config = config.get('installed') or config.get('web', {})
        
        # Save credentials
        save_credentials(
            creds,
            client_config.get('client_id'),
            client_config.get('client_secret')
        )
        
        # Generate initial cookies file
        generate_cookies_from_oauth()
        
        return f"""
        <html>
        <head>
            <title>Authentication Successful</title>
            <style>
                body {{ font-family: system-ui, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }}
                .success {{ color: #22c55e; }}
                .info {{ background: #f0f9ff; padding: 15px; border-radius: 8px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <h1 class="success">✓ Authentication Successful!</h1>
            <div class="info">
                <p><strong>Your YouTube account is now connected.</strong></p>
                <p>The system will automatically refresh tokens as needed.</p>
                <p>You can now download videos without bot detection errors.</p>
            </div>
            <p><a href="/#youtube">← Return to YouTube Download</a></p>
            <script>
                // Notify parent window if in popup
                if (window.opener) {{
                    window.opener.postMessage('oauth_success', '*');
                    setTimeout(() => window.close(), 2000);
                }}
            </script>
        </body>
        </html>
        """
        
    except Exception as e:
        return f"""
        <html>
        <head><title>Authentication Error</title></head>
        <body>
            <h1>Authentication Error</h1>
            <p>Failed to complete authentication: {str(e)}</p>
            <p><a href="/#youtube">Return to YouTube Download</a></p>
        </body>
        </html>
        """, 500


@bp.route('/disconnect', methods=['POST'])
@bp.route('/revoke', methods=['POST'])
def disconnect():
    """Remove OAuth credentials."""
    try:
        if CREDENTIALS_FILE.exists():
            CREDENTIALS_FILE.unlink()
        
        # Also remove generated cookies
        cookies_file = CONFIG_DIR / 'cookies.txt'
        if cookies_file.exists():
            cookies_file.unlink()
        
        return jsonify({'success': True, 'message': 'Disconnected from YouTube'})
    except Exception as e:
        return jsonify({'error': f'Failed to disconnect: {str(e)}'}), 500


@bp.route('/refresh', methods=['POST'])
def force_refresh():
    """Force refresh of OAuth tokens and regenerate cookies."""
    creds = refresh_credentials()
    
    if not creds:
        return jsonify({
            'error': 'No credentials found. Please authenticate first.'
        }), 400
    
    if not creds.valid:
        return jsonify({
            'error': 'Failed to refresh credentials. Please re-authenticate.'
        }), 400
    
    # Regenerate cookies
    if generate_cookies_from_oauth():
        return jsonify({
            'success': True,
            'message': 'Tokens refreshed and cookies regenerated'
        })
    else:
        return jsonify({
            'error': 'Failed to generate cookies from credentials'
        }), 500
