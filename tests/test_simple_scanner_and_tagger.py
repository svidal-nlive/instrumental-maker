from typing import Any, cast
from pathlib import Path
from app.simple_runner import scan_incoming_candidates
from app.config import Config


def test_scan_candidates_lone_and_album(tmp_path: Any):
    incoming = cast(Path, tmp_path / "incoming")
    incoming.mkdir()
    # Lone files
    (incoming / "track1.mp3").write_bytes(b"x")
    (incoming / "note.txt").write_text("ignore")
    # Album dir with audio inside
    album = incoming / "Artist - Album"
    album.mkdir()
    (album / "song01.flac").write_bytes(b"y")

    lone, albums = scan_incoming_candidates(incoming)
    assert any(p.name == "track1.mp3" for p in lone)
    assert any(p.name == "Artist - Album" for p in albums)


def test_mp3_encoding_toggle(monkeypatch: Any):
    # Ensure MP3_ENCODING env toggles normalize in Config
    monkeypatch.setenv("MP3_ENCODING", "v0")
    assert Config().MP3_ENCODING == "v0"
    monkeypatch.setenv("MP3_ENCODING", "cbr320")
    assert Config().MP3_ENCODING == "cbr320"
