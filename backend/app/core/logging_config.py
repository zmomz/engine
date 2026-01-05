import logging
import logging.handlers
import os
import re
from pathlib import Path
from app.core.config import settings
from app.core.correlation import CorrelationIdFilter

class SensitiveDataFilter(logging.Filter):
    """
    Filter to mask sensitive data in log records.
    """
    def __init__(self, name=""):
        super().__init__(name)
        self.patterns = [
            (r"(api_key=)[\"']?([^\s\"']+)[\"']?", r"\1***MASKED***"),
            (r"(secret_key=)[\"']?([^\s\"']+)[\"']?", r"\1***MASKED***"),
            (r"(password=)[\"']?([^\s\"']+)[\"']?", r"\1***MASKED***"),
            (r"(token=)[\"']?([^\s\"']+)[\"']?", r"\1***MASKED***"),
            (r"(encrypted_api_keys=).*?([,}])", r"\1***MASKED***\2") # Mask encrypted blobs too
        ]

    def filter(self, record):
        if not isinstance(record.msg, str):
            return True
        
        msg = record.msg
        for pattern, replacement in self.patterns:
            msg = re.sub(pattern, replacement, msg, flags=re.IGNORECASE)
        
        record.msg = msg
        return True

def setup_logging():
    """
    Configures the logging for the application.
    Writes logs to stdout and to a rotating file in the configured log directory.
    """
    log_path = Path(settings.LOG_FILE_PATH)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = log_path

    # Create formatters - include correlation_id for request tracing
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - [%(correlation_id)s] - %(message)s"
    )

    # Filters
    sensitive_filter = SensitiveDataFilter()
    correlation_filter = CorrelationIdFilter()

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(sensitive_filter)
    console_handler.addFilter(correlation_filter)

    # File Handler (Rotating)
    # Rotates when file size reaches 10MB, keeps 5 backup files
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(sensitive_filter)
    file_handler.addFilter(correlation_filter)

    # Root Logger Configuration
    root_logger = logging.getLogger()
    log_level = settings.LOG_LEVEL.upper()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers to avoid duplicates if called multiple times
    root_logger.handlers = []
    
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Set specific levels for noisy libraries if needed
    # If main log level is DEBUG, these might still be too noisy, so we keep them somewhat restricted
    # unless explicitly debugging them.
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("ccxt").setLevel(logging.ERROR)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING) 
    
    return log_file