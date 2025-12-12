#!/usr/bin/env python3
"""
Queue Priority Testing Script
Tests all 4 priority rules by manipulating queue state and monitoring promotion behavior
"""

import asyncio
import aiohttp
import json
from datetime import datetime
from typing import List, Dict

USER_ID = "f937c6cb-f9f9-4d25-be19-db9bf596d7e1"
SECRET = "ecd78c38d5ec54b4cd892735d0423671"
BASE_URL = "http://localhost:8000"

# Test authentication token (you'll need to get a valid token)
# For now, we'll use the webhook approach


async def send_signal(symbol: str, exchange: str, entry_price: float, order_size: float, timeframe: int = 60):
    """Send webhook signal"""
    url = f"{BASE_URL}/api/v1/webhooks/{USER_ID}/tradingview"

    payload = {
        "user_id": USER_ID,
        "secret": SECRET,
        "source": "tradingview_sim",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "tv": {
            "exchange": exchange,
            "symbol": symbol,
            "timeframe": timeframe,
            "action": "buy",
            "market_position": "flat",
            "market_position_size": 0.0,
            "prev_market_position": "flat",
            "prev_market_position_size": 0.0,
            "entry_price": entry_price,
            "close_price": 50000.0,
            "order_size": order_size
        },
        "strategy_info": {
            "trade_id": f"test_priority_{symbol}",
            "alert_name": f"Priority Test {symbol}",
            "alert_message": "Queue priority testing"
        },
        "execution_intent": {
            "type": "signal",
            "side": "long",
            "position_size_type": "contracts",
            "precision_mode": "auto"
        },
        "risk": {
            "max_slippage_percent": 0.5
        }
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            result = await resp.json()
            return resp.status, result


async def get_queue_status():
    """Get current queue status from database"""
    print("\n" + "=" * 70)
    print("  CURRENT QUEUE STATUS")
    print("=" * 70)
    # This would query the database, but we'll use the monitoring script instead
    print("  Run: docker compose exec app python3 scripts/list_queue.py")
    print("=" * 70)


async def test_priority_rule_2_deepest_loss():
    """
    Test Priority Rule 2: Deepest Loss Percent

    Expected behavior: Signal with deepest negative PnL should be promoted first

    Current queue state:
    - BNBUSDT: +26.80% (profit)
    - AVAXUSDT: -65.98% (deepest loss) ← Should be promoted first
    - LTCUSDT: -16.05% (loss)
    """
    print("\n" + "=" * 70)
    print("  TEST: Priority Rule 2 - Deepest Loss Percent")
    print("=" * 70)
    print()
    print("Current queue:")
    print("  1. BNBUSDT:  +26.80% (profit)")
    print("  2. AVAXUSDT: -65.98% (DEEPEST LOSS) ← Should promote first")
    print("  3. LTCUSDT:  -16.05% (loss)")
    print()
    print("Expected: AVAXUSDT promoted first due to deepest loss")
    print()
    print("Action: Pool now has space (8/10). Check which signal was promoted.")
    print()
    print("Verification steps:")
    print("  1. Check queue: docker compose exec app python3 scripts/list_queue.py")
    print("  2. Check positions: docker compose exec app python3 scripts/monitor_all_tests.py")
    print("  3. Verify AVAXUSDT is no longer in queue")
    print("  4. Verify AVAXUSDT position was created")
    print()


async def test_priority_rule_1_pyramid():
    """
    Test Priority Rule 1: Same Pair/Timeframe (Pyramid Continuation)

    Expected behavior: Signal matching an existing position should be promoted first
    """
    print("\n" + "=" * 70)
    print("  TEST: Priority Rule 1 - Pyramid Continuation")
    print("=" * 70)
    print()
    print("Current active positions:")
    print("  - BTCUSDT: 1/2 pyramids (can add 1 more)")
    print("  - ETHUSDT: 1/3 pyramids (can add 2 more)")
    print("  - LINKUSDT: 0/3 pyramids (can add 3)")
    print()
    print("Test plan:")
    print("  1. Queue 4 signals:")
    print("     - Signal A: New pair (UNIUSDT)")
    print("     - Signal B: BTCUSDT (matches active position) ← Should promote first")
    print("     - Signal C: New pair (BCHUSDT)")
    print("     - Signal D: ETHUSDT (matches active position)")
    print()
    print("  2. Free pool space")
    print("  3. Verify BTCUSDT promoted first (pyramid priority)")
    print()

    # Add signals for pyramid test
    print("Adding test signals...")

    # Signal A: New pair
    print("\n  Adding UNIUSDT (new pair)...")
    status, result = await send_signal("UNIUSDT", "binance", 12.0, 5.0)
    print(f"    Status: {status}, Result: {result.get('result', 'N/A')}")
    await asyncio.sleep(1)

    # Signal B: BTCUSDT pyramid
    print("\n  Adding BTCUSDT (PYRAMID - should have highest priority)...")
    status, result = await send_signal("BTCUSDT", "binance", 91000.0, 0.001)
    print(f"    Status: {status}, Result: {result.get('result', 'N/A')}")
    await asyncio.sleep(1)

    # Signal C: New pair
    print("\n  Adding BCHUSDT (new pair)...")
    status, result = await send_signal("BCHUSDT", "binance", 450.0, 0.1)
    print(f"    Status: {status}, Result: {result.get('result', 'N/A')}")
    await asyncio.sleep(1)

    # Signal D: ETHUSDT pyramid
    print("\n  Adding ETHUSDT (PYRAMID)...")
    status, result = await send_signal("ETHUSDT", "binance", 3200.0, 0.01)
    print(f"    Status: {status}, Result: {result.get('result', 'N/A')}")

    print()
    print("✅ Test signals added!")
    print()
    print("Next steps:")
    print("  1. Check queue: docker compose exec app python3 scripts/list_queue.py")
    print("  2. Verify priority scores (BTCUSDT and ETHUSDT should have highest)")
    print("  3. Close one position to free space")
    print("  4. Verify BTCUSDT pyramid promoted first")
    print()


async def test_priority_rule_3_replacement():
    """
    Test Priority Rule 3: Highest Replacement Count

    Expected behavior: Signal with most replacements should be promoted first
    """
    print("\n" + "=" * 70)
    print("  TEST: Priority Rule 3 - Highest Replacement Count")
    print("=" * 70)
    print()
    print("Test plan:")
    print("  1. Queue signal for ATOMUSDT")
    print("  2. Send 3 more ATOMUSDT signals (replacements)")
    print("  3. Queue signal for NEARUSDT (no replacements)")
    print("  4. Free pool space")
    print("  5. Verify ATOMUSDT promoted first (due to replacements)")
    print()

    print("Adding initial ATOMUSDT signal...")
    status, result = await send_signal("ATOMUSDT", "binance", 10.0, 2.0)
    print(f"  Status: {status}, Result: {result.get('result', 'N/A')}")
    await asyncio.sleep(2)

    print("\nSending replacement signals for ATOMUSDT...")
    for i in range(3):
        print(f"  Replacement {i+1}/3...")
        status, result = await send_signal("ATOMUSDT", "binance", 10.0 + (i * 0.1), 2.0)
        print(f"    Status: {status}, Result: {result.get('result', 'N/A')}")
        await asyncio.sleep(1)

    print("\nAdding NEARUSDT signal (no replacements)...")
    status, result = await send_signal("NEARUSDT", "binance", 5.0, 10.0)
    print(f"  Status: {status}, Result: {result.get('result', 'N/A')}")

    print()
    print("✅ Test signals added!")
    print()
    print("Verification:")
    print("  1. Check queue - ATOMUSDT should have replacement_count=3")
    print("  2. Close a position to free space")
    print("  3. Verify ATOMUSDT promoted first")
    print()


async def test_priority_rule_4_fifo():
    """
    Test Priority Rule 4: FIFO Fallback

    Expected behavior: When all else is equal, oldest signal should be promoted first
    """
    print("\n" + "=" * 70)
    print("  TEST: Priority Rule 4 - FIFO Fallback")
    print("=" * 70)
    print()
    print("Test plan:")
    print("  1. Queue 3 signals with similar characteristics (no pyramid, no loss, no replacements)")
    print("  2. Signals: APTUSDT, ARBUSDT, OPUSDT")
    print("  3. Free pool space")
    print("  4. Verify APTUSDT promoted first (queued first)")
    print()

    signals = [
        ("APTUSDT", 8.0, 5.0),
        ("ARBUSDT", 1.5, 30.0),
        ("OPUSDT", 2.5, 20.0)
    ]

    print("Adding signals in order...")
    for symbol, price, size in signals:
        print(f"\n  Adding {symbol}...")
        status, result = await send_signal(symbol, "binance", price, size)
        print(f"    Status: {status}, Result: {result.get('result', 'N/A')}")
        await asyncio.sleep(2)  # Wait to ensure different timestamps

    print()
    print("✅ Test signals added!")
    print()
    print("Verification:")
    print("  1. Check queue - verify all have replacement_count=0, similar loss %")
    print("  2. Close a position")
    print("  3. Verify APTUSDT promoted first (oldest)")
    print()


async def test_queue_history():
    """
    Test queue history endpoint
    """
    print("\n" + "=" * 70)
    print("  TEST: Queue History")
    print("=" * 70)
    print()
    print("The queue history shows signals that were:")
    print("  - Promoted (status: 'promoted')")
    print("  - Cancelled (status: 'cancelled')")
    print()
    print("To test:")
    print("  1. Check current history:")
    print("     GET /api/v1/queue/history")
    print()
    print("  2. Promote a signal")
    print()
    print("  3. Check history again - promoted signal should appear")
    print()
    print("  4. Cancel a signal")
    print()
    print("  5. Check history - cancelled signal should appear")
    print()


async def main():
    """Main test execution"""
    print()
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 20 + "QUEUE PRIORITY TESTS" + " " * 28 + "║")
    print("╚" + "=" * 68 + "╝")
    print()
    print(f"🕒 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    print("=" * 70)
    print("  PRIORITY RULES (in order):")
    print("=" * 70)
    print("  1. Same Pair/Timeframe (Pyramid) - Highest priority")
    print("  2. Deepest Loss Percent - Continue losing positions")
    print("  3. Highest Replacement Count - Respect updated signals")
    print("  4. FIFO Fallback - First in, first out")
    print("=" * 70)
    print()

    print("Select test to run:")
    print("  1. Test Rule 1: Pyramid Continuation")
    print("  2. Test Rule 2: Deepest Loss (READY - signals already queued)")
    print("  3. Test Rule 3: Highest Replacement")
    print("  4. Test Rule 4: FIFO Fallback")
    print("  5. Test Queue History")
    print("  6. Run ALL tests")
    print()

    # For automated execution, test rule 2 first (already set up)
    choice = "2"

    if choice == "1":
        await test_priority_rule_1_pyramid()
    elif choice == "2":
        await test_priority_rule_2_deepest_loss()
    elif choice == "3":
        await test_priority_rule_3_replacement()
    elif choice == "4":
        await test_priority_rule_4_fifo()
    elif choice == "5":
        await test_queue_history()
    elif choice == "6":
        await test_priority_rule_2_deepest_loss()
        print("\n\nContinue with manual testing for other rules...")

    print()
    print("=" * 70)
    print("  ✅ Test script complete")
    print("=" * 70)
    print()
    print("IMPORTANT: Queue promotion is currently manual via API.")
    print("To promote the highest priority signal:")
    print("  1. Get signal ID from queue")
    print("  2. POST /api/v1/queue/{signal_id}/promote")
    print()
    print("Or wait for automatic promotion (if background service is running)")
    print()


if __name__ == "__main__":
    asyncio.run(main())
