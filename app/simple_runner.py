from __future__ import annotations

import shutil
import subprocess
import sys
import time
import os
import socket
import signal
from dataclasses import dataclass
import re
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any, cast

from .config import Config
try:
    from . import metadata as _meta
except ImportError:
    class _MetaShim:
        @staticmethod
        def read_basic_tags(_p: Path) -> Dict[str, str]:
            return {}
    _meta = _MetaShim()  # type: ignore
try:
    from .metadata import find_album_art_in_dir, extract_first_embedded_art
except ImportError:
    def find_album_art_in_dir(dir_path: Path) -> Optional[Path]:
        del dir_path
        return None
    def extract_first_embedded_art(src_audio: Path, out_img: Path) -> Optional[Path]:
        del src_audio, out_img
        return None
from .utils import ensure_dir, sanitize_filename
import json


SUPPORTED_EXTS = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".opus"}


@dataclass
class Job:
    src: Path
    album_root: Optional[Path]  # top-level album dir under incoming, else None
    cover: Optional[Path]


def _is_audio(p: Path) -> bool:
    return p.is_file() and p.suffix.lower() in SUPPORTED_EXTS


def _run(cmd: List[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)


class TimeoutError(Exception):
    """Raised when a subprocess times out."""
    pass


def _run_with_timeout(cmd: List[str], timeout_sec: Optional[int] = None, description: str = "") -> subprocess.CompletedProcess[str]:
    """Run command with optional timeout. Returns CompletedProcess or raises TimeoutError."""
    if description:
        print(f"[simple] {description}")
    
    try:
        proc = subprocess.run(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True, 
            check=False,
            timeout=timeout_sec
        )
        return proc
    except subprocess.TimeoutExpired as e:
        print(f"[simple] TIMEOUT after {timeout_sec}s: {' '.join(cmd[:3])}...")
        raise TimeoutError(f"Command timed out after {timeout_sec}s: {description}") from e



def _read_tags(p: Path) -> Dict[str, str]:
    raw = cast(Dict[Any, Any], _meta.read_basic_tags(p))  # may contain non-str keys/values
    result: Dict[str, str] = {}
    for k, v in raw.items():
        try:
            result[f"{k}"] = f"{v[0] if isinstance(v, list) and v else v}"
        except (ValueError, TypeError):
            continue
    return result


def _ffprobe_tags(p: Path) -> Dict[str, str]:
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format_tags=artist,album,title",
            "-of", "json",
            str(p),
        ]
        proc = _run(cmd)
        if proc.returncode != 0:
            return {}
        data_any: Any = json.loads(proc.stdout or proc.stderr or "{}")
        if not isinstance(data_any, dict):
            return {}
        data: Dict[str, Any] = cast(Dict[str, Any], data_any)
        fmt_any: Any = data.get("format", {})
        if not isinstance(fmt_any, dict):
            return {}
        fmt = cast(Dict[str, Any], fmt_any)
        tag_any2: Any = fmt.get("tags", {})
        if not isinstance(tag_any2, dict):
            return {}
        tag_any = cast(Dict[str, Any], tag_any2)
        out: Dict[str, str] = {}
        for k in ("artist", "album", "title"):
            v = tag_any.get(k)
            if isinstance(v, str) and v.strip():
                out[k] = v.strip()
        return out
    except (json.JSONDecodeError, ValueError, TypeError, FileNotFoundError, OSError):
        return {}


def _strip_tracknum_from_title(name: str) -> str:
    s = re.sub(r"^\s*\d{1,3}\s*[-_. ]+\s*", "", name).strip()
    # remove trailing/leading dashes/underscores and squeeze spaces
    s = re.sub(r"\s+", " ", s)
    return s


def _compute_tags(src: Path, album_root: Optional[Path]) -> Tuple[str, str, str]:
    # Base from mutagen
    base = _read_tags(src)
    artist = (base.get("artist") or base.get("ARTIST") or "").strip()
    album = (base.get("album") or base.get("ALBUM") or "").strip()
    title = (base.get("title") or base.get("TITLE") or "").strip()
    # Try ffprobe if missing
    if not (artist and album and title):
        probe = _ffprobe_tags(src)
        artist = artist or probe.get("artist", "").strip()
        album = album or probe.get("album", "").strip()
        title = title or probe.get("title", "").strip()
    # Filename-based title
    if not title:
        title = _strip_tracknum_from_title(src.stem)
    # Album-folder heuristics
    if album_root and not (artist and album):
        folder = album_root.name.strip()
        # Support hyphen or en dash as separator
        sep_idx = -1
        for sep in (" - ", " – "):
            if sep in folder:
                sep_idx = folder.index(sep)
                a_guess, b_guess = folder.split(sep, 1)
                a_guess, b_guess = a_guess.strip(), b_guess.strip()
                artist = artist or (a_guess if a_guess else "Unknown")
                album = album or (b_guess if b_guess else "Unknown")
                break
        if sep_idx == -1:
            # If src is nested under an album directory, use src.parent as Album and album_root as Artist
            src_parent = src.parent.name.strip()
            if src_parent and src_parent != folder:
                artist = artist or (folder if folder else "Unknown")
                album = album or src_parent
            else:
                album = album or (folder if folder else "Unknown")
    # Fallbacks
    artist = artist or "Unknown"
    album = album or "Unknown"
    title = title or src.stem or "Unknown"
    return title, artist, album


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except FileNotFoundError:
        return time.time()


def _file_size(path: Path) -> int:
    """Get file size, return 0 if file doesn't exist."""
    try:
        return path.stat().st_size
    except FileNotFoundError:
        return 0


def _is_file_stable(path: Path, stability_seconds: float = 2.0) -> bool:
    """
    Check if a file has been stable (unchanged size and mtime) for the specified duration.
    This prevents picking up files that are still being written (e.g., during download/conversion).
    """
    try:
        initial_size = _file_size(path)
        initial_mtime = _mtime(path)
        
        # Check how old the file is - if recently modified, wait for stability
        age = time.time() - initial_mtime
        if age < stability_seconds:
            # File was modified too recently, wait and check again
            time.sleep(stability_seconds)
            
            # Re-check if file still exists and compare
            if not path.exists():
                return False
            
            new_size = _file_size(path)
            new_mtime = _mtime(path)
            
            # If size or mtime changed, file is still being written
            if new_size != initial_size or new_mtime != initial_mtime:
                return False
        
        return True
    except (OSError, IOError):
        return False


def _scan_candidates(incoming: Path) -> Tuple[List[Path], List[Path]]:
    # lone files in incoming root, and album roots (dirs directly under incoming that contain any audio)
    # Only include files that have been stable (not being written to) for at least 2 seconds
    lone: List[Path] = []
    album_roots: List[Path] = []
    if not incoming.exists():
        return lone, album_roots
    # lone files (non-recursive) - only include stable files
    for p in incoming.iterdir():
        if p.is_file() and _is_audio(p) and _is_file_stable(p):
            lone.append(p)
    # album roots (top-level dirs with audio inside) - only include if all audio files are stable
    for d in incoming.iterdir():
        if d.is_dir():
            audio_files = [x for x in d.rglob("*") if _is_audio(x)]
            if audio_files and all(_is_file_stable(f) for f in audio_files):
                album_roots.append(d)
    return lone, album_roots


# Public wrapper for tests and tooling
def scan_incoming_candidates(incoming: Path) -> Tuple[List[Path], List[Path]]:
    return _scan_candidates(incoming)


def _pick_next(incoming: Path, album_lock: Path) -> Optional[Job]:
    # If an album is active, keep processing it sequentially until finished
    if album_lock.exists():
        try:
            album_path_str = album_lock.read_text().strip()
            if album_path_str:
                album_root = Path(album_path_str)
                if album_root.exists():
                    tracks = sorted([p for p in album_root.rglob("*") if _is_audio(p)], key=str)
                    if tracks:
                        track = min(tracks, key=_mtime)
                        cover = find_album_art_in_dir(album_root) or None
                        if cover is None:
                            cover = extract_first_embedded_art(track, incoming / ".tmp_cover.jpg")
                        return Job(src=track, album_root=album_root, cover=cover)
                # Stale lock (album gone or empty). Remove and proceed to normal scan.
                try:
                    album_lock.unlink()
                except OSError:
                    pass
        except OSError:
            pass

    lone, albums = _scan_candidates(incoming)
    if not lone and not albums:
        return None
    oldest_lone: Optional[Path] = min(lone, key=_mtime) if lone else None
    oldest_album: Optional[Path] = min(albums, key=_mtime) if albums else None
    # choose older between oldest lone file and oldest album dir
    pick_album = False
    if oldest_lone and oldest_album:
        pick_album = _mtime(oldest_album) <= _mtime(oldest_lone)
    elif oldest_album and not oldest_lone:
        pick_album = True
    # when album picked, select next track to process: by track number if available, else natural sort order
    if pick_album:
        # sort candidates inside album
        assert oldest_album is not None
        tracks = sorted([p for p in oldest_album.rglob("*") if _is_audio(p)], key=str)
        if not tracks:
            return None
        # choose oldest track by mtime to be robust and preserve sequential-ish order
        track = min(tracks, key=_mtime)
        cover = find_album_art_in_dir(oldest_album) or None
        if cover is None:
            # optionally try embedded art from first track
            cover = extract_first_embedded_art(track, incoming / ".tmp_cover.jpg")
        return Job(src=track, album_root=oldest_album, cover=cover)
    else:
        assert oldest_lone is not None
        return Job(src=oldest_lone, album_root=None, cover=None)


def _chunk_plan_seconds(total_sec: float, chunk_sec: int = 120, overlap_sec: float = 0.5) -> List[Tuple[float, float, float, float]]:
    """Return list of (start, dur, head_trim, tail_trim)."""
    plan: List[Tuple[float, float, float, float]] = []
    start = 0.0
    while start < total_sec:
        end = min(total_sec, start + chunk_sec)
        dur = end - start
        head = overlap_sec if plan else 0.0
        tail = overlap_sec if end < total_sec else 0.0
        plan.append((max(0.0, start - (overlap_sec if plan else 0.0)), dur + (tail if end < total_sec else 0.0) + (overlap_sec if plan else 0.0), head, tail))
        start += chunk_sec
    return plan


def _ffprobe_duration_sec(p: Path) -> float:
    from .audio import ffprobe_duration
    cfg = Config()
    return ffprobe_duration(p, cfg)


def _ffmpeg_extract(src: Path, dst: Path, start: float, dur: float, sr: int, threads: int):
    ensure_dir(dst.parent)
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{start:.3f}", "-t", f"{dur:.3f}",
        "-i", str(src),
        "-c:a", "pcm_s16le", "-ar", str(sr),
    ]
    if threads and threads > 0:
        cmd += ["-threads", str(threads)]
    cmd += [str(dst)]
    p = _run(cmd)
    if p.returncode != 0:
        raise RuntimeError(p.stderr or p.stdout)


def _demucs_no_vocals(chunk_wav: Path, out_dir: Path, model: str, device: str = "cpu", jobs: int = 1, 
                      chunk_index: int = 0, total_chunks: int = 1, timeout_sec: int = 3600) -> Path:
    """
    Run Demucs on a chunk with timeout protection.
    
    Args:
        chunk_wav: Input chunk file
        out_dir: Output directory for Demucs
        model: Demucs model name
        device: cpu or cuda
        jobs: Number of parallel jobs
        chunk_index: Current chunk index for progress reporting
        total_chunks: Total number of chunks for progress reporting
        timeout_sec: Timeout in seconds (default 1 hour per chunk)
    
    Returns:
        Path to the instrumental/no_vocals output file
    
    Raises:
        TimeoutError: If processing exceeds timeout
        RuntimeError: If Demucs fails or output not found
    """
    ensure_dir(out_dir)
    
    # Progress indicator
    progress = f"[{chunk_index + 1}/{total_chunks}]"
    chunk_name = chunk_wav.name
    
    print(f"[simple] {progress} Processing chunk: {chunk_name}")
    start_time = time.time()
    
    # Use two-stems=vocals so we can take the accompaniment quickly
    cmd = [
        "demucs", "-n", model,
        "--two-stems", "vocals",
        "-o", str(out_dir),
        "--device", device,
        "--jobs", str(max(1, int(jobs))),
        str(chunk_wav),
    ]
    
    try:
        p = _run_with_timeout(
            cmd, 
            timeout_sec=timeout_sec,
            description=f"{progress} Running Demucs on {chunk_name} (timeout: {timeout_sec}s)"
        )
        
        elapsed = time.time() - start_time
        
        if p.returncode != 0:
            error_msg = (p.stderr or p.stdout or "Unknown error").strip()
            print(f"[simple] {progress} FAILED after {elapsed:.1f}s: {error_msg}")
            raise RuntimeError(f"Demucs failed on {chunk_name}: {error_msg}")
        
        print(f"[simple] {progress} Completed in {elapsed:.1f}s (~{elapsed/60:.1f} min)")
        
    except TimeoutError as e:
        elapsed = time.time() - start_time
        print(f"[simple] {progress} TIMEOUT after {elapsed:.1f}s on {chunk_name}")
        raise
    
    # Demucs output layout varies by version:
    # - out_dir/model/<base>/{vocals,other}.wav
    # - out_dir/model/<base>/{vocals,no_vocals}.wav
    # - sometimes directly under out_dir/<base>/*
    candidates = ("other.wav", "no_vocals.wav", "accompaniment.wav")
    
    # First try within model dir
    model_dir = out_dir / model
    if model_dir.exists():
        for d in model_dir.rglob("*.wav"):
            if d.name in candidates:
                print(f"[simple] {progress} Found output: {d.name}")
                return d
    
    # Then search anywhere under out_dir
    for name in candidates:
        for f in out_dir.rglob(name):
            print(f"[simple] {progress} Found output: {f.name}")
            return f
    
    # Output not found - list what we actually got
    print(f"[simple] {progress} ERROR: Demucs output not found in {out_dir}")
    try:
        contents = list(out_dir.rglob("*"))
        print(f"[simple] {progress} Directory contents: {[str(p.relative_to(out_dir)) for p in contents[:10]]}")
    except Exception:
        pass
    
    raise RuntimeError(f"Demucs output not found for {chunk_name} in {out_dir}")


def _concat_with_crossfades(parts: List[Path], out_wav: Path, crossfade_ms: int, threads: int):
    ensure_dir(out_wav.parent)
    if len(parts) == 1:
        shutil.copy2(parts[0], out_wav)
        return
    # iteratively acrossfade pairwise
    tmp = parts[0]
    cf_s = max(0, crossfade_ms) / 1000.0
    for i in range(1, len(parts)):
        nxt = parts[i]
        tmp_out = out_wav.parent / f"_xf_{i}.wav"
        cmd = [
            "ffmpeg", "-y",
            "-i", str(tmp), "-i", str(nxt),
            "-filter_complex", f"acrossfade=d={cf_s:.3f}",
        ]
        if threads and threads > 0:
            cmd += ["-threads", str(threads)]
        cmd += [str(tmp_out)]
        p = _run(cmd)
        if p.returncode != 0:
            raise RuntimeError(p.stderr or p.stdout)
        tmp = tmp_out
    tmp.rename(out_wav)


def _encode_and_tag(final_wav: Path, dst_mp3: Path, comment_str: str, cover: Optional[Path], threads: int,
                    title: str, artist: str, album: str):
    # sanitize for path (POSIX keeps ':' and quotes; sanitize_filename is POSIX-aware)
    fn_artist = sanitize_filename(artist)
    fn_album = sanitize_filename(album)
    fn_title = sanitize_filename(title)
    ensure_dir(dst_mp3.parent)
    # Determine MP3 encoding mode from config
    cfg = Config()
    # 1) Inputs first
    cmd = ["ffmpeg", "-y", "-i", str(final_wav)]
    if cover and cover.exists():
        cmd += ["-i", str(cover)]
    # 2) Mapping
    if cover and cover.exists():
        cmd += [
            "-map", "0:a",
            "-map", "1:v",
            "-disposition:v", "attached_pic",
            "-metadata:s:v", "title=Album cover",
            "-metadata:s:v", "comment=Cover (front)",
        ]
    else:
        cmd += ["-map", "0:a"]
    # 3) Output encoding and tags
    cmd += ["-c:a", "libmp3lame"]
    if cfg.MP3_ENCODING == "cbr320":
        cmd += ["-b:a", "320k"]
    else:
        cmd += ["-q:a", "0"]
    cmd += [
        "-id3v2_version", "3",
        "-metadata", f"artist={artist}",
        "-metadata", f"album={album}",
        "-metadata", f"title={title}",
        "-metadata", f"comment={comment_str}",
    ]
    if threads and threads > 0:
        cmd += ["-threads", str(threads)]
    cmd += [str(dst_mp3)]
    p = _run(cmd)
    if p.returncode != 0:
        raise RuntimeError(p.stderr or p.stdout)
    # return paths and tag set
    return fn_artist, fn_album, fn_title


def process_one(cfg: Config) -> bool:
    incoming = Path(cfg.INCOMING)
    music = Path(cfg.MUSIC_LIBRARY)
    ensure_dir(incoming)
    ensure_dir(music)
    state_dir = Path(cfg.DB_PATH).parent
    album_lock = state_dir / "album_active.txt"
    job = _pick_next(incoming, album_lock)
    if not job:
        print("[simple] nothing to process")
        return False

    src = job.src
    print(f"[simple] processing: {src}")
    print(f"[simple] ============================================")
    
    overall_start = time.time()
    work = Path(cfg.WORKING) / f"simple_{int(time.time())}"
    ensure_dir(work)

    # 1) chunk into 2-minute segments with small overlap
    try:
        duration = _ffprobe_duration_sec(src)
    except Exception as e:
        # Corrupt or unreadable input; move to archive/rejects or quarantine and continue
        dest_root = Path(cfg.QUARANTINE_DIR) if cfg.CORRUPT_DEST == "quarantine" else Path(cfg.ARCHIVE_DIR) / "rejects"
        dest = dest_root / src.name
        moved_ok = False
        try:
            from .utils import safe_move_file
            safe_move_file(src, dest)
            moved_ok = True
            action = "quarantined" if cfg.CORRUPT_DEST == "quarantine" else "archived"
            print(f"[simple] skipped corrupt input → {action}: {src} -> {dest} ({e})")
        except Exception:
            print(f"[simple] skipped corrupt input (failed to move): {src} ({e})")
        # Log structured event
        try:
            log_dir = Path(cfg.LOG_DIR); ensure_dir(log_dir)
            evt: Dict[str, Any] = {
                "event": "skipped_corrupt",
                "source": str(src),
                "destination": str(dest) if moved_ok else None,
                "error": f"{e}",
                "corrupt_dest": cfg.CORRUPT_DEST,
                "timestamp": int(time.time()),
            }
            (log_dir / "simple_runner.jsonl").open("a").write(json.dumps(evt) + "\n")
        except Exception:
            pass
        # best-effort: remove work dir if created
        try:
            shutil.rmtree(work)
        except Exception:
            pass
        return True
    plan = _chunk_plan_seconds(duration, chunk_sec=120, overlap_sec=cfg.CHUNK_OVERLAP_SEC)
    chunks: List[Path] = []
    
    print(f"[simple] Audio duration: {duration:.1f}s (~{duration/60:.1f} min)")
    print(f"[simple] Creating {len(plan)} chunks with {cfg.CHUNK_OVERLAP_SEC}s overlap")
    
    for i, (start, dur, _, _) in enumerate(plan):
        cpath = work / f"chunk_{i:03d}.wav"
        print(f"[simple] [{i+1}/{len(plan)}] Extracting chunk at {start:.1f}s, duration {dur:.1f}s")
        _ffmpeg_extract(src, cpath, start, dur, cfg.SAMPLE_RATE, cfg.FFMPEG_THREADS)
        chunks.append(cpath)

    # 2) demucs for each chunk to get accompaniment (no vocals)
    # Add retry logic and timeout for each chunk
    stems: List[Path] = []
    max_retries = cfg.DEMUCS_MAX_RETRIES
    # Use configured timeout, or calculate based on chunk duration
    chunk_timeout_sec = cfg.DEMUCS_CHUNK_TIMEOUT_SEC if cfg.DEMUCS_CHUNK_TIMEOUT_SEC > 0 else max(600, int(120 * 5))
    
    print(f"[simple] Processing {len(chunks)} chunks with Demucs (timeout: {chunk_timeout_sec}s per chunk, max retries: {max_retries})")
    
    for i, c in enumerate(chunks):
        out_dir = work / f"demucs_{i:03d}"
        retry_count = 0
        success = False
        last_error = None
        
        while retry_count <= max_retries and not success:
            try:
                if retry_count > 0:
                    print(f"[simple] [{i+1}/{len(chunks)}] Retry {retry_count}/{max_retries} for {c.name}")
                    # Clean up failed output directory before retry
                    if out_dir.exists():
                        try:
                            shutil.rmtree(out_dir)
                        except Exception as e:
                            print(f"[simple] Warning: Could not clean {out_dir}: {e}")
                
                acc = _demucs_no_vocals(
                    c, out_dir, cfg.MODEL, cfg.DEMUCS_DEVICE, cfg.DEMUCS_JOBS,
                    chunk_index=i, total_chunks=len(chunks), timeout_sec=chunk_timeout_sec
                )
                stems.append(acc)
                success = True
                
            except TimeoutError as e:
                last_error = e
                print(f"[simple] [{i+1}/{len(chunks)}] Chunk {c.name} timed out")
                retry_count += 1
                
            except Exception as e:
                last_error = e
                print(f"[simple] [{i+1}/{len(chunks)}] Chunk {c.name} failed: {e}")
                retry_count += 1
        
        if not success:
            # All retries exhausted
            error_msg = f"Failed to process chunk {i} ({c.name}) after {max_retries} retries: {last_error}"
            print(f"[simple] FATAL: {error_msg}")
            
            # Log the failure
            try:
                log_dir = Path(cfg.LOG_DIR); ensure_dir(log_dir)
                evt: Dict[str, Any] = {
                    "event": "chunk_processing_failed",
                    "source": str(src),
                    "chunk_index": i,
                    "chunk_path": str(c),
                    "error": str(last_error),
                    "retries": retry_count,
                    "timestamp": int(time.time()),
                }
                (log_dir / "simple_runner.jsonl").open("a").write(json.dumps(evt) + "\n")
            except Exception:
                pass
            
            # Clean up and abort processing this file
            try:
                shutil.rmtree(work)
            except Exception:
                pass
            
            raise RuntimeError(error_msg)

    # 3) concat with crossfades
    final_wav = work / "instrumental.wav"
    print(f"[simple] Merging {len(stems)} stems with crossfades ({cfg.CROSSFADE_MS}ms)")
    _concat_with_crossfades(stems, final_wav, cfg.CROSSFADE_MS, cfg.FFMPEG_THREADS)
    print(f"[simple] Crossfade merge complete")

    # 4) encode to MP3, tag, embed cover, and move to /music-library/Artist/Album/Title.mp3
    comment = "[INST_DBO__model-htdemucs__sr-44100__bit-16]"
    # determine cover: prefer provided, else if album root present, search
    cover = job.cover
    if cover is None:
        if job.album_root is not None:
            cover = find_album_art_in_dir(job.album_root)
        else:
            cover = find_album_art_in_dir(src.parent)
    # Compute tags with fallbacks (mutagen, ffprobe, folder, filename)
    title, artist, album = _compute_tags(src, job.album_root)
    # dst path
    dst = music / sanitize_filename(artist) / sanitize_filename(album) / f"{sanitize_filename(title)}.mp3"
    
    print(f"[simple] Encoding to MP3 ({cfg.MP3_ENCODING.upper()}) and tagging")
    print(f"[simple] Output: {dst.relative_to(music) if dst.is_relative_to(music) else dst}")
    
    _encode_and_tag(final_wav, dst, comment, cover, cfg.FFMPEG_THREADS, title, artist, album)

    # mark album active if this job is part of an album
    if job.album_root is not None and not album_lock.exists():
        try:
            album_lock.write_text(str(job.album_root))
        except OSError:
            pass

    # 5) cleanup: delete original audio file only
    try:
        src.unlink()
    except OSError:
        pass
    # 6) if album: if no audio files remain under album_root, remove album root (even if non-audio remains)
    if job.album_root is not None:
        remaining_audio = any(_is_audio(x) for x in job.album_root.rglob("*"))
        if not remaining_audio:
            try:
                shutil.rmtree(job.album_root)
            except OSError:
                pass
            # clear album lock when finished
            try:
                if album_lock.exists():
                    album_lock.unlink()
            except OSError:
                pass
    # 7) purge work dir
    try:
        shutil.rmtree(work)
    except OSError:
        pass

    # Structured processing log
    overall_elapsed = time.time() - overall_start
    
    log: Dict[str, Any] = {
        "event": "processed",
        "source": str(src),
        "output": str(dst),
        "artist": artist,
        "album": album,
        "title": title,
        "encoding": Config().MP3_ENCODING,
        "chunk_count": len(stems),
        "crossfade_ms": cfg.CROSSFADE_MS,
        "overlap_sec": cfg.CHUNK_OVERLAP_SEC,
        "model": cfg.MODEL,
        "demucs_device": cfg.DEMUCS_DEVICE,
        "demucs_jobs": cfg.DEMUCS_JOBS,
        "duration_sec": duration,
        "processing_time_sec": overall_elapsed,
        "timestamp": int(time.time()),
    }
    try:
        log_dir = Path(cfg.LOG_DIR)
        ensure_dir(log_dir)
        (log_dir / "simple_runner.jsonl").open("a").write(json.dumps(log) + "\n")
    except OSError:
        pass
    
    print(f"[simple] ============================================")
    print(f"[simple] COMPLETE in {overall_elapsed:.1f}s ({overall_elapsed/60:.1f} min)")
    print(f"[simple] Realtime ratio: {overall_elapsed/duration:.2f}x")
    print(f"[simple] Output: {dst}")
    print(f"[simple] ============================================")
    
    return True


def _pid_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Exists but not permitted; assume running
        return True
    return True


def _acquire_singleton_lock(lock_path: Path) -> Optional[int]:
    """Create a PID lock file. If lock exists and process is alive, return None.
    If stale, remove and acquire. Returns this process PID on success."""
    pid = os.getpid()
    host = socket.gethostname()
    try:
        # Attempt atomic create
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        with os.fdopen(fd, "w") as f:
            # Write hostname:pid to guard multi-container deployments
            f.write(f"{host}:{pid}")
        return pid
    except FileExistsError:
        try:
            content = (lock_path.read_text().strip() or "")
        except OSError:
            content = ""
        existing_pid = 0
        existing_host = ""
        if ":" in content:
            # New format hostname:pid
            parts = content.split(":", 1)
            existing_host = parts[0].strip()
            try:
                existing_pid = int(parts[1].strip())
            except (ValueError, IndexError):
                existing_pid = 0
        else:
            # Legacy numeric-only format
            try:
                existing_pid = int(content or "0")
            except ValueError:
                existing_pid = 0
        # If the lock is on another host, assume another instance is active
        if existing_host and existing_host != host:
            return None
        # If the existing PID matches our own (common with PID 1 reuse), treat as acquired
        if existing_pid == pid:
            return pid
        if existing_pid > 0 and _pid_is_running(existing_pid):
            return None
        # Stale lock; try to remove and acquire again
        try:
            lock_path.unlink()
        except OSError:
            pass
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            with os.fdopen(fd, "w") as f:
                f.write(f"{host}:{pid}")
            return pid
        except FileExistsError:
            return None


# Public test hook to allow unit tests to exercise lock parsing behavior
def acquire_singleton_lock_for_tests(lock_path: Path) -> Optional[int]:
    return _acquire_singleton_lock(lock_path)


def _cleanup_stale_working_dirs(working_dir: Path, max_age_seconds: int = 3600) -> int:
    """
    Clean up stale working directories on startup.
    
    This handles the case where the container is restarted mid-processing,
    leaving behind orphaned working directories that cause the UI to show
    lingering "processing" jobs.
    
    Returns the number of directories cleaned up.
    """
    if not working_dir.exists():
        return 0
    
    cleaned = 0
    now = time.time()
    
    for d in working_dir.iterdir():
        if not d.is_dir() or not d.name.startswith('simple_'):
            continue
        
        try:
            # Check the last modification time of any file in the directory
            all_files = list(d.rglob('*'))
            if not all_files:
                # Empty directory, remove it
                shutil.rmtree(d, ignore_errors=True)
                print(f"[simple] Cleaned up empty working dir: {d.name}")
                cleaned += 1
                continue
            
            latest_mtime = max(f.stat().st_mtime for f in all_files if f.is_file())
            age = now - latest_mtime
            
            if age > max_age_seconds:
                print(f"[simple] Cleaning up stale working dir (idle {int(age)}s): {d.name}")
                shutil.rmtree(d, ignore_errors=True)
                cleaned += 1
        except (OSError, ValueError) as e:
            print(f"[simple] Warning: could not check/clean {d.name}: {e}")
    
    return cleaned


def main(argv: Optional[List[str]] = None):
    cfg = Config()
    # loop once by default; if --daemon, keep processing
    args = sys.argv[1:] if argv is None else argv
    daemon = "--daemon" in args
    interval = 2
    state_dir = Path(cfg.DB_PATH).parent
    ensure_dir(state_dir)
    singleton_lock = state_dir / "simple_runner.pid"
    acquired_pid: Optional[int] = None
    try:
        if daemon:
            acquired_pid = _acquire_singleton_lock(singleton_lock)
            if acquired_pid is None:
                print("[simple] another instance appears to be running; exiting")
                return
            # Clean up any stale working directories from previous runs
            working_dir = Path(os.environ.get("WORKING", cfg.WORKING))
            stale_cleaned = _cleanup_stale_working_dirs(working_dir)
            if stale_cleaned > 0:
                print(f"[simple] Cleaned up {stale_cleaned} stale working director{'y' if stale_cleaned == 1 else 'ies'}")
        while True:
            progressed = process_one(cfg)
            if not daemon:
                break
            if not progressed:
                time.sleep(interval)
    finally:
        if acquired_pid is not None:
            try:
                if singleton_lock.exists():
                    singleton_lock.unlink()
            except OSError:
                pass


if __name__ == "__main__":
    main()
