from decimal import Decimal
from typing import List, Literal, Optional, Dict
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

class DCAGridConfig(BaseModel):
    levels: List[DCALevelConfig] = Field(..., description="List of DCA levels with their respective configurations.")
    tp_mode: Literal["per_leg", "aggregate", "hybrid"] = Field("per_leg", description="Take-profit mode for the position group.")
    tp_aggregate_percent: Decimal = Field(Decimal("0"), description="Aggregate take-profit percentage for the position group, used in aggregate and hybrid TP modes.")
    max_pyramids: int = Field(5, description="Maximum number of pyramids allowed for this position group.")
    
    @model_validator(mode='after')
    def validate_total_weight(self):
        if self.levels: # Only validate if there are levels
            total_weight = sum(level.weight_percent for level in self.levels)
            if total_weight != Decimal("100"):
                raise ValueError(f"Total weight_percent must sum to 100, but got {total_weight}")
        return self

class PriorityRulesConfig(BaseModel):
    """Configuration for queue priority rules"""
    priority_rules_enabled: Dict[str, bool] = Field(
        default={
            "same_pair_timeframe": True,
            "deepest_loss_percent": True,
            "highest_replacement": True,
            "fifo_fallback": True
        },
        description="Toggle switches for each priority rule"
    )
    priority_order: List[str] = Field(
        default=[
            "same_pair_timeframe",
            "deepest_loss_percent",
            "highest_replacement",
            "fifo_fallback"
        ],
        description="Execution order of priority rules (top to bottom)"
    )

    @model_validator(mode='after')
    def validate_priority_rules(self):
        """Ensure at least one rule is enabled and all rules in order are valid"""
        # Check at least one rule is enabled
        enabled_count = sum(1 for enabled in self.priority_rules_enabled.values() if enabled)
        if enabled_count == 0:
            raise ValueError("At least one priority rule must be enabled")
        
        # Validate that all rules in priority_order are valid
        valid_rules = {"same_pair_timeframe", "deepest_loss_percent", "highest_replacement", "fifo_fallback"}
        for rule in self.priority_order:
            if rule not in valid_rules:
                raise ValueError(f"Invalid rule in priority_order: {rule}")
        
        # Ensure all valid rules are in priority_order (no missing rules)
        if set(self.priority_order) != valid_rules:
            raise ValueError(f"priority_order must contain all four rules: {valid_rules}")
        
        return self

class RiskEngineConfig(BaseModel):
    # Pre-trade Risk Checks
    max_open_positions_global: int = 10
    max_open_positions_per_symbol: int = 1
    max_total_exposure_usd: Decimal = Decimal("10000")
    max_daily_loss_usd: Decimal = Decimal("500") # Circuit breaker

    # Position Sizing
    risk_per_position_percent: Decimal = Field(Decimal("10.0"), description="Percentage of available capital to allocate to a single position group.")
    risk_per_position_cap_usd: Optional[Decimal] = Field(None, description="Maximum absolute USD amount to allocate to a single position group (optional cap).")

    # Post-trade Risk Management
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

    # Queue Priority Rules Configuration
    priority_rules: PriorityRulesConfig = Field(
        default_factory=PriorityRulesConfig,
        description="Configuration for queue priority rules (enabled/disabled and execution order)"
    )

    @model_validator(mode='before')
    @classmethod
    def convert_floats_to_decimals(cls, values):
        for key in ['loss_threshold_percent', 'max_total_exposure_usd', 'max_daily_loss_usd', 'min_close_notional', 'risk_per_position_percent', 'risk_per_position_cap_usd']:
            if key in values and isinstance(values[key], float):
                values[key] = Decimal(str(values[key]))
        return values
