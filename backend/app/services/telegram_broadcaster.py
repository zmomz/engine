"""
Telegram Signal Broadcasting Service
Sends trading signals to Telegram channels with smart, informative messages
"""
import logging
import aiohttp
from typing import Optional, Dict, Any, List
from decimal import Decimal
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.pyramid import Pyramid
from app.models.dca_order import DCAOrder
from app.schemas.telegram_config import TelegramConfig

logger = logging.getLogger(__name__)


class TelegramBroadcaster:
    """Service for broadcasting trading signals to Telegram with smart formatting"""

    def __init__(self, config: TelegramConfig):
        self.config = config
        self.base_url = f"https://api.telegram.org/bot{config.bot_token}"

    # ═══════════════════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    def _format_duration(self, hours: Optional[float]) -> str:
        """Format duration in human-readable form"""
        if hours is None:
            return "N/A"
        if hours < 1:
            return f"{int(hours * 60)}m"
        elif hours < 24:
            return f"{hours:.1f}h"
        else:
            days = hours / 24
            return f"{days:.1f}d"

    def _format_price(self, price: Optional[Decimal], decimals: int = 2) -> str:
        """Format price with comma separators"""
        if price is None:
            return "TBD"
        return f"{float(price):,.{decimals}f}"

    def _format_pnl(self, percent: Decimal, usd: Optional[Decimal] = None) -> str:
        """Format P&L with sign and optional USD value"""
        pnl_str = f"{float(percent):+.2f}%"
        if usd is not None:
            pnl_str += f" (${float(usd):+,.2f})"
        return pnl_str

    def _get_position_id_short(self, position_group: PositionGroup) -> str:
        """Get shortened position ID for display"""
        return str(position_group.id)[:8]

    def _get_header(self, position_group: PositionGroup) -> str:
        """Get standard header with exchange, symbol, timeframe"""
        return f"{position_group.exchange.upper()} · {position_group.symbol} · {position_group.timeframe}m"

    def _get_duration_hours(self, position_group: PositionGroup) -> Optional[float]:
        """Calculate position duration in hours"""
        if position_group.created_at:
            end_time = position_group.closed_at or datetime.utcnow()
            duration = end_time - position_group.created_at
            return duration.total_seconds() / 3600
        return None

    def _is_quiet_hours(self) -> bool:
        """Check if current time is within quiet hours"""
        if not self.config.quiet_hours_enabled:
            return False
        if not self.config.quiet_hours_start or not self.config.quiet_hours_end:
            return False

        try:
            now = datetime.utcnow().time()
            start = datetime.strptime(self.config.quiet_hours_start, "%H:%M").time()
            end = datetime.strptime(self.config.quiet_hours_end, "%H:%M").time()

            # Handle overnight quiet hours (e.g., 22:00 - 08:00)
            if start <= end:
                return start <= now <= end
            else:
                return now >= start or now <= end
        except ValueError:
            return False

    def _should_send(self, is_urgent: bool = False) -> bool:
        """Check if message should be sent based on quiet hours"""
        if not self._is_quiet_hours():
            return True
        # During quiet hours, only send urgent messages if configured
        return is_urgent and self.config.quiet_hours_urgent_only

    # ═══════════════════════════════════════════════════════════════════════════
    # MESSAGE BUILDERS - ENTRY SIGNALS
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_entry_message(
        self,
        position_group: PositionGroup,
        pyramid: Pyramid,
        entry_prices: List[Optional[Decimal]],
        weights: List[int],
        filled_count: int,
        total_count: int,
        tp_prices: List[Optional[Decimal]] = None,
        tp_mode: str = None,
        aggregate_tp: Decimal = None,
        pyramid_tp_percent: Decimal = None
    ) -> str:
        """Build smart entry signal message with TP-type specific formatting"""

        group_id = self._get_position_id_short(position_group)
        side = position_group.side.upper()
        pyramid_num = (pyramid.pyramid_index if pyramid else 0) + 1
        duration = self._get_duration_hours(position_group)

        # Header
        msg = f"📈 {side} Entry\n"
        msg += f"{self._get_header(position_group)}\n"
        msg += f"🆔 {group_id}\n\n"

        # DCA Levels box
        msg += "┌─ DCA Levels ─────────────────\n"
        for i, price in enumerate(entry_prices):
            weight = weights[i] if i < len(weights) else 0
            filled = "✅" if price is not None else "⏳"
            price_str = self._format_price(price)

            # Build level line based on TP mode
            if tp_mode == "per_leg" and tp_prices and i < len(tp_prices) and tp_prices[i]:
                tp_str = self._format_price(tp_prices[i])
                msg += f"│ {filled} {weight}%  {price_str}  → TP {tp_str}\n"
            else:
                msg += f"│ {filled} {weight}%  {price_str}\n"

        msg += "└──────────────────────────────\n"

        # TP section based on mode
        if tp_mode == "aggregate" and aggregate_tp:
            tp_percent = self._calculate_tp_percent(position_group.weighted_avg_entry, aggregate_tp)
            msg += f"🎯 Aggregate TP: {self._format_price(aggregate_tp)} (+{tp_percent:.1f}%)\n"
        elif tp_mode == "hybrid" and aggregate_tp:
            msg += f"🎯 Fallback Aggregate TP: {self._format_price(aggregate_tp)}\n"
        elif tp_mode == "pyramid_aggregate" and pyramid_tp_percent:
            # Calculate pyramid-specific TP target
            if position_group.weighted_avg_entry:
                tp_target = position_group.weighted_avg_entry * (1 + pyramid_tp_percent / 100)
                msg += f"🎯 P{pyramid_num} TP Target: {self._format_price(tp_target)} (+{float(pyramid_tp_percent):.1f}%)\n"

        msg += "\n"

        # Status section
        status_name = position_group.status.value if hasattr(position_group.status, 'value') else str(position_group.status)
        msg += f"📊 {status_name.upper()} ({filled_count}/{total_count} legs)\n"

        if self.config.show_invested_amount and position_group.total_invested_usd:
            msg += f"💰 Invested: ${self._format_price(position_group.total_invested_usd)}\n"

        if self.config.show_unrealized_pnl and position_group.unrealized_pnl_percent:
            pnl = position_group.unrealized_pnl_percent
            pnl_usd = position_group.unrealized_pnl_usd
            emoji = "📈" if float(pnl) >= 0 else "📉"
            msg += f"{emoji} Unrealized: {self._format_pnl(pnl, pnl_usd)}\n"

        if position_group.weighted_avg_entry:
            msg += f"📈 Avg Entry: {self._format_price(position_group.weighted_avg_entry)}\n"

        msg += "\n"

        # Footer with pyramid info and TP mode
        tp_mode_display = tp_mode.replace("_", " ") if tp_mode else "unknown"
        msg += f"🔷 Pyramid {pyramid_num}/{position_group.max_pyramids} · {tp_mode_display} TP\n"

        if self.config.show_duration and duration:
            msg += f"⏱️ Open: {self._format_duration(duration)}"

        return msg

    def _calculate_tp_percent(self, entry: Optional[Decimal], tp: Optional[Decimal]) -> float:
        """Calculate TP percentage from entry"""
        if entry and tp and entry > 0:
            return float((tp - entry) / entry * 100)
        return 0.0

    # ═══════════════════════════════════════════════════════════════════════════
    # MESSAGE BUILDERS - DCA FILL
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_dca_fill_message(
        self,
        position_group: PositionGroup,
        order: DCAOrder,
        filled_count: int,
        total_count: int,
        pyramid: Pyramid
    ) -> str:
        """Build DCA leg fill notification message"""

        group_id = self._get_position_id_short(position_group)
        pyramid_num = (pyramid.pyramid_index if pyramid else 0) + 1
        duration = self._get_duration_hours(position_group)
        leg_num = order.leg_index + 1 if hasattr(order, 'leg_index') else filled_count

        # Header
        msg = f"✅ Leg {leg_num} Filled\n"
        msg += f"{self._get_header(position_group)}\n"
        msg += f"🆔 {group_id}\n\n"

        # Fill details
        msg += f"📍 Price: {self._format_price(order.price)}\n"
        value = float(order.price or 0) * float(order.filled_quantity or order.quantity or 0)
        msg += f"📦 Qty: {float(order.filled_quantity or order.quantity or 0):.6f} (${value:,.2f})\n\n"

        # Progress box
        fill_percent = int((filled_count / total_count) * 100) if total_count > 0 else 0
        msg += "┌─ Progress ───────────────────\n"
        msg += f"│ Filled: {filled_count}/{total_count} legs ({fill_percent}%)\n"
        if position_group.weighted_avg_entry:
            msg += f"│ Avg Entry: {self._format_price(position_group.weighted_avg_entry)}\n"
        if position_group.total_invested_usd:
            msg += f"│ Invested: ${self._format_price(position_group.total_invested_usd)}\n"
        msg += "└──────────────────────────────\n\n"

        # Footer
        msg += f"🔷 Pyramid {pyramid_num}/{position_group.max_pyramids} · {position_group.side.upper()}\n"
        if self.config.show_duration and duration:
            msg += f"⏱️ Filling: {self._format_duration(duration)}"

        return msg

    # ═══════════════════════════════════════════════════════════════════════════
    # MESSAGE BUILDERS - STATUS CHANGE
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_status_message(
        self,
        position_group: PositionGroup,
        old_status: str,
        new_status: str,
        pyramid: Pyramid,
        filled_count: int,
        total_count: int,
        tp_mode: str = None,
        tp_percent: Decimal = None
    ) -> str:
        """Build status change notification message"""

        group_id = self._get_position_id_short(position_group)
        pyramid_num = (pyramid.pyramid_index if pyramid else 0) + 1
        duration = self._get_duration_hours(position_group)

        # Header
        msg = f"📊 Status Changed\n"
        msg += f"{self._get_header(position_group)}\n"
        msg += f"🆔 {group_id}\n\n"

        # Status transition
        status_emoji = "✅" if new_status.upper() == "ACTIVE" else "📊"
        msg += f"{old_status.upper()} → {new_status.upper()} {status_emoji}\n\n"

        # Summary box
        msg += "┌─ Position Summary ───────────\n"
        if new_status.upper() == "ACTIVE":
            msg += f"│ All {total_count} DCA legs filled!\n"
        else:
            msg += f"│ {filled_count}/{total_count} DCA legs filled\n"

        if position_group.weighted_avg_entry:
            msg += f"│ Avg Entry: {self._format_price(position_group.weighted_avg_entry)}\n"
        if position_group.total_invested_usd:
            msg += f"│ Invested: ${self._format_price(position_group.total_invested_usd)}\n"
        if duration:
            msg += f"│ Time to fill: {self._format_duration(duration)}\n"
        msg += "└──────────────────────────────\n\n"

        # Footer
        msg += f"🔷 Pyramid {pyramid_num}/{position_group.max_pyramids} · {position_group.side.upper()}\n"
        if tp_mode and tp_percent:
            msg += f"🎯 TP Mode: {tp_mode.replace('_', ' ')} (+{float(tp_percent):.1f}%)"

        return msg

    # ═══════════════════════════════════════════════════════════════════════════
    # MESSAGE BUILDERS - TP HIT
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_tp_hit_message(
        self,
        position_group: PositionGroup,
        pyramid: Optional[Pyramid],
        tp_type: str,
        tp_price: Decimal,
        pnl_percent: Decimal,
        pnl_usd: Optional[Decimal] = None,
        closed_quantity: Optional[Decimal] = None,
        remaining_pyramids: int = 0,
        leg_index: Optional[int] = None
    ) -> str:
        """Build TP hit notification message with type-specific formatting"""

        group_id = self._get_position_id_short(position_group)
        duration = self._get_duration_hours(position_group)
        pyramid_num = (pyramid.pyramid_index if pyramid else 0) + 1

        # Header based on TP type
        if tp_type == "per_leg":
            msg = f"🎯 Per-Leg TP Hit!\n"
        elif tp_type == "pyramid_aggregate":
            msg = f"🎯 Pyramid TP Hit!\n"
        else:
            msg = f"🎯 Aggregate TP Hit!\n"

        msg += f"{self._get_header(position_group)}\n"
        msg += f"🆔 {group_id}\n\n"

        # Description based on type
        if tp_type == "per_leg" and leg_index is not None:
            msg += f"Leg {leg_index + 1} closed at TP\n\n"
        else:
            msg += f"Full pyramid closed at TP\n\n"

        # Price and P&L details
        msg += f"📍 Avg Entry: {self._format_price(position_group.weighted_avg_entry)}\n"
        msg += f"📍 Exit: {self._format_price(tp_price)}\n"

        pnl_emoji = "📈" if float(pnl_percent) >= 0 else "📉"
        msg += f"{pnl_emoji} Profit: {self._format_pnl(pnl_percent, pnl_usd)}\n"

        if closed_quantity:
            value = float(tp_price or 0) * float(closed_quantity)
            msg += f"📦 Closed: {float(closed_quantity):.6f} (${value:,.2f})\n"

        msg += "\n"

        # Result box
        msg += "┌─ Result ─────────────────────\n"
        if tp_type == "per_leg":
            msg += f"│ Leg {leg_index + 1 if leg_index else '?'} TP hit\n"
        else:
            msg += f"│ Pyramid {pyramid_num} closed\n"
        msg += f"│ Pyramids remaining: {remaining_pyramids}\n"
        if position_group.total_invested_usd and remaining_pyramids > 0:
            msg += f"│ Still invested: ${self._format_price(position_group.total_invested_usd)}\n"
        msg += "└──────────────────────────────\n\n"

        if self.config.show_duration and duration:
            msg += f"⏱️ Position duration: {self._format_duration(duration)}"

        return msg

    # ═══════════════════════════════════════════════════════════════════════════
    # MESSAGE BUILDERS - RISK ALERTS
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_risk_event_message(
        self,
        position_group: PositionGroup,
        event_type: str,
        loss_percent: Optional[Decimal] = None,
        loss_usd: Optional[Decimal] = None,
        timer_minutes: Optional[int] = None,
        offset_position: Optional[str] = None,
        offset_profit: Optional[Decimal] = None,
        net_result: Optional[Decimal] = None
    ) -> str:
        """Build risk event notification message"""

        group_id = self._get_position_id_short(position_group)
        duration = self._get_duration_hours(position_group)

        # Header based on event type
        if event_type == "timer_started":
            msg = f"⚠️ Risk Timer Started\n"
        elif event_type == "timer_expired":
            msg = f"🔴 Risk Timer Expired\n"
        elif event_type == "timer_reset":
            msg = f"✅ Risk Timer Reset\n"
        elif event_type == "offset_executed":
            msg = f"⚖️ Risk Offset Executed\n"
        else:
            msg = f"⚠️ Risk Alert\n"

        msg += f"{self._get_header(position_group)}\n"
        msg += f"🆔 {group_id}\n\n"

        # Event-specific content
        if event_type == "timer_started":
            if loss_percent:
                msg += f"📉 Current Loss: {self._format_pnl(loss_percent, loss_usd)}\n"
            if timer_minutes:
                msg += f"⏱️ Evaluation in: {timer_minutes} minutes\n\n"

            msg += "┌─ Position Info ──────────────\n"
            if position_group.total_invested_usd:
                msg += f"│ Invested: ${self._format_price(position_group.total_invested_usd)}\n"
            msg += f"│ Pyramids: {position_group.pyramid_count}/{position_group.max_pyramids} filled\n"
            if position_group.weighted_avg_entry:
                msg += f"│ Avg Entry: {self._format_price(position_group.weighted_avg_entry)}\n"
            msg += "└──────────────────────────────\n\n"

            msg += f"🔷 {position_group.side.upper()} · Open {self._format_duration(duration)}\n\n"
            msg += "Position will be evaluated for\noffset when timer expires."

        elif event_type == "timer_expired":
            msg += "Loss persisted beyond threshold!\n\n"
            if loss_percent:
                msg += f"📉 Loss: {self._format_pnl(loss_percent, loss_usd)}\n"
            if timer_minutes:
                msg += f"⏱️ Timer ran for: {timer_minutes} minutes\n\n"
            msg += "Engine will attempt risk offset\nagainst profitable positions."

        elif event_type == "timer_reset":
            msg += "Position recovered - timer cancelled.\n\n"
            if position_group.unrealized_pnl_percent:
                pnl = position_group.unrealized_pnl_percent
                emoji = "📈" if float(pnl) >= 0 else "📉"
                msg += f"{emoji} Current P&L: {float(pnl):+.2f}%"

        elif event_type == "offset_executed":
            msg += "Position closed to offset losses\n\n"
            if position_group.weighted_avg_entry:
                msg += f"📍 Entry: {self._format_price(position_group.weighted_avg_entry)}\n"
            if loss_percent:
                msg += f"📉 Loss: {self._format_pnl(loss_percent, loss_usd)}\n\n"
            if offset_position and offset_profit:
                msg += f"Offset against: {offset_position} (+${float(offset_profit):,.2f})\n"
            if net_result is not None:
                emoji = "📈" if float(net_result) >= 0 else "📉"
                msg += f"{emoji} Net result: ${float(net_result):+,.2f}\n\n"
            if duration:
                msg += f"⏱️ Duration: {self._format_duration(duration)}"

        return msg

    # ═══════════════════════════════════════════════════════════════════════════
    # MESSAGE BUILDERS - FAILURE ALERTS
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_failure_message(
        self,
        position_group: PositionGroup,
        error_type: str,
        error_message: str,
        pyramid: Optional[Pyramid] = None,
        order: Optional[DCAOrder] = None
    ) -> str:
        """Build failure alert message"""

        group_id = self._get_position_id_short(position_group)
        pyramid_num = (pyramid.pyramid_index if pyramid else 0) + 1
        leg_num = order.leg_index + 1 if order and hasattr(order, 'leg_index') else "?"

        # Header
        if error_type == "order_failed":
            msg = f"🚨 Order Failed\n"
        elif error_type == "position_failed":
            msg = f"🚨 Position Failed\n"
        else:
            msg = f"🚨 Error\n"

        msg += f"{self._get_header(position_group)}\n"
        msg += f"🆔 {group_id}\n\n"

        if error_type == "order_failed" and order:
            msg += f"❌ Leg {leg_num} failed to place\n\n"

        # Error details box
        msg += "┌─ Error Details ──────────────\n"
        msg += f"│ Error: {error_message}\n"
        if order:
            if order.price:
                msg += f"│ Price: {self._format_price(order.price)}\n"
            if order.quantity:
                msg += f"│ Qty: {float(order.quantity):.6f}\n"
                if order.price:
                    value = float(order.price) * float(order.quantity)
                    msg += f"│ Value: ${value:,.2f}\n"
        msg += "└──────────────────────────────\n\n"

        # Action required
        msg += "⚠️ Action Required:\n"
        if "balance" in error_message.lower():
            msg += "Check exchange balance or\nreduce position size."
        elif "connection" in error_message.lower():
            msg += "Check exchange connectivity."
        else:
            msg += "Review error and take action."

        msg += f"\n\n🔷 Pyramid {pyramid_num}/{position_group.max_pyramids} · {position_group.side.upper()}"

        return msg

    # ═══════════════════════════════════════════════════════════════════════════
    # MESSAGE BUILDERS - PYRAMID ADDED
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_pyramid_message(
        self,
        position_group: PositionGroup,
        pyramid: Pyramid,
        entry_prices: List[Optional[Decimal]],
        weights: List[int],
        tp_percent: Optional[Decimal] = None
    ) -> str:
        """Build new pyramid added notification message"""

        group_id = self._get_position_id_short(position_group)
        pyramid_num = pyramid.pyramid_index + 1
        duration = self._get_duration_hours(position_group)

        # Header
        msg = f"🔺 Pyramid {pyramid_num} Added\n"
        msg += f"{self._get_header(position_group)}\n"
        msg += f"🆔 {group_id}\n\n"

        msg += "New pyramid entry triggered!\n\n"

        # Pyramid levels box
        msg += f"┌─ Pyramid {pyramid_num} Levels ───────────\n"
        for i, price in enumerate(entry_prices):
            weight = weights[i] if i < len(weights) else 0
            price_str = self._format_price(price) if price else "TBD"
            msg += f"│ ⏳ {weight}%  {price_str}\n"
        msg += "└──────────────────────────────\n\n"

        # Summary
        msg += f"📊 Total pyramids: {pyramid_num}/{position_group.max_pyramids}\n"
        if position_group.total_invested_usd:
            msg += f"💰 Previously invested: ${self._format_price(position_group.total_invested_usd)}\n"
        if tp_percent:
            # Calculate TP target from base entry
            if position_group.base_entry_price:
                tp_target = position_group.base_entry_price * (1 + tp_percent / 100)
                msg += f"🎯 P{pyramid_num} TP Target: {self._format_price(tp_target)} (+{float(tp_percent):.1f}%)\n"

        msg += f"\n🔷 {position_group.side.upper()} · Open {self._format_duration(duration)}"

        return msg

    # ═══════════════════════════════════════════════════════════════════════════
    # MESSAGE BUILDERS - EXIT SIGNAL
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_exit_message(
        self,
        position_group: PositionGroup,
        exit_price: Decimal,
        pnl_percent: Decimal,
        pyramids_used: int,
        exit_reason: str = "engine",
        pnl_usd: Optional[Decimal] = None,
        duration_hours: Optional[float] = None,
        filled_legs: int = 0,
        total_legs: int = 0,
        tp_mode: str = None
    ) -> str:
        """Build enhanced exit signal message"""

        group_id = self._get_position_id_short(position_group)

        # Exit reason mapping
        reason_info = {
            "manual": ("🖐️", "Manual Close", "Position manually closed by user"),
            "engine": ("🤖", "Engine Exit", "Engine closed based on market conditions"),
            "tp_hit": ("🎯", "Take Profit", "Take profit target reached"),
            "risk_offset": ("⚖️", "Risk Offset", "Closed to offset losses from another position"),
        }
        icon, title, description = reason_info.get(exit_reason, ("🚪", "Exit", "Position closed"))

        # Header
        msg = f"🚪 Position Closed\n"
        msg += f"{self._get_header(position_group)}\n"
        msg += f"🆔 {group_id}\n\n"

        msg += f"{icon} {title}\n\n"

        # Trade summary box
        is_profit = float(pnl_percent) >= 0
        pnl_emoji = "📈" if is_profit else "📉"

        msg += "┌─ Trade Summary ──────────────\n"
        msg += f"│ Side: {position_group.side.upper()}\n"
        msg += f"│ Avg Entry: {self._format_price(position_group.weighted_avg_entry)}\n"
        msg += f"│ Exit Price: {self._format_price(exit_price)}\n"
        msg += f"│\n"
        msg += f"│ {pnl_emoji} Profit: {self._format_pnl(pnl_percent, pnl_usd)}\n"
        if self.config.show_invested_amount and position_group.total_invested_usd:
            msg += f"│ 💰 Invested: ${self._format_price(position_group.total_invested_usd)}\n"
        if position_group.total_filled_quantity:
            msg += f"│ 📦 Quantity: {float(position_group.total_filled_quantity):.6f}\n"
        msg += "└──────────────────────────────\n\n"

        # Position stats box
        msg += "┌─ Position Stats ─────────────\n"
        msg += f"│ Pyramids used: {pyramids_used}/{position_group.max_pyramids}\n"
        if filled_legs and total_legs:
            msg += f"│ DCA legs filled: {filled_legs}/{total_legs}\n"
        if tp_mode:
            msg += f"│ TP Mode: {tp_mode.replace('_', ' ')}\n"
        if self.config.show_duration and duration_hours:
            msg += f"│ Duration: {self._format_duration(duration_hours)}\n"
        msg += "└──────────────────────────────\n\n"

        msg += f"💡 {description}"

        return msg

    # ═══════════════════════════════════════════════════════════════════════════
    # SEND METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    async def send_entry_signal(
        self,
        position_group: PositionGroup,
        pyramid: Pyramid,
        entry_prices: List[Optional[Decimal]],
        weights: List[int],
        filled_count: int = 0,
        total_count: int = 0,
        tp_prices: List[Optional[Decimal]] = None,
        tp_mode: str = None,
        aggregate_tp: Decimal = None,
        pyramid_tp_percent: Decimal = None,
        session: AsyncSession = None
    ) -> Optional[int]:
        """Send or update entry signal message"""

        if not self.config.enabled or not self.config.send_entry_signals:
            return None

        if not self._should_send():
            return None

        # Calculate filled count if not provided
        if filled_count == 0:
            filled_count = sum(1 for p in entry_prices if p is not None)
        if total_count == 0:
            total_count = len(entry_prices)

        message = self._build_entry_message(
            position_group=position_group,
            pyramid=pyramid,
            entry_prices=entry_prices,
            weights=weights,
            filled_count=filled_count,
            total_count=total_count,
            tp_prices=tp_prices,
            tp_mode=tp_mode,
            aggregate_tp=aggregate_tp,
            pyramid_tp_percent=pyramid_tp_percent
        )

        # Check if we should update existing message
        if position_group.telegram_message_id and self.config.update_existing_message:
            message_id = await self._update_message(position_group.telegram_message_id, message)
            return message_id
        else:
            message_id = await self._send_message(message)
            if message_id and session:
                await self._save_message_id(position_group, message_id, session)
            return message_id

    async def send_exit_signal(
        self,
        position_group: PositionGroup,
        exit_price: Decimal,
        pnl_percent: Decimal,
        pyramids_used: int,
        exit_reason: str = "engine",
        pnl_usd: Optional[Decimal] = None,
        duration_hours: Optional[float] = None,
        filled_legs: int = 0,
        total_legs: int = 0,
        tp_mode: str = None
    ) -> Optional[int]:
        """Send exit signal message"""

        if not self.config.enabled or not self.config.send_exit_signals:
            return None

        if not self._should_send():
            return None

        message = self._build_exit_message(
            position_group=position_group,
            exit_price=exit_price,
            pnl_percent=pnl_percent,
            pyramids_used=pyramids_used,
            exit_reason=exit_reason,
            pnl_usd=pnl_usd,
            duration_hours=duration_hours,
            filled_legs=filled_legs,
            total_legs=total_legs,
            tp_mode=tp_mode
        )

        return await self._send_message(message)

    async def send_dca_fill(
        self,
        position_group: PositionGroup,
        order: DCAOrder,
        filled_count: int,
        total_count: int,
        pyramid: Pyramid,
        session: AsyncSession = None
    ) -> Optional[int]:
        """Send DCA fill notification"""

        if not self.config.enabled or not self.config.send_dca_fill_updates:
            return None

        if not self._should_send():
            return None

        message = self._build_dca_fill_message(
            position_group=position_group,
            order=order,
            filled_count=filled_count,
            total_count=total_count,
            pyramid=pyramid
        )

        # Update existing message or send new
        if position_group.telegram_message_id and self.config.update_existing_message:
            return await self._update_message(position_group.telegram_message_id, message)
        else:
            message_id = await self._send_message(message)
            if message_id and session:
                await self._save_message_id(position_group, message_id, session)
            return message_id

    async def send_status_change(
        self,
        position_group: PositionGroup,
        old_status: str,
        new_status: str,
        pyramid: Pyramid,
        filled_count: int,
        total_count: int,
        tp_mode: str = None,
        tp_percent: Decimal = None
    ) -> Optional[int]:
        """Send status change notification"""

        if not self.config.enabled or not self.config.send_status_updates:
            return None

        if not self._should_send():
            return None

        message = self._build_status_message(
            position_group=position_group,
            old_status=old_status,
            new_status=new_status,
            pyramid=pyramid,
            filled_count=filled_count,
            total_count=total_count,
            tp_mode=tp_mode,
            tp_percent=tp_percent
        )

        return await self._send_message(message)

    async def send_tp_hit(
        self,
        position_group: PositionGroup,
        pyramid: Optional[Pyramid],
        tp_type: str,
        tp_price: Decimal,
        pnl_percent: Decimal,
        pnl_usd: Optional[Decimal] = None,
        closed_quantity: Optional[Decimal] = None,
        remaining_pyramids: int = 0,
        leg_index: Optional[int] = None
    ) -> Optional[int]:
        """Send TP hit notification"""

        if not self.config.enabled or not self.config.send_tp_hit_updates:
            return None

        if not self._should_send():
            return None

        message = self._build_tp_hit_message(
            position_group=position_group,
            pyramid=pyramid,
            tp_type=tp_type,
            tp_price=tp_price,
            pnl_percent=pnl_percent,
            pnl_usd=pnl_usd,
            closed_quantity=closed_quantity,
            remaining_pyramids=remaining_pyramids,
            leg_index=leg_index
        )

        return await self._send_message(message)

    async def send_risk_event(
        self,
        position_group: PositionGroup,
        event_type: str,
        loss_percent: Optional[Decimal] = None,
        loss_usd: Optional[Decimal] = None,
        timer_minutes: Optional[int] = None,
        offset_position: Optional[str] = None,
        offset_profit: Optional[Decimal] = None,
        net_result: Optional[Decimal] = None
    ) -> Optional[int]:
        """Send risk event notification"""

        if not self.config.enabled or not self.config.send_risk_alerts:
            return None

        # Risk alerts are urgent - always send
        if not self._should_send(is_urgent=True):
            return None

        message = self._build_risk_event_message(
            position_group=position_group,
            event_type=event_type,
            loss_percent=loss_percent,
            loss_usd=loss_usd,
            timer_minutes=timer_minutes,
            offset_position=offset_position,
            offset_profit=offset_profit,
            net_result=net_result
        )

        return await self._send_message(message)

    async def send_failure(
        self,
        position_group: PositionGroup,
        error_type: str,
        error_message: str,
        pyramid: Optional[Pyramid] = None,
        order: Optional[DCAOrder] = None
    ) -> Optional[int]:
        """Send failure alert notification"""

        if not self.config.enabled or not self.config.send_failure_alerts:
            return None

        # Failure alerts are urgent - always send
        if not self._should_send(is_urgent=True):
            return None

        message = self._build_failure_message(
            position_group=position_group,
            error_type=error_type,
            error_message=error_message,
            pyramid=pyramid,
            order=order
        )

        return await self._send_message(message)

    async def send_pyramid_added(
        self,
        position_group: PositionGroup,
        pyramid: Pyramid,
        entry_prices: List[Optional[Decimal]],
        weights: List[int],
        tp_percent: Optional[Decimal] = None
    ) -> Optional[int]:
        """Send new pyramid added notification"""

        if not self.config.enabled or not self.config.send_pyramid_updates:
            return None

        if not self._should_send():
            return None

        message = self._build_pyramid_message(
            position_group=position_group,
            pyramid=pyramid,
            entry_prices=entry_prices,
            weights=weights,
            tp_percent=tp_percent
        )

        return await self._send_message(message)

    # ═══════════════════════════════════════════════════════════════════════════
    # TELEGRAM API METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    async def _save_message_id(
        self,
        position_group: PositionGroup,
        message_id: int,
        session: AsyncSession
    ) -> None:
        """Save message ID to position group for persistence"""
        try:
            position_group.telegram_message_id = message_id
            await session.commit()
            logger.debug(f"Saved Telegram message ID {message_id} to position {position_group.id}")
        except Exception as e:
            logger.error(f"Failed to save Telegram message ID: {e}")

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
        """Test Telegram bot connection"""
        try:
            async with aiohttp.ClientSession() as session:
                # Check bot token
                async with session.get(f"{self.base_url}/getMe") as r:
                    if r.status != 200:
                        return False, await r.text()

                # Check channel access
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
