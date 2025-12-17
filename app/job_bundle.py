"""
Job bundle schema and utilities for queue-based pipeline.

A job bundle is the standardized handoff between retrieval services and the processor.
All retrievers (YouTube, Deemix, custom services) produce job bundles in the same format.
"""

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict, Any, Optional
import json
from datetime import datetime


@dataclass
class ArtifactMetadata:
    """Describes a single produced file (audio, video, or stem)."""
    kind: str  # "audio", "video", "stems"
    variant: str  # "instrumental", "no_drums", "drums_only", "source", "drums_stem", etc.
    label: str  # Human-readable: "Instrumental", "Instrumental (no drum)", "Drums only"
    path: str  # Relative path under job's files/ directory
    codec: Optional[str] = None  # "mp3", "wav", "flac", "aac", etc.
    container: Optional[str] = None  # "m4a", "mp3", "wav", etc.
    duration_sec: Optional[float] = None
    sha256: Optional[str] = None


@dataclass
class YouTubeMetadata:
    """YouTube-specific provenance metadata."""
    video_id: str
    url: str
    channel: str
    title: str
    online_duration_sec: float


@dataclass
class ValidationResult:
    """Validation status for a job bundle."""
    duration_checks: str  # "pass", "fail", "skipped"
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class JobManifest:
    """
    Complete manifest for a processing job.
    Written as manifest.json in the output directory after processing completes.
    NAS Sync service consumes these manifests to route artifacts to remote paths.
    """
    job_id: str
    source_type: str  # "youtube", "deemix", "custom", "local", etc.
    artist: str
    album: str
    title: str
    processed_at: str  # ISO timestamp
    artifacts: List[ArtifactMetadata]
    
    # Source-specific metadata
    youtube: Optional[YouTubeMetadata] = None
    
    # Validation
    validation: Optional[ValidationResult] = None
    
    # Processing notes
    stems_generated: bool = False  # True if instrument variants were created
    stems_preserved: bool = False  # True if stem files (.wav) are included
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        data = asdict(self)
        # Convert dataclass instances to dicts recursively
        if self.youtube:
            data["youtube"] = asdict(self.youtube)
        if self.validation:
            data["validation"] = asdict(self.validation)
        data["artifacts"] = [asdict(a) for a in self.artifacts]
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JobManifest":
        """Create from dict (reverse of to_dict)."""
        data = dict(data)  # Shallow copy to avoid mutating original
        
        # Reconstruct artifacts
        if "artifacts" in data:
            data["artifacts"] = [ArtifactMetadata(**a) for a in data["artifacts"]]
        
        # Reconstruct youtube metadata
        if "youtube" in data and data["youtube"]:
            data["youtube"] = YouTubeMetadata(**data["youtube"])
        
        # Reconstruct validation
        if "validation" in data and data["validation"]:
            data["validation"] = ValidationResult(**data["validation"])
        
        return cls(**data)
    
    def save(self, output_dir: Path) -> Path:
        """Write manifest.json to output directory."""
        manifest_path = output_dir / "manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(manifest_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        return manifest_path
    
    @staticmethod
    def load(manifest_path: Path) -> "JobManifest":
        """Load manifest from file."""
        with open(manifest_path, "r") as f:
            data = json.load(f)
        return JobManifest.from_dict(data)


@dataclass
class JobBundle:
    """
    A retriever's output: contains metadata + paths to produced files.
    Before enqueueing to a holding queue, the bundle is moved atomically from .tmp to final folder.
    """
    job_id: str
    source_type: str  # "youtube", "deemix", etc.
    
    # Core metadata
    title: str
    artist: str
    album: str
    
    # Files produced by retriever
    audio_path: Optional[Path] = None  # Main audio to process
    video_path: Optional[Path] = None  # Optional source video
    cover_path: Optional[Path] = None  # Optional artwork
    
    # Extended metadata (retriever-specific)
    youtube: Optional[YouTubeMetadata] = None
    
    # Validation status
    validation: Optional[ValidationResult] = None
    
    def to_job_json(self) -> Dict[str, Any]:
        """Convert to job.json format (what goes in the queue folder)."""
        data: Dict[str, Any] = {
            "job_id": self.job_id,
            "source_type": self.source_type,
            "artist": self.artist,
            "album": self.album,
            "title": self.title,
        }
        
        # Include relative paths if they exist
        if self.audio_path:
            data["audio_path"] = self.audio_path.name
        if self.video_path:
            data["video_path"] = self.video_path.name
        if self.cover_path:
            data["cover_path"] = self.cover_path.name
        
        # Include source metadata
        if self.youtube:
            data["youtube"] = asdict(self.youtube)
        
        # Include validation
        if self.validation:
            data["validation"] = asdict(self.validation)
        
        return data
    
    def save_to_queue_folder(self, queue_folder: Path) -> Path:
        """
        Write job.json and referenced files to a queue folder.
        The folder should be named job_<id>/ (not .tmp).
        """
        job_folder = queue_folder / f"job_{self.job_id}"
        job_folder.mkdir(parents=True, exist_ok=True)
        
        # Write job.json
        job_json_path = job_folder / "job.json"
        with open(job_json_path, "w") as f:
            json.dump(self.to_job_json(), f, indent=2)
        
        return job_folder
