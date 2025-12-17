#!/usr/bin/env python3
"""
NAS Sync Service - Main entry point.

Watches /outputs for manifest.json files and syncs artifacts to configured
remote paths based on kind + variant matching.

Usage:
    # Single manifest
    python main.py /data/outputs/job_123/manifest.json
    
    # Daemon mode (watch for new manifests)
    python main.py --daemon
    
    # Dry run (log but don't sync)
    python main.py --daemon --dry-run
"""

import argparse
import logging
import sys
import time
from pathlib import Path

from config import (
    OUTPUTS_DIR,
    WORK_DIR,
    LOG_FILE,
    SYNC_METHOD,
    REMOTE_ROOTS,
    ROUTES,
    DRY_RUN,
    DAEMON_MODE,
    POLL_INTERVAL_SEC,
    LOG_LEVEL,
    SKIP_ON_MISSING_REMOTE,
    RSYNC_BW_LIMIT,
    RSYNC_COMPRESS,
    S3_BUCKET,
    S3_PREFIX,
    S3_REGION,
    S3_ENDPOINT,
    SCP_HOST,
    SCP_USER,
    SCP_KEY,
    log_config,
    validate_config,
)
from manifest_processor import ManifestProcessor, RouteResolver, ManifestWatcher
from syncer import RsyncBackend, S3Backend, ScpBackend, LocalBackend

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)


def create_sync_backend():
    """Create sync backend based on SYNC_METHOD."""
    if SYNC_METHOD == "rsync":
        return RsyncBackend(bw_limit=RSYNC_BW_LIMIT, compress=RSYNC_COMPRESS)
    elif SYNC_METHOD == "s3":
        return S3Backend(
            bucket=S3_BUCKET,
            prefix=S3_PREFIX,
            region=S3_REGION,
            endpoint=S3_ENDPOINT,
        )
    elif SYNC_METHOD == "scp":
        return ScpBackend(host=SCP_HOST, user=SCP_USER, key=SCP_KEY)
    elif SYNC_METHOD == "local":
        return LocalBackend()
    else:
        raise ValueError(f"Unknown sync method: {SYNC_METHOD}")


def setup():
    """Setup work directory and logging."""
    Path(WORK_DIR).mkdir(parents=True, exist_ok=True)
    Path(OUTPUTS_DIR).mkdir(parents=True, exist_ok=True)
    Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)


def process_single_manifest(manifest_path: Path, dry_run: bool = False):
    """Process a single manifest file."""
    if not manifest_path.exists():
        logger.error(f"Manifest not found: {manifest_path}")
        return False
    
    logger.info(f"Processing manifest: {manifest_path}")
    
    # Create processor
    resolver = RouteResolver(ROUTES, REMOTE_ROOTS)
    backend = create_sync_backend()
    processor = ManifestProcessor(resolver, backend, OUTPUTS_DIR)
    
    # Process
    success, skipped = processor.process_manifest(
        manifest_path,
        dry_run=dry_run,
        skip_on_missing=SKIP_ON_MISSING_REMOTE,
    )
    
    logger.info(
        f"Manifest processed: {success} synced, {skipped} skipped/warning"
    )
    return True


def run_daemon(dry_run: bool = False, poll_interval: float = POLL_INTERVAL_SEC):
    """Run in daemon mode: watch for new manifests and process them."""
    logger.info("Starting daemon mode...")
    logger.info(f"Watching {OUTPUTS_DIR} for manifest.json files")
    logger.info(f"Poll interval: {poll_interval}s")
    
    # Create processor once
    resolver = RouteResolver(ROUTES, REMOTE_ROOTS)
    backend = create_sync_backend()
    processor = ManifestProcessor(resolver, backend, OUTPUTS_DIR)
    
    # Track processed manifests
    processed = set()
    
    try:
        while True:
            # Discover new manifests
            manifests = processor.watcher.discover_manifests()
            
            for manifest_path in manifests:
                manifest_str = str(manifest_path)
                
                # Skip if already processed
                if manifest_str in processed:
                    continue
                
                logger.info(f"Found new manifest: {manifest_path}")
                
                # Process it
                success, skipped = processor.process_manifest(
                    manifest_path,
                    dry_run=dry_run,
                    skip_on_missing=SKIP_ON_MISSING_REMOTE,
                )
                
                logger.info(
                    f"Manifest processed: {success} synced, {skipped} skipped"
                )
                
                # Mark as processed
                processed.add(manifest_str)
            
            # Wait before next poll
            time.sleep(poll_interval)
    
    except KeyboardInterrupt:
        logger.info("Daemon shutting down...")
        return True
    except Exception as e:
        logger.error(f"Daemon error: {e}", exc_info=True)
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="NAS Sync Service - sync artifacts to remote storage"
    )
    parser.add_argument(
        "manifest",
        nargs="?",
        help="Path to manifest.json to process (optional, use --daemon for watch mode)",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run in daemon mode (watch for new manifests)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log but don't actually sync",
    )
    parser.add_argument(
        "--poll",
        type=float,
        default=POLL_INTERVAL_SEC,
        help=f"Poll interval in seconds (default: {POLL_INTERVAL_SEC})",
    )
    
    args = parser.parse_args()
    
    # Setup
    setup()
    log_config()
    
    # Check for config warnings
    warnings = validate_config()
    if warnings:
        for w in warnings:
            logger.warning(f"Configuration: {w}")
    
    # Determine mode
    dry_run = args.dry_run or DRY_RUN
    
    if dry_run:
        logger.warning("DRY RUN MODE - no artifacts will be synced")
    
    if args.daemon:
        # Daemon mode
        success = run_daemon(dry_run=dry_run, poll_interval=args.poll)
        return 0 if success else 1
    
    elif args.manifest:
        # Single manifest mode
        manifest_path = Path(args.manifest)
        success = process_single_manifest(manifest_path, dry_run=dry_run)
        return 0 if success else 1
    
    else:
        # No mode specified - use default from config
        if DAEMON_MODE:
            logger.info("Using daemon mode from config")
            success = run_daemon(dry_run=dry_run, poll_interval=POLL_INTERVAL_SEC)
            return 0 if success else 1
        else:
            parser.print_help()
            logger.error("Please specify a manifest file or use --daemon")
            return 1


if __name__ == "__main__":
    sys.exit(main())
