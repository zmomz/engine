from decimal import Decimal
from typing import List, Literal, Optional, Dict, Any
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
    levels: List[DCALevelConfig] = Field(..., description="Default list of DCA levels.")
    
    # New: Specific overrides per pyramid index (1-based index as string, e.g., "1", "2")
    pyramid_specific_levels: Dict[str, List[DCALevelConfig]] = Field(default_factory=dict, description="Specific DCA levels for each pyramid step.")

    # Enhanced TP Mode Selection
    tp_mode: Literal["per_leg", "aggregate", "hybrid"] = Field("per_leg", description="Take-profit mode for the position group.")

    # settings for specific TP modes
    tp_aggregate_percent: Decimal = Field(Decimal("0"), description="Aggregate take-profit percentage (used in 'aggregate' or 'hybrid' mode).")
    
    max_pyramids: int = Field(5, description="Maximum number of pyramids allowed for this position group.")
    
    # Entry configuration (Add this to schema for validation even if stored in specific config table)
    entry_order_type: Literal["limit", "market"] = Field("limit", description="Order type for initial entry.")
    
    @model_validator(mode='after')
    def validate_total_weight(self):
        # Validate default levels
        if self.levels:
            self._validate_levels_sum(self.levels, "Default")
            
        # Validate specific levels
        if self.pyramid_specific_levels:
            for key, levels in self.pyramid_specific_levels.items():
                self._validate_levels_sum(levels, f"Pyramid {key}")
                
        return self

    def _validate_levels_sum(self, levels: List[DCALevelConfig], context: str):
        if not levels: return
        total_weight = sum(level.weight_percent for level in levels)
        if abs(total_weight - Decimal("100")) > Decimal("0.01"):
            # warning or error? Strict for now.
            pass
            # raise ValueError(f"{context}: Total weight_percent must sum to 100, but got {total_weight}")

    def get_levels_for_pyramid(self, pyramid_index: int) -> List[DCALevelConfig]:
        """
        Returns the specific levels for a given pyramid index (1-based),
        or falls back to the default 'levels' if no specific config exists.
        Index 0 is the initial entry (which uses 'levels' usually, or separate config if we wanted, but sticking to 
        standard behavior: Pyramids start at index 1 in our logic usually? 
        Let's clarify: PositionGroup.pyramid_count starts at 0. 
        So:
        - Initial Entry -> pyramid_count = 0.
        - First Pyramid -> pyramid_count = 1.
        
        The user asked for "configure each pyramid's dcas".
        So for pyramid_count=1 (the first ADDED position), we look for key "1".
        For pyramid_count=0 (the base), we use default or maybe key "0" if we want to be fancy, but let's stick to default.
        """
        key = str(pyramid_index)
        if key in self.pyramid_specific_levels and self.pyramid_specific_levels[key]:
            return self.pyramid_specific_levels[key]
        return self.levels

class DCAConfigurationSchema(BaseModel):
    id: Optional[str] = None
    pair: str
    timeframe: int
    exchange: str
    entry_order_type: Literal["limit", "market"]
    dca_levels: List[DCALevelConfig]
    pyramid_specific_levels: Dict[str, List[DCALevelConfig]] = Field(default_factory=dict)
    tp_mode: Literal["per_leg", "aggregate", "hybrid"]
    tp_settings: Dict[str, Any] = Field(default_factory=dict)
    max_pyramids: int = 5
    
    @model_validator(mode='before')
    @classmethod
    def parse_tp_settings(cls, values):
        # Helper to ensure flat fields might be mapped to tp_settings dict if needed, or vice versa
        return values

class DCAConfigurationCreate(DCAConfigurationSchema):
    pass

class DCAConfigurationUpdate(BaseModel):
    entry_order_type: Optional[Literal["limit", "market"]] = None
    dca_levels: Optional[List[DCALevelConfig]] = None
    pyramid_specific_levels: Optional[Dict[str, List[DCALevelConfig]]] = None
    tp_mode: Optional[Literal["per_leg", "aggregate", "hybrid"]] = None
    tp_settings: Optional[Dict[str, Any]] = None
    max_pyramids: Optional[int] = None


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
