from pathlib import Path
from typing import Dict, Optional, List
from mutagen._file import File as MutFile  # type: ignore[attr-defined]
import subprocess
from .config import Config

ALBUM_ART_CANDIDATES = [
    "cover.jpg","cover.jpeg","cover.png","folder.jpg","folder.png",
    "front.jpg","front.png","album.jpg","album.png"
]

def find_album_art_in_dir(dir_path: Path) -> Path | None:
    for name in ALBUM_ART_CANDIDATES:
        p = dir_path / name
        if p.exists() and p.is_file():
            return p
    # fallback to any jpg/png
    for p in dir_path.iterdir():
        if p.suffix.lower() in (".jpg",".jpeg",".png"):
            return p
    return None

def extract_first_embedded_art(src_audio: Path, out_img: Path) -> Path | None:
    # Try ffmpeg to extract first attached picture
    out_img.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg","-y","-i",str(src_audio),"-an","-vcodec","copy","-map","0:v:0", str(out_img)]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if p.returncode == 0 and out_img.exists() and out_img.stat().st_size>0:
        return out_img
    try:
        if out_img.exists():
            out_img.unlink()
    except OSError:
        pass
    return None

def copy_tags_and_artwork(src_in: Path, rendered_wav: Path, out_path: Path,
                 codec: str, sr: int, bit_depth: int, cfg: Optional[Config] = None,
                 cover_art: Optional[Path] = None):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Build base ffmpeg command with optional cover art
    map_args = ["-map","0:a:0","-map_metadata","1:0"]
    inputs = ["-i", str(rendered_wav), "-i", str(src_in)]
    # If external cover art provided, add as third input and mapping
    if cover_art and Path(cover_art).exists():
        inputs += ["-i", str(cover_art)]
        map_args += ["-map","2:0","-id3v2_version","3","-metadata:s:v","title=Album cover","-metadata:s:v","comment=Cover (front)"]
    if codec.lower() == "flac":
        cmd = ["ffmpeg","-y", *inputs, *map_args,
               "-c:a","flac","-sample_fmt",f"s{bit_depth}","-ar",str(sr)]
    elif codec.lower() == "wav":
        cmd = ["ffmpeg","-y", *inputs, *map_args,
               "-c:a","pcm_s16le","-ar",str(sr)]
    elif codec.lower() == "mp3":
        cmd = ["ffmpeg","-y", *inputs, *map_args,
               "-c:a","libmp3lame","-q:a","2"]
    elif codec.lower() in ("opus","ogg"):
        cmd = ["ffmpeg","-y", *inputs, *map_args,
               "-c:a","libopus","-b:a","160k"]
    elif codec.lower() in ("m4a","alac"):
        cmd = ["ffmpeg","-y", *inputs, *map_args,
               "-c:a","alac"]
    else:
        raise ValueError(f"Unsupported codec {codec}")
    # threads if limited
    if cfg and cfg.FFMPEG_THREADS and cfg.FFMPEG_THREADS>0:
        cmd += ["-threads", str(cfg.FFMPEG_THREADS)]
    cmd += [str(out_path)]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if p.returncode != 0:
        err_txt = (p.stderr or p.stdout or "")
        # ffmpeg may emit either 'Invalid metadata type 0' or generic 'Invalid metadata'
        if "Invalid metadata" in err_txt:
            # Retry without metadata mapping (e.g., synthetic test tone without tags)
            base_cmd: List[str] = []
            skip_next = False
            for c in cmd:
                if skip_next:
                    skip_next = False
                    continue
                if c == "-map_metadata":
                    skip_next = True  # skip its following argument
                    continue
                base_cmd.append(c)
            p2 = subprocess.run(base_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            if p2.returncode != 0:
                raise RuntimeError(f"ffmpeg tag copy failed: {p2.stderr or p2.stdout}")
        else:
            raise RuntimeError(f"ffmpeg tag copy failed: {err_txt}")

def read_basic_tags(p: Path) -> Dict[str, str]:
    tags: Dict[str, str] = {}
    try:
        mf = MutFile(p)  # type: ignore[call-arg]
    except Exception:
        # Unreadable or invalid file; treat as no tags
        return tags
    if not mf:
        return tags
    frames = getattr(mf, 'tags', {}) or {}  # type: ignore[call-overload]
    # ID3 specific frame mapping
    if 'TPE1' in frames and 'artist' not in tags:
        val = frames['TPE1']
        try:
            tags['artist'] = str(getattr(val, 'text', [val])[0])
        except (AttributeError, IndexError, TypeError, ValueError):
            pass
    if 'TIT2' in frames and 'title' not in tags:
        val = frames['TIT2']
        try:
            tags['title'] = str(getattr(val, 'text', [val])[0])
        except (AttributeError, IndexError, TypeError, ValueError):
            pass
    if 'TALB' in frames and 'album' not in tags:
        val = frames['TALB']
        try:
            tags['album'] = str(getattr(val, 'text', [val])[0])
        except (AttributeError, IndexError, TypeError, ValueError):
            pass
    # Generic lowercase/uppercase variants (Vorbis/FLAC)
    for key in ("artist","ARTIST"):
        if key in frames and 'artist' not in tags:
            try:
                tags['artist'] = str(frames[key][0])
            except (IndexError, TypeError, ValueError):
                pass
            break
    for key in ("title","TITLE"):
        if key in frames and 'title' not in tags:
            try:
                tags['title'] = str(frames[key][0])
            except (IndexError, TypeError, ValueError):
                pass
            break
    for key in ("album","ALBUM"):
        if key in frames and 'album' not in tags:
            try:
                tags['album'] = str(frames[key][0])
            except (IndexError, TypeError, ValueError):
                pass
            break
    return tags
