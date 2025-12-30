"""
Base Validators for Demo Framework.

Provides assertion-style validators for checking position state,
queue state, order state, and risk engine state.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


@dataclass
class ValidationResult:
    """Result of a validation check."""
    passed: bool
    name: str
    expected: Any
    actual: Any
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.passed


class BaseValidator:
    """
    Base class for validators.

    Validators provide assertion-style checks with detailed
    expected/actual reporting for demo presentations.
    """

    @staticmethod
    def equals(
        name: str,
        expected: Any,
        actual: Any,
        message: str = "",
    ) -> ValidationResult:
        """Check if two values are equal."""
        passed = expected == actual
        return ValidationResult(
            passed=passed,
            name=name,
            expected=expected,
            actual=actual,
            message=message or f"Expected {expected}, got {actual}",
        )

    @staticmethod
    def not_equals(
        name: str,
        not_expected: Any,
        actual: Any,
        message: str = "",
    ) -> ValidationResult:
        """Check if value is not equal to something."""
        passed = not_expected != actual
        return ValidationResult(
            passed=passed,
            name=name,
            expected=f"not {not_expected}",
            actual=actual,
            message=message or f"Expected not {not_expected}, got {actual}",
        )

    @staticmethod
    def greater_than(
        name: str,
        threshold: Union[int, float],
        actual: Union[int, float],
        message: str = "",
    ) -> ValidationResult:
        """Check if value is greater than threshold."""
        passed = actual > threshold
        return ValidationResult(
            passed=passed,
            name=name,
            expected=f"> {threshold}",
            actual=actual,
            message=message or f"Expected > {threshold}, got {actual}",
        )

    @staticmethod
    def less_than(
        name: str,
        threshold: Union[int, float],
        actual: Union[int, float],
        message: str = "",
    ) -> ValidationResult:
        """Check if value is less than threshold."""
        passed = actual < threshold
        return ValidationResult(
            passed=passed,
            name=name,
            expected=f"< {threshold}",
            actual=actual,
            message=message or f"Expected < {threshold}, got {actual}",
        )

    @staticmethod
    def in_range(
        name: str,
        min_val: Union[int, float],
        max_val: Union[int, float],
        actual: Union[int, float],
        message: str = "",
    ) -> ValidationResult:
        """Check if value is within range (inclusive)."""
        passed = min_val <= actual <= max_val
        return ValidationResult(
            passed=passed,
            name=name,
            expected=f"{min_val} <= x <= {max_val}",
            actual=actual,
            message=message or f"Expected {min_val}-{max_val}, got {actual}",
        )

    @staticmethod
    def contains(
        name: str,
        expected_item: Any,
        collection: List,
        message: str = "",
    ) -> ValidationResult:
        """Check if collection contains item."""
        passed = expected_item in collection
        return ValidationResult(
            passed=passed,
            name=name,
            expected=f"contains {expected_item}",
            actual=f"list of {len(collection)} items",
            message=message or f"Expected {expected_item} in collection",
        )

    @staticmethod
    def not_contains(
        name: str,
        item: Any,
        collection: List,
        message: str = "",
    ) -> ValidationResult:
        """Check if collection does not contain item."""
        passed = item not in collection
        return ValidationResult(
            passed=passed,
            name=name,
            expected=f"not contains {item}",
            actual=f"list of {len(collection)} items",
            message=message or f"Expected {item} not in collection",
        )

    @staticmethod
    def is_true(
        name: str,
        value: bool,
        message: str = "",
    ) -> ValidationResult:
        """Check if value is True."""
        return ValidationResult(
            passed=value is True,
            name=name,
            expected=True,
            actual=value,
            message=message or f"Expected True, got {value}",
        )

    @staticmethod
    def is_false(
        name: str,
        value: bool,
        message: str = "",
    ) -> ValidationResult:
        """Check if value is False."""
        return ValidationResult(
            passed=value is False,
            name=name,
            expected=False,
            actual=value,
            message=message or f"Expected False, got {value}",
        )

    @staticmethod
    def is_none(
        name: str,
        value: Any,
        message: str = "",
    ) -> ValidationResult:
        """Check if value is None."""
        return ValidationResult(
            passed=value is None,
            name=name,
            expected=None,
            actual=value,
            message=message or f"Expected None, got {value}",
        )

    @staticmethod
    def is_not_none(
        name: str,
        value: Any,
        message: str = "",
    ) -> ValidationResult:
        """Check if value is not None."""
        return ValidationResult(
            passed=value is not None,
            name=name,
            expected="not None",
            actual=value,
            message=message or f"Expected not None, got {value}",
        )

    @staticmethod
    def has_length(
        name: str,
        expected_length: int,
        collection: List,
        message: str = "",
    ) -> ValidationResult:
        """Check if collection has expected length."""
        actual_length = len(collection)
        passed = actual_length == expected_length
        return ValidationResult(
            passed=passed,
            name=name,
            expected=expected_length,
            actual=actual_length,
            message=message or f"Expected length {expected_length}, got {actual_length}",
        )

    @staticmethod
    def in_list(
        name: str,
        expected_values: List,
        actual: Any,
        message: str = "",
    ) -> ValidationResult:
        """Check if value is one of expected values."""
        passed = actual in expected_values
        return ValidationResult(
            passed=passed,
            name=name,
            expected=f"one of {expected_values}",
            actual=actual,
            message=message or f"Expected one of {expected_values}, got {actual}",
        )


class PositionValidator(BaseValidator):
    """Validators specific to position state."""

    @staticmethod
    def has_status(
        position: Dict,
        expected_status: str,
    ) -> ValidationResult:
        """Check if position has expected status."""
        actual = position.get("status", "N/A")
        return ValidationResult(
            passed=actual == expected_status,
            name="Position status",
            expected=expected_status,
            actual=actual,
        )

    @staticmethod
    def has_symbol(
        position: Dict,
        expected_symbol: str,
    ) -> ValidationResult:
        """Check if position has expected symbol."""
        actual = position.get("symbol", "N/A")
        return ValidationResult(
            passed=actual == expected_symbol,
            name="Position symbol",
            expected=expected_symbol,
            actual=actual,
        )

    @staticmethod
    def has_pyramid_count(
        position: Dict,
        expected_count: int,
    ) -> ValidationResult:
        """Check if position has expected pyramid count."""
        actual = position.get("pyramid_count", 0)
        return ValidationResult(
            passed=actual == expected_count,
            name="Pyramid count",
            expected=expected_count,
            actual=actual,
        )

    @staticmethod
    def is_in_profit(position: Dict) -> ValidationResult:
        """Check if position is in profit."""
        pnl = float(position.get("unrealized_pnl_percent", 0) or 0)
        return ValidationResult(
            passed=pnl > 0,
            name="Position in profit",
            expected="> 0%",
            actual=f"{pnl:.2f}%",
        )

    @staticmethod
    def is_in_loss(position: Dict) -> ValidationResult:
        """Check if position is in loss."""
        pnl = float(position.get("unrealized_pnl_percent", 0) or 0)
        return ValidationResult(
            passed=pnl < 0,
            name="Position in loss",
            expected="< 0%",
            actual=f"{pnl:.2f}%",
        )

    @staticmethod
    def is_risk_eligible(position: Dict) -> ValidationResult:
        """Check if position is risk eligible."""
        eligible = position.get("risk_eligible", False)
        return ValidationResult(
            passed=eligible is True,
            name="Risk eligible",
            expected=True,
            actual=eligible,
        )

    @staticmethod
    def is_not_risk_blocked(position: Dict) -> ValidationResult:
        """Check if position is not risk blocked."""
        blocked = position.get("risk_blocked", False)
        return ValidationResult(
            passed=blocked is False,
            name="Not risk blocked",
            expected=False,
            actual=blocked,
        )

    @staticmethod
    def has_filled_quantity(
        position: Dict,
        min_quantity: float = 0,
    ) -> ValidationResult:
        """Check if position has filled quantity above minimum."""
        qty = float(position.get("total_filled_quantity", 0) or 0)
        return ValidationResult(
            passed=qty > min_quantity,
            name="Filled quantity",
            expected=f"> {min_quantity}",
            actual=qty,
        )


class QueueValidator(BaseValidator):
    """Validators specific to queue state."""

    @staticmethod
    def signal_exists(
        queue: List[Dict],
        symbol: str,
    ) -> ValidationResult:
        """Check if signal exists in queue for symbol."""
        symbols = [s.get("symbol") for s in queue]
        passed = symbol in symbols
        return ValidationResult(
            passed=passed,
            name=f"Signal for {symbol} in queue",
            expected="exists",
            actual="exists" if passed else "not found",
        )

    @staticmethod
    def signal_not_exists(
        queue: List[Dict],
        symbol: str,
    ) -> ValidationResult:
        """Check if signal does not exist in queue for symbol."""
        symbols = [s.get("symbol") for s in queue]
        passed = symbol not in symbols
        return ValidationResult(
            passed=passed,
            name=f"Signal for {symbol} not in queue",
            expected="not exists",
            actual="not exists" if passed else "found",
        )

    @staticmethod
    def has_replacement_count(
        signal: Dict,
        expected_count: int,
    ) -> ValidationResult:
        """Check if signal has expected replacement count."""
        actual = signal.get("replacement_count", 0)
        return ValidationResult(
            passed=actual == expected_count,
            name="Replacement count",
            expected=expected_count,
            actual=actual,
        )

    @staticmethod
    def is_highest_priority(
        queue: List[Dict],
        symbol: str,
    ) -> ValidationResult:
        """Check if symbol's signal has highest priority in queue."""
        if not queue:
            return ValidationResult(
                passed=False,
                name=f"{symbol} highest priority",
                expected="highest",
                actual="queue empty",
            )

        # Sort by priority (highest first)
        sorted_queue = sorted(
            queue,
            key=lambda s: float(s.get("priority_score", 0) or 0),
            reverse=True,
        )
        highest_symbol = sorted_queue[0].get("symbol")
        passed = highest_symbol == symbol

        return ValidationResult(
            passed=passed,
            name=f"{symbol} highest priority",
            expected=symbol,
            actual=highest_symbol,
        )


class OrderValidator(BaseValidator):
    """Validators specific to exchange orders."""

    @staticmethod
    def has_open_orders(
        orders: List[Dict],
        symbol: str,
        min_count: int = 1,
    ) -> ValidationResult:
        """Check if there are open orders for symbol."""
        symbol_orders = [o for o in orders if o.get("symbol") == symbol]
        actual = len(symbol_orders)
        passed = actual >= min_count
        return ValidationResult(
            passed=passed,
            name=f"Open orders for {symbol}",
            expected=f">= {min_count}",
            actual=actual,
        )

    @staticmethod
    def has_filled_orders(
        orders: List[Dict],
        symbol: str,
        min_count: int = 1,
    ) -> ValidationResult:
        """Check if there are filled orders for symbol."""
        symbol_orders = [
            o for o in orders
            if o.get("symbol") == symbol and o.get("status") == "FILLED"
        ]
        actual = len(symbol_orders)
        passed = actual >= min_count
        return ValidationResult(
            passed=passed,
            name=f"Filled orders for {symbol}",
            expected=f">= {min_count}",
            actual=actual,
        )


class RiskValidator(BaseValidator):
    """Validators specific to risk engine state."""

    @staticmethod
    def has_eligible_losers(
        risk_status: Dict,
        min_count: int = 1,
    ) -> ValidationResult:
        """Check if there are eligible losers."""
        losers = risk_status.get("eligible_losers", [])
        actual = len(losers)
        passed = actual >= min_count
        return ValidationResult(
            passed=passed,
            name="Eligible losers",
            expected=f">= {min_count}",
            actual=actual,
        )

    @staticmethod
    def has_eligible_winners(
        risk_status: Dict,
        min_count: int = 1,
    ) -> ValidationResult:
        """Check if there are eligible winners."""
        winners = risk_status.get("eligible_winners", [])
        actual = len(winners)
        passed = actual >= min_count
        return ValidationResult(
            passed=passed,
            name="Eligible winners",
            expected=f">= {min_count}",
            actual=actual,
        )

    @staticmethod
    def engine_is_running(risk_status: Dict) -> ValidationResult:
        """Check if risk engine is running."""
        status = risk_status.get("status", "unknown")
        passed = status in ("running", "active", "ok")
        return ValidationResult(
            passed=passed,
            name="Engine running",
            expected="running",
            actual=status,
        )
