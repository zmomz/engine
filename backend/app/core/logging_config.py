import logging
import logging.handlers
import os
from pathlib import Path

def setup_logging():
    """
    Configures the logging for the application.
    Writes logs to stdout and to a rotating file in the logs/ directory.
    """
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "app.log"

    # Create formatters
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # File Handler (Rotating)
    # Rotates when file size reaches 10MB, keeps 5 backup files
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5
    )
    file_handler.setFormatter(formatter)

    # Root Logger Configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Remove existing handlers to avoid duplicates if called multiple times
    root_logger.handlers = []
    
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Set specific levels for noisy libraries if needed
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    
    return log_file
