
import pytest
from decimal import Decimal
from app.services.grid_calculator import GridCalculatorService, ValidationError
from app.schemas.grid_config import DCAGridConfig
from typing import List, Dict

# --- Fixtures ---

@pytest.fixture
def sample_dca_config() -> DCAGridConfig:
    return DCAGridConfig.model_validate({
        "levels": [
            {"gap_percent": 0.0, "weight_percent": 20, "tp_percent": 1.0},
            {"gap_percent": -0.5, "weight_percent": 20, "tp_percent": 0.5},
            {"gap_percent": -1.0, "weight_percent": 20, "tp_percent": 0.5},
            {"gap_percent": -2.0, "weight_percent": 20, "tp_percent": 0.5},
            {"gap_percent": -4.0, "weight_percent": 20, "tp_percent": 0.5}
        ],
        "tp_mode": "per_leg",
        "tp_aggregate_percent": Decimal("0")
    })

@pytest.fixture
def sample_precision_rules() -> Dict:
    return {
        "tick_size": Decimal("0.01"),
        "step_size": Decimal("0.001"),
        "min_qty": Decimal("0.001"),
        "min_notional": Decimal("10.0")
    }

@pytest.fixture
def grid_calculator():
    return GridCalculatorService()

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

# --- Tests for calculate_dca_levels ---

def test_calculate_dca_levels_long(sample_dca_config, sample_precision_rules):
    base_price = Decimal("50000.00")
    side = "long"
    
    levels = GridCalculatorService.calculate_dca_levels(base_price, sample_dca_config, side, sample_precision_rules)
    
    assert len(levels) == 5
    assert levels[0]["price"] == Decimal("50000.00")
    assert levels[1]["price"] == Decimal("49750.00")
    assert levels[2]["price"] == Decimal("49500.00")
    assert levels[3]["price"] == Decimal("49000.00")
    assert levels[4]["price"] == Decimal("48000.00")
    
    assert levels[0]["tp_price"] == Decimal("50500.00")
    assert levels[1]["tp_price"] == Decimal("49998.75")
    assert levels[2]["tp_price"] == Decimal("49747.50")

def test_calculate_dca_levels_short(sample_dca_config, sample_precision_rules):
    base_price = Decimal("50000.00")
    side = "short"
    
    levels = GridCalculatorService.calculate_dca_levels(base_price, sample_dca_config, side, sample_precision_rules)
    
    assert len(levels) == 5
    assert levels[0]["price"] == Decimal("50000.00")
    assert levels[1]["price"] == Decimal("50250.00")
    assert levels[2]["price"] == Decimal("50500.00")
    assert levels[3]["price"] == Decimal("51000.00")
    assert levels[4]["price"] == Decimal("52000.00")

    assert levels[0]["tp_price"] == Decimal("49500.00")
    assert levels[1]["tp_price"] == Decimal("49998.75")
    assert levels[2]["tp_price"] == Decimal("50247.50")

# --- Tests for calculate_order_quantities ---

def test_calculate_order_quantities_sufficient_capital(sample_precision_rules):
    dca_levels = [
        {"price": Decimal("50000"), "weight_percent": 20},
        {"price": Decimal("49000"), "weight_percent": 80},
    ]
    total_capital_usd = Decimal("1000")
    
    levels_with_qty = GridCalculatorService.calculate_order_quantities(dca_levels, total_capital_usd, sample_precision_rules)
    
    # Leg 1: 1000 * 0.20 = 200 USD. 200 / 50000 = 0.004 qty
    assert levels_with_qty[0]["quantity"] == Decimal("0.004")
    # Leg 2: 1000 * 0.80 = 800 USD. 800 / 49000 = 0.01632... rounded to 0.016
    assert levels_with_qty[1]["quantity"] == Decimal("0.016")

def test_calculate_order_quantities_below_min_qty(sample_precision_rules):
    dca_levels = [{"price": Decimal("50000"), "weight_percent": 100}]
    total_capital_usd = Decimal("40") # 40 / 50000 = 0.0008, which is < min_qty 0.001
    
    with pytest.raises(ValidationError, match="Quantity 0.000 below minimum 0.001"):
        GridCalculatorService.calculate_order_quantities(dca_levels, total_capital_usd, sample_precision_rules)

def test_calculate_order_quantities_below_min_notional(sample_precision_rules):
    dca_levels = [{"price": Decimal("1.0"), "weight_percent": 100}]
    total_capital_usd = Decimal("5") # Notional will be 5, which is < min_notional 10
    
    with pytest.raises(ValidationError, match="Notional 5.0000 below minimum 10.0"):
        GridCalculatorService.calculate_order_quantities(dca_levels, total_capital_usd, sample_precision_rules)

# --- Tests for TakeProfitService (to be added in a separate file) ---
# These will require more complex mocking of the database and exchange connector.
# For now, we are focusing on the pure calculation logic.
