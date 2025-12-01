"""
Test script to verify Bybit API key permissions
Run this to confirm your API keys have the required permissions
"""
import asyncio
import ccxt.async_support as ccxt

async def test_bybit_permissions(api_key: str, secret_key: str, testnet: bool = True):
    """
    Test Bybit API key permissions
    """
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
    
    print(f"Testing Bybit API Key: {api_key[:8]}...{api_key[-4:]}")
    print(f"Testnet Mode: {testnet}")
    print("=" * 60)
    
    try:
        # Test 1: Read Permission (fetch balance)
        print("\n[TEST 1] Fetching balance (requires READ permission)...")
        try:
            balance = await exchange.fetch_balance()
            print("✅ READ permission: OK")
            print(f"   Balance fetched successfully")
        except Exception as e:
            print(f"❌ READ permission: FAILED - {e}")
            return
        
        # Test 2: Trade Permission (try to place a test order)
        print("\n[TEST 2] Testing order placement (requires TRADE permission)...")
        print("   Note: This will attempt to place a small LIMIT order")
        print("   The order may fail for other reasons, but we're checking for permission errors")
        
        try:
            # Try to place a very small limit order that's unlikely to fill
            # Using a price far from market to avoid actual execution
            test_order = await exchange.create_order(
                symbol='BTC/USDT',
                type='limit',
                side='buy',
                amount=0.001,  # Very small amount
                price=1.0      # Far below market price
            )
            print("✅ TRADE permission: OK")
            print(f"   Test order created: {test_order.get('id', 'unknown')}")
            
            # Cancel the test order immediately
            try:
                await exchange.cancel_order(test_order['id'], 'BTC/USDT')
                print("   Test order canceled successfully")
            except:
                pass
                
        except ccxt.ExchangeError as e:
            error_msg = str(e)
            if "10005" in error_msg or "Invalid API-key" in error_msg or "permissions" in error_msg.lower():
                print(f"❌ TRADE permission: MISSING OR DISABLED")
                print(f"   Error: {error_msg}")
                print("\n" + "=" * 60)
                print("ACTION REQUIRED:")
                print("1. Go to https://testnet.bybit.com/")
                print("2. Navigate to: Account → API Management")
                print("3. Edit your API key or create a new one")
                print("4. Enable 'Trade' permission")
                print("5. Update your application with the new key")
                print("=" * 60)
            else:
                print(f"⚠️  Order placement failed (but not due to permissions)")
                print(f"   Error: {error_msg}")
        
        # Test 3: Check API key info (if available)
        print("\n[TEST 3] Checking API key info...")
        try:
            # Note: Not all exchanges support this endpoint
            key_info = await exchange.fetch_api_key_permissions()
            print("API Key Permissions:")
            print(f"   {key_info}")
        except:
            print("   (API key info endpoint not available)")
        
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
    finally:
        await exchange.close()
    
    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)

# Example usage:
if __name__ == "__main__":
    # Replace with your actual API keys
    API_KEY = "yJIGPFqyMqcxnYLPn3"
    SECRET_KEY = "Fvucd6ZKYBRC7oGULuED0pHLKpEsxdpB2gsb"
    
    asyncio.run(test_bybit_permissions(API_KEY, SECRET_KEY, testnet=True))