#!/usr/bin/env python3
"""
YouTube retriever service: watches for download requests and produces job bundles.

Usage:
  python3 main.py <url>                    # Process single URL
  python3 main.py --watch                  # Watch /data/requests/ for URLs
  python3 main.py --daemon                 # Run continuously
"""

import sys
import logging
from pathlib import Path
from typing import Optional

from config import Config
from retriever import YouTubeRetriever, DurationMismatchError
from job_producer import JobBundleProducer


def setup_logging(cfg: Config):
    """Configure logging."""
    log_dir = Path(cfg.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_level = getattr(logging, cfg.LOG_LEVEL.upper(), logging.INFO)
    
    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s] %(levelname)s: %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "youtube_retriever.log"),
            logging.StreamHandler(),
        ]
    )


def process_url(url: str, cfg: Config) -> bool:
    """Process a single URL and produce job bundle."""
    logger = logging.getLogger(__name__)
    
    logger.info(f"Processing URL: {url}")
    
    try:
        # Download and validate
        retriever = YouTubeRetriever(cfg)
        result = retriever.download_and_validate(url)
        
        # Produce job bundle
        producer = JobBundleProducer(cfg)
        bundle_path = producer.produce_bundle(result)
        
        if bundle_path:
            logger.info(f"Success: Job bundle created at {bundle_path}")
            return True
        else:
            logger.error("Failed to create job bundle")
            return False
    
    except DurationMismatchError as e:
        logger.error(f"Duration validation failed: {e}")
        return False
    
    except Exception as e:
        logger.error(f"Processing failed: {e}", exc_info=True)
        return False


def watch_requests(cfg: Config) -> None:
    """Watch requests folder for URLs to download."""
    logger = logging.getLogger(__name__)
    requests_dir = Path(cfg.REQUESTS_DIR)
    requests_dir.mkdir(parents=True, exist_ok=True)
    
    import time
    
    logger.info(f"Watching {requests_dir} for download requests...")
    processed = set()
    
    while True:
        try:
            # Look for .txt or .url files
            for req_file in requests_dir.glob("*.txt"):
                if req_file.name in processed:
                    continue
                
                try:
                    url = req_file.read_text().strip()
                    if url and not url.startswith("#"):
                        logger.info(f"Found request: {req_file.name}")
                        success = process_url(url, cfg)
                        
                        if success:
                            req_file.rename(req_file.with_suffix(".done"))
                        else:
                            req_file.rename(req_file.with_suffix(".fail"))
                        
                        processed.add(req_file.name)
                
                except Exception as e:
                    logger.error(f"Error processing {req_file.name}: {e}")
            
            time.sleep(5)  # Check every 5 seconds
        
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            break
        except Exception as e:
            logger.error(f"Watch error: {e}", exc_info=True)
            time.sleep(5)


def main():
    """Main entry point."""
    cfg = Config()
    setup_logging(cfg)
    
    logger = logging.getLogger(__name__)
    logger.info("YouTube Retriever Service Starting")
    logger.info(f"Mode: {cfg.MODE}")
    logger.info(f"Audio format: {cfg.AUDIO_FORMAT}")
    
    args = sys.argv[1:]
    
    if not args:
        print(__doc__)
        sys.exit(1)
    
    if args[0] == "--watch":
        watch_requests(cfg)
    
    elif args[0] == "--daemon":
        logger.info("Running in daemon mode (watching requests)")
        watch_requests(cfg)
    
    else:
        # Single URL
        url = args[0]
        success = process_url(url, cfg)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
