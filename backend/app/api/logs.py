from fastapi import APIRouter, HTTPException, Query, Depends
from pathlib import Path
import logging

from app.api.dependencies.users import get_current_active_user
from app.models.user import User
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

LOG_FILE_PATH = Path(settings.LOG_FILE_PATH)

@router.get("")
async def get_logs(
    lines: int = Query(100, ge=1, le=1000),
    level: str = Query(None, regex="^(INFO|WARNING|ERROR|DEBUG)$"),
    current_user: User = Depends(get_current_active_user)
):
    """
    Retrieves the last N lines of the application log.
    Optionally filters by log level (text search).
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Insufficient privileges")

    if not LOG_FILE_PATH.exists():
        return {"logs": []}

    try:
        # Efficiently read last N lines
        # This is a simple implementation; for very large files, seeking from end is better.
        # Given the rotating handler max size (10MB), reading lines is acceptable for now,
        # but we should implement a reverse read for performance.
        
        collected_logs = []
        with open(LOG_FILE_PATH, "r") as f:
            # Read all lines (potentially expensive if file is huge, but rotating handler limits it)
            # Optimization: `tail` logic in python is tricky without external libs or seeking.
            # We'll stick to reading and slicing for simplicity in this prototype.
            all_lines = f.readlines()
            
            # Filter first
            if level:
                filtered_lines = [line for line in all_lines if level in line]
            else:
                filtered_lines = all_lines
            
            # Slice last N
            collected_logs = filtered_lines[-lines:]
            
        return {"logs": [line.strip() for line in collected_logs]}
        
    except Exception as e:
        logger.error(f"Error reading log file: {e}")
        raise HTTPException(status_code=500, detail="Could not read logs")
