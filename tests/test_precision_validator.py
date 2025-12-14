"""Tests for PrecisionValidator service"""
import pytest
from decimal import Decimal

from app.services.precision_validator import PrecisionValidator


@pytest.fixture
def complete_rules():
    """Complete precision rules for multiple symbols"""
    return {
        "BTCUSDT": {
            "tick_size": Decimal("0.01"),
            "step_size": Decimal("0.001"),
            "min_qty": Decimal("0.00001"),
            "min_notional": Decimal("10")
        },
        "ETHUSDT": {
            "tick_size": Decimal("0.01"),
            "step_size": Decimal("0.0001"),
            "min_qty": Decimal("0.0001"),
            "min_notional": Decimal("5")
        }
    }


@pytest.fixture
def incomplete_rules():
    """Incomplete precision rules (missing some fields)"""
    return {
        "BTCUSDT": {
            "tick_size": Decimal("0.01"),
            "step_size": Decimal("0.001")
            # Missing min_qty and min_notional
        }
    }


@pytest.fixture
def fallback_rules():
    """Default fallback rules"""
    return {
        "tick_size": Decimal("0.01"),
        "step_size": Decimal("0.01"),
        "min_qty": Decimal("0.001"),
        "min_notional": Decimal("10")
    }


class TestPrecisionValidatorInit:
    """Tests for PrecisionValidator initialization"""

    def test_init_with_defaults(self, complete_rules):
        """Test initialization with default settings"""
        validator = PrecisionValidator(complete_rules)

        assert validator.rules == complete_rules
        assert validator.fallback_rules == {}
        assert validator.block_on_missing is True

    def test_init_with_fallback(self, complete_rules, fallback_rules):
        """Test initialization with fallback rules"""
        validator = PrecisionValidator(
            precision_rules=complete_rules,
            fallback_rules=fallback_rules
        )

        assert validator.fallback_rules == fallback_rules

    def test_init_with_block_on_missing_false(self, complete_rules):
        """Test initialization with block_on_missing=False"""
        validator = PrecisionValidator(
            precision_rules=complete_rules,
            block_on_missing=False
        )

        assert validator.block_on_missing is False


class TestValidateSymbol:
    """Tests for validate_symbol method"""

    def test_validate_symbol_exists_complete(self, complete_rules):
        """Test validation of symbol with complete metadata"""
        validator = PrecisionValidator(complete_rules)

        assert validator.validate_symbol("BTCUSDT") is True
        assert validator.validate_symbol("ETHUSDT") is True

    def test_validate_symbol_not_found_block(self, complete_rules):
        """Test validation fails for unknown symbol when blocking"""
        validator = PrecisionValidator(complete_rules, block_on_missing=True)

        assert validator.validate_symbol("UNKNOWN") is False

    def test_validate_symbol_not_found_allow(self, complete_rules, fallback_rules):
        """Test validation passes for unknown symbol when not blocking"""
        validator = PrecisionValidator(
            precision_rules=complete_rules,
            fallback_rules=fallback_rules,
            block_on_missing=False
        )

        assert validator.validate_symbol("UNKNOWN") is True

    def test_validate_symbol_incomplete_block(self, incomplete_rules):
        """Test validation fails for incomplete metadata when blocking"""
        validator = PrecisionValidator(incomplete_rules, block_on_missing=True)

        assert validator.validate_symbol("BTCUSDT") is False

    def test_validate_symbol_incomplete_allow(self, incomplete_rules, fallback_rules):
        """Test validation passes for incomplete metadata when not blocking"""
        validator = PrecisionValidator(
            precision_rules=incomplete_rules,
            fallback_rules=fallback_rules,
            block_on_missing=False
        )

        assert validator.validate_symbol("BTCUSDT") is True

    def test_validate_symbol_missing_tick_size(self, fallback_rules):
        """Test validation with missing tick_size field"""
        rules = {
            "BTCUSDT": {
                "step_size": Decimal("0.001"),
                "min_qty": Decimal("0.00001"),
                "min_notional": Decimal("10")
            }
        }
        validator = PrecisionValidator(rules, block_on_missing=True)

        assert validator.validate_symbol("BTCUSDT") is False

    def test_validate_symbol_missing_step_size(self, fallback_rules):
        """Test validation with missing step_size field"""
        rules = {
            "BTCUSDT": {
                "tick_size": Decimal("0.01"),
                "min_qty": Decimal("0.00001"),
                "min_notional": Decimal("10")
            }
        }
        validator = PrecisionValidator(rules, block_on_missing=True)

        assert validator.validate_symbol("BTCUSDT") is False

    def test_validate_symbol_missing_min_qty(self, fallback_rules):
        """Test validation with missing min_qty field"""
        rules = {
            "BTCUSDT": {
                "tick_size": Decimal("0.01"),
                "step_size": Decimal("0.001"),
                "min_notional": Decimal("10")
            }
        }
        validator = PrecisionValidator(rules, block_on_missing=True)

        assert validator.validate_symbol("BTCUSDT") is False

    def test_validate_symbol_missing_min_notional(self, fallback_rules):
        """Test validation with missing min_notional field"""
        rules = {
            "BTCUSDT": {
                "tick_size": Decimal("0.01"),
                "step_size": Decimal("0.001"),
                "min_qty": Decimal("0.00001")
            }
        }
        validator = PrecisionValidator(rules, block_on_missing=True)

        assert validator.validate_symbol("BTCUSDT") is False


class TestGetPrecisionForSymbol:
    """Tests for get_precision_for_symbol method"""

    def test_get_precision_complete(self, complete_rules):
        """Test getting precision for symbol with complete rules"""
        validator = PrecisionValidator(complete_rules)

        result = validator.get_precision_for_symbol("BTCUSDT")

        assert result["tick_size"] == Decimal("0.01")
        assert result["step_size"] == Decimal("0.001")
        assert result["min_qty"] == Decimal("0.00001")
        assert result["min_notional"] == Decimal("10")

    def test_get_precision_symbol_not_found_uses_fallback(self, complete_rules, fallback_rules):
        """Test getting precision for unknown symbol uses fallback"""
        validator = PrecisionValidator(
            precision_rules=complete_rules,
            fallback_rules=fallback_rules,
            block_on_missing=False
        )

        result = validator.get_precision_for_symbol("UNKNOWN")

        assert result == fallback_rules

    def test_get_precision_incomplete_merges_fallback(self, incomplete_rules, fallback_rules):
        """Test getting precision for incomplete rules merges with fallback"""
        validator = PrecisionValidator(
            precision_rules=incomplete_rules,
            fallback_rules=fallback_rules,
            block_on_missing=False
        )

        result = validator.get_precision_for_symbol("BTCUSDT")

        # Should have values from both
        assert result["tick_size"] == Decimal("0.01")  # From incomplete rules
        assert result["step_size"] == Decimal("0.001")  # From incomplete rules
        assert result["min_qty"] == Decimal("0.001")  # From fallback
        assert result["min_notional"] == Decimal("10")  # From fallback

    def test_get_precision_empty_rules_uses_fallback(self, fallback_rules):
        """Test getting precision when rules are empty"""
        validator = PrecisionValidator(
            precision_rules={},
            fallback_rules=fallback_rules,
            block_on_missing=False
        )

        result = validator.get_precision_for_symbol("BTCUSDT")

        assert result == fallback_rules

    def test_get_precision_no_fallback_returns_empty(self):
        """Test getting precision without fallback returns empty dict"""
        validator = PrecisionValidator(
            precision_rules={},
            fallback_rules={},
            block_on_missing=False
        )

        result = validator.get_precision_for_symbol("BTCUSDT")

        assert result == {}

    def test_get_precision_partial_overlap(self, fallback_rules):
        """Test merging with partial overlap"""
        rules = {
            "BTCUSDT": {
                "tick_size": Decimal("0.001"),  # Different from fallback
                "step_size": Decimal("0.0001")  # Different from fallback
                # min_qty and min_notional from fallback
            }
        }
        validator = PrecisionValidator(
            precision_rules=rules,
            fallback_rules=fallback_rules,
            block_on_missing=False
        )

        result = validator.get_precision_for_symbol("BTCUSDT")

        # Symbol-specific values override fallback
        assert result["tick_size"] == Decimal("0.001")
        assert result["step_size"] == Decimal("0.0001")
        # Fallback fills missing
        assert result["min_qty"] == Decimal("0.001")
        assert result["min_notional"] == Decimal("10")


class TestPrecisionValidatorIntegration:
    """Integration tests for PrecisionValidator"""

    def test_validate_then_get_precision_complete(self, complete_rules):
        """Test workflow: validate then get precision for valid symbol"""
        validator = PrecisionValidator(complete_rules)

        # First validate
        assert validator.validate_symbol("BTCUSDT") is True

        # Then get precision
        precision = validator.get_precision_for_symbol("BTCUSDT")
        assert "tick_size" in precision
        assert "step_size" in precision

    def test_validate_then_get_precision_with_fallback(self, complete_rules, fallback_rules):
        """Test workflow with fallback for unknown symbol"""
        validator = PrecisionValidator(
            precision_rules=complete_rules,
            fallback_rules=fallback_rules,
            block_on_missing=False
        )

        # Validate passes due to fallback
        assert validator.validate_symbol("NEWCOIN") is True

        # Get precision returns fallback
        precision = validator.get_precision_for_symbol("NEWCOIN")
        assert precision == fallback_rules

    def test_block_mode_prevents_trading(self, complete_rules):
        """Test that block mode prevents trading on unknown symbols"""
        validator = PrecisionValidator(complete_rules, block_on_missing=True)

        # Unknown symbol blocked
        assert validator.validate_symbol("UNKNOWN") is False

        # Known symbol allowed
        assert validator.validate_symbol("BTCUSDT") is True

    def test_lenient_mode_allows_trading(self, complete_rules, fallback_rules):
        """Test that lenient mode allows trading on unknown symbols"""
        validator = PrecisionValidator(
            precision_rules=complete_rules,
            fallback_rules=fallback_rules,
            block_on_missing=False
        )

        # All symbols allowed
        assert validator.validate_symbol("UNKNOWN") is True
        assert validator.validate_symbol("BTCUSDT") is True
        assert validator.validate_symbol("ANYNEWSYMBOL") is True
