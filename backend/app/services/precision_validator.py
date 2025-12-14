from typing import Dict, Any, Optional
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class PrecisionValidator:
    """
    Validates signals against exchange precision rules.

    Supports two modes controlled by `block_on_missing`:
    - True (default): Block orders when precision metadata is missing
    - False: Allow orders using fallback_rules when metadata is unavailable
    """
    def __init__(
        self,
        precision_rules: Dict[str, Any],
        fallback_rules: Optional[Dict[str, Any]] = None,
        block_on_missing: bool = True
    ):
        self.rules = precision_rules
        self.fallback_rules = fallback_rules or {}
        self.block_on_missing = block_on_missing

    def validate_symbol(self, symbol: str) -> bool:
        """
        Checks if the symbol exists in the exchange metadata.

        Returns:
            True if symbol has valid metadata OR if fallback is allowed
            False if symbol is missing and block_on_missing is True
        """
        if symbol not in self.rules:
            if self.block_on_missing:
                logger.warning(f"PrecisionValidator: Metadata missing for symbol '{symbol}'. Blocking order.")
                return False
            else:
                logger.warning(
                    f"PrecisionValidator: Metadata missing for symbol '{symbol}'. "
                    f"Using fallback rules (block_on_missing=False)."
                )
                return True

        rule = self.rules[symbol]
        required_fields = ['tick_size', 'step_size', 'min_qty', 'min_notional']

        for field in required_fields:
            if field not in rule:
                if self.block_on_missing:
                    logger.warning(
                        f"PrecisionValidator: Incomplete metadata for '{symbol}'. "
                        f"Missing '{field}'. Blocking order."
                    )
                    return False
                else:
                    logger.warning(
                        f"PrecisionValidator: Incomplete metadata for '{symbol}'. "
                        f"Missing '{field}'. Using fallback rules."
                    )
                    return True

        return True

    def get_precision_for_symbol(self, symbol: str) -> Dict[str, Any]:
        """
        Returns precision rules for a symbol, falling back to default rules if needed.

        This method should be used after validate_symbol() returns True to get
        the actual precision values to use for calculations.
        """
        if symbol in self.rules:
            rule = self.rules[symbol]
            # Check if rule is complete, otherwise merge with fallback
            required_fields = ['tick_size', 'step_size', 'min_qty', 'min_notional']
            complete = all(field in rule for field in required_fields)

            if complete:
                return rule
            else:
                # Merge with fallback for missing fields
                merged = dict(self.fallback_rules)
                merged.update(rule)
                logger.info(f"PrecisionValidator: Merged incomplete metadata for '{symbol}' with fallback rules.")
                return merged
        else:
            # Use fallback rules entirely
            logger.info(f"PrecisionValidator: Using fallback rules for '{symbol}'.")
            return dict(self.fallback_rules)
