import json, time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List
from .utils import run_cmd, ensure_dir
from .config import Config

STEM_KEYS = ["vocals","drums","bass","other"]
CODE_MAP = {"V":"vocals","D":"drums","B":"bass","O":"other"}

class OOMError(RuntimeError): pass

def is_oom(returncode: int, stderr: str) -> bool:
    if returncode in (137, 9): return True
    s = (stderr or "").lower()
    for n in ["out of memory","cuda out of memory","killed","oom"]:
        if n in s: return True
    return False

def ffprobe_duration(path: Path, cfg: Config=None) -> float:
    p = run_cmd(["ffprobe","-v","error","-show_entries","format=duration",
                 "-of","json",str(path)], capture=True, cfg=cfg)
    if p.returncode!=0: raise RuntimeError(p.stderr)
    j = json.loads(p.stdout)
    return float(j["format"]["duration"])

def extract_chunk(src: Path, dst: Path, start: float, dur: float, sr: int, cfg: Config):
    ensure_dir(dst.parent)
    cmd = ["ffmpeg","-y","-ss",f"{start:.3f}","-t",f"{dur:.3f}",
           "-i",str(src),"-c:a","pcm_s16le","-ar",str(sr)]
    if cfg and cfg.FFMPEG_THREADS and cfg.FFMPEG_THREADS>0:
        cmd += ["-threads", str(cfg.FFMPEG_THREADS)]
    cmd += [str(dst)]
    p = run_cmd(cmd, capture=True, cfg=cfg)
    if p.returncode != 0: raise RuntimeError(p.stderr)

def acrossfade_two(a: Path, b: Path, out: Path, crossfade_s: float, cfg: Config):
    ensure_dir(out.parent)
    cmd = ["ffmpeg","-y","-i",str(a),"-i",str(b),
           "-filter_complex",f"acrossfade=d={crossfade_s:.3f}"]
    if cfg and cfg.FFMPEG_THREADS and cfg.FFMPEG_THREADS>0:
        cmd += ["-threads", str(cfg.FFMPEG_THREADS)]
    cmd += [str(out)]
    p = run_cmd(cmd, capture=True, cfg=cfg)
    if p.returncode != 0: raise RuntimeError(p.stderr)

def concat_with_crossfades(parts: List[Path], out: Path, crossfade_ms: int, cfg: Config):
    if len(parts)==1:
        cmd = ["ffmpeg","-y","-i",str(parts[0]),"-c","copy"]
        if cfg and cfg.FFMPEG_THREADS and cfg.FFMPEG_THREADS>0:
            cmd += ["-threads", str(cfg.FFMPEG_THREADS)]
        run_cmd(cmd + [str(out)], capture=True, check=True, cfg=cfg)
        return
    temp = parts[0]
    cf_s = crossfade_ms/1000.0
    for i in range(1,len(parts)):
        nxt = parts[i]
        tmpout = out.parent / f"_xf_{i}.wav"
        acrossfade_two(temp, nxt, tmpout, cf_s, cfg)
        temp = tmpout
    temp.rename(out)

def run_demucs_once(input_path: Path, out_dir: Path, model: str, cfg: Config):
    ensure_dir(out_dir)
    cmd = ["demucs","-n",model,"-o",str(out_dir),str(input_path)]
    p = run_cmd(cmd, capture=True, cfg=cfg)
    if is_oom(p.returncode, p.stderr or p.stdout):
        raise OOMError(f"Demucs OOM: {p.stderr or p.stdout}")
    if p.returncode != 0:
        raise RuntimeError(f"Demucs failed: {p.stderr or p.stdout}")
    # demucs writes banded subdir; find it
    # pattern: {out_dir}/{model}/{basename}/
    base = input_path.stem
    model_dir = out_dir / model
    # find first subdir containing stems
    stem_root = None
    if model_dir.exists():
        for d in model_dir.iterdir():
            if d.is_dir() and (d/"vocals.wav").exists():
                stem_root = d; break
            if d.is_dir() and (d/"drums.wav").exists():
                stem_root = d; break
    if stem_root is None:
        # fallback: search
        for d in out_dir.rglob("vocals.wav"):
            stem_root = d.parent; break
    if stem_root is None:
        raise RuntimeError("Cannot locate Demucs stem outputs")
    return stem_root

def split_plan(duration: float, n: int, overlap: float):
    # returns list of (start, dur, head_trim, tail_trim)
    base = duration / n
    plan = []
    for i in range(n):
        start = max(0.0, i*base - (overlap if i>0 else 0.0))
        end = min(duration, (i+1)*base + (overlap if i<n-1 else 0.0))
        dur = max(0.001, end - start)
        head_trim = overlap if i>0 else 0.0
        tail_trim = overlap if i<n-1 else 0.0
        plan.append((start, dur, head_trim, tail_trim))
    return plan

def trim_overlap(src: Path, dst: Path, head: float, tail: float, cfg: Config):
    # trim head and tail seconds
    if head==0 and tail==0:
        cmd = ["ffmpeg","-y","-i",str(src),"-c","copy"]
        if cfg and cfg.FFMPEG_THREADS and cfg.FFMPEG_THREADS>0:
            cmd += ["-threads", str(cfg.FFMPEG_THREADS)]
        run_cmd(cmd + [str(dst)], capture=True, check=True, cfg=cfg)
        return
    # get full duration
    dur = ffprobe_duration(src, cfg)
    start = head
    length = max(0.001, dur - head - tail)
    cmd = ["ffmpeg","-y","-ss",f"{start:.3f}","-t",f"{length:.3f}",
           "-i",str(src),"-c","copy"]
    if cfg and cfg.FFMPEG_THREADS and cfg.FFMPEG_THREADS>0:
        cmd += ["-threads", str(cfg.FFMPEG_THREADS)]
    cmd += [str(dst)]
    p = run_cmd(cmd, capture=True, cfg=cfg)
    if p.returncode != 0: raise RuntimeError(p.stderr)

def run_demucs_with_adaptive_chunking(in_path: Path, workdir: Path, model: str, cfg: Config):
    # try whole file first
    try:
        return run_demucs_once(in_path, workdir / "full", model, cfg)
    except OOMError:
        if not cfg.CHUNKING_ENABLED:
            raise

    duration = ffprobe_duration(in_path, cfg)
    n = 2
    while n <= cfg.CHUNK_MAX:
        try:
            cdir = workdir / f"chunks_{n}"
            stems_collected = {k: [] for k in STEM_KEYS}
            plan = split_plan(duration, n, cfg.CHUNK_OVERLAP_SEC)
            # 1) extract chunks
            chunk_paths = []
            for i,(start,dur,_,_) in enumerate(plan):
                cpath = cdir / f"chunk_{i}.wav"
                extract_chunk(in_path, cpath, start, dur, cfg.SAMPLE_RATE, cfg)
                chunk_paths.append(cpath)

            # 2) demucs per chunk
            for i, cpath in enumerate(chunk_paths):
                sroot = run_demucs_once(cpath, cdir / f"demucs_{i}", model, cfg)
                for sk in STEM_KEYS:
                    sfile = sroot / f"{sk}.wav"
                    if sfile.exists():
                        stems_collected[sk].append((sfile, plan[i]))
            # 3) per-stem stitch with trimming overlaps + crossfade
            stitched = {}
            outstemdir = workdir / f"stitched_{n}"
            ensure_dir(outstemdir)
            for sk, parts in stems_collected.items():
                if not parts:
                    continue
                trimmed_parts = []
                for (filep,(start,dur,head,tail)) in parts:
                    tp = outstemdir / f"{sk}_trim_{filep.stem}.wav"
                    trim_overlap(filep, tp, head, tail, cfg)
                    trimmed_parts.append(tp)
                final = outstemdir / f"{sk}.wav"
                concat_with_crossfades(trimmed_parts, final, cfg.CROSSFADE_MS, cfg)
                stitched[sk] = final
            # require at least drums/bass/other
            if not stitched:
                raise RuntimeError("No stems stitched")
            return outstemdir
        except OOMError:
            time.sleep(cfg.RETRY_BACKOFF_SEC)
            n *= 2
    raise RuntimeError(f"OOM persisted up to {cfg.CHUNK_MAX} chunks")

def mix_selected_stems(stem_dir: Path, keep_codes: List[str],
                       tmp_wav: Path, cfg: Config):
    keep_files = []
    for code in keep_codes:
        sk = CODE_MAP[code]
        f = stem_dir / f"{sk}.wav"
        if f.exists(): keep_files.append(f)
    if not keep_files:
        raise RuntimeError("No stems selected or stems missing.")
    # first pass loudnorm measure (concat stems then loudnorm 2-pass)
    # We’ll amix stems, then loudnorm in 2-pass if requested
    inputs = []
    for f in keep_files: inputs += ["-i", str(f)]
    n = len(keep_files)
    # pure amix to PCM
    cmd = ["ffmpeg","-y", *inputs,
           "-filter_complex", f"amix=inputs={n}:normalize=0",
           "-c:a","pcm_s16le"]
    if cfg and cfg.FFMPEG_THREADS and cfg.FFMPEG_THREADS>0:
        cmd += ["-threads", str(cfg.FFMPEG_THREADS)]
    cmd += [str(tmp_wav)]
    p = run_cmd(cmd, capture=True, cfg=cfg)
    if p.returncode != 0: raise RuntimeError(p.stderr or p.stdout)

def loudnorm_two_pass(in_wav: Path, out_wav: Path, cfg: Config):
    # measure
    cmd1 = ["ffmpeg","-y","-i",str(in_wav),
            "-filter_complex",f"loudnorm=I={cfg.TARGET_LUFS}:TP={cfg.TRUE_PEAK_DBFS}:LRA=11:print_format=json",
            "-f","null","-"]
    if cfg and cfg.FFMPEG_THREADS and cfg.FFMPEG_THREADS>0:
        cmd1 = [*cmd1[:-2], "-threads", str(cfg.FFMPEG_THREADS), *cmd1[-2:]]
    p1 = run_cmd(cmd1, capture=True, cfg=cfg)
    if p1.returncode != 0: raise RuntimeError(p1.stderr or p1.stdout)
    # parse last JSON in stderr/stdout
    txt = (p1.stderr or p1.stdout or "")

    def extract_last_json(s: str):
        last_open = s.rfind('{')
        if last_open == -1:
            return {}
        # attempt brace-balanced extraction
        depth = 0
        for i, ch in enumerate(s[last_open:]):
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    block = s[last_open:last_open + i + 1]
                    try:
                        return json.loads(block)
                    except json.JSONDecodeError:
                        return {}
        return {}

    params = extract_last_json(txt)

    needed = {"measured_I","measured_LRA","measured_TP","measured_thresh","offset"}
    if params and needed.issubset(params.keys()):
        flt = ("loudnorm=I={I}:TP={TP}:LRA=11:"
               "measured_I={measured_I}:measured_LRA={measured_LRA}:"
               "measured_TP={measured_TP}:measured_thresh={measured_thresh}:"
               "offset={offset}:linear=true:print_format=summary").format(
                   I=cfg.TARGET_LUFS, TP=cfg.TRUE_PEAK_DBFS, **params)
    else:
        # Fallback: single-pass loudnorm without measured params
        flt = f"loudnorm=I={cfg.TARGET_LUFS}:TP={cfg.TRUE_PEAK_DBFS}:LRA=11:print_format=summary"

    cmd2 = ["ffmpeg","-y","-i",str(in_wav),
            "-filter_complex", flt, "-c:a","pcm_s16le","-ar",str(cfg.SAMPLE_RATE)]
    if cfg and cfg.FFMPEG_THREADS and cfg.FFMPEG_THREADS>0:
        cmd2 += ["-threads", str(cfg.FFMPEG_THREADS)]
    cmd2 += [str(out_wav)]
    p2 = run_cmd(cmd2, capture=True, cfg=cfg)
    if p2.returncode != 0:
        raise RuntimeError(p2.stderr or p2.stdout)
