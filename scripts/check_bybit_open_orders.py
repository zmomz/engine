"""
Check what orders are actually open on Bybit and compare with our database
"""
import asyncio
import ccxt.async_support as ccxt

API_KEY = "yJIGPFqyMqcxnYLPn3"
SECRET_KEY = "Fvucd6ZKYBRC7oGULuED0pHLKpEsxdpB2gsb"

async def check_bybit_orders():
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
    print("CHECKING OPEN ORDERS ON BYBIT")
    print("="*70)
    
    try:
        # Try different account types
        for account_type in ['UNIFIED', 'SPOT', 'CONTRACT']:
            print(f"\n{account_type} Account:")
            print("-"*70)
            try:
                if account_type == 'UNIFIED':
                    orders = await exchange.fetch_open_orders('DOGEUSDT')
                else:
                    orders = await exchange.fetch_open_orders('DOGEUSDT', params={'accountType': account_type})
                
                if orders:
                    print(f"Found {len(orders)} open orders:")
                    for order in orders:
                        full_id = order.get('id')
                        info_id = order.get('info', {}).get('orderId')
                        print(f"\n  Order:")
                        print(f"    CCXT ID:      {full_id}")
                        print(f"    Info orderId: {info_id}")
                        print(f"    Last 8 digits: {str(full_id)[-8:] if full_id else 'N/A'}")
                        print(f"    Symbol:       {order.get('symbol')}")
                        print(f"    Side:         {order.get('side')}")
                        print(f"    Price:        {order.get('price')}")
                        print(f"    Amount:       {order.get('amount')}")
                        print(f"    Status:       {order.get('status')}")
                else:
                    print("  No open orders")
            except Exception as e:
                print(f"  Error: {e}")
    
    finally:
        await exchange.close()

if __name__ == "__main__":
    asyncio.run(check_bybit_orders())
