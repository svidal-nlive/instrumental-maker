from pathlib import Path
from typing import Dict, Any
import yaml, json

def load_sidecar(path: Path) -> Dict[str, Any]:
    """
    Look for a sidecar YAML next to the audio file:
      e.g., "Song.mp3" -> "Song.stems.yml"
    Supported keys:
      model: htdemucs|htdemucs_6s|...
      keep_stems: [D,B,O]  # codes from {V,D,B,O}
      sample_rate: 44100
      bit_depth: 16
      codec: flac|wav|mp3|opus|m4a
      mix:
        target_lufs: -14
        true_peak: -1.0
        dual_pass_loudnorm: true
    Returns {} if not found.
    """
    sidecar = path.with_suffix("")  # drop ext
    sidecar = sidecar.parent / (sidecar.name + ".stems.yml")
    if not sidecar.exists():
        return {}
    data = yaml.safe_load(sidecar.read_text()) or {}
    return data

def apply_overrides(base_cfg: Dict[str, Any], sidecar: Dict[str, Any]) -> Dict[str, Any]:
    cfg = dict(base_cfg)
    if not sidecar:
        return cfg

    # Top-level overrides
    if "model" in sidecar:
        cfg["model"] = str(sidecar["model"])
    if "keep_stems" in sidecar and isinstance(sidecar["keep_stems"], list):
        cfg["stem_set"] = "".join(s.strip().upper() for s in sidecar["keep_stems"])
    if "sample_rate" in sidecar:
        cfg["sample_rate"] = int(sidecar["sample_rate"])
    if "bit_depth" in sidecar:
        cfg["bit_depth"] = int(sidecar["bit_depth"])
    if "codec" in sidecar:
        cfg["codec"] = str(sidecar["codec"]).lower()

    # Mix block
    mix = sidecar.get("mix") or {}
    if "target_lufs" in mix:
        cfg["target_lufs"] = float(mix["target_lufs"])
    if "true_peak" in mix:
        cfg["true_peak"] = float(mix["true_peak"])
    if "dual_pass_loudnorm" in mix:
        cfg["dual_pass_loudnorm"] = bool(mix["dual_pass_loudnorm"])

    return cfg
