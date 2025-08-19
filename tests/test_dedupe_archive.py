from pathlib import Path
from app.config import Config
from app.db import connect, get_filename_count
from app.watcher import handle_new_file


def make_cfg(tmpdir: Path):
    class TCfg(Config):
        INCOMING = str(tmpdir / 'incoming')
        WORKING = str(tmpdir / 'working')
        OUTPUT = str(tmpdir / 'output')
        DB_PATH = str(tmpdir / 'db' / 'jobs.sqlite')
        LOG_DIR = str(tmpdir / 'logs')
        ARCHIVE_DIR = str(tmpdir / 'archive')
        RESCAN_INTERVAL_SEC = 0
        DEDUPE_BY_FILENAME = True
        DEDUPE_RENAME_SECOND = True
        DEDUPE_CLEANUP_METHOD = 'archive'
    cfg = TCfg()
    for d in (cfg.INCOMING, cfg.WORKING, cfg.OUTPUT, cfg.LOG_DIR, cfg.ARCHIVE_DIR, Path(cfg.DB_PATH).parent):
        Path(d).mkdir(parents=True, exist_ok=True)
    return cfg


def _write_dummy(mp: Path, size=2048):  # must exceed MIN_INPUT_BYTES default (1024)
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_bytes(b'0' * size)


def test_third_duplicate_archives(tmp_path):
    """Validate that a third duplicate filename is archived (cleanup=archive)."""
    cfg = make_cfg(tmp_path)
    assert cfg.DEDUPE_BY_FILENAME and cfg.DEDUPE_RENAME_SECOND and cfg.DEDUPE_CLEANUP_METHOD == 'archive'

    db = connect(cfg.DB_PATH)
    base = '001 - Song.mp3'

    # First occurrence
    f1 = Path(cfg.INCOMING) / base
    _write_dummy(f1)
    handle_new_file(f1, cfg, db)

    # Mark first job as done to clear active_present state
    db.execute("UPDATE jobs SET status='done' WHERE input_path LIKE ?", ('%001 - Song.mp3',))
    db.commit()

    # Second occurrence (same name different folder) -> maybe renamed to (2)
    f2 = Path(cfg.INCOMING) / 'd2' / base
    _write_dummy(f2)
    handle_new_file(f2, cfg, db)

    # Mark second (renamed) job done so third isn't deferred
    db.execute("UPDATE jobs SET status='done' WHERE status='queued'")
    db.commit()

    # Third occurrence -> should archive (>=3rd rule)
    f3 = Path(cfg.INCOMING) / 'd3' / base
    _write_dummy(f3)
    handle_new_file(f3, cfg, db)

    # Assert archived copy present
    archived = list(Path(cfg.ARCHIVE_DIR).rglob(base))
    assert archived, 'Expected archived copy of third duplicate'

    # Count should reflect at least first + second occurrences
    count = get_filename_count(db, base)
    assert count >= 2
    db.close()
