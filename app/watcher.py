import json, time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from .config import Config
from .utils import advisory_lock, wait_until_stable, sha256_file
from .db import connect, enqueue_if_new, get_filename_count, set_filename_count, basename_statuses, get_first_job_path
from .overrides import load_sidecar, apply_overrides
import shutil, errno

LOCK_DIR = ".locks"
DEFERRED_FILE = ".deferred_duplicates.json"
ALBUM_MARKER = ".album_job"
ALBUM_LOCKED = ".album_locked"

# Simple in-process metrics; can be exported later.
METRICS = {
    'rename_second': 0,
    'archived': 0,
    'purged': 0,
    'deferred': 0,
}

def stemset_from_env(cfg: Config) -> str:
    return "".join([s.strip().upper() for s in cfg.STEMS])

def effective_job_config(cfg: Config, src: Path):
    base = {
        "model": cfg.MODEL,
        "stem_set": stemset_from_env(cfg),
        "sample_rate": cfg.SAMPLE_RATE,
        "bit_depth": cfg.BIT_DEPTH,
        "codec": cfg.CODEC,
        "target_lufs": cfg.TARGET_LUFS,
        "true_peak": cfg.TRUE_PEAK_DBFS,
        "dual_pass_loudnorm": cfg.DUAL_PASS_LOUDNORM,
    }
    if cfg.SIDECAR_ENABLED:
        side = load_sidecar(src)
        base = apply_overrides(base, side)
    return base

def _is_audio_file(p: Path, cfg: Config) -> bool:
    return p.is_file() and p.suffix.lower() in tuple(cfg.AUDIO_EXTS)

def parent_has_album_marker(p: Path) -> bool:
    for cur in [p] + list(p.parents):
        if (cur / ALBUM_MARKER).exists() or (cur / ALBUM_LOCKED).exists():
            return True
    return False

def _path_lock_id(p: Path) -> str:
    from hashlib import sha256 as _sha
    return _sha(str(p).encode()).hexdigest()[:16]

def is_queued_locked(lock_root: Path, p: Path) -> bool:
    lid = _path_lock_id(p)
    return (lock_root / f"{lid}.queued").exists()

def create_persistent_lock(lock_root: Path, p: Path):
    try:
        lock_root.mkdir(parents=True, exist_ok=True)
        (lock_root / f"{_path_lock_id(p)}.queued").write_text(str(p))
    except Exception:
        pass

def compute_album_signature(album_dir: Path, cfg: Config) -> str:
    # Stable signature based on relative paths + sizes + mtimes of audio files
    import hashlib
    h = hashlib.sha256()
    for f in sorted([q for q in album_dir.rglob('*') if _is_audio_file(q, cfg)], key=lambda x: str(x.relative_to(album_dir))):
        rel = str(f.relative_to(album_dir)).encode()
        try:
            st = f.stat()
            h.update(rel)
            h.update(str(st.st_size).encode())
            h.update(str(int(st.st_mtime)).encode())
        except FileNotFoundError:
            continue
    return h.hexdigest()

def handle_new_album(album_dir: Path, cfg: Config, db):
    # Only consider top-level directories directly inside INCOMING
    try:
        if not album_dir.is_dir():
            return
        if album_dir.parent != Path(cfg.INCOMING):
            return
        # Must contain at least one audio file
        has_audio = any(_is_audio_file(p, cfg) for p in album_dir.rglob('*'))
        if not has_audio:
            return
        # Compute signature before move
        sha = compute_album_signature(album_dir, cfg)
        eff = effective_job_config(cfg, album_dir)
        # Optionally stage album: move dir from INCOMING to STAGING
        staged_dir = album_dir
        if cfg.MOVE_TO_STAGING_ENABLED:
            staged_root = Path(cfg.STAGING)
            staged_root.mkdir(parents=True, exist_ok=True)
            staged_dir = staged_root / album_dir.name
            try:
                if staged_dir.exists():
                    shutil.rmtree(staged_dir)
                try:
                    album_dir.rename(staged_dir)
                except OSError as e:
                    if e.errno == errno.EXDEV or 'Invalid cross-device link' in str(e):
                        shutil.copytree(album_dir, staged_dir)
                        try:
                            shutil.rmtree(album_dir)
                        except Exception:
                            pass
                    else:
                        raise
            except Exception as e:
                print(f"[watcher] album staging move failed: {e}")
                return
        job = {
            "input_path": str(staged_dir),
            "input_sha256": sha,
            "model": eff["model"],
            "stem_set": eff["stem_set"],
            "sample_rate": eff["sample_rate"],
            "bit_depth": eff["bit_depth"],
            "codec": eff["codec"],
            "kind": "album",
        }
        enq = enqueue_if_new(db, job)
        if enq:
            try:
                (staged_dir / ALBUM_LOCKED).write_text("1")
            except Exception:
                pass
            print(f"[watcher] Enqueued album: {staged_dir.name} sha={sha[:10]} stems={eff['stem_set']} model={eff['model']}")
    except Exception as e:
        print(f"[watcher] album enqueue error: {e}")

def filename_exists(db, basename: str, include_errors: bool) -> bool:
    q = "SELECT 1 FROM jobs WHERE (substr(input_path, -length(?)) = ?)"
    if not include_errors:
        q += " AND status != 'error'"
    q += " LIMIT 1"
    cur = db.execute(q, (basename, basename))
    return cur.fetchone() is not None

def _unique_dest(dest: Path) -> Path:
    """Return a destination path that does not already exist by appending __N if needed (unbounded)."""
    if not dest.exists():
        return dest
    base = dest.stem
    suffix = dest.suffix
    i = 2
    while True:
        cand = dest.with_name(f"{base}__{i}{suffix}")
        if not cand.exists():
            return cand
        i += 1

def _safe_archive_move(src: Path, dest: Path) -> Path:
    """Attempt fast rename; on cross-device (EXDEV) fall back to copy+unlink. Ensure unique dest."""
    dest = _unique_dest(dest)
    # Ensure destination directory exists for initial rename attempt to avoid ENOENT
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        src.rename(dest)
        return dest
    except OSError as e:
        if e.errno == errno.EXDEV or 'Invalid cross-device link' in str(e):
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            try:
                src.unlink()
            except Exception:
                pass
            return dest
        raise

def handle_new_file(path: Path, cfg: Config, db):
    lock_root = Path(cfg.INCOMING) / LOCK_DIR
    if is_queued_locked(lock_root, path):
        return
    if cfg.ALBUMS_ENABLED and parent_has_album_marker(path):
        # File belongs to an album job; skip individual enqueue.
        return
    if path.suffix.lower() not in tuple(cfg.AUDIO_EXTS):
        return
    try:
        if path.stat().st_size < cfg.MIN_INPUT_BYTES:
            # too small, likely placeholder or incomplete; skip silently
            return
    except FileNotFoundError:
        return
    if not wait_until_stable(path, cfg.STABILITY_PASSES, cfg.STABILITY_CHECK_SECONDS):
        return
    incremented_pre_enqueue = False
    if cfg.DEDUPE_BY_FILENAME:
        base_original = path.name
        try:
            count = get_filename_count(db, base_original)
            statuses = basename_statuses(db, base_original)
            active_present = any(s in ("queued","running") for s in statuses)
            # Third or more occurrence logic
            if count >= 2:
                if active_present:
                    METRICS['deferred'] += 1
                    print(f"[watcher] Duplicate (>=3rd) deferred until original completes: {base_original}")
                    return
                action = cfg.DEDUPE_CLEANUP_METHOD
                # Increment count bookkeeping even if we archive/purge so future duplicates still treated as >=3rd
                try:
                    set_filename_count(db, base_original, count + 1)
                    incremented_pre_enqueue = True
                except Exception:
                    pass
                if action == 'archive':
                    rel = path.relative_to(cfg.INCOMING) if str(path).startswith(cfg.INCOMING) else Path(base_original)
                    dest = Path(cfg.ARCHIVE_DIR) / rel
                    try:
                        before = dest
                        final_dest = _safe_archive_move(path, dest)
                        if final_dest != before:
                            print(f"[watcher][debug] Archive unique suffix applied: {before.name} -> {final_dest.name}")
                        METRICS['archived'] += 1
                        print(f"[watcher] Filename dedupe archived (>=3rd): {base_original} -> {final_dest}")
                    except Exception as e:
                        print(f"[watcher] Archive failed for {base_original}: {e}")
                elif action == 'purge':
                    try:
                        path.unlink()
                        METRICS['purged'] += 1
                        print(f"[watcher] Filename dedupe purged (>=3rd): {base_original}")
                    except Exception as e:
                        print(f"[watcher] Purge failed for {base_original}: {e}")
                else:
                    print(f"[watcher] Filename dedupe skipped (>=3rd): {base_original}")
                return
            # Second occurrence rename
            elif count == 1 and cfg.DEDUPE_RENAME_SECOND:
                if active_present:
                    METRICS['deferred'] += 1
                    print(f"[watcher] Second occurrence deferred (active processing): {base_original}")
                    return
                first_path = get_first_job_path(db, base_original)
                if first_path and Path(first_path) == path:
                    print(f"[watcher] Detected original file (no rename): {base_original}")
                else:
                    new_name = path.with_name(f"{path.stem} (2){path.suffix}")
                    try:
                        if new_name.exists():
                            i = 2
                            while True:
                                i += 1
                                candidate = path.with_name(f"{path.stem} ({i}){path.suffix}")
                                if not candidate.exists():
                                    new_name = candidate
                                    break
                        path.rename(new_name)
                        path = new_name
                        METRICS['rename_second'] += 1
                        print(f"[watcher] Renamed duplicate to: {path.name}")
                    except Exception as e:
                        print(f"[watcher] Failed to rename duplicate ({e}); skipping")
                        return
                # Update count for second occurrence pre-enqueue so third detection works even if not enqueued
                try:
                    set_filename_count(db, base_original, count + 1)
                    incremented_pre_enqueue = True
                except Exception:
                    pass
        except Exception:
            pass
    try:
        with advisory_lock(lock_root, path):
            sha = sha256_file(path)
            eff = effective_job_config(cfg, path)
            # Optionally stage file: move from INCOMING to STAGING (preserve relative path)
            if cfg.MOVE_TO_STAGING_ENABLED:
                staged_root = Path(cfg.STAGING)
                staged_root.mkdir(parents=True, exist_ok=True)
                if str(path).startswith(cfg.INCOMING):
                    rel = path.relative_to(cfg.INCOMING)
                    dest = staged_root / rel
                else:
                    dest = staged_root / path.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                try:
                    path.rename(dest)
                except OSError as e:
                    if e.errno == errno.EXDEV or 'Invalid cross-device link' in str(e):
                        shutil.copy2(path, dest)
                        try:
                            path.unlink()
                        except Exception:
                            pass
                    else:
                        raise
                path = dest
            job = {
                "input_path": str(path),
                "input_sha256": sha,
                "model": eff["model"],
                "stem_set": eff["stem_set"],
                "sample_rate": eff["sample_rate"],
                "bit_depth": eff["bit_depth"],
                "codec": eff["codec"],
            }
            enq = enqueue_if_new(db, job)
            if enq:
                if cfg.DEDUPE_BY_FILENAME and not incremented_pre_enqueue:
                    # Determine canonical basename (strip ' (n)' suffix if present)
                    original_base = path.name
                    import re as _re
                    m = _re.match(r"^(.*) \((\d+)\)(\.[^.]+)?$", original_base)
                    if m:
                        original_base = (m.group(1) + (m.group(3) or ""))
                    try:
                        cprev = get_filename_count(db, original_base)
                        set_filename_count(db, original_base, (cprev + 1) if cprev else 1)
                    except Exception:
                        pass
                print(f"[watcher] Enqueued: {path.name} sha={sha[:10]} stems={eff['stem_set']} model={eff['model']}")
            else:
                print(f"[watcher] Duplicate ignored: {path.name}")
    except RuntimeError:
        pass

class Handler(FileSystemEventHandler):
    """Handler opens a short‑lived SQLite connection per event to avoid cross-thread use."""
    def __init__(self, cfg: Config, db_path: str):
        self.cfg = cfg
        self.db_path = db_path

    def _process(self, path: Path):
        # Ignore events under STAGING when staging enabled
        try:
            if self.cfg.MOVE_TO_STAGING_ENABLED and str(path).startswith(self.cfg.STAGING):
                return
        except Exception:
            pass
        conn = connect(self.db_path)
        try:
            handle_new_file(path, self.cfg, conn)
        finally:
            try: conn.close()
            except Exception: pass

    def on_created(self, event):
        p = Path(event.src_path)
        if self.cfg.MOVE_TO_STAGING_ENABLED and str(p).startswith(self.cfg.STAGING):
            return
        if event.is_directory:
            if self.cfg.ALBUMS_ENABLED and p.parent == Path(self.cfg.INCOMING):
                conn = connect(self.db_path)
                try:
                    handle_new_album(p, self.cfg, conn)
                finally:
                    try: conn.close()
                    except Exception: pass
            return
        self._process(p)

    def on_moved(self, event):
        p = Path(event.dest_path)
        if self.cfg.MOVE_TO_STAGING_ENABLED and str(p).startswith(self.cfg.STAGING):
            return
        if event.is_directory:
            if self.cfg.ALBUMS_ENABLED and p.parent == Path(self.cfg.INCOMING):
                conn = connect(self.db_path)
                try:
                    handle_new_album(p, self.cfg, conn)
                finally:
                    try: conn.close()
                    except Exception: pass
            return
        self._process(p)

def main():
    cfg = Config()
    Path(cfg.INCOMING).mkdir(parents=True, exist_ok=True)
    if cfg.MOVE_TO_STAGING_ENABLED:
        Path(cfg.STAGING).mkdir(parents=True, exist_ok=True)
    # Use a single connection for initial sweep (not threaded), then per-event connections.
    init_conn = connect(cfg.DB_PATH)
    # Initial sweep: first enqueue albums for top-level directories, then files not under album
    if cfg.ALBUMS_ENABLED:
        for p in Path(cfg.INCOMING).iterdir():
            if p.is_dir():
                handle_new_album(p, cfg, init_conn)
    for p in Path(cfg.INCOMING).rglob("*"):
        if cfg.MOVE_TO_STAGING_ENABLED and str(p).startswith(cfg.STAGING):
            continue
        if p.is_file():
            handle_new_file(p, cfg, init_conn)
    init_conn.close()

    obs = Observer()
    # Recursive observer so files created inside newly added subdirectories are detected
    obs.schedule(Handler(cfg, cfg.DB_PATH), cfg.INCOMING, recursive=True)
    obs.start()
    print(f"[watcher] running (dedupe_by_filename={cfg.DEDUPE_BY_FILENAME} rename_second={cfg.DEDUPE_RENAME_SECOND} cleanup={cfg.DEDUPE_CLEANUP_METHOD} fast_fs={cfg.FAST_FS_STABILITY})")
    next_rescan = time.time() + cfg.RESCAN_INTERVAL_SEC
    deferred_path = Path(cfg.INCOMING) / DEFERRED_FILE
    # Load deferred list if any (each entry is full path string)
    try:
        if deferred_path.exists():
            import json as _json
            deferred = set(_json.loads(deferred_path.read_text()))
        else:
            deferred = set()
    except Exception:
        deferred = set()
    try:
        while True:
            time.sleep(1)
            if cfg.RESCAN_INTERVAL_SEC > 0 and time.time() >= next_rescan:
                try:
                    conn = connect(cfg.DB_PATH)
                    scanned = 0
                    for p in Path(cfg.INCOMING).rglob("*"):
                        if cfg.MOVE_TO_STAGING_ENABLED and str(p).startswith(cfg.STAGING):
                            continue
                        if p.is_file():
                            handle_new_file(p, cfg, conn)
                            scanned += 1
                    # Retry deferred duplicates whose originals may now be done
                    still_deferred = set()
                    for f in list(deferred):
                        fp = Path(f)
                        if not fp.exists():
                            continue
                        # Re-run handle_new_file (it will enqueue or keep deferring)
                        handle_new_file(fp, cfg, conn)
                        # If still active job prevents, it will print defer message again; keep it
                        # We detect this by checking if job not enqueued and file still same name
                        # Simplicity: always keep for one more cycle, will naturally drop once renamed/archived
                        still_deferred.add(f)
                    deferred = still_deferred
                    # Persist deferred set
                    try:
                        import json as _json
                        deferred_path.write_text(_json.dumps(sorted(list(deferred))))
                    except Exception:
                        pass
                    conn.close()
                    print(f"[watcher] periodic rescan complete (files walked: {scanned})")
                except Exception as e:
                    print(f"[watcher] periodic rescan error: {e}")
                finally:
                    next_rescan = time.time() + cfg.RESCAN_INTERVAL_SEC
    except KeyboardInterrupt:
        obs.stop()
    obs.join()

if __name__ == "__main__":
    main()
