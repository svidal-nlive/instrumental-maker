# Pipeline Directory Permissions Setup

## Overview

This document explains the directory permission configuration for the Instrumental Maker pipeline, ensuring consistency between local testing and production Docker environments.

## Problem Statement

Previously, tests used temporary local directories (`tempfile.TemporaryDirectory`), which created a disconnect between:
- **Testing environment**: Files created in `/tmp` with temp user ownership
- **Production environment**: Files created in Docker containers running as root

This inconsistency could mask bugs related to:
- File permissions and access control
- Directory initialization and structure
- Docker volume mounting and file ownership
- Multi-user access patterns

## Solution

All tests and Docker containers now use the **actual pipeline directories** (`/home/roredev/instrumental-maker/pipeline-data/`), with carefully configured permissions that allow:

1. **Local User Access**: `roredev` user (UID 1000) can read/write all files
2. **Docker Container Access**: Containers running as root (UID 0) can read/write all files
3. **Consistency**: Same directory structure whether testing locally or in Docker

## Directory Permissions

### Default Permission Structure

```
pipeline-data/
├── incoming/      (755) - Local user: rwx, Group: r-x, Others: r-x
├── output/        (755) - Local user: rwx, Group: r-x, Others: r-x
├── outputs/       (755) - Local user: rwx, Group: r-x, Others: r-x
├── working/       (755) - Local user: rwx, Group: r-x, Others: r-x
├── logs/          (755) - Local user: rwx, Group: r-x, Others: r-x
├── archive/       (755) - Local user: rwx, Group: r-x, Others: r-x
├── quarantine/    (755) - Local user: rwx, Group: r-x, Others: r-x
├── db/            (755) - Local user: rwx, Group: r-x, Others: r-x
├── config/        (755) - Local user: rwx, Group: r-x, Others: r-x
└── models/        (755) - Local user: rwx, Group: r-x, Others: r-x

All files: (644)  - Local user: rw-, Group: r--, Others: r--
All scripts: (755) - Local user: rwx, Group: r-x, Others: r-x
```

### Ownership

- **User**: `roredev` (UID 1000)
- **Group**: `roredev` (GID 1000)

This ensures:
- Local host user (`roredev`) owns all files
- Local user can modify files directly for testing
- Docker containers (running as root) can read/write via volume mounts
- Permission changes only occur at container startup via `fix-permissions.sh`

## How to Fix Permissions

### Automatic (Recommended)

```bash
./fix-permissions.sh
```

This script:
1. Creates missing directories
2. Changes ownership to local user
3. Sets directory permissions to 755
4. Sets file permissions to 644
5. Makes scripts executable (755)

### Manual (Advanced)

```bash
# Change ownership
sudo chown -R roredev:roredev pipeline-data/

# Set directory permissions
sudo find pipeline-data/ -type d -exec chmod 755 {} \;

# Set file permissions
sudo find pipeline-data/ -type f -exec chmod 644 {} \;

# Make scripts executable
sudo find pipeline-data/ -type f -name "*.sh" -exec chmod 755 {} \;
```

## Impact on Tests

### Before (Temp Directories)
```python
@pytest.fixture
def app():
    with tempfile.TemporaryDirectory() as tmpdir:  # ❌ Isolated, temporary
        os.environ['DB_PATH'] = tmpdir
        yield app
        # Cleanup happens automatically
```

### After (Actual Pipeline Directories)
```python
@pytest.fixture
def app():
    # ✅ Uses actual pipeline-data directory
    pipeline_root = Path(__file__).parent.parent / 'pipeline-data'
    db_dir = pipeline_root / 'db'
    db_dir.mkdir(parents=True, exist_ok=True)
    
    os.environ['DB_PATH'] = str(db_dir)
    
    app = create_app()
    yield app
    
    # Cleanup: Remove test artifacts
    test_job_dir = outputs_dir / 'test_job_001'
    if test_job_dir.exists():
        import shutil
        shutil.rmtree(test_job_dir)
```

## Benefits

1. **Consistency**: Tests operate on the same directories as production
2. **Real-world Simulation**: Test with actual file I/O patterns
3. **Permission Testing**: Validate Docker volume access control
4. **Debugging**: Inspect test artifacts in actual locations
5. **CI/CD Compatible**: Works in both local and containerized environments

## Modified Test Files

- ✅ `tests/test_phase1_dashboard.py` - Updated to use pipeline directories
- ✅ `tests/test_phase2_settings.py` - Updated to use pipeline directories
- ✅ `tests/test_phase3_monitoring.py` - Updated to use pipeline directories

## Test Results

All 28 tests pass with actual pipeline directories:
```
tests/test_phase1_dashboard.py ✓ (3 tests)
tests/test_phase2_settings.py  ✓ (4 tests)
tests/test_phase3_monitoring.py ✓ (21 tests)
─────────────────────────────────────────
TOTAL: 28 tests PASSED
```

## Troubleshooting

### Permission Denied Errors
```bash
# Run permission fix
./fix-permissions.sh

# Or manually fix:
sudo chown -R roredev:roredev pipeline-data/
sudo find pipeline-data/ -type d -exec chmod 755 {} \;
sudo find pipeline-data/ -type f -exec chmod 644 {} \;
```

### Docker Container Can't Write Files
```bash
# Verify Docker volume mount is correct in docker-compose.yml
volumes:
  - ./pipeline-data/output:/data/output  # Maps to 755 directory

# Inside container, verify permissions:
ls -la /data/output  # Should show 755, writable
```

### Test Artifacts Not Cleaned Up
```bash
# Manually remove test artifacts
rm -rf pipeline-data/outputs/test_job_*
rm -f pipeline-data/logs/nas_sync.jsonl

# Re-run tests
pytest tests/test_phase*.py -v
```

## Environment Variables

All components respect these environment variables:

```bash
DB_PATH=/home/roredev/instrumental-maker/pipeline-data/db
OUTPUTS_DIR=/home/roredev/instrumental-maker/pipeline-data/outputs
NAS_SYNC_LOG=/home/roredev/instrumental-maker/pipeline-data/logs/nas_sync.jsonl
```

These are automatically set by:
- Flask app (`app.webui.app.create_app()`)
- Test fixtures (all three phases)
- Docker Compose (`.env` file)

## Running Tests

```bash
# All WebUI tests with actual pipeline directories
pytest tests/test_phase1_dashboard.py tests/test_phase2_settings.py tests/test_phase3_monitoring.py -v

# Run with coverage
pytest tests/test_phase*.py --cov=app.webui --cov-report=html

# Run specific test
pytest tests/test_phase3_monitoring.py::TestNASSyncStatus -v
```

## Future Enhancements

1. **CI/CD Integration**: Add permission check to GitHub Actions
2. **Permission Monitoring**: Log permission changes during test execution
3. **Multi-user Support**: Configure for multiple local users
4. **Container Volumes**: Optimize volume mount permissions
5. **Network Shares**: Extend permissions for NAS mount points

## References

- Linux File Permissions: `man chmod`, `man chown`
- Docker Volume Mounts: https://docs.docker.com/storage/volumes/
- Python `pathlib`: https://docs.python.org/3/library/pathlib.html
- pytest Fixtures: https://docs.pytest.org/en/stable/fixture.html
