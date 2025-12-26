"""
Position Manager components package.

This package contains the split components of the Position Manager:
- position_creator: Position and pyramid creation logic
- position_closer: Exit and close action handling
- position_manager: Main orchestrator service
"""
from app.services.position.position_manager import (
    PositionManagerService,
    UserNotFoundException,
    DuplicatePositionException,
)
from app.services.position.position_creator import (
    create_position_group_from_signal,
    handle_pyramid_continuation,
)
from app.services.position.position_closer import (
    execute_handle_exit_signal,
    save_close_action,
)

__all__ = [
    "PositionManagerService",
    "UserNotFoundException",
    "DuplicatePositionException",
    "create_position_group_from_signal",
    "handle_pyramid_continuation",
    "execute_handle_exit_signal",
    "save_close_action",
]
