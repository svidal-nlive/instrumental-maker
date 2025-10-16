# WebUI Enhancements

## Overview
Enhanced the Instrumental Maker WebUI to provide real-time processing visibility and audio playback capabilities.

## Changes Made (October 10, 2024)

### 1. Backend API Enhancements

#### `/api/processing/status` Endpoint Enhanced
- **File**: `app/webui/routes/processing.py`
- **New Features**:
  - Detailed current job tracking with:
    - Directory counting (chunks, demucs outputs, merged files)
    - Progress percentage calculation
    - Stage detection (preparing, separating, merging, encoding)
    - Idle time tracking
    - File path and metadata display
  - Processor status (running/idle)
  - Real-time progress updates

#### `/api/processing/history` Endpoint (NEW)
- **File**: `app/webui/routes/processing.py`
- **Purpose**: Retrieve recent processing history from JSONL logs
- **Returns**: Last 20 processed items with timing and metadata

#### `/api/files/library` Endpoint (NEW)
- **File**: `app/webui/routes/files.py`
- **Purpose**: List all instrumentals in the output directory
- **Features**:
  - Recursive directory scanning
  - Artist/Album extraction from path structure
  - File metadata (size, modified time, title)
  - Sorted output by artist → album → title

#### `/api/files/stream/<path>` Endpoint (NEW)
- **File**: `app/webui/routes/files.py`
- **Purpose**: Stream audio files with seek support
- **Features**:
  - HTTP Range request support (206 Partial Content)
  - Proper MIME type detection
  - Efficient chunked streaming
  - Enables in-browser audio seeking

### 2. Frontend JavaScript Components

#### ProcessingMonitor Class (NEW)
- **File**: `app/webui/static/js/processing-monitor.js`
- **Purpose**: Real-time processing status display
- **Features**:
  - 2-second refresh interval
  - Progress bar (0-100%) with chunk indicators
  - Visual chunk grid (1px colored divs showing per-chunk status)
  - Stage labels (preparing, separating, merging, encoding)
  - Idle warnings (yellow badge if >120s idle)
  - History display with timing information
  - Processor status badges
- **Initialization**: Auto-starts on page load

#### AudioPlayer Class (NEW)
- **File**: `app/webui/static/js/audio-player.js`
- **Purpose**: In-browser audio playback with library management
- **Features**:
  - Grid layout for library display
  - Album art placeholders
  - Play/pause/next/previous controls
  - Seek support via progress bar
  - Time display (current/duration)
  - Fixed bottom player UI
  - Streaming from `/api/files/stream` endpoint
  - Download functionality
- **UI**: Fixed bottom player with minimal, modern design

### 3. HTML Template Updates

#### `app/webui/templates/index.html`
- **Script Includes**: Added processing-monitor.js and audio-player.js
- **Dashboard Enhancements**:
  - Added `#processing-status` section
  - Added `#current-job` div for real-time job details
  - Added `#processing-history` section
  - Progress indicators with loading states
- **Library Page Enhancements**:
  - Added fixed bottom audio player UI
  - Grid layout for library cards
  - Play controls integrated into each card
  - Refresh button for library reload
- **Player UI**:
  - Fixed bottom position (z-index: 50)
  - Track info display (title, artist, album)
  - Controls (previous, play/pause, next)
  - Progress bar with seek support
  - Time display
  - Close button

#### `app/webui/static/js/app.js`
- **Initialization**: Added ProcessingMonitor and AudioPlayer initialization in DOMContentLoaded
- **Library Loading**: Delegated to AudioPlayer class
- **Integration**: Wired up monitor to start on page load

### 4. Container Rebuild

Rebuilt and restarted the webui container:
```bash
docker compose build webui
docker compose up -d webui
```

## How to Use

### Real-Time Processing Monitor

1. Navigate to the Dashboard page
2. The **Current Processing** section shows:
   - Current file being processed
   - Progress percentage
   - Chunk indicators (visual grid)
   - Current stage (preparing/separating/merging/encoding)
   - Time elapsed
   - Idle warnings if stuck
3. The **Processing History** section shows:
   - Recent completions
   - Processing times
   - Success/failure status

### Audio Library & Player

1. Navigate to the Library page
2. Click **Refresh** to load latest instrumentals
3. Browse cards organized by artist/album
4. Click **Play** button on any card
5. Player appears at bottom with:
   - Track info
   - Play/pause control
   - Seek bar (drag to jump)
   - Time display
   - Previous/next track buttons
6. Click **Download** to save instrumental
7. Click **X** to close player

## Technical Details

### Processing Monitor Updates

- **Polling Interval**: 2 seconds
- **Data Sources**: 
  - `/api/processing/status` (current job)
  - `/api/processing/config` (settings)
  - `/api/processing/history` (recent completions)
- **Stage Detection**:
  - `preparing`: Chunk files exist, no demucs outputs
  - `separating`: Demucs processing active
  - `merging`: Demucs complete, merging chunks
  - `encoding`: Final MP3 encoding
- **Progress Calculation**: `(chunks + demucs_outputs + merged_files) / (total_chunks * 3) * 100`

### Audio Player Features

- **Format Support**: MP3 (primary output format)
- **Streaming**: HTTP Range requests for efficient seeking
- **Controls**: HTML5 Audio API
- **Seek**: Click progress bar to jump to position
- **Library**: Automatically scans output directory

### File Organization

The library endpoint expects output structure:
```
output/
  Artist Name/
    Album Name/
      Track Title.mp3
```

Paths are parsed to extract artist/album/title for display.

## API Response Examples

### `/api/processing/status`
```json
{
  "status": "running",
  "current_job": {
    "path": "simple_1760067990",
    "filename": "Jesus, Lamb Of God (Live).mp3",
    "artist": "Phil Thompson",
    "album": "Jesus, Lamb Of God (Live)",
    "total_chunks": 5,
    "chunks_created": 5,
    "demucs_outputs": 1,
    "merged_files": 0,
    "progress_percent": 20,
    "stage": "separating",
    "idle_time": 45.3,
    "start_time": "2024-10-10T03:46:30Z"
  }
}
```

### `/api/files/library`
```json
[
  {
    "path": "Alex Jean/Matthew 18:20/Matthew 18:20.mp3",
    "name": "Matthew 18:20.mp3",
    "artist": "Alex Jean",
    "album": "Matthew 18:20",
    "title": "Matthew 18:20",
    "size": 8234567,
    "modified": "2024-01-15T10:30:00Z"
  }
]
```

## Browser Compatibility

- **Modern Browsers**: Chrome, Firefox, Safari, Edge (latest versions)
- **HTML5 Audio**: Required for playback
- **Range Requests**: Required for seeking
- **Fetch API**: Required for data loading

## Performance

- **Dashboard Refresh**: Every 2 seconds (minimal overhead)
- **Library Loading**: On-demand (user clicks Refresh)
- **Streaming**: Chunked, efficient for large files
- **UI Updates**: Debounced to prevent excessive DOM manipulation

## Future Enhancements

Potential improvements:
- [ ] Waveform visualization
- [ ] Playlist management
- [ ] Queue management UI
- [ ] Real-time log streaming (WebSockets)
- [ ] Cancel/retry buttons for failed jobs
- [ ] Configurable chunk size from UI
- [ ] Album art display (if embedded in files)
- [ ] Search/filter in library
- [ ] Sort options (artist, album, date)
- [ ] Batch download

## Troubleshooting

### Processing Monitor Shows "Idle" But Files Are Processing
- Check simple_runner logs: `tail -f pipeline-data/logs/simple_runner.jsonl`
- Verify working directory has recent activity: `ls -lth pipeline-data/working/`
- Restart simple_runner container if needed

### Audio Player Not Loading Library
- Check output directory permissions
- Verify files exist in `pipeline-data/minio-data/instrumentals/`
- Check browser console for API errors
- Verify webui container has access to output directory

### Audio Streaming Fails
- Check file paths in library response
- Verify MIME types are correct (should be audio/mpeg for MP3)
- Test direct file access: `curl -I http://localhost:5000/api/files/stream/Artist/Album/Track.mp3`
- Check browser console for CORS or network errors

## Configuration

No additional configuration required. All settings use existing environment variables:
- `DEMUCS_CHUNK_TIMEOUT_SEC`: Timeout per chunk
- `DEMUCS_MAX_RETRIES`: Retry attempts
- `OUTPUT_PATH`: Where instrumentals are stored
- `WORKING_PATH`: Where processing happens

## Notes

- Monitor automatically stops updates when navigating away from Dashboard
- Audio player state persists across library refreshes
- Both components are non-blocking and error-tolerant
- Processing status updates continue even while playing audio
