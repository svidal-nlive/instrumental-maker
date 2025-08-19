import sqlite3, json, time
from pathlib import Path
from typing import Optional, Dict

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY,
  input_path TEXT NOT NULL,
  input_sha256 TEXT NOT NULL,
  model TEXT NOT NULL,
  stem_set TEXT NOT NULL,
  sample_rate INTEGER NOT NULL,
  bit_depth INTEGER NOT NULL,
  codec TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued',
  created_at TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT,
  output_path TEXT,
  manifest_path TEXT,
  error TEXT,
    notes TEXT,
    kind TEXT NOT NULL DEFAULT 'single',
  UNIQUE(input_sha256, model, stem_set, sample_rate, bit_depth, codec)
);
CREATE TABLE IF NOT EXISTS filename_counts (
    basename TEXT PRIMARY KEY,
    count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS locks (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT NOT NULL
);
"""

def connect(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    # SCHEMA now contains multiple statements; executescript handles them safely.
    conn.executescript(SCHEMA)
    # Lightweight migration for old DBs missing 'kind'
    try:
        cur = conn.execute("PRAGMA table_info(jobs)")
        cols = [r[1] for r in cur.fetchall()]
        if 'kind' not in cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN kind TEXT NOT NULL DEFAULT 'single'")
    except Exception:
        pass
    return conn

def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def enqueue_if_new(conn, job: Dict) -> bool:
    q = """INSERT OR IGNORE INTO jobs
    (input_path,input_sha256,model,stem_set,sample_rate,bit_depth,codec,status,created_at,kind)
    VALUES (?,?,?,?,?,?,?,?,?,?)"""
    with conn:
        cur = conn.execute(q, (
            job["input_path"], job["input_sha256"], job["model"], job["stem_set"],
            job["sample_rate"], job["bit_depth"], job["codec"], "queued", now(), job.get("kind","single")
        ))
    return cur.rowcount > 0

def get_filename_count(conn, basename: str) -> int:
    cur = conn.execute("SELECT count FROM filename_counts WHERE basename=?", (basename,))
    row = cur.fetchone()
    return int(row[0]) if row else 0

def set_filename_count(conn, basename: str, new_count: int):
    with conn:
        conn.execute("""INSERT INTO filename_counts (basename, count)
            VALUES (?,?) ON CONFLICT(basename) DO UPDATE SET count=excluded.count""",
            (basename, new_count))

def basename_statuses(conn, basename: str):
    cur = conn.execute("SELECT status FROM jobs WHERE substr(input_path, -length(?))=?", (basename, basename))
    return [r[0] for r in cur.fetchall()]

def get_first_job_path(conn, basename: str):
    cur = conn.execute("""SELECT input_path FROM jobs
        WHERE substr(input_path, -length(?))=?
        ORDER BY id ASC LIMIT 1""", (basename, basename))
    row = cur.fetchone()
    return row[0] if row else None

def next_queued(conn) -> Optional[Dict]:
    # Prioritize album jobs first
    q = "SELECT * FROM jobs WHERE status='queued' ORDER BY CASE WHEN kind='album' THEN 0 ELSE 1 END, id LIMIT 1"
    cur = conn.execute(q)
    row = cur.fetchone()
    return dict_from_row(cur, row) if row else None

def mark_running(conn, job_id: int):
    with conn:
        conn.execute("UPDATE jobs SET status='running', started_at=? WHERE id=?",
                     (now(), job_id))

def mark_done(conn, job_id: int, output_path: str, manifest_path: str, notes: Dict=None):
    with conn:
        conn.execute("""UPDATE jobs
            SET status='done', finished_at=?, output_path=?, manifest_path=?, notes=?
            WHERE id=?""",
            (now(), output_path, manifest_path, json.dumps(notes or {}), job_id))

def mark_error(conn, job_id: int, error: str, notes: Dict=None):
    with conn:
        conn.execute("""UPDATE jobs
            SET status='error', finished_at=?, error=?, notes=? WHERE id=?""",
            (now(), error, json.dumps(notes or {}), job_id))

def dict_from_row(cur, row):
    if row is None: return None
    cols = [d[0] for d in cur.description]
    return {c:v for c,v in zip(cols,row)}

# Cooperative DB-backed lock helpers (used to ensure album job exclusivity across workers)
def get_lock(conn, key: str) -> Optional[str]:
    cur = conn.execute("SELECT value FROM locks WHERE key=?", (key,))
    row = cur.fetchone()
    return row[0] if row else None

def acquire_lock(conn, key: str, value: str) -> bool:
    with conn:
        try:
            cur = conn.execute("INSERT INTO locks (key,value,updated_at) VALUES (?,?,?)",
                               (key, value, now()))
            return cur.rowcount > 0
        except sqlite3.IntegrityError:
            return False

def release_lock(conn, key: str, value: Optional[str]=None):
    with conn:
        if value is None:
            conn.execute("DELETE FROM locks WHERE key=?", (key,))
        else:
            conn.execute("DELETE FROM locks WHERE key=? AND value=?", (key, value))
