import os

from typing import Optional

def _env_clean(key: str, default: Optional[str] = None) -> str:
    """Return env var value with inline comments stripped and whitespace trimmed.
    Example: "true   # comment" -> "true". If missing, returns default (as string).
    """
    val = os.getenv(key, default)
    if val is None:
        return ""
    s = str(val)
    # Strip inline comment starting with '#'
    if "#" in s:
        s = s.split("#", 1)[0]
    return s.strip()

def env_bool(key: str, default: str = "false") -> bool:
    s = _env_clean(key, default).lower()
    return s in ("1", "true", "yes", "on")

class Config:
    MODEL = _env_clean("MODEL", "htdemucs")
    STEMS = [s.strip().upper() for s in _env_clean("STEMS", "D,B,O").split(",") if s.strip()]
    SAMPLE_RATE = int(_env_clean("SAMPLE_RATE", "44100") or 44100)
    BIT_DEPTH = int(_env_clean("BIT_DEPTH", "16") or 16)
    # Allow OUTPUT_FORMAT to override legacy CODEC; default now mp3 for broader compatibility
    CODEC = (_env_clean("OUTPUT_FORMAT") or _env_clean("CODEC") or "mp3").lower()
    # MP3 encoding mode default; instance property reads env dynamically
    _MP3_ENCODING_DEFAULT = _env_clean("MP3_ENCODING", "v0").lower()
    @property
    def MP3_ENCODING(self) -> str:
        return _env_clean("MP3_ENCODING", Config._MP3_ENCODING_DEFAULT).lower()

    TARGET_LUFS = float(_env_clean("TARGET_LUFS", "-14") or -14)
    TRUE_PEAK_DBFS = float(_env_clean("TRUE_PEAK_DBFS", "-1.0") or -1.0)
    DUAL_PASS_LOUDNORM = env_bool("DUAL_PASS_LOUDNORM", "true")

    INCOMING = _env_clean("INCOMING", "/data/incoming")
    WORKING  = _env_clean("WORKING", "/data/working")
    OUTPUT   = _env_clean("OUTPUT", "/data/output")
    # Final music library root (Artist/Album/Title.mp3). Default maps to /data/output in compose.
    MUSIC_LIBRARY = _env_clean("MUSIC_LIBRARY", "/data/music-library")
    DB_PATH  = _env_clean("DB_PATH", "/data/db/jobs.sqlite")
    LOG_DIR  = _env_clean("LOG_DIR", "/data/logs")
    ARCHIVE_DIR = _env_clean("ARCHIVE_DIR", "/data/archive")
    # Optional quarantine directory for corrupt/problem inputs
    QUARANTINE_DIR = _env_clean("QUARANTINE_DIR", "/data/quarantine")
    # Where to send corrupt/problem files: "archive" (to ARCHIVE_DIR/rejects) or "quarantine" (to QUARANTINE_DIR)
    CORRUPT_DEST = _env_clean("CORRUPT_DEST", "archive").lower()
    # Optional staging directory for newly enqueued inputs. If not provided,
    # default to a hidden subfolder under INCOMING so tests/dev don’t require /data.
    STAGING = _env_clean("STAGING") or os.path.join(INCOMING, ".queued")

    _STABILITY_CHECK_SECONDS_RAW = int(_env_clean("STABILITY_CHECK_SECONDS", "5") or 5)
    _STABILITY_PASSES_RAW = int(_env_clean("STABILITY_PASSES", "2") or 2)
    MAX_PARALLEL_JOBS = int(_env_clean("MAX_PARALLEL_JOBS", "1") or 1)

    CHUNKING_ENABLED = env_bool("CHUNKING_ENABLED", "true")
    CHUNK_MAX = int(_env_clean("CHUNK_MAX", "16") or 16)
    CHUNK_OVERLAP_SEC = float(_env_clean("CHUNK_OVERLAP_SEC", "0.5") or 0.5)
    CROSSFADE_MS = int(_env_clean("CROSSFADE_MS", "200") or 200)
    RETRY_BACKOFF_SEC = int(_env_clean("RETRY_BACKOFF_SEC", "3") or 3)

    # Minimum input file size in bytes (skip zero-length or tiny placeholder files)
    MIN_INPUT_BYTES = int(_env_clean("MIN_INPUT_BYTES", "1024") or 1024)

    # Sidecar overrides
    SIDECAR_ENABLED = env_bool("SIDECAR_ENABLED", "true")
    SIDECAR_SCHEMA_VALIDATE = env_bool("SIDECAR_SCHEMA_VALIDATE", "true")

    # MinIO mirroring
    MINIO_MIRROR_ENABLED = env_bool("MINIO_MIRROR_ENABLED", "false")
    MINIO_ENDPOINT = _env_clean("MINIO_ENDPOINT", "")
    MINIO_USE_SSL = env_bool("MINIO_USE_SSL", "true")
    MINIO_ACCESS_KEY = _env_clean("MINIO_ACCESS_KEY", "")
    MINIO_SECRET_KEY = _env_clean("MINIO_SECRET_KEY", "")
    MINIO_BUCKET = _env_clean("MINIO_BUCKET", "")
    # Strip any inline comments after value (people sometimes append guidance)
    MINIO_PREFIX = _env_clean("MINIO_PREFIX", "")
    MINIO_CONTENT_TYPE_BY_EXT = env_bool("MINIO_CONTENT_TYPE_BY_EXT", "true")
    MINIO_SCAN_INTERVAL_SEC = int(_env_clean("MINIO_SCAN_INTERVAL_SEC", "10") or 10)
    # Region is optional; empty string treated as None by consumers
    MINIO_REGION = _env_clean("MINIO_REGION", "")

    # Dedupe strategy: existing behavior dedupes by content hash+config. Optionally also skip
    # enqueueing another file if a job with the same base filename already exists (even if
    # different content). Enable with DEDUPE_BY_FILENAME=true. You can allow reprocessing
    # when prior job errored by setting DEDUPE_INCLUDE_ERRORS=false (default true to skip even errors).
    DEDUPE_BY_FILENAME = env_bool("DEDUPE_BY_FILENAME", "false")
    DEDUPE_INCLUDE_ERRORS = env_bool("DEDUPE_INCLUDE_ERRORS", "true")
    # If true, second occurrence of same basename is auto-renamed with a numeric suffix instead of skipped;
    # third and further occurrences are skipped.
    DEDUPE_RENAME_SECOND = env_bool("DEDUPE_RENAME_SECOND", "false")
    DEDUPE_CLEANUP_METHOD = _env_clean("DEDUPE_CLEANUP_METHOD", "none").lower()  # none|archive|purge
    RESCAN_INTERVAL_SEC = int(_env_clean("RESCAN_INTERVAL_SEC", "300") or 300)  # periodic deep scan for missed files

    # Fast filesystem stability shortcut for dev/tests: skip multiple stability passes entirely.
    FAST_FS_STABILITY = env_bool("FAST_FS_STABILITY", "false")
    STABILITY_CHECK_SECONDS = 0 if FAST_FS_STABILITY else _STABILITY_CHECK_SECONDS_RAW
    STABILITY_PASSES = 1 if FAST_FS_STABILITY else _STABILITY_PASSES_RAW

    # CPU/Resource limiting
    # Max threads used by underlying libs (OpenBLAS/MKL/OMP/NumExpr). 0 means do not override.
    CPU_MAX_THREADS = int(_env_clean("CPU_MAX_THREADS", "0") or 0)
    # Optional CPU affinity mask for child processes, e.g. "0-3" or "0,2". Empty means disabled.
    CPU_AFFINITY = _env_clean("CPU_AFFINITY", "")
    # Optional process niceness for child processes (lower priority). Empty or 0 means disabled.
    CPU_NICE = int(_env_clean("CPU_NICE", "0") or 0)
    # FFmpeg thread limit; if 0, ffmpeg decides. If unset, will fall back to CPU_MAX_THREADS.
    FFMPEG_THREADS = int(_env_clean("FFMPEG_THREADS", str(CPU_MAX_THREADS if CPU_MAX_THREADS>0 else 0)) or (CPU_MAX_THREADS if CPU_MAX_THREADS>0 else 0))

    # Demucs execution controls
    DEMUCS_DEVICE = _env_clean("DEMUCS_DEVICE", "cpu").lower()  # cpu|cuda
    DEMUCS_JOBS = int(_env_clean("DEMUCS_JOBS", "1") or 1)
    # Timeout for Demucs processing per chunk (in seconds). 0 means no timeout.
    # Default: 3600 (1 hour) to prevent infinite hangs on CPU processing
    DEMUCS_CHUNK_TIMEOUT_SEC = int(_env_clean("DEMUCS_CHUNK_TIMEOUT_SEC", "3600") or 3600)
    # Maximum retry attempts for failed chunks
    DEMUCS_MAX_RETRIES = int(_env_clean("DEMUCS_MAX_RETRIES", "2") or 2)

    # Album processing behavior
    # When true, treat any top-level directory placed directly in INCOMING as an album job.
    ALBUMS_ENABLED = env_bool("ALBUMS_ENABLED", "false")
    # Valid audio extensions (lowercase) to consider when scanning albums.
    AUDIO_EXTS = [e.strip().lower() for e in _env_clean(
        "AUDIO_EXTS",
        ".mp3,.wav,.flac,.m4a,.aac,.ogg,.opus"
    ).split(",") if e.strip()]
    # Use structured output path (Artist/Album/Title) for singles as well; false keeps legacy flat output for singles.
    STRUCTURED_OUTPUT_SINGLES = env_bool("STRUCTURED_OUTPUT_SINGLES", "false")

    # Staging behavior: when enabled, watcher moves inputs from INCOMING to STAGING before enqueue
    # to avoid rescans/archival while processing. Disabled by default to preserve legacy/tests.
    MOVE_TO_STAGING_ENABLED = env_bool("MOVE_TO_STAGING_ENABLED", "false")
