#!/usr/bin/env python3
"""
Simulate TradingView webhook signals for all configured DCA assets.

Usage: python scripts/simulate_signals.py [--user username] [--action buy|sell] [--delay seconds]

This script sends entry signals to all configured DCA pairs to test the system.
"""
import argparse
import asyncio
import sys
import uuid
from datetime import datetime
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import httpx
from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.models.dca_configuration import DCAConfiguration
from app.models.user import User


# Configuration
# Use 127.0.0.1 instead of localhost for compatibility inside Docker
# When running inside Docker, use the service name or host.docker.internal
import os
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api/v1")


async def get_user_and_configs(username: str = None):
    """Get user and their DCA configurations from database."""
    async with AsyncSessionLocal() as session:
        # Find user
        if username:
            result = await session.execute(
                select(User).where(User.username == username)
            )
            user = result.scalar_one_or_none()
            if not user:
                print(f"Error: User '{username}' not found")
                return None, []
        else:
            # Get first user
            result = await session.execute(select(User).limit(1))
            user = result.scalar_one_or_none()
            if not user:
                print("Error: No users found in database")
                return None, []

        # Get DCA configs for this user
        result = await session.execute(
            select(DCAConfiguration).where(DCAConfiguration.user_id == user.id)
        )
        configs = result.scalars().all()

        return user, configs


def build_webhook_payload(user_id: str, secret: str, symbol: str, timeframe: int,
                          exchange: str, action: str = "buy", capital_usd: float = 200.0):
    """Build a TradingView webhook payload.

    Args:
        user_id: User UUID
        secret: Webhook secret
        symbol: Trading pair (e.g., BTC/USDT)
        timeframe: Timeframe in minutes
        exchange: Exchange name
        action: 'buy' or 'sell'
        capital_usd: Total capital to allocate in USD (default: 200)
    """
    # Use a placeholder entry price - the actual price will be fetched by the system
    # The order_size in quote mode represents total USD to allocate
    return {
        "user_id": str(user_id),
        "secret": secret,
        "source": "tradingview",
        "timestamp": datetime.utcnow().isoformat(),
        "tv": {
            "exchange": exchange,
            "symbol": symbol,
            "timeframe": timeframe,
            "action": action,
            "market_position": "long" if action == "buy" else "short",
            "market_position_size": capital_usd,
            "prev_market_position": "flat",
            "prev_market_position_size": 0.0,
            "entry_price": 1.0,  # Placeholder - system uses current price
            "close_price": 1.0,  # Placeholder
            "order_size": capital_usd  # Total USD to allocate
        },
        "strategy_info": {
            "trade_id": str(uuid.uuid4())[:8],
            "alert_name": f"Simulated Signal - {symbol}",
            "alert_message": f"Entry signal for {symbol} on {exchange}"
        },
        "execution_intent": {
            "type": "signal",
            "side": action,
            "position_size_type": "quote",  # USD value
            "precision_mode": "auto"
        },
        "risk": {
            "stop_loss": None,
            "take_profit": None,
            "max_slippage_percent": 1.0
        }
    }


async def send_signal(client: httpx.AsyncClient, user_id: str, payload: dict):
    """Send a webhook signal to the API."""
    url = f"{API_BASE_URL}/webhooks/{user_id}/tradingview"
    try:
        response = await client.post(url, json=payload, timeout=30.0)
        return response.status_code, response.json() if response.status_code < 500 else response.text
    except Exception as e:
        import traceback
        return None, f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"


async def simulate_signals(username: str = None, action: str = "buy", delay: float = 1.0,
                           dry_run: bool = False, symbols: list = None, exchange: str = None,
                           capital: float = 200.0):
    """Send signals to all configured DCA pairs."""
    user, configs = await get_user_and_configs(username)

    if not user:
        return

    if not configs:
        print(f"No DCA configurations found for user {user.username}")
        return

    print(f"\n{'='*70}")
    print(f"Signal Simulation for user: {user.username} (ID: {user.id})")
    print(f"Action: {action.upper()}")
    print(f"Capital per signal: ${capital}")
    print(f"Delay between signals: {delay}s")
    print(f"Dry run: {dry_run}")
    if exchange:
        print(f"Exchange filter: {exchange}")
    print(f"{'='*70}\n")

    # Filter configs by exchange if specified
    if exchange:
        configs = [c for c in configs if c.exchange.lower() == exchange.lower()]
        if not configs:
            print(f"No configurations found for exchange: {exchange}")
            return

    # Filter configs if specific symbols requested
    if symbols:
        configs = [c for c in configs if c.pair in symbols]
        if not configs:
            print(f"No matching configurations found for symbols: {symbols}")
            return

    print(f"Found {len(configs)} DCA configurations:\n")
    print(f"{'Pair':<15} {'TF':<5} {'Exchange':<10} {'Entry':<10} {'TP Mode':<20} {'Pyramids'}")
    print("-" * 80)

    for cfg in configs:
        print(f"{cfg.pair:<15} {cfg.timeframe:<5} {cfg.exchange:<10} {cfg.entry_order_type.value:<10} {cfg.tp_mode.value:<20} {cfg.max_pyramids}")

    print(f"\n{'='*70}\n")

    if dry_run:
        print("DRY RUN - No signals will be sent")
        print("\nSample payload:")
        sample = build_webhook_payload(
            user_id=str(user.id),
            secret=user.webhook_secret,
            symbol=configs[0].pair if configs else "BTC/USDT",
            timeframe=configs[0].timeframe if configs else 60,
            exchange=configs[0].exchange if configs else "mock",
            action=action,
            capital_usd=capital
        )
        import json
        print(json.dumps(sample, indent=2, default=str))
        return

    # Send signals
    async with httpx.AsyncClient() as client:
        results = []

        for i, cfg in enumerate(configs, 1):
            print(f"[{i}/{len(configs)}] Sending {action.upper()} signal for {cfg.pair} ({cfg.exchange})...", end=" ")

            payload = build_webhook_payload(
                user_id=str(user.id),
                secret=user.webhook_secret,
                symbol=cfg.pair,
                timeframe=cfg.timeframe,
                exchange=cfg.exchange,
                action=action,
                capital_usd=capital
            )

            status_code, response = await send_signal(client, str(user.id), payload)

            if status_code == 202:
                print(f"OK (202)")
                results.append((cfg.pair, "success", response))
            elif status_code == 409:
                print(f"CONFLICT (409) - Another signal being processed")
                results.append((cfg.pair, "conflict", response))
            elif status_code is None:
                print(f"ERROR - Connection failed: {response}")
                results.append((cfg.pair, "failed", response))
            else:
                print(f"FAILED ({status_code})")
                results.append((cfg.pair, "failed", response))

            # Delay between signals
            if i < len(configs) and delay > 0:
                await asyncio.sleep(delay)

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")

    success = sum(1 for _, status, _ in results if status == "success")
    conflicts = sum(1 for _, status, _ in results if status == "conflict")
    failed = sum(1 for _, status, _ in results if status == "failed")

    print(f"Success: {success}")
    print(f"Conflicts: {conflicts}")
    print(f"Failed: {failed}")

    if failed > 0:
        print("\nFailed signals:")
        for pair, status, response in results:
            if status == "failed":
                print(f"  - {pair}: {response}")


def main():
    parser = argparse.ArgumentParser(description='Simulate TradingView webhook signals')
    parser.add_argument(
        '--user', '-u',
        default=None,
        help='Username to send signals for (default: first user in database)'
    )
    parser.add_argument(
        '--action', '-a',
        choices=['buy', 'sell'],
        default='buy',
        help='Signal action (default: buy)'
    )
    parser.add_argument(
        '--delay', '-d',
        type=float,
        default=1.0,
        help='Delay between signals in seconds (default: 1.0)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be sent without actually sending'
    )
    parser.add_argument(
        '--symbols', '-s',
        nargs='+',
        default=None,
        help='Specific symbols to send signals for (e.g., BTC/USDT ETH/USDT)'
    )
    parser.add_argument(
        '--exchange', '-e',
        default=None,
        help='Filter by exchange (e.g., mock, binance, bybit)'
    )
    parser.add_argument(
        '--capital', '-c',
        type=float,
        default=200.0,
        help='Capital per signal in USD (default: 200.0)'
    )

    args = parser.parse_args()

    asyncio.run(simulate_signals(
        username=args.user,
        action=args.action,
        delay=args.delay,
        dry_run=args.dry_run,
        symbols=args.symbols,
        capital=args.capital,
        exchange=args.exchange
    ))


if __name__ == '__main__':
    main()
