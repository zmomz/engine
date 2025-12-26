"""
Telegram Configuration Schema
"""
from pydantic import BaseModel, Field
from typing import Optional


class TelegramConfig(BaseModel):
    """Telegram channel configuration for signal broadcasting"""

    # Connection
    enabled: bool = Field(default=False, description="Enable/disable Telegram signal broadcasting")
    bot_token: Optional[str] = Field(default=None, description="Telegram bot token")
    channel_id: Optional[str] = Field(default=None, description="Telegram channel ID (e.g., @channelname or -100123456789)")
    channel_name: str = Field(default="AlgoMakers.Ai Signals", description="Channel display name")
    engine_signature: str = Field(
        default="AlgoMakers Engine\nLong only. Up to five pyramids. One full exit.\nNo fixed targets. Market driven logic.",
        description="Engine signature shown in messages"
    )

    # ═══════════════════════════════════════════
    # MESSAGE TYPE TOGGLES
    # ═══════════════════════════════════════════

    # Position Lifecycle
    send_entry_signals: bool = Field(default=True, description="Send entry signal messages when position opens")
    send_exit_signals: bool = Field(default=True, description="Send exit signal messages when position closes")
    send_status_updates: bool = Field(default=True, description="Send status transition notifications (PARTIALLY_FILLED, ACTIVE, etc.)")

    # Fill Updates
    send_dca_fill_updates: bool = Field(default=True, description="Send notifications when individual DCA legs fill")
    send_pyramid_updates: bool = Field(default=True, description="Send notifications when new pyramids are added")

    # Take Profit
    send_tp_hit_updates: bool = Field(default=True, description="Send notifications when TP targets are hit")

    # Alerts (Urgent)
    send_failure_alerts: bool = Field(default=True, description="Send alerts for order/position failures")
    send_risk_alerts: bool = Field(default=True, description="Send alerts for risk timer events")

    # ═══════════════════════════════════════════
    # ADVANCED CONTROLS
    # ═══════════════════════════════════════════

    # Message Strategy
    update_existing_message: bool = Field(default=True, description="Update existing message instead of sending new ones (less spam)")
    update_on_pyramid: bool = Field(default=True, description="Update message when new pyramid fills")
    show_unrealized_pnl: bool = Field(default=True, description="Show live unrealized P&L in updates")
    show_invested_amount: bool = Field(default=True, description="Show invested amount in messages")
    show_duration: bool = Field(default=True, description="Show position duration in messages")

    # Threshold Alerts (optional - only alert if threshold exceeded)
    alert_loss_threshold_percent: Optional[float] = Field(default=None, description="Alert if loss exceeds this percentage (e.g., 5.0)")
    alert_profit_threshold_percent: Optional[float] = Field(default=None, description="Alert if profit exceeds this percentage (e.g., 10.0)")

    # Quiet Hours (optional)
    quiet_hours_enabled: bool = Field(default=False, description="Enable quiet hours to reduce notifications")
    quiet_hours_start: Optional[str] = Field(default=None, description="Quiet hours start time (e.g., '22:00')")
    quiet_hours_end: Optional[str] = Field(default=None, description="Quiet hours end time (e.g., '08:00')")
    quiet_hours_urgent_only: bool = Field(default=True, description="Only send urgent alerts (failures/risk) during quiet hours")

    # Test mode
    test_mode: bool = Field(default=False, description="Test mode - logs messages without sending")

    class Config:
        json_schema_extra = {
            "example": {
                "enabled": True,
                "bot_token": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
                "channel_id": "@algomakers_signals",
                "channel_name": "AlgoMakers.Ai Signals",
                "send_entry_signals": True,
                "send_exit_signals": True,
                "send_status_updates": True,
                "send_dca_fill_updates": True,
                "send_pyramid_updates": True,
                "send_tp_hit_updates": True,
                "send_failure_alerts": True,
                "send_risk_alerts": True,
                "update_existing_message": True,
                "update_on_pyramid": True,
                "show_unrealized_pnl": True,
                "show_invested_amount": True,
                "show_duration": True,
                "alert_loss_threshold_percent": None,
                "alert_profit_threshold_percent": None,
                "quiet_hours_enabled": False,
                "quiet_hours_start": None,
                "quiet_hours_end": None,
                "quiet_hours_urgent_only": True,
                "test_mode": False
            }
        }


class TelegramConfigUpdate(BaseModel):
    """Schema for updating Telegram configuration"""

    # Connection
    enabled: Optional[bool] = None
    bot_token: Optional[str] = None
    channel_id: Optional[str] = None
    channel_name: Optional[str] = None
    engine_signature: Optional[str] = None

    # Message Type Toggles
    send_entry_signals: Optional[bool] = None
    send_exit_signals: Optional[bool] = None
    send_status_updates: Optional[bool] = None
    send_dca_fill_updates: Optional[bool] = None
    send_pyramid_updates: Optional[bool] = None
    send_tp_hit_updates: Optional[bool] = None
    send_failure_alerts: Optional[bool] = None
    send_risk_alerts: Optional[bool] = None

    # Advanced Controls
    update_existing_message: Optional[bool] = None
    update_on_pyramid: Optional[bool] = None
    show_unrealized_pnl: Optional[bool] = None
    show_invested_amount: Optional[bool] = None
    show_duration: Optional[bool] = None

    # Threshold Alerts
    alert_loss_threshold_percent: Optional[float] = None
    alert_profit_threshold_percent: Optional[float] = None

    # Quiet Hours
    quiet_hours_enabled: Optional[bool] = None
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None
    quiet_hours_urgent_only: Optional[bool] = None

    # Test mode
    test_mode: Optional[bool] = None
