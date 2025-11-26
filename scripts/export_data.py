#!/usr/bin/env python3
"""
Exports data from the database to JSON or CSV.

Usage:
    python scripts/export_data.py --type {positions,history} [--format {json,csv}] [--output FILE]
"""
import sys
import os
import argparse
import asyncio
import json
import csv
import logging
from datetime import datetime

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../backend'))

# Load .env variables
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '../.env'))
except ImportError:
    pass # dotenv might not be available, or handled by caller

try:
    from app.db.database import AsyncSessionLocal
    from app.models.position_group import PositionGroup
    from app.models.user import User # Import User model
    from sqlalchemy import select
except ImportError as e:
    print(f"Error: Could not import backend modules. {e}", file=sys.stderr)
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

async def fetch_data(data_type):
    async with AsyncSessionLocal() as session:
        if data_type == 'positions':
            stmt = select(PositionGroup)
            result = await session.execute(stmt)
            groups = result.scalars().all()
            # Convert to dict
            data = []
            for g in groups:
                data.append({
                    "id": str(g.id),
                    "user_id": str(g.user_id),
                    "exchange": g.exchange,
                    "symbol": g.symbol,
                    "timeframe": g.timeframe,
                    "side": g.side,
                    "status": g.status.value if hasattr(g.status, 'value') else str(g.status),
                    "base_entry_price": float(g.base_entry_price) if g.base_entry_price else None,
                    "weighted_avg_entry": float(g.weighted_avg_entry) if g.weighted_avg_entry else None,
                    "total_filled_quantity": float(g.total_filled_quantity) if g.total_filled_quantity else 0.0,
                    "total_invested_usd": float(g.total_invested_usd) if g.total_invested_usd else 0.0,
                    "unrealized_pnl_usd": float(g.unrealized_pnl_usd) if g.unrealized_pnl_usd else 0.0,
                    "realized_pnl_usd": float(g.realized_pnl_usd) if g.realized_pnl_usd else 0.0,
                    "pyramid_count": g.pyramid_count,
                    "created_at": g.created_at.isoformat() if g.created_at else None,
                    "updated_at": g.updated_at.isoformat() if g.updated_at else None,
                    "closed_at": g.closed_at.isoformat() if g.closed_at else None
                })
            return data
        elif data_type == 'users':
            stmt = select(User)
            result = await session.execute(stmt)
            users = result.scalars().all()
            data = []
            for u in users:
                # Exclude sensitive fields like hashed_password and encrypted_api_keys
                data.append({
                    "id": str(u.id),
                    "username": u.username,
                    "email": u.email,
                    "is_active": u.is_active,
                    "is_superuser": u.is_superuser,
                    "exchange": u.exchange, 
                    "configured_exchanges": u.configured_exchanges,
                    "risk_config": u.risk_config,
                    "dca_grid_config": u.dca_grid_config,
                    "created_at": u.created_at.isoformat() if u.created_at else None,
                    "updated_at": u.updated_at.isoformat() if u.updated_at else None,
                    "webhook_secret_set": bool(u.webhook_secret) 
                })
            return data
        else:
            return []

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--type', choices=['positions', 'users'], required=True, help='Data type to export')
    parser.add_argument('--format', choices=['json', 'csv'], default='json', help='Output format')
    parser.add_argument('--output', help='Output file path')
    
    args = parser.parse_args()
    
    try:
        data = asyncio.run(fetch_data(args.type))
    except Exception as e:
        logger.error(f"Fetch failed: {e}")
        return 1

    if args.format == 'json':
        output_str = json.dumps(data, indent=2)
    else:
        # CSV
        if not data:
            output_str = ""
        else:
            import io
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
            output_str = output.getvalue()

    if args.output:
        with open(args.output, 'w') as f:
            f.write(output_str)
        logger.info(f"Exported {len(data)} records to {args.output}")
    else:
        print(output_str)

    return 0

if __name__ == "__main__":
    sys.exit(main())
