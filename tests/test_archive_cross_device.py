import errno
from pathlib import Path
from app.config import Config
from app.db import connect, get_filename_count
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
        # Speed up stability waits for test
        STABILITY_CHECK_SECONDS = 0
        STABILITY_PASSES = 1
        # Dedupe flags
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


def test_archive_cross_device_fallback(monkeypatch, tmp_path):
    """Simulate EXDEV during archive (rename) and ensure copy+unlink fallback succeeds."""
    cfg = make_cfg(tmp_path)
    db = connect(cfg.DB_PATH)
    base = 'xd.mp3'
    # First occurrence (count becomes 1 after enqueue)
    f1 = Path(cfg.INCOMING)/base; write_dummy(f1, size=2048); handle_new_file(f1,cfg,db)
    db.execute("update jobs set status='done'"); db.commit()
    # Second occurrence (different hash) triggers rename to (2) and increments count to 2
    f2 = Path(cfg.INCOMING)/'b'/base; write_dummy(f2, size=4096); handle_new_file(f2,cfg,db)
    db.execute("update jobs set status='done'"); db.commit()
    assert get_filename_count(db, base) == 2, 'Expected filename count=2 after second occurrence rename'
    # Monkeypatch Path.rename to raise EXDEV only for third occurrence (dir 'c') to simulate cross-device
    orig_rename = Path.rename
    third_src = Path(cfg.INCOMING)/'c'/base
    def fake_rename(self, target):
        # Simulate cross-device only for archive move of the third source file
        if self == third_src:
            raise OSError(errno.EXDEV, 'Invalid cross-device link')
        return orig_rename(self, target)
    monkeypatch.setattr(Path, 'rename', fake_rename)
    # Third occurrence (should archive via dedupe count >=2, invoking EXDEV fallback)
    f3 = third_src; write_dummy(f3, size=6000); handle_new_file(f3,cfg,db)
    archived = list(Path(cfg.ARCHIVE_DIR).rglob(base))
    assert archived, 'Expected archived file after EXDEV fallback'
    # Original source removed
    assert not f3.exists(), 'Source file should be removed after fallback copy+unlink'
