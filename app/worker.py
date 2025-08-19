import json, time
from pathlib import Path
from typing import Dict, List, Tuple
from .config import Config
from .db import connect, next_queued, mark_running, mark_done, mark_error, acquire_lock, release_lock
from .utils import ensure_dir, sanitize_filename, write_json
from .metadata import copy_tags_and_artwork, read_basic_tags, find_album_art_in_dir, extract_first_embedded_art
from .audio import (run_demucs_with_adaptive_chunking, mix_selected_stems, loudnorm_two_pass, OOMError)
from .overrides import load_sidecar, apply_overrides

def compose_output_name(tags: Dict, stem_set: str, model: str, sr: int, bitdepth: int, codec: str, src: Path) -> str:
    # Determine artist/title first, then sanitize to avoid default 'untitled' preventing fallback
    raw_artist = (tags.get("artist", "") or "").strip()
    raw_title = (tags.get("title", "") or "").strip()
    if not raw_title:
        raw_title = src.stem
    artist = sanitize_filename(raw_artist)
    title = sanitize_filename(raw_title)
    base = f"{artist} - {title}".strip(" -")
    suffix = f"[INST_{stem_set}__model-{model}__sr-{sr}__bit-{bitdepth}].{codec}"
    return f"{base} {suffix}"

def compose_structured_output_path(cfg: Config, tags: Dict, filename: str) -> Path:
    artist = sanitize_filename(tags.get("artist","Unknown")).strip() or "Unknown"
    album  = sanitize_filename(tags.get("album","Unknown")).strip() or "Unknown"
    return Path(cfg.OUTPUT) / artist / album / filename

def _gather_album_tracks(album_dir: Path, cfg: Config) -> List[Path]:
    files: List[Path] = []
    for p in album_dir.rglob("*"):
        if p.is_file() and p.suffix.lower() in tuple(cfg.AUDIO_EXTS):
            files.append(p)
    files.sort(key=lambda x: str(x))
    return files

def _process_single_file(in_path: Path, workdir: Path, eff: Dict, cfg: Config, cover_art: Path|None=None) -> Tuple[str, Dict]:
    keep_codes = list(eff["stem_set"])

    notes = {}
    stems_root = run_demucs_with_adaptive_chunking(in_path, workdir, eff["model"], cfg)
    notes["oom_recovered"] = stems_root.name.startswith("stitched_")
    if notes["oom_recovered"]:
        try:
            notes["chunking"] = {"num_chunks": int(stems_root.name.split("_")[-1])}
        except Exception:
            pass

    tmp_mix = workdir / "mix.wav"
    mix_selected_stems(stems_root, keep_codes, tmp_mix, cfg)

    norm_wav = workdir / "mix_norm.wav"
    loudnorm_two_pass(tmp_mix, norm_wav, cfg)

    tags = read_basic_tags(in_path)
    out_name = compose_output_name(tags, eff["stem_set"], eff["model"], eff["sample_rate"], eff["bit_depth"], eff["codec"], in_path)
    if cfg.STRUCTURED_OUTPUT_SINGLES:
        out_path = compose_structured_output_path(cfg, tags, out_name)
    else:
        out_path = Path(cfg.OUTPUT) / out_name
    copy_tags_and_artwork(in_path, norm_wav, out_path, eff["codec"], eff["sample_rate"], eff["bit_depth"], cfg, cover_art=cover_art)
    return str(out_path), {"input": str(in_path), "output": str(out_path), "tags": tags, "notes": notes}

def process_job(job: Dict, cfg: Config):
    in_path = Path(job["input_path"])
    workdir = Path(cfg.WORKING) / f"job_{job['id']}"
    ensure_dir(workdir)

    # Build effective per-job config (re-apply sidecar in case it changed after enqueue)
    eff = {
        "model": job["model"],
        "stem_set": job["stem_set"],
        "sample_rate": job["sample_rate"],
        "bit_depth": job["bit_depth"],
        "codec": job["codec"],
        "target_lufs": cfg.TARGET_LUFS,
        "true_peak": cfg.TRUE_PEAK_DBFS,
        "dual_pass_loudnorm": cfg.DUAL_PASS_LOUDNORM,
    }
    if cfg.SIDECAR_ENABLED:
        side = load_sidecar(in_path)
        eff = apply_overrides(eff, side)

    # Album job (directory): process all tracks sequentially and write album manifest
    if in_path.is_dir():
        tracks = _gather_album_tracks(in_path, cfg)
        if not tracks:
            raise RuntimeError("Album contains no audio files")
        # Determine cover art: from folder or extract from first track with embedded art
        cover = find_album_art_in_dir(in_path)
        if not cover:
            for t in tracks:
                extracted = extract_first_embedded_art(t, workdir / "album_cover.jpg", cfg)
                if extracted:
                    cover = extracted
                    break
        album_manifest = {
            "album_dir": str(in_path),
            "model": eff["model"],
            "stem_set": eff["stem_set"],
            "sample_rate": eff["sample_rate"],
            "bit_depth": eff["bit_depth"],
            "codec": eff["codec"],
            "tracks": []
        }
        mpath = workdir / "manifest.json"
        write_json(mpath, album_manifest)
        last_out = None
        for idx, track in enumerate(tracks, start=1):
            twork = workdir / f"track_{idx}"
            ensure_dir(twork)
            outp, tentry = _process_single_file(track, twork, eff, cfg, cover_art=cover)
            album_manifest["tracks"].append(tentry)
            last_out = outp
            # Incremental manifest update
            write_json(mpath, album_manifest)
        # Return last output as job output_path for DB, manifest path points to album manifest
        return last_out, str(mpath), {"album": True, "num_tracks": len(tracks), "album_cover": str(cover) if cover else None}

    # Single-file job
    outp, tentry = _process_single_file(in_path, workdir, eff, cfg)
    manifest = {
        "input": tentry["input"],
        "output": tentry["output"],
        "model": eff["model"],
        "stem_set": eff["stem_set"],
        "sample_rate": eff["sample_rate"],
        "bit_depth": eff["bit_depth"],
        "codec": eff["codec"],
        "notes": tentry.get("notes", {}),
        "timestamps": {"finished": time.time()}
    }
    mpath = workdir / "manifest.json"
    write_json(mpath, manifest)
    return str(outp), str(mpath), tentry.get("notes", {})

def main():
    cfg = Config()
    Path(cfg.OUTPUT).mkdir(parents=True, exist_ok=True)
    db = connect(cfg.DB_PATH)
    print("[worker] running")
    while True:
        job = next_queued(db)
        if not job:
            time.sleep(1)
            continue
        mark_running(db, job["id"])  # tentatively claim the job
        lock_acquired = False
        lock_key = "album_busy"
        if job.get("kind") == "album":
            # Ensure exclusive album processing across multiple workers
            lock_acquired = acquire_lock(db, lock_key, f"job_{job['id']}")
            if not lock_acquired:
                # Could not acquire exclusivity; put job back to queue and retry later
                with db:
                    db.execute("UPDATE jobs SET status='queued', started_at=NULL WHERE id=?", (job["id"],))
                time.sleep(1)
                continue
        try:
            outp, mpath, notes = process_job(job, cfg)
            mark_done(db, job["id"], outp, mpath, notes)
            print(f"[worker] done #{job['id']} → {outp}")
        except Exception as e:
            mark_error(db, job["id"], repr(e), {"trace": str(e)})
            print(f"[worker] error #{job['id']}: {e}")
            time.sleep(1)
        finally:
            # Release global album lock
            if lock_acquired:
                try:
                    release_lock(db, lock_key)
                except Exception:
                    pass
            # Remove persistent on-disk queue locks/markers
            try:
                in_path = Path(job.get("input_path", ""))
                incoming_root = Path(cfg.INCOMING)
                staging_root = Path(cfg.STAGING)
                if in_path.is_dir():
                    # Remove album locked marker
                    alp = in_path / ".album_locked"
                    if alp.exists():
                        alp.unlink()
                    # Optionally remove staged album dir if desired (leave for auditing otherwise)
                    # shutil.rmtree(in_path)
                else:
                    # Remove file queued lock marker
                    from hashlib import sha256 as _sha
                    lid = _sha(str(in_path).encode()).hexdigest()[:16]
                    lp = incoming_root / ".locks" / f"{lid}.queued"
                    if lp.exists():
                        lp.unlink()
                    # Optionally remove staged file
                    # if in_path.parent == staging_root:
                    #     in_path.unlink(missing_ok=True)
            except Exception:
                pass

if __name__ == "__main__":
    main()
