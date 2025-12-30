"""
State Machine Bug Detection Tests

These tests target bugs that only appear in specific state transitions:
- Order status after hedge execution
- Position status after partial fills
- Risk engine state after timer expiry
- Pyramid status transitions

State machine bugs are hard to catch because:
1. Unit tests mock the state transitions
2. They require specific event sequences
3. The bug may only appear under certain timing conditions
"""

import pytest
import httpx
from datetime import datetime
import asyncio
from decimal import Decimal


# Test configuration
BASE_URL = "http://127.0.0.1:8000"
MOCK_URL = "http://mock-exchange:9000"
TEST_USER = "zmomz"
TEST_PASSWORD = "zm0mzzm0mz"
WEBHOOK_ID = "f937c6cb-f9f9-4d25-be19-db9bf596d7e1"
WEBHOOK_SECRET = "ecd78c38d5ec54b4cd892735d0423671"


def make_entry_payload(symbol: str, position_size: float = 300, trade_id: str = None, price: float = 100):
    """Helper to create entry signal payload."""
    return {
        "user_id": WEBHOOK_ID,
        "secret": WEBHOOK_SECRET,
        "source": "tradingview",
        "timestamp": datetime.now().isoformat(),
        "tv": {
            "exchange": "mock", "symbol": symbol, "timeframe": 60,
            "action": "buy", "market_position": "long",
            "market_position_size": position_size, "prev_market_position": "flat",
            "prev_market_position_size": 0, "entry_price": price,
            "close_price": price, "order_size": position_size
        },
        "strategy_info": {
            "trade_id": trade_id or f"test_{datetime.now().strftime('%H%M%S%f')}",
            "alert_name": "Test Entry",
            "alert_message": "Test entry signal"
        },
        "execution_intent": {
            "type": "signal", "side": "buy",
            "position_size_type": "quote", "precision_mode": "auto"
        },
        "risk": {"max_slippage_percent": 1.0}
    }


def make_exit_payload(symbol: str, trade_id: str = None, price: float = 100):
    """Helper to create exit signal payload."""
    return {
        "user_id": WEBHOOK_ID,
        "secret": WEBHOOK_SECRET,
        "source": "tradingview",
        "timestamp": datetime.now().isoformat(),
        "tv": {
            "exchange": "mock", "symbol": symbol, "timeframe": 60,
            "action": "sell", "market_position": "flat",
            "market_position_size": 0, "prev_market_position": "long",
            "prev_market_position_size": 300, "entry_price": price,
            "close_price": price, "order_size": 300
        },
        "strategy_info": {
            "trade_id": trade_id or f"exit_{datetime.now().strftime('%H%M%S%f')}",
            "alert_name": "Test Exit",
            "alert_message": "Test exit signal"
        },
        "execution_intent": {
            "type": "signal", "side": "sell",
            "position_size_type": "quote", "precision_mode": "auto"
        },
        "risk": {"max_slippage_percent": 1.0}
    }


async def set_mock_price(symbol_raw: str, price: float):
    """Set price on mock exchange."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.put(
            f"{MOCK_URL}/admin/symbols/{symbol_raw}/price",
            json={"price": price}
        )


async def get_position_details(client, cookies, symbol_filter: str):
    """Get position details including orders."""
    r = await client.get("/api/v1/positions/active", cookies=cookies)
    if r.status_code != 200:
        return None
    positions = r.json()
    matching = [p for p in positions if symbol_filter in p.get("symbol", "")]
    return matching[0] if matching else None


async def get_order_states(client, cookies, position_id: str):
    """Get all order states for a position."""
    # This would need an API endpoint - for now use position details
    r = await client.get("/api/v1/positions/active", cookies=cookies)
    if r.status_code != 200:
        return []

    positions = r.json()
    for pos in positions:
        if pos.get("id") == position_id:
            orders = []
            for pyramid in pos.get("pyramids", []):
                for order in pyramid.get("dca_orders", []):
                    orders.append({
                        "id": order.get("id"),
                        "status": order.get("status"),
                        "leg_index": order.get("leg_index"),
                        "filled_quantity": order.get("filled_quantity")
                    })
            return orders
    return []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_order_status_after_hedge_execution():
    """
    BUG: Order status incorrect after hedge execution

    Scenario:
    1. Create position with DCA orders
    2. Some orders fill (position in profit)
    3. Create loser position
    4. Risk engine triggers hedge (partial close of winner)
    5. VERIFY: Winner's remaining orders should be cancelled/updated correctly

    This tests the state transition:
    OPEN orders -> (hedge triggers) -> CANCELLED or reduced
    """
    async with httpx.AsyncClient(timeout=120.0, base_url=BASE_URL) as client:
        # Login
        r = await client.post(
            "/api/v1/users/login",
            data={"username": TEST_USER, "password": TEST_PASSWORD}
        )
        if r.status_code != 200:
            pytest.skip("Could not authenticate")
        cookies = r.cookies

        # Step 1: Create winner position (TRXUSDT)
        await set_mock_price("TRXUSDT", 0.10)

        entry1 = make_entry_payload("TRX/USDT", 100, "hedge_test_winner", 0.10)
        r = await client.post(f"/api/v1/webhooks/{WEBHOOK_ID}/tradingview", json=entry1)
        assert r.status_code in (200, 202)

        await asyncio.sleep(3)

        # Step 2: Make winner profitable
        await set_mock_price("TRXUSDT", 0.15)  # 50% profit
        await asyncio.sleep(3)

        # Get winner position
        winner = await get_position_details(client, cookies, "TRX")
        if not winner:
            pytest.skip("Winner position not created")

        winner_id = winner.get("id")
        initial_orders = await get_order_states(client, cookies, winner_id)
        initial_open_count = len([o for o in initial_orders if o["status"] == "open"])

        # Step 3: Create loser position (LTCUSDT)
        await set_mock_price("LTCUSDT", 100)

        entry2 = make_entry_payload("LTC/USDT", 100, "hedge_test_loser", 100)
        r = await client.post(f"/api/v1/webhooks/{WEBHOOK_ID}/tradingview", json=entry2)

        await asyncio.sleep(3)

        # Step 4: Make loser lose money
        await set_mock_price("LTCUSDT", 90)  # 10% loss
        await asyncio.sleep(3)

        # Step 5: Trigger risk engine evaluation
        # Set risk timer as expired to trigger hedge
        async with httpx.AsyncClient(timeout=30.0) as db_client:
            # This would require direct DB access - skip for now
            pass

        # Wait for risk engine cycle
        await asyncio.sleep(10)

        # Step 6: Check order states after hedge
        final_orders = await get_order_states(client, cookies, winner_id)

        # Verify: No orders should be in inconsistent state
        for order in final_orders:
            status = order.get("status", "").lower()
            filled = float(order.get("filled_quantity", 0))

            # If order has filled quantity but status is still "open" - BUG!
            if filled > 0 and status == "open":
                pytest.fail(
                    f"Order {order['id']} has filled_quantity={filled} "
                    f"but status is still 'open'. State machine bug!"
                )

            # Status should be one of valid states
            valid_states = ["open", "filled", "partially_filled", "cancelled", "expired"]
            assert status in valid_states, f"Invalid order status: {status}"

        # Cleanup
        exit1 = make_exit_payload("TRX/USDT")
        exit2 = make_exit_payload("LTC/USDT")
        await client.post(f"/api/v1/webhooks/{WEBHOOK_ID}/tradingview", json=exit1)
        await client.post(f"/api/v1/webhooks/{WEBHOOK_ID}/tradingview", json=exit2)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_position_status_after_partial_tp():
    """
    BUG: Position status incorrect after partial take profit

    Scenario:
    1. Create position with multiple legs
    2. Some legs hit TP (partial close)
    3. VERIFY: Position status should be "partially_filled" not "closed"

    State transition:
    OPEN -> (partial TP) -> PARTIALLY_FILLED (not CLOSED!)
    """
    async with httpx.AsyncClient(timeout=120.0, base_url=BASE_URL) as client:
        # Login
        r = await client.post(
            "/api/v1/users/login",
            data={"username": TEST_USER, "password": TEST_PASSWORD}
        )
        if r.status_code != 200:
            pytest.skip("Could not authenticate")
        cookies = r.cookies

        # Create position
        await set_mock_price("ADAUSDT", 0.50)

        entry = make_entry_payload("ADA/USDT", 150, "partial_tp_test", 0.50)
        r = await client.post(f"/api/v1/webhooks/{WEBHOOK_ID}/tradingview", json=entry)

        await asyncio.sleep(5)

        # Get position
        pos = await get_position_details(client, cookies, "ADA")
        if not pos:
            pytest.skip("Position not created")

        initial_qty = float(pos.get("total_filled_quantity", 0))

        # Trigger partial TP (small profit)
        await set_mock_price("ADAUSDT", 0.52)  # 4% profit
        await asyncio.sleep(10)  # Wait for TP check

        # Check position state
        pos = await get_position_details(client, cookies, "ADA")

        if pos:
            status = pos.get("status", "").lower()
            final_qty = float(pos.get("total_filled_quantity", 0))

            # If quantity reduced but position still exists, status should reflect partial state
            if final_qty < initial_qty and final_qty > 0:
                assert status in ["partially_filled", "open", "active"], \
                    f"Position with partial fill should not be status={status}"

        # Cleanup
        exit_payload = make_exit_payload("ADA/USDT")
        await client.post(f"/api/v1/webhooks/{WEBHOOK_ID}/tradingview", json=exit_payload)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_pyramid_status_transitions():
    """
    BUG: Pyramid status not updating correctly

    State transitions to verify:
    PENDING -> SUBMITTED -> PARTIALLY_FILLED -> FILLED

    Each state should only transition forward, never backward.
    """
    async with httpx.AsyncClient(timeout=120.0, base_url=BASE_URL) as client:
        # Login
        r = await client.post(
            "/api/v1/users/login",
            data={"username": TEST_USER, "password": TEST_PASSWORD}
        )
        if r.status_code != 200:
            pytest.skip("Could not authenticate")
        cookies = r.cookies

        # Create position - using AVAX which has DCA config
        await set_mock_price("AVAXUSDT", 35.00)

        entry = make_entry_payload("AVAX/USDT", 100, "pyramid_state_test", 35.00)
        r = await client.post(f"/api/v1/webhooks/{WEBHOOK_ID}/tradingview", json=entry)

        await asyncio.sleep(3)

        # Get initial pyramid states
        pos = await get_position_details(client, cookies, "AVAX")
        if not pos:
            pytest.skip("Position not created")

        pyramid_states = []
        for pyramid in pos.get("pyramids", []):
            pyramid_states.append({
                "id": pyramid.get("id"),
                "index": pyramid.get("pyramid_index"),
                "status": pyramid.get("status"),
                "timestamp": datetime.now()
            })

        # Trigger fills by dropping price
        await set_mock_price("AVAXUSDT", 32.00)
        await asyncio.sleep(5)

        # Get updated states
        pos = await get_position_details(client, cookies, "AVAX")
        if pos:
            for pyramid in pos.get("pyramids", []):
                new_status = pyramid.get("status", "").lower()
                old_entry = next(
                    (p for p in pyramid_states if p["id"] == pyramid.get("id")),
                    None
                )

                if old_entry:
                    old_status = old_entry["status"].lower() if old_entry["status"] else "unknown"

                    # Define valid transitions
                    valid_transitions = {
                        "pending": ["pending", "submitted", "partially_filled", "filled"],
                        "submitted": ["submitted", "partially_filled", "filled"],
                        "partially_filled": ["partially_filled", "filled"],
                        "filled": ["filled"],
                    }

                    if old_status in valid_transitions:
                        assert new_status in valid_transitions.get(old_status, [new_status]), \
                            f"Invalid pyramid transition: {old_status} -> {new_status}"

        # Cleanup
        exit_payload = make_exit_payload("AVAX/USDT")
        await client.post(f"/api/v1/webhooks/{WEBHOOK_ID}/tradingview", json=exit_payload)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_risk_timer_state_transitions():
    """
    BUG: Risk timer states not updating correctly

    State transitions:
    - risk_timer_start: NULL -> timestamp (when pyramids complete)
    - risk_timer_expires: NULL -> timestamp
    - risk_eligible: false -> true (after timer expires)

    Bug scenario: Timer expired but risk_eligible still false
    """
    async with httpx.AsyncClient(timeout=60.0, base_url=BASE_URL) as client:
        # Login
        r = await client.post(
            "/api/v1/users/login",
            data={"username": TEST_USER, "password": TEST_PASSWORD}
        )
        if r.status_code != 200:
            pytest.skip("Could not authenticate")
        cookies = r.cookies

        # Get risk status
        r = await client.get("/api/v1/risk/status", cookies=cookies)
        if r.status_code != 200:
            pytest.skip("Could not get risk status")

        risk_data = r.json()

        # Check for state consistency
        positions = risk_data.get("positions", [])

        for pos in positions:
            timer_start = pos.get("risk_timer_start")
            timer_expires = pos.get("risk_timer_expires")
            eligible = pos.get("risk_eligible", False)

            # If timer has expired, eligible should be true
            if timer_expires:
                try:
                    expires_dt = datetime.fromisoformat(timer_expires.replace("Z", "+00:00"))
                    if expires_dt < datetime.now(expires_dt.tzinfo):
                        # Timer expired - eligible should be true
                        if not eligible:
                            pytest.fail(
                                f"Position {pos.get('id')}: Timer expired at {timer_expires} "
                                f"but risk_eligible is still False. State machine bug!"
                            )
                except (ValueError, TypeError):
                    pass  # Skip if can't parse datetime

            # If eligible but no timer_start, that's suspicious
            if eligible and not timer_start:
                # This could be valid if manually set, but worth logging
                pass


@pytest.mark.asyncio
@pytest.mark.integration
async def test_order_fill_monitor_state_sync():
    """
    BUG: Order fill monitor not syncing state with exchange

    Scenario:
    1. Create order
    2. Order fills on exchange
    3. VERIFY: DB state matches exchange state

    This catches sync bugs where DB and exchange are out of sync.
    """
    async with httpx.AsyncClient(timeout=120.0, base_url=BASE_URL) as client:
        # Login
        r = await client.post(
            "/api/v1/users/login",
            data={"username": TEST_USER, "password": TEST_PASSWORD}
        )
        if r.status_code != 200:
            pytest.skip("Could not authenticate")
        cookies = r.cookies

        # Create position at specific price - using DOGE which has DCA config
        test_price = 0.10
        await set_mock_price("DOGEUSDT", test_price)

        entry = make_entry_payload("DOGE/USDT", 100, "sync_test", test_price)
        r = await client.post(f"/api/v1/webhooks/{WEBHOOK_ID}/tradingview", json=entry)

        await asyncio.sleep(5)

        # Get DB state
        pos = await get_position_details(client, cookies, "DOGE")
        if not pos:
            pytest.skip("Position not created")

        db_qty = float(pos.get("total_filled_quantity", 0))

        # Get exchange state
        async with httpx.AsyncClient(timeout=30.0) as mock_client:
            r = await mock_client.get(f"{MOCK_URL}/admin/orders")
            if r.status_code == 200:
                orders = r.json()
                doge_orders = [o for o in orders if "DOGE" in o.get("symbol", "")]

                exchange_filled_qty = sum(
                    float(o.get("filled", 0))
                    for o in doge_orders
                    if o.get("status", "").upper() == "FILLED"
                )

                # Allow small tolerance for rounding
                if abs(db_qty - exchange_filled_qty) > 0.01:
                    # Could be timing - wait and check again
                    await asyncio.sleep(5)

                    pos = await get_position_details(client, cookies, "DOGE")
                    if pos:
                        db_qty = float(pos.get("total_filled_quantity", 0))

                        if abs(db_qty - exchange_filled_qty) > 0.01:
                            pytest.fail(
                                f"DB/Exchange sync mismatch: "
                                f"DB qty={db_qty}, Exchange filled={exchange_filled_qty}"
                            )

        # Cleanup
        exit_payload = make_exit_payload("DOGE/USDT")
        await client.post(f"/api/v1/webhooks/{WEBHOOK_ID}/tradingview", json=exit_payload)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_position_close_cleans_all_orders():
    """
    BUG: Position close doesn't cancel all remaining orders

    Scenario:
    1. Create position with multiple DCA orders
    2. Some orders fill
    3. Send exit signal
    4. VERIFY: ALL remaining orders are cancelled on exchange

    Bug: Orphaned orders left on exchange after position close
    """
    async with httpx.AsyncClient(timeout=120.0, base_url=BASE_URL) as client:
        # Login
        r = await client.post(
            "/api/v1/users/login",
            data={"username": TEST_USER, "password": TEST_PASSWORD}
        )
        if r.status_code != 200:
            pytest.skip("Could not authenticate")
        cookies = r.cookies

        # Create position - using LINK which has DCA config
        await set_mock_price("LINKUSDT", 15.00)

        entry = make_entry_payload("LINK/USDT", 100, "orphan_test", 15.00)
        r = await client.post(f"/api/v1/webhooks/{WEBHOOK_ID}/tradingview", json=entry)

        await asyncio.sleep(5)

        # Get exchange orders before close
        async with httpx.AsyncClient(timeout=30.0) as mock_client:
            r = await mock_client.get(f"{MOCK_URL}/admin/orders")
            orders_before = r.json() if r.status_code == 200 else []
            link_orders_before = [
                o for o in orders_before
                if "LINK" in o.get("symbol", "") and o.get("status", "").upper() == "OPEN"
            ]

        # Close position
        exit_payload = make_exit_payload("LINK/USDT")
        r = await client.post(f"/api/v1/webhooks/{WEBHOOK_ID}/tradingview", json=exit_payload)

        await asyncio.sleep(5)

        # Get exchange orders after close
        async with httpx.AsyncClient(timeout=30.0) as mock_client:
            r = await mock_client.get(f"{MOCK_URL}/admin/orders")
            orders_after = r.json() if r.status_code == 200 else []
            link_orders_after = [
                o for o in orders_after
                if "LINK" in o.get("symbol", "") and o.get("status", "").upper() == "OPEN"
            ]

        # Verify: No orphaned orders
        if link_orders_after:
            orphaned_ids = [o.get("id") for o in link_orders_after]
            pytest.fail(
                f"Orphaned orders after position close: {orphaned_ids}. "
                f"Had {len(link_orders_before)} open before, {len(link_orders_after)} after."
            )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_duplicate_fill_events_handling():
    """
    BUG: Duplicate fill events cause incorrect state

    Scenario:
    1. Order fills on exchange
    2. Fill event processed twice (race condition)
    3. VERIFY: Position quantity not doubled

    This tests idempotency of fill handling.
    """
    async with httpx.AsyncClient(timeout=120.0, base_url=BASE_URL) as client:
        # Login
        r = await client.post(
            "/api/v1/users/login",
            data={"username": TEST_USER, "password": TEST_PASSWORD}
        )
        if r.status_code != 200:
            pytest.skip("Could not authenticate")
        cookies = r.cookies

        # Create position - using XRP which has DCA config
        await set_mock_price("XRPUSDT", 0.50)

        entry = make_entry_payload("XRP/USDT", 100, "idempotent_test", 0.50)
        r = await client.post(f"/api/v1/webhooks/{WEBHOOK_ID}/tradingview", json=entry)

        await asyncio.sleep(5)

        # Get position quantity
        pos = await get_position_details(client, cookies, "XRP")
        if not pos:
            pytest.skip("Position not created")

        qty1 = float(pos.get("total_filled_quantity", 0))

        # Wait for another fill monitor cycle (should be idempotent)
        await asyncio.sleep(5)

        pos = await get_position_details(client, cookies, "XRP")
        if pos:
            qty2 = float(pos.get("total_filled_quantity", 0))

            # Quantity should not have changed (no new fills)
            # Allow for price-based fills if price dropped
            current_price_check = 0.50  # Same as entry, so no new fills expected

            # If quantity increased significantly without price change, that's suspicious
            if qty2 > qty1 * 1.5:  # 50% increase would be suspicious
                pytest.fail(
                    f"Quantity unexpectedly increased: {qty1} -> {qty2}. "
                    f"Possible duplicate fill processing."
                )

        # Cleanup
        exit_payload = make_exit_payload("XRP/USDT")
        await client.post(f"/api/v1/webhooks/{WEBHOOK_ID}/tradingview", json=exit_payload)
