import sys
from .minio_mirror import run as mirror_run
from .simple_runner import main as simple_main

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m app.main [simple|minio-mirror]")
        print("\nAvailable commands:")
        print("  simple        - Run simple file processor (recommended)")
        print("  minio-mirror  - Run MinIO mirror service")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "watcher":
        print("ERROR: 'watcher' command is deprecated and has been removed.")
        print("Use 'simple' instead: python -m app.main simple --daemon")
        sys.exit(1)
    elif cmd == "worker":
        print("ERROR: 'worker' command is deprecated and has been removed.")
        print("Use 'simple' instead: python -m app.main simple --daemon")
        sys.exit(1)
    elif cmd == "minio-mirror":
        mirror_run()
    elif cmd == "simple":
        simple_main(sys.argv[2:])
    else:
        print(f"Unknown command: {cmd}")
        print("Use 'simple' or 'minio-mirror'")
        sys.exit(1)
