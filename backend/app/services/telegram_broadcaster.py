"""
Telegram Signal Broadcasting Service
Sends trading signals to Telegram channels
"""
import logging
import aiohttp
from typing import Optional, Dict, Any
from decimal import Decimal
from datetime import datetime

from app.models.position_group import PositionGroup
from app.models.pyramid import Pyramid
from app.schemas.telegram_config import TelegramConfig

logger = logging.getLogger(__name__)


class TelegramBroadcaster:
    """Service for broadcasting trading signals to Telegram"""

    def __init__(self, config: TelegramConfig):
        self.config = config
        self.base_url = f"https://api.telegram.org/bot{config.bot_token}"
        # Store message IDs for updating (keyed by position_group_id)
        self.message_ids: Dict[str, int] = {}

    async def send_entry_signal(
        self,
        position_group: PositionGroup,
        pyramid: Pyramid,
        entry_prices: list[Optional[Decimal]],
        weights: list[int],
        tp_prices: list[Optional[Decimal]] = None,
        tp_mode: str = None,
        aggregate_tp: Decimal = None
    ) -> Optional[int]:
        """
        Send or update entry signal message

        Args:
            position_group: The position group
            pyramid: Current pyramid
            entry_prices: List of entry prices (None for TBD)
            weights: List of weights for each level
            tp_prices: List of TP prices for per_leg mode
            tp_mode: TP mode ("per_leg" or "aggregate")
            aggregate_tp: Aggregate TP price for aggregate mode

        Returns:
            Message ID if sent successfully
        """
        if not self.config.enabled or not self.config.send_entry_signals:
            return None

        # Build message
        message = self._build_entry_message(
            position_group=position_group,
            pyramid=pyramid,
            entry_prices=entry_prices,
            weights=weights,
            tp_prices=tp_prices,
            tp_mode=tp_mode,
            aggregate_tp=aggregate_tp
        )

        # Check if we should update existing message
        pg_id = str(position_group.id)
        if pg_id in self.message_ids and self.config.update_on_pyramid:
            # Update existing message
            message_id = await self._update_message(self.message_ids[pg_id], message)
            return message_id
        else:
            # Send new message
            message_id = await self._send_message(message)
            if message_id:
                self.message_ids[pg_id] = message_id
            return message_id

    async def send_exit_signal(
        self,
        position_group: PositionGroup,
        exit_price: Decimal,
        pnl_percent: Decimal,
        pyramids_used: int,
        exit_reason: str = "engine",
        pnl_usd: Optional[Decimal] = None,
        duration_hours: Optional[float] = None
    ) -> Optional[int]:
        """
        Send exit signal message

        Args:
            position_group: The position group
            exit_price: Exit price
            pnl_percent: PnL percentage
            pyramids_used: Number of pyramids used
            exit_reason: Reason for exit ("manual", "engine", "tp_hit", "risk_offset")
            pnl_usd: Realized PnL in USD
            duration_hours: How long the position was open

        Returns:
            Message ID if sent successfully
        """
        if not self.config.enabled or not self.config.send_exit_signals:
            return None

        # Build message
        message = self._build_exit_message(
            position_group=position_group,
            exit_price=exit_price,
            pnl_percent=pnl_percent,
            pyramids_used=pyramids_used,
            exit_reason=exit_reason,
            pnl_usd=pnl_usd,
            duration_hours=duration_hours
        )

        # Send new message
        message_id = await self._send_message(message)

        # Clean up stored message ID
        pg_id = str(position_group.id)
        if pg_id in self.message_ids:
            del self.message_ids[pg_id]

        return message_id

    def _build_entry_message(
        self,
        position_group: PositionGroup,
        pyramid: Pyramid,
        entry_prices: list[Optional[Decimal]],
        weights: list[int],
        tp_prices: list[Optional[Decimal]] = None,
        tp_mode: str = None,
        aggregate_tp: Decimal = None
    ) -> str:
        """Build entry signal message"""

        # Format group ID (first 8 chars)
        group_id_short = str(position_group.id)[:8]

        # Header
        message = f"📈 Entry Setup\n"
        message += f"{position_group.exchange.capitalize()}:{position_group.symbol}\n"
        message += f"🆔 {group_id_short}\n\n"

        # Entry levels
        message += "🟩 Entries Levels\n"
        num_levels = len(entry_prices)

        for i in range(num_levels):
            weight = weights[i] if i < len(weights) else 0
            entry_price = entry_prices[i]

            if entry_price is not None:
                line = f"• {weight} % Entry Price {i + 1} {float(entry_price):.2f}"

                # Add TP if mode is per_leg
                if tp_mode == "per_leg" and tp_prices and i < len(tp_prices) and tp_prices[i] is not None:
                    line += f"  TP : {float(tp_prices[i]):.2f}"

                message += line + "\n"
            else:
                message += f"• {weight} % Entry Price {i + 1} TBD\n"

        # Add aggregate TP if mode is aggregate
        if tp_mode == "aggregate" and aggregate_tp is not None:
            message += f"\nTP aggregate: {float(aggregate_tp):.2f}\n"

        # Engine notes
        message += "\n🧩 Engine Notes\n"
        message += "• Long only\n"
        message += f"• Up to {num_levels} pyramids\n"
        message += "• This message will be updated as new levels fill\n"
        message += "• Unknown levels remain as TBD\n"
        message += "• The exit is one trigger that closes the full position"

        return message

    def _build_exit_message(
        self,
        position_group: PositionGroup,
        exit_price: Decimal,
        pnl_percent: Decimal,
        pyramids_used: int,
        exit_reason: str = "engine",
        pnl_usd: Optional[Decimal] = None,
        duration_hours: Optional[float] = None
    ) -> str:
        """Build exit signal message"""

        # Exit reason icons and descriptions
        reason_info = {
            "manual": ("🖐️", "Manual Close", "Position manually closed by user"),
            "engine": ("🤖", "Engine Exit", "Engine closed based on market conditions"),
            "tp_hit": ("🎯", "Take Profit", "Take profit target reached"),
            "risk_offset": ("⚖️", "Risk Offset", "Closed to offset losses from another position"),
        }

        icon, title, description = reason_info.get(exit_reason, ("🚪", "Exit", "Position closed"))

        # Determine if profit or loss
        is_profit = float(pnl_percent) >= 0
        result_emoji = "📈" if is_profit else "📉"
        result_color = "🟢" if is_profit else "🔴"

        # Format group ID (first 8 chars)
        group_id_short = str(position_group.id)[:8]

        # Header with symbol info
        message = f"{icon} {title}\n"
        message += f"{position_group.exchange.upper()} | {position_group.symbol}\n"
        message += f"🆔 {group_id_short}\n"
        message += f"{'─' * 25}\n\n"

        # Position details
        side_emoji = "🟢" if position_group.side == "long" else "🔴"
        message += f"{side_emoji} Side: {position_group.side.upper()}\n"
        message += f"📊 Timeframe: {position_group.timeframe}m\n\n"

        # Price info
        message += f"🎯 Entry: {float(position_group.weighted_avg_entry):.4f}\n"
        message += f"💰 Exit: {float(exit_price):.4f}\n\n"

        # PnL section
        message += f"{result_color} Result\n"
        message += f"  {result_emoji} {float(pnl_percent):+.2f}%\n"
        if pnl_usd is not None:
            message += f"  💵 {float(pnl_usd):+.2f} USD\n"
        message += "\n"

        # Trade info
        message += f"📦 Pyramids: {pyramids_used}\n"
        message += f"💼 Invested: {float(position_group.total_invested_usd):.2f} USD\n"

        # Duration if available
        if duration_hours is not None:
            if duration_hours < 1:
                duration_str = f"{int(duration_hours * 60)}m"
            elif duration_hours < 24:
                duration_str = f"{duration_hours:.1f}h"
            else:
                days = duration_hours / 24
                duration_str = f"{days:.1f}d"
            message += f"⏱️ Duration: {duration_str}\n"

        message += f"\n{'─' * 25}\n"
        message += f"💡 {description}"

        return message

    async def _send_message(self, text: str) -> Optional[int]:
        """Send a new message to the Telegram channel"""

        if self.config.test_mode:
            logger.info(f"[TEST MODE] Would send Telegram message:\n{text}")
            return 999999  # Fake message ID for testing

        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/sendMessage"
                data = {
                    "chat_id": self.config.channel_id,
                    "text": text,
                    "disable_web_page_preview": True
                }

                async with session.post(url, json=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        message_id = result.get("result", {}).get("message_id")
                        logger.info(f"Sent Telegram message {message_id} to {self.config.channel_id}")
                        return message_id
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to send Telegram message: {response.status} - {error_text}")
                        return None

        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return None

    async def _update_message(self, message_id: int, text: str) -> Optional[int]:
        """Update an existing message"""

        if self.config.test_mode:
            logger.info(f"[TEST MODE] Would update Telegram message {message_id}:\n{text}")
            return message_id

        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/editMessageText"
                data = {
                    "chat_id": self.config.channel_id,
                    "message_id": message_id,
                    "text": text,
                    "disable_web_page_preview": True
                }

                async with session.post(url, json=data) as response:
                    if response.status == 200:
                        logger.info(f"Updated Telegram message {message_id}")
                        return message_id
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to update Telegram message: {response.status} - {error_text}")
                        return None

        except Exception as e:
            logger.error(f"Error updating Telegram message: {e}")
            return None

    async def test_connection(self) -> tuple[bool, str]:
        try:
            async with aiohttp.ClientSession() as session:

                # 1️⃣ Check bot token
                async with session.get(f"{self.base_url}/getMe") as r:
                    if r.status != 200:
                        return False, await r.text()

                # 2️⃣ Check channel access
                async with session.post(
                    f"{self.base_url}/sendMessage",
                    json={
                        "chat_id": self.config.channel_id,
                        "text": "✅ Telegram connection test",
                        "disable_web_page_preview": True
                    }
                ) as r:
                    if r.status != 200:
                        return False, await r.text()

                return True, "OK"

        except Exception as e:
            return False, str(e)
