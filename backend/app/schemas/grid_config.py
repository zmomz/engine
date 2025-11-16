from decimal import Decimal
from typing import List, Literal
from pydantic import BaseModel, Field, RootModel, model_validator

class DCALevelConfig(BaseModel):
    gap_percent: Decimal = Field(..., description="Percentage gap from the base price for this DCA level.")
    weight_percent: Decimal = Field(..., gt=Decimal("0"), description="Weight allocation for this DCA level as a percentage of total capital.")
    tp_percent: Decimal = Field(..., gt=Decimal("0"), description="Take-profit percentage for this DCA level.")

    @model_validator(mode='before')
    @classmethod
    def convert_floats_to_decimals(cls, values):
        for key in ['gap_percent', 'weight_percent', 'tp_percent']:
            if key in values and isinstance(values[key], float):
                values[key] = Decimal(str(values[key]))
        return values

class DCAGridConfig(RootModel[List[DCALevelConfig]]):
    @model_validator(mode='after')
    def validate_total_weight(self):
        if self.root: # Only validate if there are levels
            total_weight = sum(level.weight_percent for level in self.root)
            if total_weight != Decimal("100"):
                raise ValueError(f"Total weight_percent must sum to 100, but got {total_weight}")
        return self

class RiskEngineConfig(BaseModel):
    loss_threshold_percent: Decimal = Decimal("-1.5")
    timer_start_condition: str = "after_all_dca_filled"
    post_full_wait_minutes: int = 15
    max_winners_to_combine: int = 3
    use_trade_age_filter: bool = False
    age_threshold_minutes: int = 120
    require_full_pyramids: bool = True
    reset_timer_on_replacement: bool = False
    partial_close_enabled: bool = True
    min_close_notional: Decimal = Decimal("10")

    @model_validator(mode='before')
    @classmethod
    def convert_floats_to_decimals(cls, values):
        for key in ['loss_threshold_percent']:
            if key in values and isinstance(values[key], float):
                values[key] = Decimal(str(values[key]))
        return values
