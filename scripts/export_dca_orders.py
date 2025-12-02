import asyncio
import os
import sys
import uuid
from sqlalchemy import select
import json
from datetime import datetime
import argparse

sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.db.database import AsyncSessionLocal
from app.models.dca_order import DCAOrder
from app.models.position_group import PositionGroup

async def export_dca_orders(position_group_id: str):
    async with AsyncSessionLocal() as session:
        pg_uuid = uuid.UUID(position_group_id)
        
        result = await session.execute(
            select(DCAOrder).where(DCAOrder.group_id == pg_uuid).order_by(DCAOrder.created_at)
        )
        dca_orders = result.scalars().all()

        if not dca_orders:
            print(f"No DCA orders found for PositionGroup {position_group_id}.")
            return

        order_list = []
        for order in dca_orders:
            order_data = {
                "id": str(order.id),
                "group_id": str(order.group_id),
                "pyramid_id": str(order.pyramid_id),
                "leg_index": order.leg_index,
                "symbol": order.symbol,
                "side": order.side,
                "order_type": order.order_type.value if order.order_type else None,
                "price": float(order.price),
                "quantity": float(order.quantity),
                "gap_percent": float(order.gap_percent),
                "weight_percent": float(order.weight_percent),
                "tp_percent": float(order.tp_percent),
                "tp_price": float(order.tp_price),
                "status": order.status.value if order.status else None,
                "filled_quantity": float(order.filled_quantity),
                "avg_fill_price": float(order.avg_fill_price) if order.avg_fill_price else None,
                "tp_hit": order.tp_hit,
                "tp_order_id": order.tp_order_id,
                "tp_executed_at": order.tp_executed_at.isoformat() if order.tp_executed_at else None,
                "created_at": order.created_at.isoformat(),
                "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
                "filled_at": order.filled_at.isoformat() if order.filled_at else None,
                "cancelled_at": order.cancelled_at.isoformat() if order.cancelled_at else None,
            }
            order_list.append(order_data)
        
        print(json.dumps(order_list, indent=2))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export DCA orders for a given position group ID.")
    parser.add_argument("position_group_id", type=str, help="The ID of the position group.")
    args = parser.parse_args()
    asyncio.run(export_dca_orders(args.position_group_id))