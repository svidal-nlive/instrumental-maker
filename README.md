# Instrumental Maker (CPU‑only, Simple Runner)

A streamlined, CPU‑only pipeline that turns input songs into instrumentals and organizes them into a clean music library.

This repo includes:
- A single‑process daemon (“simple runner”) that watches a single queue (oldest‑first), processes lone files and album folders sequentially, and writes organized, tagged MP3s.
- Optional mirroring of outputs to a local MinIO (S3) instance.
- A lightweight Filebrowser UI for browsing data volumes.
- Optional Deemix container to drop downloads straight into the incoming queue.

The design prioritizes robustness, observability (structured JSON logs), and safe defaults with zero GPU dependencies.

---

## Contents
- Overview
- Architecture & Data Flow
- Key Features
- Configuration (env vars)
- Services (docker‑compose)
- Volumes & Directory Layout
- How to Run
- Development & Testing
- Operational Notes & Troubleshooting
- Changelog of Recent Enhancements

---

## Overview
- Inputs: place audio files (or full album folders) into `pipeline-data/incoming`.
- Processing: the simple runner chunks audio (default 2 minutes, small overlap), removes vocals with Demucs (CPU), crossfades segments, encodes MP3 (V0 or CBR 320), embeds tags and cover art, and organizes outputs as `Artist/Album/Title.mp3`.
- Daemonization & Safety: single‑instance guard, sequential album processing with an album lock, structured logs, and cleanup of intermediates.
- Outputs: final files are stored under `pipeline-data/output` (aka the “music library”). Optionally mirrored to MinIO.

---

## Architecture & Data Flow

### Main components (app/)
- `app/simple_runner.py`
  - Scans incoming candidates: lone files in the root and top‑level album folders.
  - Selection policy: oldest‑first across singles vs albums; album tracks processed sequentially until done.
  - Chunking: 2‑min chunks with overlap; extract via ffmpeg.
  - Separation: Demucs (htdemucs) CPU only.
  - Merge: crossfade stitched segments.
  - Tags & cover: reads tags via mutagen; falls back to ffprobe; then folder/filename heuristics; embeds cover (external or first attached picture).
  - Encoding: MP3 (V0 or CBR 320), ID3v2.3; Comment tag `[INST_DBO__model-htdemucs__sr-44100__bit-16]`.
  - Organization: `MUSIC_LIBRARY/Artist/Album/Title.mp3` with POSIX‑friendly name preservation (punctuation like `:` and `'` is preserved on Linux).
  - Cleanup: deletes source track after success; removes album folder when last track completes; purges working dir.
  - Logging: JSONL at `LOG_DIR/simple_runner.jsonl` (events include `processed`, and `skipped_corrupt`).
  - Locks:
    - Singleton PID lock: `DB_PATH`’s parent contains `simple_runner.pid` with `hostname:pid`, preventing multi‑host/multi‑container contention.
    - Album active lock: `album_active.txt` keeps album processing sequential.

- `app/metadata.py`
  - Tag helpers (mutagen) with robust fallbacks.
  - Cover helpers: find album art file in directory; extract first embedded picture via ffmpeg.

- `app/audio.py`
  - Lower‑level audio helpers (ffprobe duration, chunk extraction, crossfades, Demucs helpers) used by other modes.

- `app/config.py`
  - Centralized env‑driven configuration. `MP3_ENCODING` is an instance property (reflects live env changes), other values cached from sanitized env.

- `app/utils.py`
  - `run_cmd` with optional resource limits, `ensure_dir`, `sanitize_filename` (POSIX‑preserving), `safe_move_file` (cross‑device move fallback).

- `app/minio_mirror.py`
  - Monitors `output` and mirrors to MinIO/S3 bucket/prefix.

- `app/main.py`
  - Entrypoint providing `simple` runner daemon and the MinIO mirror command.

### Data flow (simple runner)
1) Scan incoming root:
   - Lone files in `/data/incoming/`.
   - Album roots: immediate subdirectories containing any audio file; tracks picked oldest‑mtime first.
2) Chunking & stems:
   - ffprobe duration → 2‑min chunk plan with overlap → ffmpeg extracts WAV chunks.
   - Demucs (CPU, jobs=1) generates accompaniments; stitch with crossfades.
3) Tags & cover:
   - mutagen → ffprobe → folder/filename heuristics; attach cover art if found.
4) Encode & tag:
   - MP3 via libmp3lame, V0 or CBR 320; write tags and cover.
5) Organize & cleanup:
   - Move to `Artist/Album/Title.mp3`; delete source; remove album dir when finished; purge working dir.
6) Log:
   - Append event to JSONL log (processed or skipped_corrupt) with useful metadata for audits and metrics.

---

## Key Features
- CPU‑only, no GPU required.
- Oldest‑first single queue; album folders honored and processed sequentially.
- Chunking with overlap + crossfade recombination for robustness.
- Demucs htdemucs separation on CPU.
- MP3 V0 or CBR 320 selectable via env; embedded tags and cover art.
- Structured Artist/Album/Title library organization.
- POSIX name preservation: colons `:` and quotes `'` are preserved on Linux outputs.
- Robust fallbacks for missing tags; folder naming heuristics support `Artist - Album`, `Artist – Album` (en dash), and nested `Artist/Album/` structures.
- Single‑instance daemon guard using `hostname:pid` locks to avoid multi‑host contention.
- Structured JSONL logging; explicit `skipped_corrupt` events.
- Corrupt input handling: configurable archive vs quarantine destination, with cross‑device safe moves.

---

## Configuration (env vars)
Below are the most relevant variables (defaults shown). See `app/config.py` for full list and details.

- Core processing
  - `MODEL=htdemucs`
  - `DEMUCS_DEVICE=cpu` (cpu|cuda)
  - `DEMUCS_JOBS=1`
  - `DEMUCS_CHUNK_TIMEOUT_SEC=3600` (timeout per chunk in seconds; 0 = no timeout)
  - `DEMUCS_MAX_RETRIES=2` (retry attempts for failed chunks)
  - `MP3_ENCODING=v0` (v0|cbr320)
  - `SAMPLE_RATE=44100`, `BIT_DEPTH=16`
  - `FFMPEG_THREADS=0` (0 lets ffmpeg decide)

- Paths
  - `INCOMING=/data/incoming`
  - `WORKING=/data/working`
  - `MUSIC_LIBRARY=/data/output` (final organized library)
  - `OUTPUT=/data/output` (legacy)
  - `DB_PATH=/data/db/jobs.sqlite`
  - `LOG_DIR=/data/logs`
  - `ARCHIVE_DIR=/data/archive`
  - `QUARANTINE_DIR=/data/quarantine`

- Chunking & mixing
  - `CHUNKING_ENABLED=true`
  - `CHUNK_MAX=16`
  - `CHUNK_OVERLAP_SEC=0.5`
  - `CROSSFADE_MS=200`

- Corrupt input handling
  - `CORRUPT_DEST=archive` (archive → `ARCHIVE_DIR/rejects`, or quarantine → `QUARANTINE_DIR`)

- CPU limits (optional)
  - `CPU_MAX_THREADS=0`, `CPU_AFFINITY=""`, `CPU_NICE=0`

- MinIO mirror
  - `MINIO_ENDPOINT`, `MINIO_USE_SSL`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET`, `MINIO_PREFIX`, `MINIO_REGION`

- Watcher (legacy path)
  - Variables like `ALBUMS_ENABLED`, `AUDIO_EXTS`, `MOVE_TO_STAGING_ENABLED` apply to the older watcher/worker flow; the simple runner doesn’t require them.

---

## Services (docker‑compose)
- `instrumental-simple` (this app):
  - Command: `python -u -m app.main simple --daemon`
  - Volumes: incoming, working, output, db, logs, archive, models, quarantine
  - Env: see above; e.g., `DEMUCS_DEVICE=cpu`, `MP3_ENCODING=cbr320`, `CORRUPT_DEST=archive`

- `minio` (local S3): ports 9000/9001, persists at `pipeline-data/minio-data`.
- `minio-mirror`: mirrors `output` to MinIO using `MINIO_*` env.
- `filebrowser`: web UI at port 8095 for browsing `pipeline-data` volumes.
- `pipeline-deemix`: optional downloader that writes to `pipeline-data/incoming`.

---

## Volumes & Directory Layout
```
pipeline-data/
  incoming/            # drop files or album folders here
  working/             # temp work dirs (auto-cleaned)
  output/              # final music library (Artist/Album/Title.mp3)
  archive/
    rejects/           # corrupt/problem inputs (when CORRUPT_DEST=archive)
  quarantine/          # alternative destination for corrupt inputs
  db/                  # state, pid lock, etc.
  logs/
    simple_runner.jsonl  # structured JSONL (processed, skipped_corrupt, ...)
  minio-data/          # MinIO object store data
  models/              # model caches (torch/demucs)
```

---

## How to Run

### Option 1: Using Prebuilt Images from GitHub Container Registry (Recommended)

Pull and run the prebuilt Docker images without building locally:

```bash
# Copy the environment template
cp .env.example .env
# Edit .env with your settings (DOCKER_IMAGE is already set to GHCR)

# Pull and start services using prebuilt images
docker compose -f docker-compose.prebuilt.yml up -d

# Tail logs
docker compose -f docker-compose.prebuilt.yml logs -f instrumental-simple
```

The prebuilt images are available at:
- **GitHub Container Registry (GHCR)**: `ghcr.io/svidal-nlive/instrumental-maker:latest` (recommended)
- **Docker Hub** (optional): `docker.io/<username>/instrumental-maker:latest`

To use a specific version tag:
```bash
# In your .env file, set:
DOCKER_IMAGE=ghcr.io/svidal-nlive/instrumental-maker:v1.0.0
```

**For private repositories**: You'll need to authenticate with GHCR:
```bash
echo $GITHUB_PAT | docker login ghcr.io -u USERNAME --password-stdin
```

### Option 2: Running Locally Without Traefik

If you're testing on a machine without Traefik or want direct port access:

```bash
# Use the local override compose file
docker compose -f docker-compose.prebuilt.yml -f docker-compose.local.yml up -d

# Services will be accessible at:
# - Web UI:        http://localhost:5000
# - File Browser:  http://localhost:8095
# - MinIO Console: http://localhost:9001 (S3 API at :9000)
# - Deemix:        http://localhost:6595
```

You can also use your local IP address or a custom domain (add to `/etc/hosts`):
```bash
# Example with custom local domain
echo "192.168.1.100 instrumental.local" | sudo tee -a /etc/hosts

# Access at: http://instrumental.local:5000
```

### Option 3: Building Locally

Using Docker Compose (recommended):

```bash
# Build
docker compose build

# Start services
docker compose up -d

# Tail logs (simple runner)
docker compose logs -f instrumental-simple
```

With Makefile shortcuts:

```bash
make build
make up
make logs SERVICE=instrumental-simple
```

Environment can be provided via `.env` and/or compose `environment:`. Minimal `.env` example:

First time setup:

```bash
cp .env.example .env
# then open .env and update values for your environment
```

```
MODEL=htdemucs
DEMUCS_DEVICE=cpu
DEMUCS_JOBS=1
MP3_ENCODING=cbr320
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=instrumentals
```

---

## Development & Testing
Local dev (Python 3.12):

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
```

Targeted tests are under `tests/`:
- `test_compute_tags.py` — fallbacks and folder parsing (`Artist - Album`, en dash, nested `Artist/Album`).
- `test_singleton_lock.py` — hostname:pid lock parsing and behavior.
- `test_simple_scanner_and_tagger.py` — scanning and MP3 encoding toggle.
- Legacy watcher/db tests remain but aren’t required to run the simple runner.

Coding tips:
- Config: prefer reading env through `app.config.Config`.
- When changing public behavior, add/adjust tests.
- Keep subprocess calls input‑first for ffmpeg, then mapping, then codec/metadata, to avoid ordering pitfalls.

---

## Operational Notes & Troubleshooting
- “nothing to process”: the daemon is idle; add files into `pipeline-data/incoming`.
- PID lock: see `pipeline-data/db/simple_runner.pid` → contains `hostname:pid`. Prevents multiple daemons.
- Album lock: `album_active.txt` under `pipeline-data/db/` parent ensures sequential processing within an album.
- Corrupt inputs:
  - ffprobe/ffmpeg errors are caught; file is moved to `archive/rejects` or `quarantine` per `CORRUPT_DEST`.
  - A `skipped_corrupt` JSONL event is appended with `source`, `destination`, `error`, `corrupt_dest`, `timestamp`.
- Name preservation: on Linux, colons (`:`) and apostrophes (`'`) are preserved in output paths; only path separators and NULs are removed.
- Performance knobs: `DEMUCS_JOBS`, `FFMPEG_THREADS`, `CPU_MAX_THREADS`, `CPU_AFFINITY`, `CPU_NICE`.

---

## Changelog of Recent Enhancements
- Simplified single‑queue runner replacing watcher/worker for this mode; CPU‑only Demucs with chunking and crossfades.
- Robust Demucs output discovery across versions (`other.wav`, `no_vocals.wav`, `accompaniment.wav`).
- Tag fallback logic: mutagen → ffprobe → folder heuristics; filename cleanup for titles.
- Correct ffmpeg input/mapping/metadata ordering; reliable cover embedding.
- Single‑instance lock writes `hostname:pid`; supports legacy numeric format; handles stale locks.
- POSIX‑preserving filename sanitization: keep `:` and `'` on Linux to preserve original names.
- Structured JSONL logs for `processed`.
- New `skipped_corrupt` JSONL events for corrupt/unreadable files; configurable destination (`CORRUPT_DEST`) with archive vs quarantine.
- Safe cross‑device file moves (`safe_move_file`).
- Unit tests for `_compute_tags` heuristics and singleton lock behavior.
- MP3 encoding mode is an instance property on `Config`, making tests/env toggles reliable.

---

## License
This project contains third‑party tools subject to their own licenses (Demucs, ffmpeg, etc.). Review their terms before distribution.

---

## CI/CD & Prebuilt Images
- CI (GitHub Actions): `.github/workflows/ci.yml` runs pytest on pushes and PRs.
- Docker Publish: `.github/workflows/docker-publish.yml` builds multi-arch images and pushes to Docker Hub on `main` and version tags `v*.*.*`.
- Expected GitHub secrets (Repo → Settings → Secrets and variables → Actions):
  - `DOCKERHUB_USERNAME`
  - `DOCKERHUB_TOKEN` (Docker Hub access token)

Use prebuilt images locally via `docker-compose.prebuilt.yml`:

```bash
export DOCKERHUB_USERNAME=youruser
docker compose -f docker-compose.prebuilt.yml up -d
```

To refresh a tagged image:

```bash
docker compose -f docker-compose.prebuilt.yml pull
docker compose -f docker-compose.prebuilt.yml up -d --force-recreate
```
