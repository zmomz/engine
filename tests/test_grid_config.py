import pytest
from decimal import Decimal
from pydantic import ValidationError as PydanticValidationError

from app.schemas.grid_config import DCALevelConfig, DCAGridConfig

def test_dca_level_config_valid_data():
    """
    Test DCALevelConfig with valid data.
    """
    config_data = {"gap_percent": 0.5, "weight_percent": 25.0, "tp_percent": 1.5}
    level_config = DCALevelConfig(**config_data)

    assert level_config.gap_percent == Decimal("0.5")
    assert level_config.weight_percent == Decimal("25.0")
    assert level_config.tp_percent == Decimal("1.5")

def test_dca_level_config_invalid_weight_percent():
    """
    Test DCALevelConfig with invalid weight_percent (<= 0).
    """
    config_data = {"gap_percent": 0.5, "weight_percent": 0.0, "tp_percent": 1.5}
    with pytest.raises(PydanticValidationError, match="greater than 0"):
        DCALevelConfig(**config_data)

def test_dca_level_config_invalid_tp_percent():
    """
    Test DCALevelConfig with invalid tp_percent (<= 0).
    """
    config_data = {"gap_percent": 0.5, "weight_percent": 25.0, "tp_percent": -0.1}
    with pytest.raises(PydanticValidationError, match="greater than 0"):
        DCALevelConfig(**config_data)

def test_dca_grid_config_valid_data():
    """
    Test DCAGridConfig with valid data (total weight 100).
    """
    grid_data = [
        {"gap_percent": 0.0, "weight_percent": 20.0, "tp_percent": 1.0},
        {"gap_percent": -0.5, "weight_percent": 30.0, "tp_percent": 0.5},
        {"gap_percent": -1.0, "weight_percent": 50.0, "tp_percent": 0.5}
    ]
    grid_config = DCAGridConfig(levels=grid_data, tp_mode="per_leg", tp_aggregate_percent=Decimal("0"))

    assert len(grid_config.levels) == 3
    assert grid_config.levels[0].weight_percent == Decimal("20.0")
    assert grid_config.levels[1].weight_percent == Decimal("30.0")
    assert grid_config.levels[2].weight_percent == Decimal("50.0")

def test_dca_grid_config_invalid_total_weight():
    """
    Test DCAGridConfig with invalid total weight (not 100).
    """
    grid_data = [
        {"gap_percent": 0.0, "weight_percent": 20.0, "tp_percent": 1.0},
        {"gap_percent": -0.5, "weight_percent": 30.0, "tp_percent": 0.5},
        {"gap_percent": -1.0, "weight_percent": 40.0, "tp_percent": 0.5} # Sums to 90
    ]
    with pytest.raises(ValueError, match="Total weight_percent must sum to 100"):
        DCAGridConfig(levels=grid_data, tp_mode="per_leg", tp_aggregate_percent=Decimal("0"))

def test_dca_grid_config_empty_list():
    """
    Test DCAGridConfig with an empty list.
    """
    grid_data = []
    grid_config = DCAGridConfig(levels=grid_data, tp_mode="per_leg", tp_aggregate_percent=Decimal("0"))
    assert len(grid_config.levels) == 0
