import logging
from decimal import Decimal, ROUND_DOWN
from typing import List, Dict, Literal
from app.schemas.grid_config import DCAGridConfig

logger = logging.getLogger(__name__)

class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass

def round_to_tick_size(value: Decimal, tick_size: Decimal) -> Decimal:
    """
    Rounds a value to the nearest tick size.
    """
    return (value / tick_size).quantize(Decimal("1"), rounding=ROUND_DOWN) * tick_size

def round_to_step_size(value: Decimal, step_size: Decimal) -> Decimal:
    """
    Rounds a value to the nearest step size.
    """
    return (value / step_size).quantize(Decimal("1"), rounding=ROUND_DOWN) * step_size

class GridCalculatorService:
    """
    A pure service to calculate DCA grid levels based on a base price and grid configuration.
    """

    @staticmethod
    def calculate_dca_levels(
        base_price: Decimal,
        dca_config: DCAGridConfig, # Expect DCAGridConfig object
        side: Literal["long", "short"],
        precision_rules: Dict,
        pyramid_index: int = 0
    ) -> List[Dict]:
        """
        Calculate DCA price levels with per-layer configuration.
        """
        tick_size = Decimal(str(precision_rules["tick_size"]))
        
        dca_levels = []
        
        # Resolve specific levels for this pyramid index
        levels_config = dca_config.get_levels_for_pyramid(pyramid_index)
        
        for idx, layer in enumerate(levels_config): # Iterate over resolved levels
            # Directly access attributes from DCALevelConfig objects
            gap_percent = layer.gap_percent
            weight_percent = layer.weight_percent
            
            # Determine Effective TP Percent based on Mode
            tp_percent = layer.tp_percent # Default to per-leg
            
            if dca_config.tp_mode == "pyramid":
                # In Pyramid mode, use the unified pyramid_tp_percent if available
                # Schema might strictly define this field, ensure we access it safely
                # Check if alias exists or direct access
                if hasattr(dca_config, "tp_pyramid_percent") and dca_config.tp_pyramid_percent > 0:
                     tp_percent = dca_config.tp_pyramid_percent
            
            elif dca_config.tp_mode == "hybrid":
                # In Hybrid, "First Trigger Wins". We place the Limit Order at the closest target.
                # Usually Per Leg, but if Pyramid is set and tighter, we could use that?
                # For simplicity and typical use, Hybrid uses Per Leg for the Limit Order,
                # and Aggregate/Pyramid monitors run in background.
                # If both act as Limit Orders, we'd need OCO. We assume Per Leg takes precedence for the Limit Order.
                tp_percent = layer.tp_percent
                pass

            # Calculate DCA entry price
            if side == "long":
                dca_price = base_price * (Decimal("1") + gap_percent / Decimal("100"))
            else:
                dca_price = base_price * (Decimal("1") - gap_percent / Decimal("100"))
            
            dca_price = round_to_tick_size(dca_price, tick_size)
            
            # Calculate TP price
            if side == "long":
                tp_price = dca_price * (Decimal("1") + tp_percent / Decimal("100"))
            else:
                tp_price = dca_price * (Decimal("1") - tp_percent / Decimal("100"))
                
            tp_price = round_to_tick_size(tp_price, tick_size)

            dca_levels.append({
                "leg_index": idx,
                "price": dca_price,
                "gap_percent": gap_percent,
                "weight_percent": weight_percent,
                "tp_percent": tp_percent,
                "tp_price": tp_price
            })
        
        return dca_levels

    @staticmethod
    def calculate_pyramid_levels(
        base_price: Decimal,
        pyramid_gap_percent: Decimal,
        side: Literal["long", "short"],
        precision_rules: Dict
    ) -> Dict:
        """
        Calculate the next pyramid entry price.
        """
        tick_size = Decimal(str(precision_rules["tick_size"]))
        
        if side == "long":
            entry_price = base_price * (Decimal("1") + pyramid_gap_percent / Decimal("100"))
        else:
            entry_price = base_price * (Decimal("1") - pyramid_gap_percent / Decimal("100"))
            
        entry_price = round_to_tick_size(entry_price, tick_size)
        
        return {
            "entry_price": entry_price
        }

    @staticmethod
    def calculate_order_quantities(
        dca_levels: List[Dict],
        total_capital_usd: Decimal,
        precision_rules: Dict
    ) -> List[Dict]:
        """
        Calculate order quantity for each DCA level based on weight allocation.
        """
        logger.debug(f"Entering calculate_order_quantities. Total Capital USD: {total_capital_usd}, Precision Rules: {precision_rules}")
        logger.debug(f"DCA Levels received: {dca_levels}")

        step_size = Decimal(str(precision_rules.get("step_size", "0.000001")))  # Fallback
        min_qty = Decimal(str(precision_rules.get("min_qty", "0.000001")))      # Fallback
        min_notional = Decimal(str(precision_rules.get("min_notional", "1")))    # Fallback
        
        logger.debug(f"Exchange Minimums: min_qty={min_qty}, min_notional={min_notional}, step_size={step_size}")

        for i, level in enumerate(dca_levels):
            logger.debug(f"Processing level {i}: Price={level['price']}, Weight={level['weight_percent']}%")
            
            # Calculate capital for this leg
            leg_capital = total_capital_usd * (level["weight_percent"] / Decimal("100"))
            logger.debug(f"  Calculated leg capital: {leg_capital}")

            # Calculate quantity: capital / price
            if level["price"] <= 0:
                logger.error(f"  Validation Error: Price is zero or negative for level {i}, skipping.")
                # This should ideally raise an error or be handled upstream to prevent invalid prices.
                # For now, we'll continue, but this indicates a potential data issue.
                continue  

            quantity = leg_capital / level["price"]
            logger.debug(f"  Raw quantity before rounding: {quantity}")
            
            # Round to step size
            quantity = round_to_step_size(quantity, step_size)
            logger.debug(f"  Quantity after rounding (step_size={step_size}): {quantity}")

            # Validate minimum quantity
            if quantity < min_qty:
                logger.error(f"  Validation Error: Calculated quantity {quantity} is below exchange min_qty {min_qty} for level {i}.")
                raise ValidationError(
                    f"Quantity {quantity} below minimum {min_qty}"
                )
            
            # Validate minimum notional
            notional = quantity * level["price"]
            logger.debug(f"  Calculated notional: {notional} (min_notional={min_notional})")

            if notional < min_notional:
                logger.error(f"  Validation Error: Calculated notional {notional} is below exchange min_notional {min_notional} for level {i}.")
                raise ValidationError(
                    f"Notional {notional} below minimum {min_notional}"
                )
            
            level["quantity"] = quantity
            logger.debug(f"  Level {i} quantity set to {quantity}")
        
        logger.debug("Exiting calculate_order_quantities successfully.")
        return dca_levels