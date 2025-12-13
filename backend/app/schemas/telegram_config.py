"""
Telegram Configuration Schema
"""
from pydantic import BaseModel, Field
from typing import Optional


class TelegramConfig(BaseModel):
    """Telegram channel configuration for signal broadcasting"""

    enabled: bool = Field(default=False, description="Enable/disable Telegram signal broadcasting")
    bot_token: Optional[str] = Field(default=None, description="Telegram bot token")
    channel_id: Optional[str] = Field(default=None, description="Telegram channel ID (e.g., @channelname or -100123456789)")
    channel_name: str = Field(default="AlgoMakers.Ai Signals", description="Channel display name")
    engine_signature: str = Field(
        default="⚙️ AlgoMakers Engine\nLong only. Up to five pyramids. One full exit.\nNo fixed targets. Market driven logic.",
        description="Engine signature shown in messages"
    )

    # Message options
    send_entry_signals: bool = Field(default=True, description="Send entry signal messages")
    send_exit_signals: bool = Field(default=True, description="Send exit signal messages")
    update_on_pyramid: bool = Field(default=True, description="Update message when new pyramid fills")

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
                "update_on_pyramid": True,
                "test_mode": False
            }
        }


class TelegramConfigUpdate(BaseModel):
    """Schema for updating Telegram configuration"""

    enabled: Optional[bool] = None
    bot_token: Optional[str] = None
    channel_id: Optional[str] = None
    channel_name: Optional[str] = None
    engine_signature: Optional[str] = None
    send_entry_signals: Optional[bool] = None
    send_exit_signals: Optional[bool] = None
    update_on_pyramid: Optional[bool] = None
    test_mode: Optional[bool] = None
