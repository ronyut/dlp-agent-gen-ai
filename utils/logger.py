import logging
import threading
import queue
from logging.handlers import RotatingFileHandler
from utils.config_loader import app_config

class Logger:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(Logger, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        self.log_queue = queue.Queue()
        self._setup_logging()
        
        # Start the background writer thread
        self.worker = threading.Thread(target=self._log_worker, daemon=True)
        self.worker.start()
        self._initialized = True

    def _setup_logging(self):
        self.logger = logging.getLogger("DLPAgent")
        self.logger.setLevel(logging.INFO)
        
        # Rotating file: 5MB per file, keep 3 backups
        handler = RotatingFileHandler(app_config.get("logging.log_file"), maxBytes=5*1024*1024, backupCount=3)
        formatter = logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def _log_worker(self):
        """Background thread that pulls from the queue and writes to disk."""
        while True:
            try:
                record = self.log_queue.get()
                if record is None: break # Shutdown signal
                self.logger.info(record)
                self.log_queue.task_done()
            except Exception:
                pass

    def log(self, message):
        """Thread-safe way to submit a log without blocking the caller."""
        self.log_queue.put(message)

# Global singleton instance
agent_logger = Logger()