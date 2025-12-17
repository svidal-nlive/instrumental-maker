# NAS Sync Service

Watches `/outputs` for `manifest.json` files and syncs processed artifacts to configured remote paths based on kind + variant matching.

This is a separate, optional service that runs alongside `instrumental-simple`. If not configured, it logs warnings and continues normally.

## Architecture

```
instrumental-simple (processing)
         │
         ├─→ /outputs/{job_id}/
         │       ├─ files/
         │       │   ├─ instrumental.m4a
         │       │   ├─ no_drums.m4a
         │       │   └─ drums_only.m4a
         │       └─ manifest.json
         │
         └─→ NAS Sync Service watches /outputs
                 ├─ Discovers manifest.json
                 ├─ Routes artifacts by kind + variant
                 ├─ Syncs to configured remote paths
                 └─ Logs success/failure
```

## Sync Backends

### Rsync (Local NAS or SSH)
Best for local NAS or SSH-mounted storage.

```env
NAS_SYNC_METHOD=rsync
NAS_REMOTE_ROOT_AUDIO=/mnt/nas/Instrumentals
NAS_REMOTE_ROOT_VIDEO=/mnt/nas/Videos
NAS_RSYNC_BW_LIMIT=0          # KB/s, 0 = unlimited
NAS_RSYNC_COMPRESS=true       # Compress during transfer
```

### S3 / MinIO
For cloud storage or MinIO buckets.

```env
NAS_SYNC_METHOD=s3
NAS_S3_BUCKET=instrumental-maker
NAS_S3_PREFIX=artifacts
NAS_S3_REGION=us-east-1
NAS_S3_ENDPOINT=https://minio.example.com  # Optional, for MinIO
```

Requires AWS credentials: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`

### SCP
For remote servers via SSH.

```env
NAS_SYNC_METHOD=scp
NAS_SCP_HOST=nas.example.com
NAS_SCP_USER=sync_user
NAS_SCP_KEY=/home/user/.ssh/id_rsa
```

### Local Filesystem
For testing or local NAS paths.

```env
NAS_SYNC_METHOD=local
NAS_REMOTE_ROOT_AUDIO=/mnt/nas/Instrumentals
```

## Configuration

### Core

| Variable | Default | Description |
|----------|---------|-------------|
| `OUTPUTS_DIR` | `/data/outputs` | Directory containing job outputs and manifests |
| `NAS_SYNC_WORK_DIR` | `/data/nas-sync-work` | Work directory for temp files |
| `NAS_SYNC_LOG_FILE` | `/data/logs/nas-sync.jsonl` | Log file path |

### Sync Method & Routing

| Variable | Default | Description |
|----------|---------|-------------|
| `NAS_SYNC_METHOD` | `rsync` | Sync backend: `rsync`, `s3`, `scp`, `local` |
| `NAS_SYNC_ROUTES` | See below | JSON list of route definitions |
| `NAS_REMOTE_ROOT_AUDIO` | `` | Remote root for audio artifacts |
| `NAS_REMOTE_ROOT_VIDEO` | `` | Remote root for video artifacts |
| `NAS_REMOTE_ROOT_STEMS` | `` | Remote root for stem files |

### Route Definitions

Routes determine which artifacts go where. Defined as JSON:

```json
[
    {
        "kind": "audio",
        "variant": "instrumental",
        "to": "${remoteRoots.audio}/Instrumental"
    },
    {
        "kind": "audio",
        "variant": "no_drums",
        "to": "${remoteRoots.audio}/Instrumental (no drums)"
    },
    {
        "kind": "audio",
        "variant": "drums_only",
        "to": "${remoteRoots.audio}/Drums only"
    },
    {
        "kind": "video",
        "variant": "source",
        "to": "${remoteRoots.video}"
    }
]
```

Use `${remoteRoots.KEY}` as placeholders for `NAS_REMOTE_ROOT_*` variables.

### Behavior

| Variable | Default | Description |
|----------|---------|-------------|
| `NAS_SKIP_ON_MISSING_REMOTE` | `true` | If true, warn but skip unrouted artifacts; if false, fail |
| `NAS_DRY_RUN` | `false` | If true, log actions but don't sync |
| `NAS_DAEMON_MODE` | `true` | If true, run in daemon watch mode by default |
| `NAS_POLL_INTERVAL_SEC` | `5` | Daemon poll interval in seconds |

### Logging

| Variable | Default | Description |
|----------|---------|-------------|
| `NAS_LOG_LEVEL` | `INFO` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

## Usage

### Docker

In `docker-compose.yml`:

```yaml
nas-sync:
  build: ./services/nas_sync_service
  container_name: nas-sync
  depends_on:
    - instrumental-simple
  volumes:
    - ./pipeline-data/output:/data/outputs
    - ./pipeline-data/logs:/data/logs
    - /mnt/nas:/mnt/nas  # Mount NAS storage
  environment:
    NAS_SYNC_METHOD: rsync
    NAS_REMOTE_ROOT_AUDIO: /mnt/nas/Instrumentals
    NAS_REMOTE_ROOT_VIDEO: /mnt/nas/Videos
    NAS_SKIP_ON_MISSING_REMOTE: "true"
    NAS_POLL_INTERVAL_SEC: "5"
  networks:
    - default
```

### Command Line

```bash
# Daemon mode (watch for new manifests)
python main.py --daemon

# Process single manifest
python main.py /data/outputs/job_123/manifest.json

# Dry run
python main.py --daemon --dry-run

# Custom poll interval
python main.py --daemon --poll 10
```

## Route Matching

Artifacts are matched against routes in order. First match wins.

**Match Logic:**
- `kind` must match (if specified in route)
- `variant` must match (if specified in route)
- If both are specified, both must match
- If neither specified, route matches all artifacts (dangerous!)

**Example:**
```json
[
    {"kind": "audio", "variant": "instrumental", "to": "/nas/Instrumental"},
    {"kind": "audio", "to": "/nas/Other"},  // Matches all audio that didn't match above
    {"kind": "video", "to": "/nas/Videos"}
]
```

## Manifest Format

The processor looks for `manifest.json` files in `/outputs/{job_id}/manifest.json`.

Example:
```json
{
    "job_id": "youtube_abc123_20250101_120000",
    "source_type": "youtube",
    "artist": "Example Channel",
    "album": "YTDL",
    "title": "Example Song",
    "processed_at": "2025-01-01T12:05:30Z",
    "artifacts": [
        {
            "kind": "audio",
            "variant": "instrumental",
            "label": "Instrumental",
            "path": "files/instrumental.m4a",
            "codec": "aac",
            "container": "m4a",
            "duration_sec": 180.5
        },
        {
            "kind": "audio",
            "variant": "no_drums",
            "label": "Instrumental (no drums)",
            "path": "files/no_drums.m4a",
            "codec": "aac",
            "container": "m4a",
            "duration_sec": 180.5
        }
    ],
    "youtube": {
        "video_id": "abc123xyz",
        "url": "https://www.youtube.com/watch?v=abc123xyz",
        "channel": "Example Channel",
        "title": "Example Song",
        "online_duration_sec": 185.0
    },
    "stems_generated": true,
    "stems_preserved": false
}
```

## Logging

All operations are logged to both stdout and `/data/logs/nas-sync.jsonl`.

Example log entries:
```
2025-01-01 12:05:35 [INFO] NAS Sync Configuration:
2025-01-01 12:05:35 [INFO]   OUTPUTS_DIR: /data/outputs
2025-01-01 12:05:35 [INFO]   SYNC_METHOD: rsync
2025-01-01 12:05:35 [INFO]   REMOTE_ROOTS: {'audio': '/mnt/nas/Instrumentals', ...}
2025-01-01 12:05:37 [INFO] Found new manifest: /data/outputs/job_123/manifest.json
2025-01-01 12:05:38 [RSYNC] Instrumental: rsync -av /data/outputs/job_123/files/instrumental.m4a /mnt/nas/Instrumentals
2025-01-01 12:05:40 [INFO] Manifest processed: 1 synced, 0 skipped
```

## Troubleshooting

**No artifacts synced, all skipped:**
- Check `NAS_REMOTE_ROOT_*` variables are set
- Check routes match your artifact kinds/variants
- Check `NAS_SKIP_ON_MISSING_REMOTE` setting

**Rsync fails:**
- Check NAS mount is accessible
- Check file permissions
- Verify paths exist: `ls /mnt/nas/Instrumentals`

**S3 upload fails:**
- Check AWS credentials are set: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
- Check bucket exists and is writable
- Check region is correct

**Daemon not picking up new manifests:**
- Check `/data/outputs` is mounted correctly
- Check `NAS_POLL_INTERVAL_SEC` is reasonable
- Check logs: `tail -f /data/logs/nas-sync.jsonl`

## Integration with instrumental-simple

The processor automatically generates `manifest.json` after processing a job. The NAS Sync service is passive - it just watches for these manifests and routes their artifacts.

**Flow:**
1. YouTube Retriever → queue job to `/queues/youtube_audio/`
2. instrumental-simple processes job → writes `/outputs/{job_id}/manifest.json`
3. NAS Sync Service detects manifest → routes artifacts to configured paths
4. All done! No further action needed

## Performance

- **Poll Interval:** Default 5s (configurable)
- **Rsync:** Scales to large files (streaming)
- **S3:** Parallel uploads for folders
- **Local:** Fast for testing

For high volume, consider:
- Increasing `NAS_POLL_INTERVAL_SEC` to reduce CPU usage
- Using `NAS_RSYNC_COMPRESS=true` for network NAS
- Using S3 with large batch uploads (not yet implemented)

## Future Enhancements

- [ ] Batch operations (group multiple manifests)
- [ ] S3 multipart uploads for large files
- [ ] Deduplication checks before sync
- [ ] Sync status tracking in database
- [ ] Retry logic for failed syncs
- [ ] Webhook notifications on completion
