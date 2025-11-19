import pytest
from decimal import Decimal
from app.services.grid_calculator import GridCalculatorService, ValidationError

@pytest.fixture
def grid_calculator():
    return GridCalculatorService()

def test_calculate_dca_levels_long(grid_calculator):
    base_price = Decimal("50000")
    dca_config = [
        {"gap_percent": Decimal("0.0"), "weight_percent": Decimal("50"), "tp_percent": Decimal("1.0")},
        {"gap_percent": Decimal("-1.0"), "weight_percent": Decimal("50"), "tp_percent": Decimal("1.0")}
    ]
    precision_rules = {
        "tick_size": "0.01",
        "step_size": "0.001",
        "min_qty": "0.001",
        "min_notional": "10.0"
    }
    
    levels = grid_calculator.calculate_dca_levels(base_price, dca_config, "long", precision_rules)
    
    assert len(levels) == 2
    # First level (Entry)
    assert levels[0]["price"] == Decimal("50000.00")
    assert levels[0]["tp_price"] == Decimal("50500.00") # 1% up
    
    # Second level (DCA)
    assert levels[1]["price"] == Decimal("49500.00") # 1% down
    assert levels[1]["tp_price"] == Decimal("49995.00") # 1% up from 49500

def test_calculate_order_quantities_validation_error(grid_calculator):
    dca_levels = [{"price": Decimal("1000"), "weight_percent": Decimal("100")}]
    total_capital = Decimal("9") # 0.009 qty > 0.001 min_qty, but 9 < 10 min_notional
    precision_rules = {
        "tick_size": "0.01",
        "step_size": "0.001",
        "min_qty": "0.001",
        "min_notional": "10.0"
    }
    
    with pytest.raises(ValidationError) as excinfo:
        grid_calculator.calculate_order_quantities(dca_levels, total_capital, precision_rules)
    assert "Notional" in str(excinfo.value)

def test_calculate_pyramid_levels_long(grid_calculator):
    base_price = Decimal("50000")
    gap = Decimal("2.0")
    precision_rules = {"tick_size": "0.01"}
    
    result = grid_calculator.calculate_pyramid_levels(base_price, gap, "long", precision_rules)
    assert result["entry_price"] == Decimal("51000.00")

def test_calculate_pyramid_levels_short(grid_calculator):
    base_price = Decimal("50000")
    gap = Decimal("2.0")
    precision_rules = {"tick_size": "0.01"}
    
    result = grid_calculator.calculate_pyramid_levels(base_price, gap, "short", precision_rules)
    assert result["entry_price"] == Decimal("49000.00")