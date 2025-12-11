import asyncio
import ccxt.async_support as ccxt


# WARNING: Hardcoding API keys is not secure. This is for demonstration only.
# In a real application, use environment variables or a secure key management system.
API_KEYS = {
    "binance": {
        "apiKey": "tB8ISxF1MaNEnOEZXu1GM1L8VNwYgOtDYmdmzLgclMeo4jrUwPC7NZWjQhelLoBU",
        "secret": "CPjmcbTrdtixNet1c9c6AztJUVTNyuLSZ2Ba9cR88WVvfrBwdEXlL2VKtuhQjw5L",
    },
    "bybit": {
        "apiKey": "yJIGPFqyMqcxnYLPn3",
        "secret": "Fvucd6ZKYBRC7oGULuED0pHLKpEsxdpB2gsb",
    },
}

# Filter to show only important balances (you can customize this list)
IMPORTANT_COINS = ['BTC', 'ETH', 'USDT', 'USDC', 'BNB', 'SOL', 'DAI', 'BUSD']

async def get_binance_spot_balance():
    print("Checking Binance Spot Testnet balances...")
    exchange = ccxt.binance({
        'apiKey': API_KEYS['binance']['apiKey'],
        'secret': API_KEYS['binance']['secret'],
        'enableRateLimit': True,
        'options': {
        'adjustForTimeDifference': True,
        'recvWindow': 20000,
    }
    })
    
    # Enable sandbox/testnet mode
    exchange.set_sandbox_mode(True)
    
    # Suppress the open orders warning
    exchange.options['warnOnFetchOpenOrdersWithoutSymbol'] = False
    
    try:
        await exchange.load_markets()
        
        # Fetch spot balance
        balance = await exchange.fetch_balance()
        
        # Process balances - categorize by importance
        important_balances = []
        other_balances = []
        
        for currency, amounts in balance.items():
            if currency not in ['info', 'free', 'used', 'total', 'datetime', 'timestamp']:
                if isinstance(amounts, dict):
                    total = amounts.get('total', 0)
                    free = amounts.get('free', 0)
                    used = amounts.get('used', 0)
                    
                    if total > 0:
                        bal_info = {
                            'currency': currency,
                            'total': total,
                            'free': free,
                            'used': used
                        }
                        
                        if currency in IMPORTANT_COINS:
                            important_balances.append(bal_info)
                        else:
                            other_balances.append(bal_info)
        
        # Display important balances
        if important_balances:
            print(f"\n  💰 Main Balances ({len(important_balances)}):")
            for bal in important_balances:
                free_str = f"{bal['free']}" if bal['free'] is not None else "N/A"
                used_str = f"{bal['used']}" if bal['used'] is not None else "N/A"
                print(f"     {bal['currency']:6} - Total: {bal['total']:15,.8f} | Free: {free_str:15} | Used: {used_str}")
        
        # Display summary of other balances
        if other_balances:
            print(f"\n  📊 Other Tokens: {len(other_balances)} (mostly testnet dust)")
            # Show just the first few
            for bal in other_balances[:5]:
                print(f"     {bal['currency']:6} - {bal['total']}")
            if len(other_balances) > 5:
                print(f"     ... and {len(other_balances) - 5} more tokens")
        
        if not important_balances and not other_balances:
            print("  No balances found.")
        
        # Fetch open orders with error handling
        try:
            print("\n  📋 Checking open orders...")
            open_orders = await exchange.fetch_open_orders()
            
            if open_orders:
                print(f"     Found {len(open_orders)} open order(s):")
                for order in open_orders:
                    side_emoji = "🟢" if order['side'] == 'buy' else "🔴"
                    order_type = order.get('type', 'unknown').upper()
                    price = order.get('price', 0)
                    amount = order.get('amount', 0)
                    filled = order.get('filled', 0)
                    remaining = order.get('remaining', amount)
                    
                    print(f"     {side_emoji} {order['symbol']:12} | {order_type:8} | "
                          f"Price: ${price:10,.2f} | Amount: {amount:10,.4f} | "
                          f"Filled: {filled:10,.4f} | Remaining: {remaining:10,.4f}")
            else:
                print("     No open orders")
                
        except Exception as e:
            print(f"     ⚠️  Could not fetch open orders: {e}")
            
    except Exception as e:
        print(f"❌ Error fetching from Binance Spot Testnet: {type(e).__name__}: {e}")
    finally:
        await exchange.close()

async def get_bybit_spot_balance():
    print("\nChecking Bybit Spot Testnet balances...")
    exchange = ccxt.bybit({
        'apiKey': API_KEYS['bybit']['apiKey'],
        'secret': API_KEYS['bybit']['secret'],
        'enableRateLimit': True,
        'options': {
        'adjustForTimeDifference': True,
        'recvWindow': 20000,
    }
    })
    
    # Enable sandbox/testnet mode
    exchange.set_sandbox_mode(True)
    
    # Suppress the open orders warning
    exchange.options['warnOnFetchOpenOrdersWithoutSymbol'] = False
    try:
        await exchange.load_markets()
        
        # Fetch spot balance
        balance = await exchange.fetch_balance()
        
        # Process balances - categorize by importance
        important_balances = []
        other_balances = []
        
        for currency, amounts in balance.items():
            if currency not in ['info', 'free', 'used', 'total', 'datetime', 'timestamp']:
                if isinstance(amounts, dict):
                    total = amounts.get('total', 0)
                    free = amounts.get('free', 0)
                    used = amounts.get('used', 0)
                    
                    if total > 0:
                        bal_info = {
                            'currency': currency,
                            'total': total,
                            'free': free if free is not None else 'N/A',
                            'used': used if used is not None else 'N/A'
                        }
                        
                        if currency in IMPORTANT_COINS:
                            important_balances.append(bal_info)
                        else:
                            other_balances.append(bal_info)
        
        # Display important balances
        if important_balances:
            print(f"\n  💰 Main Balances ({len(important_balances)}):")
            for bal in important_balances:
                free_str = f"{bal['free']}" if bal['free'] != 'N/A' else "N/A"
                used_str = f"{bal['used']}" if bal['used'] != 'N/A' else "N/A"
                print(f"     {bal['currency']:6} - Total: {bal['total']:15,.8f} | Free: {free_str:>15} | Used: {used_str}")
        
        # Display summary of other balances
        if other_balances:
            print(f"\n  📊 Other Tokens: {len(other_balances)}")
            for bal in other_balances[:5]:
                print(f"     {bal['currency']:6} - {bal['total']}")
            if len(other_balances) > 5:
                print(f"     ... and {len(other_balances) - 5} more tokens")
        
        if not important_balances and not other_balances:
            print("  No balances found.")
        
        # Fetch open orders
        try:
            print("\n  📋 Checking open orders...")
            open_orders = await exchange.fetch_open_orders()
            
            if open_orders:
                print(f"     Found {len(open_orders)} open order(s):")
                for order in open_orders:
                    side_emoji = "🟢" if order['side'] == 'buy' else "🔴"
                    order_type = order.get('type', 'unknown').upper()
                    price = order.get('price', 0)
                    amount = order.get('amount', 0)
                    filled = order.get('filled', 0)
                    remaining = order.get('remaining', amount)
                    
                    print(f"     {side_emoji} {order['symbol']:12} | {order_type:8} | "
                          f"Price: ${price:10,.2f} | Amount: {amount:10,.4f} | "
                          f"Filled: {filled:10,.4f} | Remaining: {remaining:10,.4f}")
            else:
                print("     No open orders")
                
        except Exception as e:
            print(f"     ⚠️  Could not fetch open orders: {e}")
            
    except Exception as e:
        print(f"❌ Error fetching from Bybit Spot Testnet: {type(e).__name__}: {e}")
    finally:
        await exchange.close()

async def main():
    print("=" * 80)
    print("FETCHING SPOT BALANCES FROM TESTNETS")
    print("=" * 80)
    await get_binance_spot_balance()
    await get_bybit_spot_balance()
    print("\n" + "=" * 80)
    print("COMPLETED")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())