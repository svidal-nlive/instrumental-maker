from pathlib import Path
import os

from app.config import Config
from app.db import connect, get_filename_count
from app.watcher import handle_new_file


def make_cfg(tmpdir: Path, method='archive', rename_second=True, dedupe=True):
    def base_env(method='archive'):
        return {
            'DEDUPE_BY_FILENAME': dedupe,
            'DEDUPE_RENAME_SECOND': rename_second,
            'DEDUPE_CLEANUP_METHOD': method
        }
    class TCfg(Config):
        INCOMING = str(tmpdir / 'incoming')
        WORKING = str(tmpdir / 'working')
        OUTPUT = str(tmpdir / 'output')
        DB_PATH = str(tmpdir / 'db' / 'jobs.sqlite')
        LOG_DIR = str(tmpdir / 'logs')
        ARCHIVE_DIR = str(tmpdir / 'archive')
        RESCAN_INTERVAL_SEC = 0
        DEDUPE_BY_FILENAME = base_env(method)['DEDUPE_BY_FILENAME']
        DEDUPE_RENAME_SECOND = base_env(method)['DEDUPE_RENAME_SECOND']
        DEDUPE_CLEANUP_METHOD = base_env(method)['DEDUPE_CLEANUP_METHOD']
    cfg = TCfg()
    for d in (cfg.INCOMING, cfg.WORKING, cfg.OUTPUT, cfg.LOG_DIR, cfg.ARCHIVE_DIR, Path(cfg.DB_PATH).parent):
        Path(d).mkdir(parents=True, exist_ok=True)
    return cfg


def write_dummy(p: Path, size=2048):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b'0'*size)


def test_second_duplicate_renamed(tmp_path):
    cfg = make_cfg(tmp_path, 'archive', rename_second=True)
    db = connect(cfg.DB_PATH)
    base = 'track.mp3'
    f1 = Path(cfg.INCOMING)/base; write_dummy(f1); handle_new_file(f1,cfg,db)
    # Mark done to clear active
    db.execute("update jobs set status='done'"); db.commit()
    f2 = Path(cfg.INCOMING)/'folder'/base; write_dummy(f2); handle_new_file(f2,cfg,db)
    renamed = list(Path(cfg.INCOMING).rglob('track (2).mp3'))
    assert renamed, 'Second duplicate should be renamed with (2) suffix'


def test_purge_mode_third_removal(tmp_path):
    cfg = make_cfg(tmp_path, 'purge', rename_second=True)
    db = connect(cfg.DB_PATH)
    base = 'song.mp3'
    f1 = Path(cfg.INCOMING)/base; write_dummy(f1); handle_new_file(f1,cfg,db)
    db.execute("update jobs set status='done'"); db.commit()
    f2 = Path(cfg.INCOMING)/'a'/base; write_dummy(f2); handle_new_file(f2,cfg,db)
    db.execute("update jobs set status='done'"); db.commit()
    f3 = Path(cfg.INCOMING)/'b'/base; write_dummy(f3); handle_new_file(f3,cfg,db)
    assert not f3.exists(), 'Third duplicate should be purged in purge mode'


def test_deferred_while_active(tmp_path):
    cfg = make_cfg(tmp_path, 'archive', rename_second=True)
    db = connect(cfg.DB_PATH)
    base = 'live.mp3'
    f1 = Path(cfg.INCOMING)/base; write_dummy(f1); handle_new_file(f1,cfg,db)
    f2 = Path(cfg.INCOMING)/'later'/base; write_dummy(f2); handle_new_file(f2,cfg,db)
    assert (Path(cfg.INCOMING)/'later'/base).exists(), 'Second duplicate should remain unrenamed while first active'
    db.execute("update jobs set status='done'"); db.commit()
    handle_new_file(Path(cfg.INCOMING)/'later'/base, cfg, db)
    renamed = list((Path(cfg.INCOMING)/'later').rglob('live (2).mp3'))
    assert renamed, 'Second duplicate should rename after original completes'


def test_fourth_duplicate_also_archived(tmp_path):
    """Ensure 3rd and 4th duplicates are both archived (archive mode)."""
    cfg = make_cfg(tmp_path, 'archive', rename_second=True)
    db = connect(cfg.DB_PATH)
    base = 'multi.mp3'
    # First
    f1 = Path(cfg.INCOMING)/base; write_dummy(f1); handle_new_file(f1,cfg,db)
    db.execute("update jobs set status='done'"); db.commit()
    # Second
    f2 = Path(cfg.INCOMING)/'d2'/base; write_dummy(f2); handle_new_file(f2,cfg,db)
    db.execute("update jobs set status='done'"); db.commit()
    # Third (archive)
    f3 = Path(cfg.INCOMING)/'d3'/base; write_dummy(f3); handle_new_file(f3,cfg,db)
    # Fourth (archive)
    f4 = Path(cfg.INCOMING)/'d4'/base; write_dummy(f4); handle_new_file(f4,cfg,db)
    a3 = Path(cfg.ARCHIVE_DIR)/'d3'/base
    a4 = Path(cfg.ARCHIVE_DIR)/'d4'/base
    assert a3.exists() and a4.exists(), 'Both 3rd and 4th duplicates should be archived'
    assert get_filename_count(db, base) >= 3


def test_no_rename_when_rename_disabled(tmp_path):
    """Second duplicate should not be renamed if DEDUPE_RENAME_SECOND=false."""
    cfg = make_cfg(tmp_path, 'archive', rename_second=False, dedupe=True)
    for d in (cfg.INCOMING,cfg.WORKING,cfg.OUTPUT,cfg.LOG_DIR,cfg.ARCHIVE_DIR, Path(cfg.DB_PATH).parent):
        Path(d).mkdir(parents=True, exist_ok=True)
    db = connect(cfg.DB_PATH)
    base = 'plain.mp3'
    # First file
    f1 = Path(cfg.INCOMING)/base; write_dummy(f1, size=4096); handle_new_file(f1,cfg,db)
    db.execute("update jobs set status='done'"); db.commit()
    # Second file (different size -> different hash) should be enqueued but not renamed
    f2 = Path(cfg.INCOMING)/'sub'/base; write_dummy(f2, size=6000); handle_new_file(f2,cfg,db)
    # Ensure original name still present (no (2) suffix) and no renamed variant created
    assert f2.exists(), 'Second duplicate should retain original name when rename disabled'
    renamed = list(Path(cfg.INCOMING).rglob('plain (2).mp3'))
    assert not renamed, 'Should not create a (2) renamed file when rename disabled'
    # Confirm count incremented to at least 2 due to separate enqueue
    assert get_filename_count(db, base) >= 2, 'Filename count should reflect second distinct enqueue'
