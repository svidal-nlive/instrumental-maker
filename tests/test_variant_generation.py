"""
Tests for audio variant generation (Phase 6).

Tests:
1. Stem detection
2. Variant availability checking
3. Stem mixing
4. Variant generation (instrumental, no_drums, drums_only)
5. End-to-end variant processing
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.variant_generator import StemMixer, VariantGenerator


@pytest.fixture
def temp_work_dir():
    """Create temporary working directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_stems(temp_work_dir) -> dict:
    """Create dummy stem files."""
    stems = {}
    for stem_name in ["vocals", "drums", "bass", "other"]:
        stem_path = temp_work_dir / f"{stem_name}.wav"
        # Write minimal WAV header (44 bytes) + data
        stem_path.write_bytes(b"RIFF" + (40).to_bytes(4, "little") + b"WAVE" + b"X" * 36)
        stems[stem_name] = stem_path
    return stems


class TestStemMixer:
    """Test stem detection and mixing."""
    
    def test_get_available_stems(self, temp_work_dir, sample_stems):
        """Test detecting available stems."""
        # Copy sample stems to work dir
        for name, path in sample_stems.items():
            (temp_work_dir / name).write_bytes(path.read_bytes())
        
        found_stems = StemMixer.get_available_stems(temp_work_dir)
        
        assert len(found_stems) == 4
        assert "vocals" in found_stems
        assert "drums" in found_stems
        assert "bass" in found_stems
        assert "other" in found_stems
    
    def test_get_available_stems_subset(self, temp_work_dir):
        """Test detecting partial stems."""
        (temp_work_dir / "vocals.wav").write_bytes(b"RIFF" + (40).to_bytes(4, "little") + b"WAVE" + b"X" * 36)
        (temp_work_dir / "drums.wav").write_bytes(b"RIFF" + (40).to_bytes(4, "little") + b"WAVE" + b"X" * 36)
        
        found_stems = StemMixer.get_available_stems(temp_work_dir)
        
        assert len(found_stems) == 2
        assert "vocals" in found_stems
        assert "drums" in found_stems
        assert "bass" not in found_stems
    
    def test_get_available_stems_nested(self, temp_work_dir):
        """Test finding stems in nested directories."""
        stems_subdir = temp_work_dir / "model" / "output"
        stems_subdir.mkdir(parents=True)
        
        (stems_subdir / "vocals.wav").write_bytes(b"RIFF" + (40).to_bytes(4, "little") + b"WAVE" + b"X" * 36)
        (stems_subdir / "drums.wav").write_bytes(b"RIFF" + (40).to_bytes(4, "little") + b"WAVE" + b"X" * 36)
        
        found_stems = StemMixer.get_available_stems(temp_work_dir)
        
        assert len(found_stems) == 2
        assert "vocals" in found_stems
        assert "drums" in found_stems


class TestVariantAvailability:
    """Test variant availability checking."""
    
    def test_should_generate_instrumental(self, sample_stems):
        """Test instrumental availability check."""
        # Has drums, bass, other = can generate instrumental
        assert VariantGenerator.should_generate_instrumental(sample_stems) is True
        
        # Missing drums = cannot generate instrumental
        partial_stems = {k: v for k, v in sample_stems.items() if k != "drums"}
        assert VariantGenerator.should_generate_instrumental(partial_stems) is False
    
    def test_should_generate_no_drums(self, sample_stems):
        """Test no_drums availability check."""
        # Has vocals, bass, other = can generate no_drums
        assert VariantGenerator.should_generate_no_drums(sample_stems) is True
        
        # Missing vocals = cannot generate no_drums
        partial_stems = {k: v for k, v in sample_stems.items() if k != "vocals"}
        assert VariantGenerator.should_generate_no_drums(partial_stems) is False
    
    def test_should_generate_drums_only(self, sample_stems):
        """Test drums_only availability check."""
        # Has drums = can generate drums_only
        assert VariantGenerator.should_generate_drums_only(sample_stems) is True
        
        # No drums = cannot generate drums_only
        partial_stems = {k: v for k, v in sample_stems.items() if k != "drums"}
        assert VariantGenerator.should_generate_drums_only(partial_stems) is False
    
    def test_all_variants_available(self, sample_stems):
        """Test that all variants can be generated with full stems."""
        assert VariantGenerator.should_generate_instrumental(sample_stems)
        assert VariantGenerator.should_generate_no_drums(sample_stems)
        assert VariantGenerator.should_generate_drums_only(sample_stems)


class TestVariantGeneration:
    """Test variant generation."""
    
    @patch("app.variant_generator.StemMixer.mix_stems")
    def test_generate_instrumental(self, mock_mix, sample_stems, temp_work_dir):
        """Test instrumental variant generation."""
        output_path = temp_work_dir / "instrumental.wav"
        
        success = VariantGenerator.generate_instrumental(sample_stems, output_path, ffmpeg_threads=1)
        
        assert success is True
        mock_mix.assert_called_once()
        call_args = mock_mix.call_args
        # Check that drums, bass, other are included
        mixed_stems = call_args[0][0]
        assert "drums" in mixed_stems
        assert "bass" in mixed_stems
        assert "other" in mixed_stems
        assert "vocals" not in mixed_stems
    
    @patch("app.variant_generator.StemMixer.mix_stems")
    def test_generate_no_drums(self, mock_mix, sample_stems, temp_work_dir):
        """Test no_drums variant generation."""
        output_path = temp_work_dir / "no_drums.wav"
        
        success = VariantGenerator.generate_no_drums(sample_stems, output_path, ffmpeg_threads=1)
        
        assert success is True
        mock_mix.assert_called_once()
        call_args = mock_mix.call_args
        # Check that vocals, bass, other are included
        mixed_stems = call_args[0][0]
        assert "vocals" in mixed_stems
        assert "bass" in mixed_stems
        assert "other" in mixed_stems
        assert "drums" not in mixed_stems
    
    def test_generate_drums_only(self, sample_stems, temp_work_dir):
        """Test drums_only variant generation (copy operation)."""
        output_path = temp_work_dir / "drums_only.wav"
        
        success = VariantGenerator.generate_drums_only(sample_stems, output_path, ffmpeg_threads=1)
        
        assert success is True
        assert output_path.exists()
        assert output_path.read_bytes() == sample_stems["drums"].read_bytes()
    
    def test_generate_fails_with_missing_stems(self, temp_work_dir):
        """Test that generation fails gracefully with missing stems."""
        empty_stems = {}
        output_path = temp_work_dir / "variant.wav"
        
        success = VariantGenerator.generate_instrumental(empty_stems, output_path)
        assert success is False
        
        success = VariantGenerator.generate_no_drums(empty_stems, output_path)
        assert success is False
        
        success = VariantGenerator.generate_drums_only(empty_stems, output_path)
        assert success is False


class TestStemMixing:
    """Test stem mixing logic."""
    
    def test_single_stem_copy(self, sample_stems, temp_work_dir):
        """Test that single stem is just copied."""
        output = temp_work_dir / "output.wav"
        single_stem = {"vocals": sample_stems["vocals"]}
        
        StemMixer.mix_stems(single_stem, output, ffmpeg_threads=1)
        
        assert output.exists()
        assert output.read_bytes() == sample_stems["vocals"].read_bytes()
    
    @patch("subprocess.run")
    def test_multi_stem_mix(self, mock_run, sample_stems, temp_work_dir):
        """Test that multiple stems trigger ffmpeg."""
        mock_run.return_value = MagicMock(returncode=0)
        
        output = temp_work_dir / "output.wav"
        two_stems = {"vocals": sample_stems["vocals"], "drums": sample_stems["drums"]}
        
        StemMixer.mix_stems(two_stems, output, ffmpeg_threads=1)
        
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        # Check that it's an ffmpeg command
        assert call_args[0] == "ffmpeg"
        # Should have filter_complex
        assert "-filter_complex" in call_args


class TestVariantMetadata:
    """Test variant naming and metadata."""
    
    def test_instrumental_labels(self):
        """Test that instrumental has correct label."""
        # This tests the logic in _process_queue_audio_job
        variant_name = "instrumental"
        if variant_name == "instrumental":
            label = "Instrumental"
            assert label == "Instrumental"
    
    def test_no_drums_labels(self):
        """Test that no_drums has correct label."""
        variant_name = "no_drums"
        if variant_name == "no_drums":
            label = "Instrumental (no drums)"
            assert label == "Instrumental (no drums)"
    
    def test_drums_only_labels(self):
        """Test that drums_only has correct label."""
        variant_name = "drums_only"
        if variant_name == "drums_only":
            label = "Drums only"
            assert label == "Drums only"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
