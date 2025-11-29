from decimal import Decimal, ROUND_DOWN
from typing import List, Dict, Literal
from app.schemas.grid_config import DCAGridConfig

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
        precision_rules: Dict
    ) -> List[Dict]:
        """
        Calculate DCA price levels with per-layer configuration.
        """
        tick_size = Decimal(str(precision_rules["tick_size"]))
        
        dca_levels = []
        
        for idx, layer in enumerate(dca_config.levels): # Iterate over dca_config.levels
            # Directly access attributes from DCALevelConfig objects
            gap_percent = layer.gap_percent
            weight_percent = layer.weight_percent
            tp_percent = layer.tp_percent
            
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
        step_size = Decimal(str(precision_rules["step_size"]))
        min_qty = Decimal(str(precision_rules["min_qty"]))
        min_notional = Decimal(str(precision_rules["min_notional"]))
        
        for level in dca_levels:
            # Calculate capital for this leg
            leg_capital = total_capital_usd * (level["weight_percent"] / Decimal("100"))
            
            # Calculate quantity: capital / price
            quantity = leg_capital / level["price"]
            
            # Round to step size
            quantity = round_to_step_size(quantity, step_size)
            
            # Validate minimum quantity
            if quantity < min_qty:
                raise ValidationError(
                    f"Quantity {quantity} below minimum {min_qty}"
                )
            
            # Validate minimum notional
            notional = quantity * level["price"]
            if notional < min_notional:
                raise ValidationError(
                    f"Notional {notional} below minimum {min_notional}"
                )
            
            level["quantity"] = quantity
        
        return dca_levels