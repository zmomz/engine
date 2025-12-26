"""
Exchange Synchronization Service.

Handles synchronization between local database state and exchange state.
Key functions:
- Detect orphaned orders on exchange not in local DB
- Update local orders whose status has changed on exchange
- Clean up local orders that no longer exist on exchange
"""
import logging
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dca_order import DCAOrder, OrderStatus
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.user import User
from app.repositories.dca_order import DCAOrderRepository
from app.repositories.position_group import PositionGroupRepository
from app.services.exchange_abstraction.interface import ExchangeInterface

logger = logging.getLogger(__name__)


class ExchangeSyncService:
    """
    Service for synchronizing exchange state with local database.
    """

    def __init__(
        self,
        session: AsyncSession,
        user: User,
        exchange_connector: ExchangeInterface,
        dca_order_repository: Optional[DCAOrderRepository] = None,
        position_group_repository: Optional[PositionGroupRepository] = None
    ):
        self.session = session
        self.user = user
        self.exchange_connector = exchange_connector
        self.dca_order_repo = dca_order_repository or DCAOrderRepository(session)
        self.position_group_repo = position_group_repository or PositionGroupRepository(session)

    async def sync_orders_with_exchange(
        self,
        position_group_id: uuid.UUID,
        update_local: bool = True
    ) -> Dict:
        """
        Synchronize all orders for a position group with exchange state.

        Args:
            position_group_id: Position group to sync
            update_local: If True, update local DB with exchange state

        Returns:
            Dict with sync results: {
                "synced": int,
                "updated": int,
                "not_found": int,
                "errors": int,
                "details": [...]
            }
        """
        result = {
            "synced": 0,
            "updated": 0,
            "not_found": 0,
            "errors": 0,
            "details": []
        }

        try:
            # Get position group
            position_group = await self.position_group_repo.get(position_group_id)
            if not position_group:
                logger.error(f"Position group {position_group_id} not found")
                return result

            # Security check
            if position_group.user_id != self.user.id:
                logger.error(f"User {self.user.id} not authorized for position group {position_group_id}")
                return result

            # Get all orders for this position group
            local_orders = await self.dca_order_repo.get_by_group_id(position_group_id)

            for order in local_orders:
                try:
                    sync_detail = await self._sync_single_order(order, update_local)
                    result["details"].append(sync_detail)

                    if sync_detail["status"] == "synced":
                        result["synced"] += 1
                    elif sync_detail["status"] == "updated":
                        result["updated"] += 1
                    elif sync_detail["status"] == "not_found":
                        result["not_found"] += 1

                except Exception as e:
                    result["errors"] += 1
                    result["details"].append({
                        "order_id": str(order.id),
                        "status": "error",
                        "error": str(e)
                    })

            logger.info(
                f"Sync completed for position {position_group_id}: "
                f"synced={result['synced']}, updated={result['updated']}, "
                f"not_found={result['not_found']}, errors={result['errors']}"
            )

            return result

        except Exception as e:
            logger.error(f"Exchange sync failed for position {position_group_id}: {e}")
            result["errors"] += 1
            return result

    async def _sync_single_order(
        self,
        order: DCAOrder,
        update_local: bool
    ) -> Dict:
        """
        Sync a single order with exchange.

        Returns:
            Dict with order sync status
        """
        detail = {
            "order_id": str(order.id),
            "exchange_order_id": order.exchange_order_id,
            "local_status": order.status,
            "status": "synced"  # Default to synced
        }

        # Skip orders without exchange ID (trigger pending, etc.)
        if not order.exchange_order_id:
            detail["status"] = "skipped"
            detail["reason"] = "no_exchange_id"
            return detail

        try:
            # Fetch order from exchange
            exchange_order = await self.exchange_connector.get_order_status(
                order_id=order.exchange_order_id,
                symbol=order.symbol
            )

            exchange_status = exchange_order["status"].lower()
            detail["exchange_status"] = exchange_status

            # Map exchange status to local status
            status_mapping = {
                "open": OrderStatus.OPEN.value,
                "closed": OrderStatus.FILLED.value,
                "filled": OrderStatus.FILLED.value,
                "canceled": OrderStatus.CANCELLED.value,
                "cancelled": OrderStatus.CANCELLED.value,
                "expired": OrderStatus.CANCELLED.value,
                "rejected": OrderStatus.FAILED.value
            }

            new_local_status = status_mapping.get(exchange_status, order.status)

            # Check if status changed
            if order.status != new_local_status:
                detail["status"] = "updated"
                detail["old_status"] = order.status
                detail["new_status"] = new_local_status

                if update_local:
                    order.status = new_local_status

                    # Update fill details if filled
                    if new_local_status == OrderStatus.FILLED.value:
                        filled_qty = exchange_order.get("filled")
                        if filled_qty:
                            order.filled_quantity = Decimal(str(filled_qty))
                        avg_price = exchange_order.get("average")
                        if avg_price:
                            order.avg_fill_price = Decimal(str(avg_price))
                        if not order.filled_at:
                            order.filled_at = datetime.utcnow()

                    await self.dca_order_repo.update(order)
                    logger.info(
                        f"Order {order.id} status updated: {detail['old_status']} -> {new_local_status}"
                    )

            return detail

        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "order does not exist" in error_str:
                detail["status"] = "not_found"
                detail["reason"] = "order_not_on_exchange"

                if update_local and order.status in [OrderStatus.OPEN.value, OrderStatus.TRIGGER_PENDING.value]:
                    # Mark as cancelled if not found on exchange
                    order.status = OrderStatus.CANCELLED.value
                    await self.dca_order_repo.update(order)
                    logger.warning(
                        f"Order {order.id} not found on exchange, marked as CANCELLED"
                    )
            else:
                raise

            return detail

    async def detect_orphaned_exchange_orders(
        self,
        symbol: str,
        since_hours: int = 24
    ) -> List[Dict]:
        """
        Detect orders that exist on exchange but not in local database.

        Args:
            symbol: Symbol to check (e.g., "BTCUSDT")
            since_hours: Look back period in hours

        Returns:
            List of orphaned order details from exchange
        """
        orphaned_orders = []

        try:
            # Fetch open orders from exchange for this symbol
            exchange_orders = await self.exchange_connector.fetch_open_orders(symbol)

            # Get local order IDs for this user/symbol
            local_orders = await self.dca_order_repo.get_by_symbol_and_user(
                user_id=self.user.id,
                symbol=symbol
            )
            local_exchange_ids = {
                order.exchange_order_id
                for order in local_orders
                if order.exchange_order_id
            }

            # Find orders on exchange not in local DB
            for ex_order in exchange_orders:
                ex_order_id = str(ex_order.get("id", ""))
                if ex_order_id and ex_order_id not in local_exchange_ids:
                    orphaned_orders.append({
                        "exchange_order_id": ex_order_id,
                        "symbol": symbol,
                        "side": ex_order.get("side"),
                        "type": ex_order.get("type"),
                        "price": ex_order.get("price"),
                        "quantity": ex_order.get("amount"),
                        "status": ex_order.get("status"),
                        "created_at": ex_order.get("datetime")
                    })

            if orphaned_orders:
                logger.warning(
                    f"Found {len(orphaned_orders)} orphaned orders on exchange for {symbol}"
                )

            return orphaned_orders

        except Exception as e:
            logger.error(f"Failed to detect orphaned orders for {symbol}: {e}")
            return []

    async def cleanup_stale_local_orders(
        self,
        position_group_id: uuid.UUID,
        stale_hours: int = 48
    ) -> Dict:
        """
        Clean up local orders that are stuck in OPEN status but likely
        cancelled or filled on exchange.

        Args:
            position_group_id: Position group to clean up
            stale_hours: Hours after which an open order is considered stale

        Returns:
            Cleanup results
        """
        result = {
            "checked": 0,
            "cleaned": 0,
            "errors": 0
        }

        try:
            local_orders = await self.dca_order_repo.get_by_group_id(position_group_id)
            stale_threshold = datetime.utcnow() - timedelta(hours=stale_hours)

            for order in local_orders:
                # Only check OPEN orders older than threshold
                if order.status != OrderStatus.OPEN.value:
                    continue
                if order.submitted_at and order.submitted_at > stale_threshold:
                    continue

                result["checked"] += 1

                try:
                    # Check with exchange
                    sync_result = await self._sync_single_order(order, update_local=True)
                    if sync_result["status"] in ["updated", "not_found"]:
                        result["cleaned"] += 1

                except Exception as e:
                    result["errors"] += 1
                    logger.error(f"Failed to cleanup order {order.id}: {e}")

            return result

        except Exception as e:
            logger.error(f"Cleanup failed for position {position_group_id}: {e}")
            return result
