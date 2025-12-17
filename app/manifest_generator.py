"""
Manifest generator: produces manifest.json after job processing completes.

The manifest describes all artifacts produced by the pipeline and their variants,
enabling NAS Sync to route them to configured remote folders.
"""

from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
import json

from .job_bundle import JobManifest, ArtifactMetadata, ValidationResult


class ManifestGenerator:
    """Generates manifests for completed jobs."""
    
    @staticmethod
    def generate_for_job(
        job_id: str,
        source_type: str,
        artist: str,
        album: str,
        title: str,
        output_dir: Path,
        audio_variants: Optional[List[Dict[str, Any]]] = None,
        video_artifact: Optional[Dict[str, Any]] = None,
        stems_preserved: bool = False,
        validation: Optional[ValidationResult] = None,
    ) -> JobManifest:
        """
        Build a complete manifest for a processed job.
        
        Args:
            job_id: Unique job identifier
            source_type: "youtube", "deemix", etc.
            artist, album, title: Metadata
            output_dir: Path to /outputs/<job_id>/
            audio_variants: List of dicts:
                {
                    "variant": "instrumental" | "no_drums" | "drums_only",
                    "label": "Human-readable label",
                    "filename": "Artist - Title.m4a" (relative to files/audio/)
                    "codec": "aac" or similar,
                    "duration_sec": float,
                    "sha256": optional
                }
            video_artifact: Dict with "filename", "codec", "duration_sec", etc.
                (relative to files/video/)
            stems_preserved: True if stem .wav files are saved
            validation: ValidationResult from retrieval phase
        
        Returns:
            JobManifest ready to save to manifest.json
        """
        artifacts: List[ArtifactMetadata] = []
        
        # Audio variants
        if audio_variants:
            for av in audio_variants:
                artifact = ArtifactMetadata(
                    kind="audio",
                    variant=av.get("variant", "instrumental"),
                    label=av.get("label", "Instrumental"),
                    path=f"files/audio/{av.get('filename', 'output.m4a')}",
                    codec=av.get("codec"),
                    container=av.get("container", av.get("codec")),
                    duration_sec=av.get("duration_sec"),
                    sha256=av.get("sha256"),
                )
                artifacts.append(artifact)
        
        # Video artifact (if present)
        if video_artifact:
            artifact = ArtifactMetadata(
                kind="video",
                variant="source",
                label="Source video",
                path=f"files/video/{video_artifact.get('filename', 'video.mp4')}",
                codec=video_artifact.get("codec"),
                container=video_artifact.get("container"),
                duration_sec=video_artifact.get("duration_sec"),
                sha256=video_artifact.get("sha256"),
            )
            artifacts.append(artifact)
        
        # Stems (if preserved)
        if stems_preserved:
            stem_dir = output_dir / "files" / "stems"
            if stem_dir.exists():
                for stem_file in sorted(stem_dir.glob("*.wav")):
                    artifact = ArtifactMetadata(
                        kind="stems",
                        variant=stem_file.stem,  # "drums", "vocals", "bass", etc.
                        label=f"{stem_file.stem.title()} stem",
                        path=f"files/stems/{stem_file.name}",
                        codec="pcm",
                        container="wav",
                    )
                    artifacts.append(artifact)
        
        manifest = JobManifest(
            job_id=job_id,
            source_type=source_type,
            artist=artist,
            album=album,
            title=title,
            processed_at=datetime.utcnow().isoformat() + "Z",
            artifacts=artifacts,
            validation=validation,
            stems_generated=len(audio_variants or []) > 1,
            stems_preserved=stems_preserved,
        )
        
        return manifest
    
    @staticmethod
    def manifest_path(output_dir: Path) -> Path:
        """Expected location of manifest.json for an output directory."""
        return output_dir / "manifest.json"
