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
        weights: list[int]
    ) -> Optional[int]:
        """
        Send or update entry signal message

        Args:
            position_group: The position group
            pyramid: Current pyramid
            entry_prices: List of entry prices (None for TBD)
            weights: List of weights for each level

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
            weights=weights
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
        pyramids_used: int
    ) -> Optional[int]:
        """
        Send exit signal message

        Args:
            position_group: The position group
            exit_price: Exit price
            pnl_percent: PnL percentage
            pyramids_used: Number of pyramids used

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
            pyramids_used=pyramids_used
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
        weights: list[int]
    ) -> str:
        """Build entry signal message"""

        # Header
        message = f"📈 Entry Setup\n"
        message += f"{position_group.exchange.capitalize()}:{position_group.symbol}\n\n"

        # Entry levels - show all levels based on max_pyramids
        max_pyramids = position_group.max_pyramids or 5  # Default to 5
        message += "🟩 Entries Levels\n"
        for i in range(max_pyramids):
            # Use provided weight or calculate dynamically
            if i < len(weights):
                weight = weights[i]
            else:
                weight = int((i + 1) * 100 / max_pyramids)

            if i < len(entry_prices) and entry_prices[i] is not None:
                # Pyramid filled - show the price
                message += f"• {weight} percent  Entry Price {i + 1}  {float(entry_prices[i]):.2f}\n"
            else:
                # Not filled yet - show TBD
                message += f"• {weight} percent  Entry Price {i + 1}  TBD\n"

        # Engine notes - dynamic pyramid count
        message += "\n🧩 Engine Notes\n"
        message += "• Long only\n"
        message += f"• Up to {max_pyramids} pyramids\n"
        message += "• This message will be updated as new levels fill\n"
        message += "• Unknown levels remain as TBD\n"
        message += "• The exit is one trigger that closes the full position"

        return message

    def _build_exit_message(
        self,
        position_group: PositionGroup,
        exit_price: Decimal,
        pnl_percent: Decimal,
        pyramids_used: int
    ) -> str:
        """Build exit signal message"""

        message = "🚪 Exit Triggered\n\n"
        message += f"💰 Exit price: {float(exit_price):.2f}\n"
        message += f"📉 Result: {float(pnl_percent):.1f} percent\n"
        message += f"📦 Pyramids used: {pyramids_used}\n\n"
        message += "🔍 Engine closed the full position based on market behavior."

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
