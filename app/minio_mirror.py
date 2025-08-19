import mimetypes, os, sqlite3, time, socket
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from minio import Minio
from minio.error import S3Error
from .config import Config

MIRROR_DB = "mirror.sqlite"

@dataclass
class MirrorCfg:
    enabled: bool
    endpoint: str
    secure: bool
    access_key: str
    secret_key: str
    bucket: str
    prefix: str
    guess_ct: bool
    scan_interval: int
    output_dir: Path
    db_path: Path
    region: Optional[str] = None

def connect_db(db_file: Path) -> sqlite3.Connection:
    db_file.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_file, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS uploaded (
          path TEXT PRIMARY KEY,
          size INTEGER NOT NULL,
          mtime REAL NOT NULL,
          etag TEXT
        );
    """)
    return conn

def already_uploaded(conn: sqlite3.Connection, f: Path) -> bool:
    row = conn.execute("SELECT size, mtime FROM uploaded WHERE path=?", (str(f),)).fetchone()
    if not row: return False
    size, mtime = row
    try:
        st = f.stat()
    except FileNotFoundError:
        return True
    return (st.st_size == size) and (st.st_mtime == mtime)

def mark_uploaded(conn: sqlite3.Connection, f: Path, etag: Optional[str]):
    st = f.stat()
    with conn:
        conn.execute("INSERT OR REPLACE INTO uploaded(path,size,mtime,etag) VALUES (?,?,?,?)",
                     (str(f), st.st_size, st.st_mtime, etag or ""))

def content_type_for(f: Path, guess: bool) -> Optional[str]:
    if not guess: return None
    ctype, _ = mimetypes.guess_type(str(f))
    return ctype

def make_client(cfg: MirrorCfg) -> Minio:
    return Minio(
        cfg.endpoint,
        access_key=cfg.access_key,
        secret_key=cfg.secret_key,
        secure=cfg.secure
    )

def _tcp_ready(host: str, port: int, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False

def wait_for_minio(client: Minio, endpoint: str, secure: bool, max_wait: int = 180):
    """Wait until MinIO is reachable and responding to API calls."""
    host, port = (endpoint.split(":") + ["443" if secure else "80"])[0:2]
    port = int(port)
    start = time.time()
    attempt = 0
    while True:
        attempt += 1
        # 1) TCP-level check
        if _tcp_ready(host, port):
            # 2) Simple API call – list_buckets() is low-cost and tests auth
            try:
                client.list_buckets()
                print(f"[minio-mirror] MinIO is ready (after {attempt} attempts).")
                return
            except S3Error as e:
                # Auth or endpoint accessible but not ready – still retry
                print(f"[minio-mirror] MinIO reachable but not ready/auth error: {e}; retrying...")
            except Exception as e:
                print(f"[minio-mirror] MinIO API error: {e}; retrying...")
        else:
            print(f"[minio-mirror] Waiting for MinIO TCP {host}:{port}...")

        if time.time() - start > max_wait:
            raise RuntimeError(f"Timed out waiting for MinIO at {endpoint}")
        time.sleep(min(2 + attempt, 10))

def ensure_bucket(client: Minio, bucket: str, region: Optional[str]):
    try:
        if not client.bucket_exists(bucket):
            # region is optional; only pass if provided
            if region:
                client.make_bucket(bucket, location=region)
            else:
                client.make_bucket(bucket)
            print(f"[minio-mirror] Created bucket: {bucket} (region={region or 'default'})")
        else:
            print(f"[minio-mirror] Bucket exists: {bucket}")
    except S3Error as e:
        # If a race occurs between multiple replicas, it's fine if it already exists
        if e.code in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
            print(f"[minio-mirror] Bucket ready: {bucket}")
        else:
            raise

def object_name(cfg: MirrorCfg, f: Path) -> str:
    rel = f.relative_to(cfg.output_dir)
    name = str(rel).replace("\\", "/")
    prefix = cfg.prefix.strip("/")
    return f"{prefix}/{name}" if prefix else name

def upload_one(client: Minio, cfg: MirrorCfg, f: Path) -> str:
    obj = object_name(cfg, f)
    ctype = content_type_for(f, cfg.guess_ct)
    result = client.fput_object(cfg.bucket, obj, str(f), content_type=ctype)
    return result.etag

def run():
    cfg0 = Config()
    cfg = MirrorCfg(
        enabled=cfg0.MINIO_MIRROR_ENABLED,
        endpoint=cfg0.MINIO_ENDPOINT,
        secure=cfg0.MINIO_USE_SSL,
        access_key=cfg0.MINIO_ACCESS_KEY,
        secret_key=cfg0.MINIO_SECRET_KEY,
        bucket=cfg0.MINIO_BUCKET,
        prefix=cfg0.MINIO_PREFIX,
        guess_ct=cfg0.MINIO_CONTENT_TYPE_BY_EXT,
        scan_interval=cfg0.MINIO_SCAN_INTERVAL_SEC,
        output_dir=Path(cfg0.OUTPUT),
        db_path=Path(os.path.dirname(cfg0.DB_PATH)) / MIRROR_DB,
        region=(cfg0.MINIO_REGION or None),
    )

    if not cfg.enabled:
        print("[minio-mirror] disabled (MINIO_MIRROR_ENABLED=false)")
        while True:
            time.sleep(60)

    client = make_client(cfg)

    # Robust readiness & bucket ensure with retries
    wait_for_minio(client, cfg.endpoint, cfg.secure, max_wait=300)

    # Create bucket if missing (idempotent)
    created = False
    for attempt in range(1, 11):
        try:
            ensure_bucket(client, cfg.bucket, cfg.region)
            created = True
            break
        except Exception as e:
            print(f"[minio-mirror] ensure_bucket attempt {attempt} failed: {e}")
            time.sleep(min(2 * attempt, 10))
    if not created:
        raise RuntimeError(f"Failed to ensure bucket {cfg.bucket} after retries")

    conn = connect_db(cfg.db_path)
    print(f"[minio-mirror] watching {cfg.output_dir} → s3://{cfg.bucket}/{cfg.prefix or ''}")
    while True:
        try:
            for f in cfg.output_dir.rglob("*"):
                if f.is_dir(): continue
                if already_uploaded(conn, f): continue
                try:
                    etag = upload_one(client, cfg, f)
                    mark_uploaded(conn, f, etag)
                    print(f"[minio-mirror] uploaded: {f} (etag={etag})")
                except Exception as e:
                    print(f"[minio-mirror] upload error for {f}: {e}")
            time.sleep(cfg.scan_interval)
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    run()
