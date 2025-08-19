from pathlib import Path
from app.config import Config
from app.db import connect
from app.watcher import handle_new_file

def make_cfg(tmpdir: Path):
    class Cfg(Config):
        INCOMING = str(tmpdir / 'incoming')
        WORKING = str(tmpdir / 'working')
        OUTPUT = str(tmpdir / 'output')
        DB_PATH = str(tmpdir / 'db' / 'jobs.sqlite')
        LOG_DIR = str(tmpdir / 'logs')
        ARCHIVE_DIR = str(tmpdir / 'archive')
        RESCAN_INTERVAL_SEC = 0
        STABILITY_CHECK_SECONDS = 0
        STABILITY_PASSES = 1
        DEDUPE_BY_FILENAME = True
        DEDUPE_RENAME_SECOND = True
        DEDUPE_CLEANUP_METHOD = 'archive'
    cfg = Cfg()
    for d in (cfg.INCOMING,cfg.WORKING,cfg.OUTPUT,cfg.LOG_DIR,cfg.ARCHIVE_DIR,Path(cfg.DB_PATH).parent):
        Path(d).mkdir(parents=True, exist_ok=True)
    return cfg


def write_dummy(p: Path, size=2048):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b'0'*size)


def test_archive_preserves_subdirectory(tmp_path):
    cfg = make_cfg(tmp_path)
    db = connect(cfg.DB_PATH)
    base = 'songx.mp3'
    # First + rename
    f1 = Path(cfg.INCOMING)/'a'/base; write_dummy(f1); handle_new_file(f1,cfg,db)
    db.execute("update jobs set status='done'"); db.commit()
    # Second occurrence (different dir, triggers rename -> count=2)
    f2 = Path(cfg.INCOMING)/'b'/base; write_dummy(f2, size=4096); handle_new_file(f2,cfg,db)
    db.execute("update jobs set status='done'"); db.commit()
    # Third occurrence in same second dir 'b' should be archived relative to that subdir
    f3 = Path(cfg.INCOMING)/'b'/base; write_dummy(f3, size=6000); handle_new_file(f3,cfg,db)
    archived = Path(cfg.ARCHIVE_DIR)/'b'/base
    assert archived.exists(), 'Archived file should retain subdirectory structure'
