"""
Test script to check if Bybit accepts trimmed order IDs for cancellation.
This will help us understand if we need to trim the long IDs to short IDs.
"""
import pytest
import ccxt.async_support as ccxt
from sqlalchemy import select
from app.models.user import User
from app.models.position_group import PositionGroup
from app.models.dca_order import DCAOrder

@pytest.mark.asyncio
async def test_trim_id(db_session):
    """
    Fetch open orders from DB, get their exchange IDs, and try to cancel them
    using both the full ID and the trimmed (last 8 digits) ID.
    """
    # Use the db_session fixture provided by pytest-asyncio/conftest
    session = db_session

    # Get user
    # Note: In a real test environment, we should probably create a user or use a fixture.
    # But since this script seems to rely on existing data or is an integration test,
    # we'll keep the logic but handle the case where user is missing gracefully.
    user_id = "977c8888-b704-43e1-a5ab-0aeec8558a21"
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    
    if not user:
        print(f"User {user_id} not found - skipping test logic requiring user")
        return

    # Get API keys
    api_keys = user.encrypted_api_keys
    if not api_keys or 'bybit' not in api_keys:
        print("Bybit API keys not found")
        return
        
    bybit_config = api_keys['bybit']
    
    # bybit_config is the encrypted config dict with keys like 'apiKey', 'secret', 'testnet'
    # Extract the actual keys
    api_key = bybit_config.get('apiKey') or bybit_config.get('api_key')
    secret_key = bybit_config.get('secret') or bybit_config.get('secret_key')
    testnet = bybit_config.get('testnet', False)
    
    if not api_key or not secret_key:
        print(f"Invalid Bybit config structure: {list(bybit_config.keys())}")
        return
    
    # Setup Bybit exchange
    exchange = ccxt.bybit({
        'apiKey': api_key,
        'secret': secret_key,
        'options': {
            'defaultType': 'spot',
            'accountType': 'UNIFIED',
            'testnet': testnet
        }
    })
    
    if testnet:
        exchange.set_sandbox_mode(True)
    
    print(f"Connected to Bybit (testnet={testnet})")
    
    try:
        # Get position groups
        result = await session.execute(select(PositionGroup).where(PositionGroup.user_id == user_id))
        groups = result.scalars().all()
        
        if not groups:
            print("No position groups found")
            return
            
        print(f"Found {len(groups)} position groups")
        
        # Get open orders
        group_ids = [g.id for g in groups]
        result = await session.execute(
            select(DCAOrder)
            .where(DCAOrder.group_id.in_(group_ids))
            .where(DCAOrder.status.in_(['open', 'pending']))
            .order_by(DCAOrder.created_at.desc())
        )
        orders = result.scalars().all()
        
        if not orders:
            print("No open orders found in DB")
            return
            
        print(f"\nFound {len(orders)} open orders in DB:")
        for order in orders:
            print(f"  - Order {order.id}: Exchange ID={order.exchange_order_id}, Status={order.status}, Symbol={order.symbol}")
        
        # Try to cancel each order with both full and trimmed ID
        for order in orders:
            if not order.exchange_order_id:
                print(f"\nSkipping order {order.id} - no exchange ID")
                continue
                
            full_id = str(order.exchange_order_id)
            trimmed_id = full_id[-8:] if len(full_id) > 8 else full_id
            
            print(f"\n{'='*60}")
            print(f"Testing order: {order.symbol}")
            print(f"Full ID: {full_id}")
            print(f"Trimmed ID (last 8): {trimmed_id}")
            print(f"{'='*60}")
            
            # Test 1: Try with full ID
            print(f"\nTest 1: Trying to cancel with FULL ID ({full_id})...")
            try:
                result = await exchange.cancel_order(full_id, order.symbol)
                print(f"✓ SUCCESS with full ID! Result: {result}")
                continue  # Don't try trimmed if full worked
            except ccxt.OrderNotFound as e:
                print(f"✗ OrderNotFound with full ID: {e}")
            except Exception as e:
                print(f"✗ Error with full ID: {type(e).__name__}: {e}")
            
            # Test 2: Try with trimmed ID
            print(f"\nTest 2: Trying to cancel with TRIMMED ID ({trimmed_id})...")
            try:
                result = await exchange.cancel_order(trimmed_id, order.symbol)
                print(f"✓ SUCCESS with trimmed ID! Result: {result}")
            except ccxt.OrderNotFound as e:
                print(f"✗ OrderNotFound with trimmed ID: {e}")
            except Exception as e:
                print(f"✗ Error with trimmed ID: {type(e).__name__}: {e}")
            
            # Test 3: Try with account type fallback for full ID
            print(f"\nTest 3: Trying SPOT account type with full ID...")
            try:
                result = await exchange.cancel_order(full_id, order.symbol, params={'accountType': 'SPOT'})
                print(f"✓ SUCCESS with full ID + SPOT! Result: {result}")
                continue
            except ccxt.OrderNotFound as e:
                print(f"✗ OrderNotFound with full ID + SPOT: {e}")
            except Exception as e:
                print(f"✗ Error with full ID + SPOT: {type(e).__name__}: {e}")
            
            # Test 4: Try with account type fallback for trimmed ID
            print(f"\nTest 4: Trying SPOT account type with trimmed ID...")
            try:
                result = await exchange.cancel_order(trimmed_id, order.symbol, params={'accountType': 'SPOT'})
                print(f"✓ SUCCESS with trimmed ID + SPOT! Result: {result}")
            except ccxt.OrderNotFound as e:
                print(f"✗ OrderNotFound with trimmed ID + SPOT: {e}")
            except Exception as e:
                print(f"✗ Error with trimmed ID + SPOT: {type(e).__name__}: {e}")
        
        # Fetch open orders from exchange to see what IDs they have
        print(f"\n{'='*60}")
        print("Fetching open orders from Bybit to see actual IDs...")
        print(f"{'='*60}")
        
        symbols = list(set([o.symbol for o in orders]))
        for symbol in symbols:
            print(f"\nFetching open orders for {symbol}...")
            try:
                open_orders = await exchange.fetch_open_orders(symbol)
                if open_orders:
                    print(f"Found {len(open_orders)} open orders:")
                    for o in open_orders:
                        print(f"  - ID: {o.get('id')}, Info.orderId: {o.get('info', {}).get('orderId')}, Status: {o.get('status')}")
                else:
                    print("No open orders found on exchange")
            except Exception as e:
                print(f"Error fetching open orders: {e}")

    finally:
        await exchange.close()
