# Deemix Retriever Service

**Phase 4 of the Instrumental Maker pipeline**: Downloads music from Deezer and produces standardized job bundles for processing.

## Overview

The Deemix Retriever is an optional microservice that extends the pipeline with support for **Deezer downloads**. It:

1. **Monitors** for Deezer URL requests (via `.deezer` files or API endpoints)
2. **Downloads** audio from Deezer using the [Deemix](https://deemix.app/) library
3. **Validates** the downloaded files
4. **Produces** standardized job bundles compatible with the processing pipeline
5. **Hands off** to the simple_runner via `/queues/other/` for instrument separation

## Features

- ✅ **Multi-threaded downloads** - concurrent processing via configurable worker threads
- ✅ **Multi-format support** - FLAC, MP3 (various bitrates), M4A, etc.
- ✅ **Album/playlist aware** - handles single tracks, albums, and playlists
- ✅ **Metadata extraction** - cover art, artist, album, title
- ✅ **Error resilience** - configurable retry logic and error handling
- ✅ **Structured logging** - JSON-compatible logs for monitoring
- ✅ **Graceful shutdown** - clean termination with signal handling

## Architecture

```
┌─────────────────────────────┐
│  Deezer URL Requests        │
│  (.deezer files or API)     │
└──────────────┬──────────────┘
               │
               v
┌──────────────────────────────────────┐
│   Deemix Retriever Service           │
│  ┌────────────────────────────────┐  │
│  │ Watch: /queues/deemix_requests │  │  (file-based example)
│  └────────────────────────────────┘  │
│  ┌──────────────────────────────────┐ │
│  │ ThreadPool (MAX_CONCURRENT)       │ │
│  │ - Fetch metadata                  │ │
│  │ - Download audio (Deemix CLI)     │ │
│  │ - Extract cover art               │ │
│  │ - Validate files                  │ │
│  └──────────────────────────────────┘ │
│  ┌──────────────────────────────────┐ │
│  │ Job Producer                      │ │
│  │ - Create standardized bundle      │ │
│  │ - Write job.json manifest         │ │
│  │ - Copy files to bundle            │ │
│  └──────────────────────────────────┘ │
└──────────────┬───────────────────────┘
               │
               v
       ┌───────────────┐
       │ /queues/other │  Job bundles ready for processing
       └───────────────┘
               │
               v
       ┌──────────────────┐
       │ simple_runner    │  Processes: vocal removal, encoding, etc.
       └──────────────────┘
```

## Installation & Configuration

### Environment Variables

```bash
# Download quality (FLAC, MP3_320, MP3_128, AAC_256, etc.)
DEEMIX_QUALITY=FLAC

# Number of parallel download workers
MAX_CONCURRENT_DEEMIX=2

# Seconds between checking for new requests
WATCH_INTERVAL=10

# Timeout per download (seconds, default 30 min)
DEEMIX_DOWNLOAD_TIMEOUT=1800

# Log level
LOG_LEVEL=INFO

# Skip non-critical errors and continue
SKIP_ON_ERROR=true

# Metadata enrichment (optional)
ENRICH_METADATA=false
MUSICBRAINZ_ENABLED=false
```

### Docker Compose Integration

Add to your `docker-compose.yml`:

```yaml
  deemix-retriever:
    build:
      context: ./services/deemix_retriever
      dockerfile: Dockerfile
    container_name: instrumental-deemix
    environment:
      - LOG_LEVEL=INFO
      - DEEMIX_QUALITY=FLAC
      - MAX_CONCURRENT_DEEMIX=2
      - QUEUE_OTHER=/queues/other/
      - DEEMIX_WORKING_DIR=/tmp/deemix_retriever
    volumes:
      - ./pipeline-data/queues:/queues
      - ./pipeline-data/working/deemix:/tmp/deemix_retriever
      - deemix_cache:/home/deemix/.cache/deemix
      - deemix_config:/home/deemix/.config/deemix
    restart: unless-stopped
    networks:
      - pipeline
    healthcheck:
      test: ["CMD", "test", "-d", "/queues/other"]
      interval: 30s
      timeout: 10s
      retries: 3
```

Add to volumes section:

```yaml
volumes:
  deemix_cache:
  deemix_config:
```

## Usage

### File-based Request (`.deezer` files)

1. Create a request file with the Deezer URL:

```bash
mkdir -p pipeline-data/queues/deemix_requests
echo "https://www.deezer.com/track/123456789" > pipeline-data/queues/deemix_requests/download_001.deezer
```

2. The service will:
   - Detect the `.deezer` file
   - Download the track
   - Create a job bundle in `/queues/other/`
   - Clean up the request file

### Job Bundle Structure

After download, you'll have a bundle like:

```
/queues/other/job_dz_123456789_deemix/
├── job.json          # Manifest with metadata
├── files/
│   ├── 01_Track_1.flac
│   ├── 02_Track_2.flac
│   └── cover.jpg
```

### Job Manifest (job.json)

```json
{
  "job_id": "dz_123456789_deemix",
  "source_type": "deemix",
  "artist": "Artist Name",
  "album": "Album Name",
  "title": "Track Title",
  "audio_files": [
    "01_Track_1.flac",
    "02_Track_2.flac"
  ],
  "cover_path": "cover.jpg",
  "deemix": {
    "url": "https://www.deezer.com/album/123456789",
    "url_type": "album",
    "job_id": "123456789",
    "track_count": 2
  },
  "tracks": [
    {
      "title": "Track 1",
      "artist": "Artist Name",
      "album": "Album Name",
      "duration_sec": 245.5,
      "filename": "01_Track_1.flac"
    }
  ]
}
```

## Supported Deezer Links

- **Track**: `https://www.deezer.com/track/123456789`
- **Album**: `https://www.deezer.com/album/123456789`
- **Playlist**: `https://www.deezer.com/playlist/123456789`

## Deemix Configuration

For authentication with Deezer (optional - some content requires a Deezer account):

1. Configure Deemix before running the container:

```bash
# Inside or before container, login to Deezer
deemix auth

# This creates ~/.config/deemix/login.json
```

2. Mount the config directory in Docker:

```yaml
volumes:
  - deemix_config:/home/deemix/.config/deemix
```

## Error Handling

### Download Failures

The service handles various failure scenarios:

- **Network timeouts**: Configurable timeout (default 30 min)
- **Invalid URLs**: Logged and skipped
- **Missing files**: Error reported, job skipped
- **Deemix errors**: Logged based on `SKIP_ON_ERROR` setting

### Logs

Logs are written to stdout in JSON-compatible format:

```bash
# View logs
docker logs instrumental-deemix -f

# Example output
2025-01-17 10:30:45 [main] INFO: Starting Deemix Retriever Service
2025-01-17 10:30:46 [__main__] INFO: Watching /queues/deemix_requests for download requests
2025-01-17 10:30:50 [retriever] INFO: Fetching Deezer metadata: https://www.deezer.com/album/123456789
2025-01-17 10:30:52 [retriever] INFO: Downloading from Deezer (album): Album Name
```

## Testing

### Unit Tests

```bash
pytest tests/test_deemix_retriever.py -v

# Run specific test
pytest tests/test_deemix_retriever.py::test_deezer_url_parsing -v
```

### Integration Test

1. Start the service with Docker Compose
2. Place a test `.deezer` request file
3. Monitor `/queues/other/` for job bundles
4. Check logs for success/failure

```bash
# Create test request
echo "https://www.deezer.com/track/3135556" > pipeline-data/queues/deemix_requests/test.deezer

# Wait and verify
sleep 30
ls -la pipeline-data/queues/other/job_dz_*
```

## Troubleshooting

### Service Crashes on Startup

**Issue**: `ModuleNotFoundError: No module named 'deemix'`

**Solution**: Rebuild the Docker image to ensure deemix is installed:

```bash
docker compose build --no-cache deemix-retriever
docker compose up -d deemix-retriever
```

### No Downloads Are Happening

**Check**:

1. Is the service running?

```bash
docker ps | grep deemix
```

2. Are request files in the right location?

```bash
ls -la pipeline-data/queues/deemix_requests/
```

3. Check the logs:

```bash
docker logs instrumental-deemix -n 50
```

### Deemix Authentication Required

Some Deezer content requires a valid Deezer account.

**Solution**:

1. Run Deemix auth locally or in the container
2. Copy the `login.json` file to the config volume
3. Restart the service

### Disk Space Issues

Large FLAC downloads consume disk space quickly.

**Workaround**:

- Use MP3_320 instead of FLAC: `DEEMIX_QUALITY=MP3_320`
- Monitor `/tmp/deemix_retriever` directory
- Set up automatic cleanup of old downloads

## Performance Tuning

### Multi-threaded Downloads

Increase `MAX_CONCURRENT_DEEMIX` to download multiple tracks in parallel:

```yaml
environment:
  - MAX_CONCURRENT_DEEMIX=4  # 4 parallel downloads
```

**Trade-offs**:
- ✓ Faster overall throughput
- ✗ Higher bandwidth and CPU usage
- ✗ May trigger Deezer rate limits if too high

### Quality vs. Size

Choose the right quality for your use case:

| Quality | File Size | Use Case |
|---------|-----------|----------|
| FLAC | ~400 MB/hr | Archival, maximum quality |
| MP3_320 | ~50 MB/hr | High quality, smaller storage |
| MP3_128 | ~15 MB/hr | Low bandwidth, testing |

### Download Timeout

Adjust for slow connections:

```yaml
environment:
  - DEEMIX_DOWNLOAD_TIMEOUT=3600  # 1 hour
```

## Extension Points

### Future Enhancements

1. **API Endpoint**: Replace `.deezer` file watching with REST API:
   - `POST /api/download` - submit Deezer URL
   - `GET /api/status` - check download status

2. **Message Queue Integration**: Support RabbitMQ/Redis for requests

3. **Metadata Enrichment**: MusicBrainz integration for better tagging

4. **Progress Tracking**: Real-time progress updates during downloads

5. **Deezer Playlist/Album Monitoring**: Watch a Deezer user account and auto-download new releases

## Related Services

- **YouTube Retriever** (`services/youtube_retriever/`): Downloads from YouTube
- **Simple Runner** (`app/simple_runner.py`): Processes job bundles (vocal removal, etc.)
- **NAS Sync** (`services/nas_sync_service/`): Syncs results to remote storage

## References

- [Deemix Documentation](https://deemix.app/)
- [Deezer Web API](https://developers.deezer.com/api)
- [Deemix GitHub](https://github.com/RemixDev/deemix)

## License

Same as Instrumental Maker

## Support

For issues or questions:

1. Check logs: `docker logs instrumental-deemix -f`
2. Review configuration in `services/deemix_retriever/config.py`
3. Check Phase 4 integration tests in `tests/`
