import sys
from .watcher import main as watcher_main
from .worker import main as worker_main
from .minio_mirror import run as mirror_run
from .simple_runner import main as simple_main

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m app.main [watcher|worker|minio-mirror|simple]")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "watcher":
        watcher_main()
    elif cmd == "worker":
        worker_main()
    elif cmd == "minio-mirror":
        mirror_run()
    elif cmd == "simple":
        simple_main(sys.argv[2:])
    else:
        print("Unknown command")
        sys.exit(1)
