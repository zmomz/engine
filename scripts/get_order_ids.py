import asyncio
import os
import sys
import uuid
from sqlalchemy import select
from sqlalchemy.orm import selectinload

sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.db.database import AsyncSessionLocal
from app.models.user import User
from app.models.position_group import PositionGroup
from app.models.dca_order import DCAOrder

async def get_order_ids_for_last_position(username: str, symbol: str):
    """
    Fetches the order IDs for the most recent position group for a given user and symbol.
    """
    async with AsyncSessionLocal() as session:
        # 1. Find the user
        user_result = await session.execute(select(User).where(User.username == username))
        user = user_result.scalars().first()

        if not user:
            print(f"User '{username}' not found.")
            return

        # 2. Find the most recent position group for the user and symbol
        position_group_result = await session.execute(
            select(PositionGroup)
            .where(PositionGroup.user_id == user.id)
            .where(PositionGroup.symbol == symbol)
            .order_by(PositionGroup.created_at.desc())
            .limit(1)
        )
        latest_position_group = position_group_result.scalars().first()

        if not latest_position_group:
            print(f"No position group found for user '{username}' and symbol '{symbol}'.")
            return

        print(f"Found latest position group: {latest_position_group.id}")

        # 3. Find all DCA orders for that position group
        orders_result = await session.execute(
            select(DCAOrder)
            .where(DCAOrder.group_id == latest_position_group.id)
            .order_by(DCAOrder.leg_index)
        )
        orders = orders_result.scalars().all()

        if not orders:
            print(f"No orders found for position group {latest_position_group.id}.")
            return

        # 4. Print the order IDs
        print("\nOrder IDs for the new position:")
        print("-" * 40)
        for order in orders:
            print(f"  Leg Index: {order.leg_index}")
            print(f"  DB Order ID: {order.id}")
            print(f"  Exchange Order ID: {order.exchange_order_id}")
            print(f"  Status: {order.status}")
            print("-" * 40)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Get order IDs for the last position of a user and symbol.")
    parser.add_argument("--username", type=str, default="testuser", help="The username to retrieve order IDs for.")
    parser.add_argument("--symbol", type=str, default="BTCUSDT", help="The symbol to retrieve order IDs for.")
    args = parser.parse_args()

    asyncio.run(get_order_ids_for_last_position(args.username, args.symbol))
