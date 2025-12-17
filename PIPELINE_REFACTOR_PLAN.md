# Pipeline Refactoring: Queue-Based Architecture

**Status:** Foundation modules created  
**Target:** Make the pipeline source-agnostic, support multiple media retrieval services, and enable optional NAS syncing.

---

## Architecture Overview

### Current State
- Single retrieval path: `/incoming/` folder is watched for audio files
- Linear processing: file → demucs → instrumental only
- No formal job contract or manifest
- Output: `/music-library/Artist/Album/Title.mp3`

### Proposed State (this refactor)
```
┌─────────────────────────────────────────────┐
│  RETRIEVAL SERVICES (separate containers)   │
│  - YouTube (yt-dlp)                         │
│  - Deemix (music service)                   │
│  - Custom services (pluggable)              │
└─────────────────────────────────────────────┘
                    ↓
     Produce standardized "job bundles"
                    ↓
┌─────────────────────────────────────────────┐
│         HOLDING QUEUES (mounted)            │
│  /queues/youtube_audio/                     │
│  /queues/youtube_video/                     │
│  /queues/other/                             │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│    INSTRUMENTAL-MAKER (main processor)      │
│  Consume job bundles → process → output     │
│  Generate manifest.json (job metadata)      │
└─────────────────────────────────────────────┘
                    ↓
           /outputs/<job_id>/
   ├── manifest.json (routes to NAS)
   └── files/
       ├── audio/
       │   ├── Artist - Track.m4a (standard)
       │   ├── Artist - Track (no drum).m4a
       │   └── Artist - Track (drums only).m4a
       └── video/
           └── Artist - Track.mp4 (optional)
                    ↓
┌─────────────────────────────────────────────┐
│      NAS SYNC SERVICE (optional)            │
│  Watch manifests → route artifacts          │
│  Sync to configured remote paths            │
└─────────────────────────────────────────────┘
```

---

## New Modules Created

### 1. `app/job_bundle.py`
**Purpose:** Define the standardized handoff between retrievers and the processor.

**Key Classes:**
- `JobBundle`: What retrievers produce (title, artist, paths to audio/video/cover)
- `JobManifest`: What the processor writes after completing a job (metadata + artifact list)
- `ArtifactMetadata`: Describes a single output file (codec, duration, variant type)
- `YouTubeMetadata`: YouTube-specific provenance (ID, URL, channel, online duration)

**Retriever Responsibility:**
1. Download media
2. Validate duration (online vs downloaded)
3. Tag audio (Artist = Channel, Album = YTDL, Title = Video Title)
4. Write `job.json` to queue folder
5. Atomically move from `job_<id>.tmp/` to `job_<id>/`

**Processor Responsibility:**
1. Read `job.json` from queue
2. Process audio (separate stems, create variants)
3. Generate `manifest.json` with all produced artifacts
4. Output organized to `/outputs/<job_id>/files/`

---

### 2. `app/queue_consumer.py`
**Purpose:** Replace the old file-watcher. Discover and claim jobs from holding queues.

**Key Methods:**
- `discover_jobs()`: Scan `/queues/*/` for ready job folders
- `load_job_bundle()`: Read and parse `job.json`
- `claim_job()`: Move job from queue to working folder (atomic)
- `archive_job()`: Move completed job to success/fail archive

**Integration Point:**
Replace the old `_pick_next()` logic in `simple_runner.py` with calls to `QueueConsumer`.

---

### 3. `app/manifest_generator.py`
**Purpose:** Build and save `manifest.json` after a job completes.

**Key Methods:**
- `generate_for_job()`: Construct complete manifest from processing results
- Returns `JobManifest` with artifact list (audio variants, video, stems if preserved)

**Integration Point:**
Call this at the end of `process_one()` in `simple_runner.py` before archiving the job.

**Example Usage:**
```python
# After instrumental.mp3 is created with variants:
manifest = ManifestGenerator.generate_for_job(
    job_id="yt_abc123",
    source_type="youtube",
    artist=artist,
    album=album,
    title=title,
    output_dir=Path("/outputs/yt_abc123"),
    audio_variants=[
        {"variant": "instrumental", "label": "Instrumental", "filename": "...mp3"},
        {"variant": "no_drums", "label": "Instrumental (no drum)", "filename": "...mp3"},
    ],
    stems_preserved=False,
)
manifest.save(output_dir)
```

---

### 4. `app/nas_sync_service.py`
**Purpose:** Optional service that watches `/outputs/` for manifests and syncs artifacts.

**Key Features:**
- Configuration-driven: reads routing rules from config
- Non-blocking: if remote path not configured → warning + skip (job completes normally)
- Extensible: sync backends can be plugged in (rsync, S3, SCP, etc.)

**Configuration Structure:**
```yaml
nasSync:
  enabled: true
  remoteRoots:
    audio: "/mnt/nas/Instrumentals"
    video: "/mnt/nas/Videos"
    stems: "/mnt/nas/Stems"
  routes:
    - match: { kind: "audio", variant: "instrumental" }
      to: "${remoteRoots.audio}/Instrumental"
    - match: { kind: "audio", variant: "no_drums" }
      to: "${remoteRoots.audio}/NoDrums"
    # ... etc
```

---

## Implementation Plan (Incremental)

### Phase 1: Queue Foundation (This Commit)
✅ Create `job_bundle.py`, `queue_consumer.py`, `manifest_generator.py`, `nas_sync_service.py`  
✅ Document expected folder structure and schemas

### Phase 2: Integrate Queue Consumer (simple_runner.py)
- [ ] Add queue folder configuration to `config.py`:
  ```python
  QUEUE_YOUTUBE_AUDIO = "/queues/youtube_audio"
  QUEUE_YOUTUBE_VIDEO = "/queues/youtube_video"
  QUEUE_OTHER = "/queues/other"
  ```
- [ ] Replace `_pick_next()` with `QueueConsumer.discover_jobs()`
- [ ] Adapt `process_one()` to:
  1. Call `QueueConsumer.claim_job()` instead of reading from `/incoming/`
  2. Process audio variants (if `variants` flag in job.json)
  3. Call `ManifestGenerator.generate_for_job()` at end
  4. Save manifest.json before archiving

### Phase 3: YouTube Retriever Service (separate Docker container)
- [ ] Create `services/youtube_retriever/` with:
  - Dockerfile
  - `retriever.py`: yt-dlp integration + duration validation + tagging
  - Queue routing logic (audio-only vs video-only vs both)
- [ ] Configuration:
  ```python
  YTDL_MODE = "audio" | "video" | "both"
  YTDL_AUDIO_FORMAT = "m4a"
  YTDL_DURATION_TOL_SEC = 2.0
  YTDL_DURATION_TOL_PCT = 0.01
  ```

### Phase 4: Deemix Retriever Service (optional, separate container)
- [ ] Create `services/deemix_retriever/` with:
  - Docker container running deemix
  - Job bundle producer
  - Maps to `/queues/other/`

### Phase 5: Manifest + NAS Sync Integration
- [ ] Wire up manifest generation in `simple_runner.py`
- [ ] Create `services/nas_sync/` with:
  - Watcher for `/outputs/**/manifest.json`
  - Routing logic and sync backends
  - Configuration loading

### Phase 6: Variant Support
- [ ] Add `variants` flag to `job.json` schema
- [ ] Extend `simple_runner.py` to:
  - Generate multiple instrumental versions (drums, no drums, etc.)
  - Name files with suffixes: `(no drum)`, `(drums only)`
  - Add all variants to manifest

---

## File Structure After Full Refactor

```
instrumental-maker/
├── app/
│   ├── job_bundle.py              (NEW: job schema)
│   ├── queue_consumer.py           (NEW: queue watcher)
│   ├── manifest_generator.py       (NEW: manifest builder)
│   ├── nas_sync_service.py         (NEW: sync service skeleton)
│   ├── simple_runner.py            (MODIFY: integrate queues)
│   ├── config.py                   (MODIFY: add queue paths)
│   ├── main.py                     (MODIFY: add nas_sync command?)
│   ├── audio.py, metadata.py, ... (unchanged)
│
├── services/
│   ├── youtube_retriever/          (NEW)
│   │   ├── Dockerfile
│   │   ├── retriever.py
│   │   ├── config.py
│   │   └── requirements.txt
│   │
│   ├── deemix_retriever/           (NEW)
│   │   ├── Dockerfile
│   │   ├── retriever.py
│   │   └── ...
│   │
│   └── nas_sync/                   (NEW)
│       ├── Dockerfile
│       ├── sync_service.py
│       ├── config.py
│       └── ...
│
├── docker-compose.yml              (MODIFY: add retriever + nas_sync services)
├── queues/                         (NEW: mount points)
│   ├── youtube_audio/
│   ├── youtube_video/
│   └── other/
```

---

## Configuration (config.py updates needed)

```python
# Queue folders
QUEUE_YOUTUBE_AUDIO = _env_clean("QUEUE_YOUTUBE_AUDIO", "/queues/youtube_audio")
QUEUE_YOUTUBE_VIDEO = _env_clean("QUEUE_YOUTUBE_VIDEO", "/queues/youtube_video")
QUEUE_OTHER = _env_clean("QUEUE_OTHER", "/queues/other")

# Output structure
OUTPUTS_DIR = _env_clean("OUTPUTS_DIR", "/data/outputs")

# Variant options
GENERATE_NO_DRUMS_VARIANT = env_bool("GENERATE_NO_DRUMS_VARIANT", "true")
GENERATE_DRUMS_ONLY_VARIANT = env_bool("GENERATE_DRUMS_ONLY_VARIANT", "false")
PRESERVE_STEMS = env_bool("PRESERVE_STEMS", "false")

# NAS Sync (optional)
NAS_SYNC_ENABLED = env_bool("NAS_SYNC_ENABLED", "false")
NAS_SYNC_CONFIG_PATH = _env_clean("NAS_SYNC_CONFIG_PATH", "/app/nas_sync_config.yaml")
```

---

## Key Design Decisions

1. **Job bundles are atomic:** Retriever writes to `job_<id>.tmp/`, renames to `job_<id>/` when complete. Processor ignores `.tmp` folders.

2. **Manifests are the contract:** NAS Sync consumes manifests, not filesystem conventions. This is robust and extensible.

3. **Variants are post-process:** After separation, mix stems differently for each variant (no re-separation).

4. **NAS Sync is optional:** If not configured, jobs complete normally and artifacts stay in `/outputs/`.

5. **YouTube is separate at retrieval, same at processing:** Queue separation keeps YouTube concerns isolated during download, but the processor treats all sources identically.

---

## Next Steps

1. **Review** this plan and the module signatures
2. **Start Phase 2:** Integrate `QueueConsumer` into `simple_runner.py`
3. **Create Phase 3:** YouTube retriever service Docker container
4. **Iterate:** Test with live YouTube downloads → queues → processing → manifest

