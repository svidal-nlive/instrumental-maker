# Architecture

This document explains how the Instrumental Maker (CPU‑only, Simple Runner) is structured: modules, data flow, algorithms, error handling, and operational behaviors. It’s intended for contributors and operators extending or troubleshooting the system.

## Goals and Non‑Goals
- Goals
  - CPU‑only, single‑daemon pipeline that converts full songs into instrumentals.
  - Deterministic, oldest‑first processing with album sequentiality.
  - Robustness against corrupt inputs; clean organization and metadata.
  - Minimal dependencies (ffmpeg, demucs, mutagen) and strong observability via JSONL events.
- Non‑Goals
  - GPU acceleration or multi‑worker orchestration.
  - Full featured media library manager (beyond organizing and tagging results).

---

## High‑Level System Overview

```
           +-------------------+
           |  pipeline-data    |
           |   incoming/       |
           +----------+--------+
                      |
                      v  (scan oldest-first)
                +-----+------+
                | simple     | 1) scan candidates
                | runner     | 2) select next (album-aware)
                +-----+------+
                      |
          +-----------+-------------+
          |  working/<job-id>/      |
          |  - chunks/*.wav         |
          |  - demucs/*             |
          |  - merged/*.wav         |
          +-----------+-------------+
                      |
                      v
             encode + tag + cover
                      |
                      v
           MUSIC_LIBRARY (output/)
           Artist/Album/Title.mp3
                      |
                      +--> JSONL logs (logs/simple_runner.jsonl)
                      +--> archive/rejects or quarantine (corrupt)
```

Primary processes:
- Simple runner daemon executes an infinite loop: scan → pick next → process_one → log → repeat.
- Optional MinIO mirror syncs finalized outputs to a bucket/prefix.

---

## Modules and Responsibilities (app/)

- simple_runner.py
  - Orchestrates the end‑to‑end pipeline.
  - Scanning: discovers lone files in `INCOMING` and album roots (top‑level directories that contain audio files).
  - Selection: oldest‑mtime first across singles/albums; within an album, tracks are processed sequentially, guarded by an album lock.
  - Processing: chunking plan → ffmpeg chunk extract → Demucs (CPU) → crossfade merge → MP3 encode → tag + cover embedding → organize to library → cleanup.
  - Logging: structured JSONL per file (`processed`) and for corrupt inputs (`skipped_corrupt`).
  - Locks:
    - Singleton PID lock: ensures only one daemon runs (multi‑host safe via `hostname:pid`).
    - Album active lock: ensures only one track per album is processed at a time.

- audio.py
  - ffprobe duration helper; chunking math and extraction helpers; Demucs helpers; crossfade concatenation helpers.

- metadata.py
  - Tag readers (mutagen + safe fallbacks) and cover art helpers (discover external art in dir, extract first embedded art).
  - Tag application/propagation via ffmpeg where needed.

- config.py
  - Central configuration sourced from environment variables (paths, toggles, encoding options).
  - `MP3_ENCODING` is an instance property, so tests and processes can see live env changes.

- utils.py
  - `run_cmd` (subprocess wrapper), `ensure_dir`, `sanitize_filename` (POSIX‑preserving), `safe_move_file` (cross‑device move fallback).

- minio_mirror.py
  - Watches output and mirrors to a MinIO/S3 bucket using configured credentials and prefix.

- main.py
  - CLI entrypoints for running the simple runner daemon and the MinIO mirror.

Legacy/auxiliary (present but not central to the simple runner):
- watcher.py / worker.py / db.py / overrides.py — legacy or auxiliary code paths from earlier designs; the simple runner doesn’t depend on them.

---

## Processing Contract
- Input
  - An audio file placed directly in `INCOMING` (single) OR
  - An album directory placed directly under `INCOMING` (top‑level folder) containing one or more audio files.
- Output
  - MP3 instrumental organized at `MUSIC_LIBRARY/Artist/Album/Title.mp3` with tags and cover.
- Success criteria
  - Audio separated and recombined (if chunking), encoded as MP3, with metadata and cover embedded, and source cleaned up.
- Error modes
  - Corrupt or unreadable inputs are moved to `ARCHIVE_DIR/rejects` or `QUARANTINE_DIR` depending on `CORRUPT_DEST`; a `skipped_corrupt` JSONL event is emitted.

---

## Selection & Album Sequentiality
- Discovery:
  - Singles = files directly in `INCOMING` (allowed audio extensions).
  - Albums = directories directly under `INCOMING` with at least one audio file.
- Ordering: oldest modification time first across singles vs albums.
- Album policy:
  - When an album is chosen, the oldest remaining track in that album is processed.
  - A per‑album active flag prevents interleaving; the album remains “active” until all tracks are processed or the album is removed.

---

## Chunking and Crossfade Algorithm
- Defaults
  - Chunk length ~120 seconds, with a small overlap (e.g., 0.5s) to aid crossfading.
  - Crossfade duration (e.g., 200ms); parameters configurable via env.
  - Optional max chunk count to avoid pathological splits.
- Plan
  - ffprobe the input duration in seconds.
  - Produce [start, end) pairs with constant length until the end; last chunk may be shorter.
  - Include overlap by backing up the start of each chunk (except the first) by `CHUNK_OVERLAP_SEC`.
- Extract
  - ffmpeg extracts WAV chunks according to the plan into working/chunks.
- Separate
  - Each chunk runs through Demucs (CPU) to produce accompaniment signals.
- Merge
  - Order accompanimental chunks and apply crossfades at boundaries to form a continuous track; amplitude‑correct boundary regions.

---

## Demucs Invocation (CPU)
- Model: `htdemucs` (configurable).
- Device: `cpu` with single job (`DEMUCS_JOBS=1`).
- Output: different Demucs versions may name the accompaniment stem as `accompaniment.wav`, `no_vocals.wav`, or be inside an `other/` subdir. The code detects these variants robustly when locating the stem.

---

## Encoding and Tagging
- Encoding
  - MP3 using libmp3lame; mode configured by `MP3_ENCODING`:
    - `v0` (VBR V0) or
    - `cbr320` (CBR 320 kbps)
- Metadata
  - Tag resolution strategy:
    1) mutagen tags from source file
    2) ffprobe tags as fallback
    3) folder/filename heuristics if no embedded tags
       - Supports `Artist - Album`, `Artist – Album` (en dash), and nested `Artist/Album/` directories.
  - Comment tag format: `[INST_DBO__model-htdemucs__sr-44100__bit-16]` (values reflect config where applicable).
- Cover Art
  - Try to find an image file in the input directory (e.g., cover.jpg/png variants);
  - Otherwise extract the first embedded picture from the source file;
  - Embed cover into the resulting MP3.

---

## Filesystem Organization
- INCOMING: drop singles or album folders here.
- WORKING: per‑job tmp dir with chunks, stems, and merged intermediates; always cleaned when done.
- MUSIC_LIBRARY (aka output): final organized results.
- ARCHIVE_DIR/rejects: destination for corrupt/problem inputs when `CORRUPT_DEST=archive`.
- QUARANTINE_DIR: alternative destination when `CORRUPT_DEST=quarantine`.
- DB path: stores runtime state (e.g., PID lock) and any auxiliary state.
- LOG_DIR: contains `simple_runner.jsonl`.

Name preservation:
- On POSIX systems (Linux), `sanitize_filename` removes only path separators and NUL. Punctuation like `:` and `'` is preserved to maintain original artist/album/title names.

---

## Concurrency and Locks
- Singleton PID lock
  - File: `.../simple_runner.pid` (under the DB path’s parent or configured location).
  - Contents: `hostname:pid`.
  - Behavior: if another process with the same hostname+pid exists, prevent start; stale/foreign host locks are handled safely.
- Album active lock
  - In‑memory/ephemeral indicator to avoid processing multiple tracks from the same album concurrently.

---

## Structured Logging (JSONL)
- Location: `LOG_DIR/simple_runner.jsonl`.
- One JSON object per line.
- Event: processed
  - Example
    ```json
    {
      "event": "processed",
      "source": "/data/incoming/Single.mp3",
      "artist": "Artist",
      "album": "Album",
      "title": "Title",
      "duration_sec": 241.3,
      "encoding": "cbr320",
      "model": "htdemucs",
      "output_path": "/data/output/Artist/Album/Title.mp3",
      "timestamp": "2025-08-18T12:34:56Z"
    }
    ```
- Event: skipped_corrupt
  - Emitted when the input cannot be probed/processed (e.g., ffprobe/ffmpeg failure).
  - Example
    ```json
    {
      "event": "skipped_corrupt",
      "source": "/data/incoming/Broken.mp3",
      "destination": "/data/archive/rejects/Broken.mp3",
      "corrupt_dest": "archive",
      "error": "ffprobe: invalid data found when processing input",
      "timestamp": "2025-08-18T12:40:00Z"
    }
    ```

Notes
- These logs are designed for auditability and downstream metrics/analytics. They intentionally avoid large payloads.

---

## Error Handling & Corrupt Inputs
- ffprobe/ffmpeg exceptions are caught at orchestration boundaries.
- On corrupt input, choose destination based on `CORRUPT_DEST`:
  - `archive` → move under `ARCHIVE_DIR/rejects` preserving filename
  - `quarantine` → move under `QUARANTINE_DIR`
- Moves are performed with `safe_move_file` to handle cross‑device moves (`EXDEV`).
- Intermediates are cleaned up even on failure paths.

---

## Configuration Overview
Key environment variables (see README for full list):
- Paths: `INCOMING`, `WORKING`, `MUSIC_LIBRARY`, `ARCHIVE_DIR`, `QUARANTINE_DIR`, `DB_PATH`, `LOG_DIR`
- Processing: `MODEL`, `DEMUCS_DEVICE=cpu`, `DEMUCS_JOBS`, `MP3_ENCODING`
- Chunking/mixing: `CHUNK_OVERLAP_SEC`, `CROSSFADE_MS`, `CHUNK_MAX`
- Corrupt handling: `CORRUPT_DEST` (archive|quarantine)
- System: CPU limits, FFMPEG threads

Configuration is read via `app.config.Config` to centralize defaults and validation.

---

## Testing Strategy
- Unit tests cover:
  - Tag computation and folder heuristics (`Artist - Album`, en dash, nested dirs).
  - Singleton PID lock parsing, stale detection, legacy compatibility.
  - Simple scanner behaviors and MP3 encoding mode toggles.
- Tests avoid hard dependencies on external binaries where possible; `MP3_ENCODING` is an instance property to reflect env during tests.
- Run tests with `pytest -q` after installing dev requirements.

---

## Observability and Operations
- Primary signal: JSONL events; tail `simple_runner.jsonl` or ingest into your log system.
- Health: Runner idles when no candidates are found; PID lock prevents duplicate daemons.
- Data hygiene: Album folders get removed when all tracks successfully process; working directories are cleaned after each job.
- Name safety: filenames preserve common punctuation on Linux; cross‑platform differences are isolated in `sanitize_filename`.

---

## Extension Points and Future Work
- Concurrency: introduce a small worker pool while keeping album sequentiality (per‑album mutex).
- Retention: policies for quarantine/archive and requeue tooling for manual retries.
- Metrics: counters for processed/skipped, processing durations, chunk counts, and model stats.
- Additional models: configure alternative stem separation models where compatible.
- CLI: manual one‑off processing command for ad‑hoc runs.

---

## Security & Compliance Notes
- MinIO/S3 credentials are read from environment; avoid committing secrets.
- Audio files may be copyrighted; ensure you have rights to process and distribute outputs.

---

## Quick Reference: Flow Summary
1) Scan incoming for singles and album roots.
2) Pick oldest candidate; apply album lock if needed.
3) Probe duration → chunk plan → ffmpeg chunk extract.
4) Demucs CPU separation → collect accompaniment stems.
5) Crossfade merge of accompanimental chunks.
6) Tag resolution (mutagen → ffprobe → heuristics), cover selection/extraction.
7) MP3 encode (V0/CBR320) and embed tags/cover.
8) Organize to `Artist/Album/Title.mp3` (POSIX name preservation), delete sources.
9) Emit JSONL event; handle corrupt inputs by moving to archive/quarantine and logging.
