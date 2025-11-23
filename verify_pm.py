import sys
import os
sys.path.append(os.path.join(os.getcwd(), "backend"))
from unittest.mock import MagicMock

try:
    from app.services.position_manager import PositionManagerService
    print("Imported PositionManagerService")
    try:
        pm = PositionManagerService(
            session_factory=MagicMock(),
            user=MagicMock(),
            position_group_repository_class=MagicMock(),
            grid_calculator_service=MagicMock(),
            order_service_class=MagicMock(),
            exchange_connector=MagicMock()
        )
        print("Successfully instantiated PositionManagerService")
    except TypeError as e:
        print(f"Failed to instantiate: {e}")
        import inspect
        print(inspect.signature(PositionManagerService.__init__))
except ImportError as e:
    print(f"Import failed: {e}")
