import os
from pathlib import Path

import pytest

from app.simple_runner import _compute_tags


def touch(p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"fake")


def test_compute_tags_hyphen_folder(tmp_path: Path):
    album_root = tmp_path / "Artist - Album"
    track = album_root / "01 - Title.wav"
    touch(track)
    title, artist, album = _compute_tags(track, album_root)
    assert title == "Title"
    assert artist == "Artist"
    assert album == "Album"


def test_compute_tags_en_dash_folder(tmp_path: Path):
    album_root = tmp_path / "Artist – Album"  # en dash
    track = album_root / "02 - Another.wav"
    touch(track)
    title, artist, album = _compute_tags(track, album_root)
    assert title == "Another"
    assert artist == "Artist"
    assert album == "Album"


def test_compute_tags_nested_artist_album(tmp_path: Path):
    incoming = tmp_path / "incoming"
    artist_dir = incoming / "Artist"
    album_dir = artist_dir / "Album"
    track = album_dir / "03 - Song.wav"
    touch(track)
    # Simulate scanner selecting top-level album_root as the Artist dir
    title, artist, album = _compute_tags(track, artist_dir)
    assert title == "Song"
    assert artist == "Artist"
    assert album == "Album"


def test_compute_tags_album_only_folder(tmp_path: Path):
    album_root = tmp_path / "LonelyAlbum"
    track = album_root / "Track.wav"
    touch(track)
    title, artist, album = _compute_tags(track, album_root)
    assert title == "Track"
    assert artist == "Unknown"
    assert album == "LonelyAlbum"
