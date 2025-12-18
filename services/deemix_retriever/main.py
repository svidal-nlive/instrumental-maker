"""Main entry point for Deemix Retriever service."""

import sys
import logging
import signal
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import queue
import threading
import time

from config import Config
from retriever import DeemixRetriever, DeemixDownloadError
from job_producer import JobBundleProducer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


class DeemixService:
    """Main service for retrieving from Deezer and producing job bundles."""
    
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.retriever = DeemixRetriever(cfg)
        self.producer = JobBundleProducer(cfg)
        self.running = True
        self.download_queue = queue.Queue()
        self.executor = ThreadPoolExecutor(max_workers=cfg.MAX_CONCURRENT)
    
    def start(self):
        """Start the service."""
        logger.info("Starting Deemix Retriever Service")
        logger.info(f"Config: {self.cfg.to_dict()}")
        
        # Ensure directories exist
        self.cfg.ensure_directories()
        
        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        # Start worker threads
        worker_threads = [
            threading.Thread(target=self._download_worker, daemon=True)
            for _ in range(self.cfg.MAX_CONCURRENT)
        ]
        
        for t in worker_threads:
            t.start()
        
        logger.info("Worker threads started")
        
        # Start watchdog for incoming download requests
        # In practice, this could be:
        # 1. API endpoint accepting POST requests
        # 2. Watching a specific directory for .deezer files
        # 3. Consuming from a message queue (Redis, RabbitMQ)
        # 4. Watching a database table
        
        # For now, provide simple example: watch for .deezer files in a directory
        watch_dir = Path(self.cfg.QUEUE_OTHER).parent / "deemix_requests"
        watch_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            self._watch_for_requests(watch_dir, worker_threads)
        except KeyboardInterrupt:
            logger.info("Shutdown requested")
        finally:
            self._shutdown()
    
    def _watch_for_requests(self, watch_dir: Path, worker_threads: list):
        """Watch directory for download requests."""
        logger.info(f"Watching {watch_dir} for download requests")
        
        seen = set()
        
        while self.running:
            try:
                # Look for .deezer request files
                for req_file in watch_dir.glob("*.deezer"):
                    if req_file.name in seen:
                        continue
                    
                    try:
                        url = req_file.read_text().strip()
                        logger.info(f"Found request: {url}")
                        self.download_queue.put((url, req_file))
                        seen.add(req_file.name)
                    except Exception as e:
                        logger.error(f"Error reading {req_file}: {e}")
                
                time.sleep(self.cfg.WATCH_INTERVAL)
            
            except Exception as e:
                logger.error(f"Error in watch loop: {e}")
                time.sleep(self.cfg.WATCH_INTERVAL)
    
    def _download_worker(self):
        """Worker thread that processes download requests."""
        logger.info(f"Download worker started")
        
        while self.running:
            try:
                # Non-blocking get with timeout
                url, req_file = self.download_queue.get(timeout=5)
                
                try:
                    logger.info(f"Processing: {url}")
                    
                    # Download and validate
                    result = self.retriever.download_and_validate(url)
                    
                    # Produce job bundle
                    bundle_path = self.producer.produce_bundle(result)
                    
                    if bundle_path:
                        logger.info(f"✓ Successfully created bundle: {bundle_path.name}")
                    else:
                        logger.error(f"✗ Failed to create bundle for {url}")
                    
                    # Cleanup temp directory
                    if "job_id" in result:
                        temp_dir = Path(self.cfg.WORKING_DIR) / f"{result['job_id']}.tmp"
                        self.retriever.cleanup_temp(temp_dir)
                
                except DeemixDownloadError as e:
                    logger.error(f"Download failed for {url}: {e}")
                    if self.cfg.SKIP_ON_ERROR:
                        logger.info("Continuing due to SKIP_ON_ERROR=true")
                    else:
                        logger.error("Stopping due to download error")
                        self.running = False
                
                except Exception as e:
                    logger.error(f"Unexpected error: {e}", exc_info=True)
                
                finally:
                    # Clean up request file
                    try:
                        req_file.unlink()
                        logger.info(f"Cleaned up request file: {req_file.name}")
                    except Exception as e:
                        logger.warning(f"Could not delete request file: {e}")
            
            except queue.Empty:
                # Normal - no items in queue
                pass
            except Exception as e:
                logger.error(f"Worker error: {e}", exc_info=True)
    
    def _signal_handler(self, signum, frame):
        """Handle termination signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    def _shutdown(self):
        """Gracefully shutdown the service."""
        logger.info("Shutting down...")
        self.running = False
        
        # Wait for executor to finish
        self.executor.shutdown(wait=True, timeout=30)
        
        logger.info("Service stopped")


def main():
    """Entry point."""
    try:
        cfg = Config()
        service = DeemixService(cfg)
        service.start()
        return 0
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
