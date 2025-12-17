"""
Audio variant generation from demucs stems.

Generates multiple audio variants (instrumental, no drums, drums only)
from a single demucs separation job.
"""

from pathlib import Path
from typing import List, Dict, Tuple, Optional
import shutil

from .utils import ensure_dir


class StemMixer:
    """Mix different combinations of demucs stems to create variants."""
    
    @staticmethod
    def get_available_stems(demucs_output_dir: Path) -> Dict[str, Path]:
        """
        Discover available stems in demucs output directory.
        
        Returns:
            Dict mapping stem name -> file path
            Expected stems: vocals, drums, bass, other
        """
        stems = {}
        
        # Look for stem files
        for candidate_path in demucs_output_dir.rglob("*.wav"):
            name = candidate_path.stem.lower()
            # Map common demucs output names
            if name in ("vocals", "drums", "bass", "other"):
                stems[name] = candidate_path
        
        return stems
    
    @staticmethod
    def mix_stems(stem_paths: Dict[str, Path], output_path: Path, ffmpeg_threads: int = 1):
        """
        Mix specified stems together using ffmpeg with volume normalization.
        
        Args:
            stem_paths: Dict mapping stem names to file paths
                       e.g. {"drums": path1, "bass": path2}
            output_path: Output WAV file path
            ffmpeg_threads: FFmpeg thread count
        """
        import subprocess
        
        if not stem_paths:
            raise ValueError("No stems provided")
        
        if len(stem_paths) == 1:
            # Single stem - just copy it
            source_path = list(stem_paths.values())[0]
            shutil.copy2(source_path, output_path)
            return
        
        # Build ffmpeg filter: mix multiple audio streams with amix filter
        # amix=inputs=N:duration=first:dropout_transition=2
        stems_list = list(stem_paths.values())
        
        cmd = ["ffmpeg", "-y"]
        
        # Add input files
        for stem_path in stems_list:
            cmd.extend(["-i", str(stem_path)])
        
        # Build filter graph
        # For 2 stems: [0:a][1:a]amix=inputs=2:duration=first[out]
        # For 3+ stems: multiple amixes chained
        n_stems = len(stems_list)
        
        if n_stems == 2:
            filter_str = f"[0:a][1:a]amix=inputs=2:duration=first[out]"
        else:
            # Chain amix operations
            filters = []
            for i in range(n_stems - 1):
                if i == 0:
                    filters.append(f"[0:a][1:a]amix=inputs=2:duration=first[mix{i}]")
                else:
                    filters.append(f"[mix{i-1}][{i+1}:a]amix=inputs=2:duration=first[mix{i}]")
            filter_str = ";".join(filters) + f";[mix{n_stems-2}]anequalizer=f=1k:t=h:w=1:g=-10[out]"
            # Simplified: just use the last mix
            filter_str = ";".join(filters)
            # Just mix all with a simple filter
            filter_str = f"{''.join(f'[{i}:a]' for i in range(n_stems))}amix=inputs={n_stems}:duration=first[out]"
        
        cmd.extend([
            "-filter_complex", filter_str,
            "-map", "[out]",
            "-c:a", "pcm_s16le",
            "-threads", str(ffmpeg_threads),
            str(output_path),
        ])
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg stem mixing failed: {result.stderr}"
            )


class VariantGenerator:
    """Generate audio variants from demucs stems."""
    
    @staticmethod
    def should_generate_instrumental(stems: Dict[str, Path]) -> bool:
        """Check if we can generate instrumental (vocals removed)."""
        # Instrumental = drums + bass + other (everything except vocals)
        return "drums" in stems and "bass" in stems and "other" in stems
    
    @staticmethod
    def should_generate_no_drums(stems: Dict[str, Path]) -> bool:
        """Check if we can generate no_drums (drums removed from instrumental)."""
        # No drums = vocals + bass + other
        return "vocals" in stems and "bass" in stems and "other" in stems
    
    @staticmethod
    def should_generate_drums_only(stems: Dict[str, Path]) -> bool:
        """Check if we can generate drums_only variant."""
        return "drums" in stems
    
    @staticmethod
    def generate_instrumental(
        stems: Dict[str, Path],
        output_path: Path,
        ffmpeg_threads: int = 1,
    ) -> bool:
        """
        Generate instrumental mix (vocals removed).
        
        Args:
            stems: Available stems dict
            output_path: Output WAV file path
            ffmpeg_threads: FFmpeg thread count
        
        Returns:
            True if successful
        """
        if not VariantGenerator.should_generate_instrumental(stems):
            return False
        
        try:
            # Instrumental = drums + bass + other
            mix_stems = {
                "drums": stems["drums"],
                "bass": stems["bass"],
                "other": stems["other"],
            }
            StemMixer.mix_stems(mix_stems, output_path, ffmpeg_threads)
            return True
        except Exception as e:
            print(f"Failed to generate instrumental: {e}")
            return False
    
    @staticmethod
    def generate_no_drums(
        stems: Dict[str, Path],
        output_path: Path,
        ffmpeg_threads: int = 1,
    ) -> bool:
        """
        Generate no_drums variant (drums removed from instrumental).
        
        Args:
            stems: Available stems dict
            output_path: Output WAV file path
            ffmpeg_threads: FFmpeg thread count
        
        Returns:
            True if successful
        """
        if not VariantGenerator.should_generate_no_drums(stems):
            return False
        
        try:
            # No drums = vocals + bass + other
            mix_stems = {
                "vocals": stems["vocals"],
                "bass": stems["bass"],
                "other": stems["other"],
            }
            StemMixer.mix_stems(mix_stems, output_path, ffmpeg_threads)
            return True
        except Exception as e:
            print(f"Failed to generate no_drums: {e}")
            return False
    
    @staticmethod
    def generate_drums_only(
        stems: Dict[str, Path],
        output_path: Path,
        ffmpeg_threads: int = 1,
    ) -> bool:
        """
        Generate drums_only variant (isolated drums).
        
        Args:
            stems: Available stems dict
            output_path: Output WAV file path
            ffmpeg_threads: FFmpeg thread count
        
        Returns:
            True if successful
        """
        if not VariantGenerator.should_generate_drums_only(stems):
            return False
        
        try:
            # Drums only = just the drums stem
            shutil.copy2(stems["drums"], output_path)
            return True
        except Exception as e:
            print(f"Failed to generate drums_only: {e}")
            return False
