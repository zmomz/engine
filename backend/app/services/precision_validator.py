from typing import Dict, Any
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class PrecisionValidator:
    """
    Validates signals against exchange precision rules.
    Enforces the requirement: 'Block if metadata missing'.
    """
    def __init__(self, precision_rules: Dict[str, Any]):
        self.rules = precision_rules

    def validate_symbol(self, symbol: str) -> bool:
        """
        Checks if the symbol exists in the exchange metadata.
        """
        if symbol not in self.rules:
            logger.warning(f"PrecisionValidator: Metadata missing for symbol '{symbol}'.")
            return False
        
        rule = self.rules[symbol]
        required_fields = ['tick_size', 'step_size', 'min_qty', 'min_notional']
        
        for field in required_fields:
            if field not in rule:
                 logger.warning(f"PrecisionValidator: Incomplete metadata for '{symbol}'. Missing '{field}'.")
                 return False
                 
        return True
