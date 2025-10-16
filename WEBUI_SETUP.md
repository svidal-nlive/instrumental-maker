# Instrumental Maker - Web UI Setup Complete! 🎵

## Overview
Your Instrumental Maker stack has been successfully deployed with a modern, sleek web UI featuring light/dark theme toggle!

## Deployed Services

All services are now running and accessible via Traefik reverse proxy:

### 🎨 **Main Web UI** (NEW!)
- **URL**: https://instrumental.nsystems.live
- **Description**: Modern dashboard with real-time monitoring, queue management, library browsing, file uploads, and live logs
- **Features**:
  - ✨ Beautiful light/dark theme toggle
  - 📊 Real-time processing statistics
  - 📁 Queue and library management
  - ⬆️ Drag & drop file uploads
  - 📜 Live log streaming
  - 🎨 Modern gradient design inspired by Plex/Jellyfin

### 📂 **File Browser**
- **URL**: https://instrumental-files.nsystems.live
- **Description**: Advanced file manager for all pipeline data

### 🎵 **Deemix**
- **URL**: https://instrumental-deemix.nsystems.live
- **Description**: Music download service (downloads go directly to incoming queue)

### 💾 **MinIO Console**
- **URL**: https://instrumental-minio.nsystems.live
- **Description**: S3-compatible storage console for backups

### 🔌 **MinIO S3 API**
- **URL**: https://instrumental-s3.nsystems.live
- **Description**: S3 API endpoint for programmatic access

## DNS Configuration Required

Before accessing the services, create these DNS A records in Cloudflare pointing to your server:

```
instrumental.nsystems.live          → <your-server-ip>
instrumental-files.nsystems.live    → <your-server-ip>
instrumental-deemix.nsystems.live   → <your-server-ip>
instrumental-minio.nsystems.live    → <your-server-ip>
instrumental-s3.nsystems.live       → <your-server-ip>
```

All domains will automatically receive SSL certificates from Let's Encrypt via the existing wildcard certificate for `*.nsystems.live`.

## Web UI Features

### Dashboard
- **Real-time Stats**: Queue size, library count, processed/failed counts (24h)
- **Recent Jobs**: Last 50 processing jobs with status indicators
- **Processor Status**: Live monitoring of the processing daemon
- **Activity Chart**: Processing activity over time (coming soon)

### Queue Management
- View all files waiting to be processed
- See album folders with track counts
- Organized file tree view

### Library Browser
- Browse your complete instrumental collection
- Organized by Artist/Album structure
- File size and metadata display

### Upload Interface
- Drag & drop file uploads
- Multiple file selection
- Optional album folder organization
- Direct upload to processing queue

### Live Logs
- Real-time log streaming via Server-Sent Events
- Color-coded events (success/failure)
- Auto-scrolling with 100-line buffer
- Timestamp formatting

### Theme Toggle
- Modern light theme (default)
- Sleek dark theme
- Persistent preference (localStorage)
- Smooth transitions

## Architecture

### Backend (Flask)
- Python 3.11
- Flask 3.0.0
- RESTful API endpoints
- Server-Sent Events for real-time updates
- Shared volumes with processing containers

### Frontend
- Vanilla JavaScript (no build step)
- Tailwind CSS 3 (CDN)
- Responsive design
- Modern gradient color scheme
- Smooth animations and transitions

### Data Flow
```
User Upload → Incoming Directory → Simple Runner → Output Library
                                        ↓
                                    JSONL Logs
                                        ↓
                                    Web UI (SSE)
```

## Container Services

### webui
- **Image**: Built from project Dockerfile
- **Command**: Flask development server
- **Ports**: Internal 5000 (Traefik routes HTTPS)
- **Networks**: internal + proxy
- **Volumes**: Shares all pipeline-data volumes (read/write access)

### instrumental-simple
- **Image**: Built from project Dockerfile
- **Command**: Simple runner daemon
- **Networks**: internal only
- **Volumes**: All pipeline directories

### minio
- **Image**: quay.io/minio/minio:latest
- **Ports**: 9000 (S3 API), 9001 (Console) via Traefik
- **Networks**: internal + proxy

### minio-mirror
- **Image**: Built from project Dockerfile
- **Command**: MinIO mirror sync daemon
- **Networks**: internal only

### filebrowser
- **Image**: filebrowser/filebrowser:latest
- **User**: root (manages files created by other containers)
- **Networks**: proxy only

### deemix
- **Image**: registry.gitlab.com/bockiii/deemix-docker:latest
- **Networks**: proxy only
- **Downloads**: Directly to incoming/

## Configuration

### Environment Variables (.env)
All configuration is managed via environment variables in `.env`:

```bash
# Processing
MODEL=htdemucs
MP3_ENCODING=cbr320
CHUNKING_ENABLED=true
CHUNK_MAX=16

# MinIO
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=instrumentals

# Web UI
FLASK_SECRET_KEY=change-this-to-a-random-secret-key-in-production
```

**⚠️ Important**: Change `FLASK_SECRET_KEY` to a random secret before production use!

## Directory Structure

```
stacks/instrumental-maker/
├── app/
│   ├── webui/              # NEW Web UI application
│   │   ├── __init__.py
│   │   ├── app.py          # Flask app factory
│   │   ├── routes/         # API endpoints
│   │   │   ├── dashboard.py
│   │   │   ├── files.py
│   │   │   ├── processing.py
│   │   │   └── logs.py
│   │   ├── static/
│   │   │   ├── css/
│   │   │   │   └── main.css
│   │   │   └── js/
│   │   │       └── app.js
│   │   └── templates/
│   │       └── index.html
│   ├── simple_runner.py    # Main processor
│   ├── audio.py
│   ├── metadata.py
│   └── ...
├── pipeline-data/          # All data volumes
│   ├── incoming/
│   ├── working/
│   ├── output/
│   ├── logs/
│   ├── db/
│   ├── models/
│   ├── archive/
│   ├── quarantine/
│   ├── minio-data/
│   ├── filebrowser/
│   └── deemix/
├── docker-compose.yml
├── Dockerfile
└── .env
```

## Usage

### Starting Services
```bash
cd /volume1/docker/stacks/instrumental-maker
docker compose up -d
```

### Stopping Services
```bash
docker compose down
```

### Viewing Logs
```bash
# Web UI
docker logs -f instrumental-webui

# Processor
docker logs -f instrumental-simple

# All services
docker compose logs -f
```

### Rebuilding After Changes
```bash
docker compose build
docker compose up -d
```

## API Endpoints

### Dashboard
- `GET /api/dashboard/stats` - Overall statistics
- `GET /api/dashboard/activity` - Processing activity chart data
- `GET /api/dashboard/recent-jobs` - Last 50 jobs

### Files
- `GET /api/files/incoming` - List incoming queue
- `GET /api/files/output` - List library
- `GET /api/files/archive` - List archive
- `GET /api/files/quarantine` - List quarantine
- `POST /api/files/upload` - Upload file(s)
- `GET /api/files/download/<path>` - Download file
- `POST /api/files/delete` - Delete file/folder

### Processing
- `GET /api/processing/status` - Current processor status
- `GET /api/processing/config` - Current configuration

### Logs
- `GET /api/logs/recent?limit=100` - Recent log entries
- `GET /api/logs/stream` - Server-Sent Events stream

## Troubleshooting

### Web UI not accessible
1. Check DNS records are created and propagated
2. Verify Traefik is running: `docker ps | grep traefik`
3. Check web UI logs: `docker logs instrumental-webui`
4. Verify proxy network exists: `docker network ls | grep proxy`

### Files not uploading
1. Check disk space: `df -h`
2. Verify permissions on pipeline-data/incoming
3. Check web UI logs for errors

### Processor not running
1. Check simple runner logs: `docker logs instrumental-simple`
2. Verify PID lock file: `ls pipeline-data/db/simple_runner.pid`
3. Check for errors in logs: `tail pipeline-data/logs/simple_runner.jsonl`

### Theme not persisting
- Clear browser localStorage and try again
- Check browser console for JavaScript errors

## Next Steps

1. **Set DNS Records**: Create the A records listed above
2. **Change Secret Key**: Update `FLASK_SECRET_KEY` in `.env`
3. **Configure Deemix**: Log in and set up your streaming service credentials
4. **Upload Test File**: Try the upload feature with a small audio file
5. **Monitor Processing**: Watch the dashboard for real-time updates

## Production Recommendations

### Security
- [ ] Change `FLASK_SECRET_KEY` to a strong random value
- [ ] Change MinIO credentials (MINIO_ACCESS_KEY, MINIO_SECRET_KEY)
- [ ] Consider adding authentication to the web UI
- [ ] Review Traefik middleware for additional security headers

### Performance
- [ ] Use a production WSGI server (Gunicorn/uWSGI) instead of Flask dev server
- [ ] Add Redis for session storage
- [ ] Implement caching for API responses
- [ ] Monitor resource usage and adjust container limits

### Reliability
- [ ] Set up automated backups of pipeline-data
- [ ] Configure log rotation
- [ ] Set up monitoring/alerting
- [ ] Document disaster recovery procedures

## Support

For issues or enhancements:
- Check logs: `docker compose logs`
- Review architecture: See `ARCHITECTURE.md`
- Check processing logs: `pipeline-data/logs/simple_runner.jsonl`

Enjoy your new Instrumental Maker Web UI! 🎉
