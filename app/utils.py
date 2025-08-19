import hashlib, json, os, shutil, subprocess, time
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Optional

from .config import Config
import sys

def sha256_file(path: Path, bufsize: int = 1024*1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(bufsize)
            if not b: break
            h.update(b)
    return h.hexdigest()

@contextmanager
def advisory_lock(lock_dir: Path, target: Path):
    lock_dir.mkdir(parents=True, exist_ok=True)
    lp = lock_dir / (target.name + ".lock")
    if lp.exists():  # simple non-blocking
        raise RuntimeError(f"Lock exists for {target.name}")
    lp.write_text(str(os.getpid()))
    try:
        yield
    finally:
        try: lp.unlink(missing_ok=True)
        except: pass

def wait_until_stable(path: Path, passes: int, delay: int) -> bool:
    prev = -1
    for _ in range(passes):
        size = path.stat().st_size
        if size == prev:  # stable across consecutive checks
            return True
        prev = size
        time.sleep(delay)
    # One more final check
    size = path.stat().st_size
    return size == prev

def _with_cpu_env(cfg: Optional[Config], extra_env: Optional[Dict[str,str]]=None) -> Dict[str,str]:
    env = os.environ.copy()
    if cfg is None:
        if extra_env:
            env.update(extra_env)
        return env
    # Limit thread-hungry libs
    if cfg.CPU_MAX_THREADS and cfg.CPU_MAX_THREADS > 0:
        for k in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS","BLIS_NUM_THREADS"):
            env[k] = str(cfg.CPU_MAX_THREADS)
    # FFmpeg threads handled via -threads flag, but also set env for libraries
    if extra_env:
        env.update(extra_env)
    return env

def _maybe_prefix_with_nice_and_taskset(cmd: List[str], cfg: Optional[Config]) -> List[str]:
    if cfg is None:
        return cmd
    pref: List[str] = []
    if cfg.CPU_NICE and cfg.CPU_NICE != 0:
        pref += ["nice","-n", str(cfg.CPU_NICE)]
    if cfg.CPU_AFFINITY:
        pref += ["taskset","-c", cfg.CPU_AFFINITY]
    return pref + cmd

def run_cmd(cmd, cwd=None, capture=True, check=False, env=None, timeout=None, cfg: Optional[Config]=None):
    # Apply optional nice/taskset and env limits
    full_cmd = _maybe_prefix_with_nice_and_taskset(list(cmd), cfg)
    env2 = _with_cpu_env(cfg, env)
    p = subprocess.run(
        full_cmd, cwd=cwd, env=env2,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        text=True, timeout=timeout
    )
    if check and p.returncode != 0:
        raise subprocess.CalledProcessError(p.returncode, cmd, p.stdout, p.stderr)
    return p

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def write_json(p: Path, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2))

def sanitize_filename(s: str) -> str:
    # Preserve original names on POSIX; only strip path separators and NULs
    if os.name == "posix":
        cleaned = s.replace("/", "").replace("\x00", "").strip()
        return cleaned or "untitled"
    # On Windows, keep conservative removal list
    cleaned = "".join(c for c in s if c not in '\\/:*?"<>|').strip()
    return cleaned or "untitled"

def safe_move_file(src: Path, dest: Path):
    """Rename with cross-device fallback copy+unlink for files."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        src.rename(dest)
        return
    except OSError as e:
        if getattr(e, "errno", None) == 18 or "Invalid cross-device link" in str(e):
            shutil.copy2(src, dest)
            try:
                src.unlink()
            except Exception:
                pass
            return
        raise

def copytree(src: Path, dst: Path):
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
