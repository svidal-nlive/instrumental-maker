import os
import shutil
from pathlib import Path
import sqlite3
import json

from app.config import Config
from app.db import connect, enqueue_if_new, next_queued
from app.metadata import find_album_art_in_dir


def test_album_priority(tmp_path, monkeypatch):
    dbp = tmp_path / 'db.sqlite'
    conn = connect(str(dbp))
    # enqueue a single and an album
    single = {
        'input_path': '/data/incoming/song1.mp3',
        'input_sha256': 'a'*64,
        'model': 'htdemucs',
        'stem_set': 'DBO',
        'sample_rate': 44100,
        'bit_depth': 16,
        'codec': 'mp3',
        'kind': 'single',
    }
    album = dict(single)
    album['input_path'] = '/data/incoming/Album1'
    album['input_sha256'] = 'b'*64
    album['kind'] = 'album'
    assert enqueue_if_new(conn, single)
    assert enqueue_if_new(conn, album)

    # Next queued should be the album first
    n1 = next_queued(conn)
    assert n1['kind'] == 'album'


def test_find_album_art(tmp_path):
    d = tmp_path / 'incoming' / 'Artist - Album'
    d.mkdir(parents=True)
    # Place cover.png and ensure it's found
    (d / 'cover.png').write_bytes(b'fakepng')
    p = find_album_art_in_dir(d)
    assert p is not None and p.name == 'cover.png'
