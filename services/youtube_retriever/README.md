# YouTube Retriever Service

Standalone service that downloads media from YouTube and produces standardized job bundles for the instrumental-maker pipeline.

## Features

- **Duration Validation**: Compares online duration with downloaded file to detect corruption or transcoding issues
- **Audio Tagging**: Automatically tags audio with YouTube metadata (Artist = Channel, Album = YTDL, Title = Video Title)
- **Flexible Modes**:
  - `audio`: Download and extract audio only
  - `video`: Download video only
  - `both`: Download both audio and video as separate jobs
- **Format Conversion**: Converts audio to target format (m4a, flac, mp3, wav)
- **Thumbnail Download**: Optionally fetches video thumbnail as cover art
- **Atomic Job Bundles**: Writes bundles safely (temp → final) to prevent partial reads

## Configuration

Environment variables (with defaults):

```bash
# Operating mode
YTDL_MODE=audio                          # audio | video | both

# Queue folders (must be mounted)
QUEUE_YOUTUBE_AUDIO=/queues/youtube_audio
QUEUE_YOUTUBE_VIDEO=/queues/youtube_video

# Audio conversion
YTDL_AUDIO_FORMAT=m4a                    # m4a | flac | mp3 | wav

# Duration validation tolerances
YTDL_DURATION_TOL_SEC=2.0                # Absolute tolerance in seconds
YTDL_DURATION_TOL_PCT=0.01               # Percentage tolerance (1%)
YTDL_FAIL_ON_DURATION_MISMATCH=true      # Fail or warn on mismatch

# yt-dlp options
YTDL_QUIET=false
YTDL_NO_WARNINGS=false
YTDL_SOCKET_TIMEOUT=30
YTDL_COOKIES_FILE=""                     # Optional cookies file path

# Logging
LOG_DIR=/data/logs
LOG_LEVEL=info                           # info | debug | warning | error

# Work directory
WORKING_DIR=/tmp/ytdl_work

# Request handling (watch this folder for .txt files with URLs)
REQUESTS_DIR=/data/requests
```

## Usage

### Single URL

```bash
python3 main.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

### Watch for requests

Create `.txt` files in `/data/requests/` with one URL per file:

```bash
echo "https://www.youtube.com/watch?v=dQw4w9WgXcQ" > /data/requests/song1.txt
```

The service will process them and rename to `.done` or `.fail`.

### Run as daemon

```bash
python3 main.py --daemon
```

Or use Docker:

```bash
docker build -t youtube-retriever .
docker run -d \
  -e YTDL_MODE=audio \
  -e QUEUE_YOUTUBE_AUDIO=/queues/youtube_audio \
  -v /path/to/queues/youtube_audio:/queues/youtube_audio \
  -v /path/to/data:/data \
  youtube-retriever
```

## Job Bundle Format

Audio bundle in `/queues/youtube_audio/job_yt_<id>_audio/`:

```
job_yt_<id>_audio/
├── job.json
├── audio.m4a
└── cover.jpg
```

`job.json`:

```json
{
  "job_id": "yt_<id>_audio",
  "source_type": "youtube",
  "artist": "Channel Name",
  "album": "YTDL",
  "title": "Video Title",
  "audio_path": "audio.m4a",
  "cover_path": "cover.jpg",
  "youtube": {
    "video_id": "<id>",
    "url": "https://...",
    "channel": "Channel Name",
    "title": "Video Title",
    "online_duration_sec": 180.5
  }
}
```

Video bundles follow the same format in `/queues/youtube_video/` with `video_path` instead.

## Integration with instrumental-maker

1. Enable queue mode in instrumental-maker:
   ```bash
   QUEUE_ENABLED=true
   ```

2. Mount the queue folders:
   ```yaml
   services:
     instrumental-maker:
       volumes:
         - ./queues/youtube_audio:/queues/youtube_audio
         - ./queues/youtube_video:/queues/youtube_video
     
     youtube-retriever:
       volumes:
         - ./queues/youtube_audio:/queues/youtube_audio
         - ./queues/youtube_video:/queues/youtube_video
   ```

3. As downloads complete, the processor picks them up automatically.

## Error Handling

- **Duration mismatch**: Logged as warning or error (configurable)
- **Download failure**: Logged and retried on next request
- **Job bundle creation failure**: Temp folder cleaned up automatically
- **Missing dependencies**: Clear error messages (ffmpeg, yt-dlp required)

## Logging

Logs go to `/data/logs/youtube_retriever.log` (configurable via `LOG_DIR`).

```
[2025-12-17 10:30:45] INFO: Fetching metadata: https://...
[2025-12-17 10:30:47] INFO: Title: Example Song
[2025-12-17 10:30:47] INFO: Channel: Example Channel
[2025-12-17 10:30:47] INFO: Online duration: 180.5s
[2025-12-17 10:30:48] INFO: Downloading audio...
[2025-12-17 10:31:02] INFO: Downloaded duration: 180.4s
[2025-12-17 10:31:03] INFO: Converting audio to m4a...
[2025-12-17 10:31:05] INFO: Tagged audio file
[2025-12-17 10:31:06] INFO: Audio bundle created: /queues/youtube_audio/job_yt_xxx_audio
```
