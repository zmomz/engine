"""
Standalone test script to check if Bybit accepts trimmed order IDs.
Uses direct API credentials (testnet).
"""
import asyncio
import ccxt.async_support as ccxt

# Bybit Testnet credentials
API_KEY = "yJIGPFqyMqcxnYLPn3"
SECRET_KEY = "Fvucd6ZKYBRC7oGULuED0pHLKpEsxdpB2gsb"

async def test_bybit_ids():
    """Test if Bybit accepts full vs trimmed order IDs"""
    
    # Setup Bybit exchange
    exchange = ccxt.bybit({
        'apiKey': API_KEY,
        'secret': SECRET_KEY,
        'options': {
            'defaultType': 'spot',
            'accountType': 'UNIFIED',
            'testnet': True
        }
    })
    
    exchange.set_sandbox_mode(True)
    
    print("="*70)
    print("BYBIT ORDER ID TEST - Testnet")
    print("="*70)
    
    try:
        # Fetch all open orders for DOGEUSDT
        print("\n1. Fetching open orders from Bybit for DOGEUSDT...")
        open_orders = await exchange.fetch_open_orders('DOGEUSDT')
        
        if not open_orders:
            print("   ✗ No open orders found on Bybit")
            print("\n   Let's check with different account types...")
            
            # Try SPOT
            print("\n   Trying SPOT account type...")
            try:
                open_orders = await exchange.fetch_open_orders('DOGEUSDT', params={'accountType': 'SPOT'})
                if open_orders:
                    print(f"   ✓ Found {len(open_orders)} orders with SPOT account type")
            except Exception as e:
                print(f"   ✗ SPOT failed: {e}")
            
            # Try CONTRACT
            if not open_orders:
                print("\n   Trying CONTRACT account type...")
                try:
                    open_orders = await exchange.fetch_open_orders('DOGEUSDT', params={'accountType': 'CONTRACT'})
                    if open_orders:
                        print(f"   ✓ Found {len(open_orders)} orders with CONTRACT account type")
                except Exception as e:
                    print(f"   ✗ CONTRACT failed: {e}")
        else:
            print(f"   ✓ Found {len(open_orders)} open orders")
        
        if not open_orders:
            print("\n   No open orders found. Cannot test cancellation.")
            return
        
        # Display orders
        print(f"\n2. Open orders on Bybit:")
        print("   " + "-"*66)
        for i, order in enumerate(open_orders, 1):
            order_id = order.get('id')
            info_order_id = order.get('info', {}).get('orderId')
            print(f"   Order {i}:")
            print(f"     - CCXT ID:        {order_id}")
            print(f"     - Info.orderId:   {info_order_id}")
            print(f"     - Symbol:         {order.get('symbol')}")
            print(f"     - Side:           {order.get('side')}")
            print(f"     - Price:          {order.get('price')}")
            print(f"     - Amount:         {order.get('amount')}")
            print(f"     - Status:         {order.get('status')}")
            
            if order_id and len(str(order_id)) > 8:
                trimmed = str(order_id)[-8:]
                print(f"     - Trimmed (last 8): {trimmed}")
        
        # Test cancellation with first order
        if open_orders:
            test_order = open_orders[0]
            full_id = str(test_order.get('id'))
            trimmed_id = full_id[-8:] if len(full_id) > 8 else full_id
            symbol = test_order.get('symbol')
            
            print(f"\n3. Testing cancellation on first order:")
            print(f"   Full ID:    {full_id}")
            print(f"   Trimmed ID: {trimmed_id}")
            print(f"   Symbol:     {symbol}")
            print("   " + "-"*66)
            
            # Test 1: Full ID with UNIFIED
            print(f"\n   Test 1: Cancel with FULL ID (UNIFIED account)...")
            try:
                result = await exchange.cancel_order(full_id, symbol)
                print(f"   ✓ SUCCESS! Order cancelled with full ID")
                print(f"   Result: {result.get('id')} - {result.get('status')}")
                return  # Success, no need to test further
            except ccxt.OrderNotFound as e:
                print(f"   ✗ OrderNotFound: {e}")
            except Exception as e:
                print(f"   ✗ Error: {type(e).__name__}: {e}")
            
            # Test 2: Full ID with SPOT
            print(f"\n   Test 2: Cancel with FULL ID (SPOT account)...")
            try:
                result = await exchange.cancel_order(full_id, symbol, params={'accountType': 'SPOT'})
                print(f"   ✓ SUCCESS! Order cancelled with full ID + SPOT")
                print(f"   Result: {result.get('id')} - {result.get('status')}")
                return
            except ccxt.OrderNotFound as e:
                print(f"   ✗ OrderNotFound: {e}")
            except Exception as e:
                print(f"   ✗ Error: {type(e).__name__}: {e}")
            
            # Test 3: Trimmed ID with UNIFIED
            print(f"\n   Test 3: Cancel with TRIMMED ID (UNIFIED account)...")
            try:
                result = await exchange.cancel_order(trimmed_id, symbol)
                print(f"   ✓ SUCCESS! Order cancelled with trimmed ID")
                print(f"   Result: {result.get('id')} - {result.get('status')}")
                return
            except ccxt.OrderNotFound as e:
                print(f"   ✗ OrderNotFound: {e}")
            except Exception as e:
                print(f"   ✗ Error: {type(e).__name__}: {e}")
            
            # Test 4: Trimmed ID with SPOT
            print(f"\n   Test 4: Cancel with TRIMMED ID (SPOT account)...")
            try:
                result = await exchange.cancel_order(trimmed_id, symbol, params={'accountType': 'SPOT'})
                print(f"   ✓ SUCCESS! Order cancelled with trimmed ID + SPOT")
                print(f"   Result: {result.get('id')} - {result.get('status')}")
            except ccxt.OrderNotFound as e:
                print(f"   ✗ OrderNotFound: {e}")
            except Exception as e:
                print(f"   ✗ Error: {type(e).__name__}: {e}")
            
            print("\n" + "="*70)
            print("CONCLUSION: All cancellation attempts failed!")
            print("This suggests the order might be in a different state or account.")
            print("="*70)
    
    finally:
        await exchange.close()

if __name__ == "__main__":
    asyncio.run(test_bybit_ids())
