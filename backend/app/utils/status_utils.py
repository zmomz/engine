"""
Utility functions for consistent status comparison across the application.
Handles the enum/string status inconsistency issue where OrderStatus
may be stored as string in the database but loaded as enum sometimes.
"""
from typing import Union
from app.models.dca_order import OrderStatus
from app.models.position_group import PositionGroupStatus
from app.models.pyramid import PyramidStatus


def normalize_order_status(status: Union[str, OrderStatus, None]) -> str:
    """
    Normalize an order status to a lowercase string for consistent comparison.

    Args:
        status: Can be an OrderStatus enum, string, or None

    Returns:
        Lowercase string representation of the status, or empty string if None
    """
    if status is None:
        return ""

    if isinstance(status, OrderStatus):
        return status.value.lower()

    if hasattr(status, 'value'):
        return str(status.value).lower()

    return str(status).lower().replace('orderstatus.', '')


def is_order_status(status: Union[str, OrderStatus, None], target: OrderStatus) -> bool:
    """
    Check if an order status matches the target status.
    Handles both enum and string representations.

    Args:
        status: The status to check (can be enum or string)
        target: The OrderStatus enum to compare against

    Returns:
        True if the status matches the target
    """
    normalized = normalize_order_status(status)
    return normalized == target.value.lower()


def is_order_filled(status: Union[str, OrderStatus, None]) -> bool:
    """Check if an order status indicates FILLED."""
    return is_order_status(status, OrderStatus.FILLED)


def is_order_open(status: Union[str, OrderStatus, None]) -> bool:
    """Check if an order status indicates OPEN."""
    return is_order_status(status, OrderStatus.OPEN)


def is_order_pending(status: Union[str, OrderStatus, None]) -> bool:
    """Check if an order status indicates PENDING."""
    return is_order_status(status, OrderStatus.PENDING)


def is_order_trigger_pending(status: Union[str, OrderStatus, None]) -> bool:
    """Check if an order status indicates TRIGGER_PENDING."""
    return is_order_status(status, OrderStatus.TRIGGER_PENDING)


def is_order_partially_filled(status: Union[str, OrderStatus, None]) -> bool:
    """Check if an order status indicates PARTIALLY_FILLED."""
    return is_order_status(status, OrderStatus.PARTIALLY_FILLED)


def is_order_cancelled(status: Union[str, OrderStatus, None]) -> bool:
    """Check if an order status indicates CANCELLED."""
    return is_order_status(status, OrderStatus.CANCELLED)


def is_order_failed(status: Union[str, OrderStatus, None]) -> bool:
    """Check if an order status indicates FAILED."""
    return is_order_status(status, OrderStatus.FAILED)


def is_order_active(status: Union[str, OrderStatus, None]) -> bool:
    """
    Check if an order is in an active state (not terminal).
    Active states: PENDING, TRIGGER_PENDING, OPEN, PARTIALLY_FILLED
    """
    normalized = normalize_order_status(status)
    active_states = {
        OrderStatus.PENDING.value.lower(),
        OrderStatus.TRIGGER_PENDING.value.lower(),
        OrderStatus.OPEN.value.lower(),
        OrderStatus.PARTIALLY_FILLED.value.lower()
    }
    return normalized in active_states


def is_order_terminal(status: Union[str, OrderStatus, None]) -> bool:
    """
    Check if an order is in a terminal state.
    Terminal states: FILLED, CANCELLED, FAILED
    """
    normalized = normalize_order_status(status)
    terminal_states = {
        OrderStatus.FILLED.value.lower(),
        OrderStatus.CANCELLED.value.lower(),
        OrderStatus.FAILED.value.lower()
    }
    return normalized in terminal_states


# Position Group Status Utilities

def normalize_position_status(status: Union[str, PositionGroupStatus, None]) -> str:
    """
    Normalize a position group status to a lowercase string for consistent comparison.
    """
    if status is None:
        return ""

    if isinstance(status, PositionGroupStatus):
        return status.value.lower()

    if hasattr(status, 'value'):
        return str(status.value).lower()

    return str(status).lower().replace('positiongroupstatus.', '')


def is_position_status(status: Union[str, PositionGroupStatus, None], target: PositionGroupStatus) -> bool:
    """
    Check if a position status matches the target status.
    """
    normalized = normalize_position_status(status)
    return normalized == target.value.lower()


def is_position_active(status: Union[str, PositionGroupStatus, None]) -> bool:
    """Check if a position is in an active/tradeable state."""
    normalized = normalize_position_status(status)
    active_states = {
        PositionGroupStatus.WAITING.value.lower(),
        PositionGroupStatus.LIVE.value.lower(),
        PositionGroupStatus.PARTIALLY_FILLED.value.lower(),
        PositionGroupStatus.ACTIVE.value.lower()
    }
    return normalized in active_states


def is_position_closed(status: Union[str, PositionGroupStatus, None]) -> bool:
    """Check if a position is closed."""
    return is_position_status(status, PositionGroupStatus.CLOSED)


def is_position_closing(status: Union[str, PositionGroupStatus, None]) -> bool:
    """Check if a position is in closing state."""
    return is_position_status(status, PositionGroupStatus.CLOSING)


# Pyramid Status Utilities

def normalize_pyramid_status(status: Union[str, PyramidStatus, None]) -> str:
    """
    Normalize a pyramid status to a lowercase string for consistent comparison.
    """
    if status is None:
        return ""

    if isinstance(status, PyramidStatus):
        return status.value.lower()

    if hasattr(status, 'value'):
        return str(status.value).lower()

    return str(status).lower().replace('pyramidstatus.', '')


def is_pyramid_status(status: Union[str, PyramidStatus, None], target: PyramidStatus) -> bool:
    """
    Check if a pyramid status matches the target status.
    """
    normalized = normalize_pyramid_status(status)
    return normalized == target.value.lower()


def is_pyramid_closed(status: Union[str, PyramidStatus, None]) -> bool:
    """Check if a pyramid is closed."""
    return is_pyramid_status(status, PyramidStatus.CLOSED)
