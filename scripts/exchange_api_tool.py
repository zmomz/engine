#!/usr/bin/env python3
"""
Universal CCXT Balance Checker
Automatically detects exchange and displays non-zero balances
Can convert all assets to USDT
"""

import ccxt
import sys
from datetime import datetime

def detect_exchange(api_key):
    """Detect exchange based on API key characteristics"""
    # Common exchange patterns
    if api_key.startswith('BPFI') or len(api_key) == 64:
        return 'binance'
    elif len(api_key) == 32 and '-' not in api_key:
        return 'bybit'
    elif api_key.count('-') >= 4:
        return 'coinbasepro'
    elif len(api_key) == 28:
        return 'kraken'
    elif api_key.startswith('ok-'):
        return 'okx'
    elif len(api_key) == 36 and api_key.count('-') == 4:
        return 'kucoin'
    
    # Default to binance if can't detect
    print("⚠️  Could not auto-detect exchange, defaulting to Binance")
    return 'binance'

def try_connect(exchange_name, api_key, secret, testnet=False, options=None):
    """Try to connect to exchange with given configuration"""
    try:
        exchange_class = getattr(ccxt, exchange_name)
        
        config = {
            'apiKey': api_key,
            'secret': secret,
            'enableRateLimit': True,
            'options': options or {},
        }
        
        # Add testnet to config for proper initialization
        if testnet:
            config['options']['testnet'] = True
        
        exchange = exchange_class(config)
        
        # Configure testnet URLs AFTER exchange is created
        if testnet:
            if exchange_name == 'binance':
                # Binance testnet configuration
                exchange.set_sandbox_mode(True)
            elif exchange_name == 'bybit':
                # Bybit testnet - must set sandbox mode
                exchange.set_sandbox_mode(True)
            else:
                # Generic testnet
                if hasattr(exchange, 'set_sandbox_mode'):
                    exchange.set_sandbox_mode(True)
        
        # Try to fetch balance
        balance = exchange.fetch_balance()
        return exchange, balance, None
        
    except ccxt.AuthenticationError as e:
        return None, None, f"Auth error: {str(e)}"
    except ccxt.NetworkError as e:
        return None, None, f"Network error: {str(e)}"
    except Exception as e:
        return None, None, f"Error: {str(e)}"

def auto_detect_network(exchange_name, api_key, secret):
    """Auto-detect if API key is for mainnet or testnet"""
    
    print("🔍 Auto-detecting network type...")
    
    # Try mainnet first
    print("   Trying mainnet...", end=" ")
    exchange, balance, error = try_connect(exchange_name, api_key, secret, testnet=False)
    if exchange:
        print("✅ Connected!")
        return exchange, balance, False
    else:
        print(f"❌ Failed")
    
    # Try testnet
    print("   Trying testnet...", end=" ")
    exchange, balance, error = try_connect(exchange_name, api_key, secret, testnet=True)
    if exchange:
        print("✅ Connected!")
        return exchange, balance, True
    else:
        print(f"❌ Failed")
    
    # Try different account types for Bybit
    if exchange_name == 'bybit':
        for account_type in ['UNIFIED', 'CONTRACT']:
            print(f"   Trying testnet with {account_type}...", end=" ")
            options = {'accountType': account_type}
            exchange, balance, error = try_connect(exchange_name, api_key, secret, testnet=True, options=options)
            if exchange:
                print("✅ Connected!")
                return exchange, balance, True
            else:
                print(f"❌ Failed")
    
    return None, None, None

def sell_all_to_usdt(exchange, non_zero_assets, dry_run=True):
    """Sell all assets and convert to USDT"""
    
    print(f"\n{'='*60}")
    print(f"💱 Converting All Assets to USDT")
    if dry_run:
        print(f"   🔍 DRY RUN MODE - No actual trades will be executed")
    else:
        print(f"   ⚠️  LIVE MODE - Real trades will be executed!")
    print(f"{'='*60}\n")
    
    results = {
        'successful': [],
        'failed': [],
        'skipped': [],
        'total_usdt_received': 0.0
    }
    
    for asset_info in non_zero_assets:
        currency = asset_info['currency']
        free_balance = asset_info['free']
        
        # Skip USDT itself
        if currency == 'USDT':
            results['skipped'].append({
                'asset': currency,
                'reason': 'Already USDT',
                'amount': free_balance
            })
            results['total_usdt_received'] += free_balance
            print(f"⏭️  Skipping {currency}: Already USDT ({free_balance:.8f})")
            continue
        
        # Skip if no free balance
        if free_balance <= 0:
            results['skipped'].append({
                'asset': currency,
                'reason': 'No free balance',
                'amount': 0
            })
            print(f"⏭️  Skipping {currency}: No free balance (all locked)")
            continue
        
        # Try to find trading pair
        symbol = f"{currency}/USDT"
        
        try:
            # Load markets if not already loaded
            if not exchange.markets:
                exchange.load_markets()
            
            # Check if market exists
            if symbol not in exchange.markets:
                results['skipped'].append({
                    'asset': currency,
                    'reason': f'No market for {symbol}',
                    'amount': free_balance
                })
                print(f"⏭️  Skipping {currency}: Market {symbol} not found")
                continue
            
            # Get current price
            ticker = exchange.fetch_ticker(symbol)
            current_price = ticker['last']
            estimated_usdt = free_balance * current_price
            
            if dry_run:
                print(f"🔍 Would sell {free_balance:.8f} {currency} at ~{current_price:.8f} USDT")
                print(f"   Estimated USDT received: {estimated_usdt:.8f}")
                results['successful'].append({
                    'asset': currency,
                    'amount': free_balance,
                    'price': current_price,
                    'usdt_received': estimated_usdt,
                    'dry_run': True
                })
                results['total_usdt_received'] += estimated_usdt
            else:
                # Execute market sell order
                print(f"💸 Selling {free_balance:.8f} {currency}...", end=" ")
                
                # Get market info for precision
                market = exchange.markets[symbol]
                
                # Round amount to exchange precision
                amount = exchange.amount_to_precision(symbol, free_balance)
                
                # Place market sell order
                order = exchange.create_market_sell_order(symbol, amount)
                
                # Calculate actual USDT received
                actual_usdt = 0
                if 'cost' in order and order['cost']:
                    actual_usdt = float(order['cost'])
                elif 'filled' in order and order['average']:
                    actual_usdt = float(order['filled']) * float(order['average'])
                
                print(f"✅ Done! Received {actual_usdt:.8f} USDT")
                
                results['successful'].append({
                    'asset': currency,
                    'amount': free_balance,
                    'price': order.get('average', current_price),
                    'usdt_received': actual_usdt,
                    'order_id': order.get('id'),
                    'dry_run': False
                })
                results['total_usdt_received'] += actual_usdt
                
        except ccxt.InsufficientFunds as e:
            error_msg = f"Insufficient funds: {str(e)}"
            print(f"❌ {currency}: {error_msg}")
            results['failed'].append({
                'asset': currency,
                'amount': free_balance,
                'error': error_msg
            })
        except ccxt.InvalidOrder as e:
            error_msg = f"Invalid order: {str(e)}"
            print(f"❌ {currency}: {error_msg}")
            results['failed'].append({
                'asset': currency,
                'amount': free_balance,
                'error': error_msg
            })
        except Exception as e:
            error_msg = str(e)
            print(f"❌ {currency}: {error_msg}")
            results['failed'].append({
                'asset': currency,
                'amount': free_balance,
                'error': error_msg
            })
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"📊 Conversion Summary")
    print(f"{'='*60}")
    print(f"✅ Successful: {len(results['successful'])}")
    print(f"❌ Failed: {len(results['failed'])}")
    print(f"⏭️  Skipped: {len(results['skipped'])}")
    print(f"💰 Total USDT: {results['total_usdt_received']:.8f}")
    if dry_run:
        print(f"   (Estimated - no actual trades executed)")
    print(f"{'='*60}\n")
    
    return results

def get_balance_info(api_key, secret, exchange_name=None, password=None, force_testnet=None, convert_to_usdt=False):
    """Fetch and display balance information"""
    
    # Auto-detect exchange if not provided
    if not exchange_name:
        exchange_name = detect_exchange(api_key)
    
    try:
        exchange = None
        balance = None
        is_testnet = False
        
        if force_testnet is None:
            # Auto-detect network
            exchange, balance, is_testnet = auto_detect_network(exchange_name, api_key, secret)
            
            if not exchange:
                print("\n❌ Could not connect with either mainnet or testnet")
                print("   Please check your API credentials")
                sys.exit(1)
        else:
            # Use forced network setting
            is_testnet = force_testnet
            print(f"🔗 Connecting to {'TESTNET' if is_testnet else 'MAINNET'}...")
            
            exchange_class = getattr(ccxt, exchange_name)
            config = {
                'apiKey': api_key,
                'secret': secret,
                'enableRateLimit': True,
                'options': {},
            }
            
            if password:
                config['password'] = password
            
            # Add testnet to options if needed
            if is_testnet:
                config['options']['testnet'] = True
            
            exchange = exchange_class(config)
            
            # Configure testnet after initialization
            if is_testnet:
                if exchange_name == 'binance':
                    # Binance testnet
                    exchange.set_sandbox_mode(True)
                elif exchange_name == 'bybit':
                    # Bybit testnet
                    exchange.set_sandbox_mode(True)
                else:
                    # Generic testnet
                    if hasattr(exchange, 'set_sandbox_mode'):
                        exchange.set_sandbox_mode(True)
            
            # Fetch balance
            balance = exchange.fetch_balance()
        
        print(f"\n{'='*60}")
        print(f"🔍 Exchange: {exchange.name}")
        print(f"{'='*60}")
        
        # Display network information
        network_type = "TESTNET 🟡" if is_testnet else "MAINNET 🟢"
        
        # Get API key permissions
        print("\n📋 API Key Information:")
        print(f"   Exchange: {exchange.name}")
        print(f"   Network: {network_type}")
        
        # Get actual API endpoint being used
        if hasattr(exchange, 'urls') and 'api' in exchange.urls:
            api_url = exchange.urls['api']
            if isinstance(api_url, dict):
                api_url = api_url.get('public', api_url.get('private', 'N/A'))
            print(f"   API Endpoint: {api_url}")
        
        print(f"   API Key: {api_key[:8]}...{api_key[-4:]}")
        
        # Try to get account info for more details
        try:
            if hasattr(exchange, 'fetch_account'):
                account_info = exchange.fetch_account()
                if 'permissions' in account_info:
                    print(f"   Permissions: {', '.join(account_info['permissions'])}")
        except:
            pass
        
        # Warning for testnet
        if is_testnet:
            print(f"\n   ⚠️  WARNING: This is a TESTNET/SANDBOX account!")
            print(f"   💡 Balances are NOT real money!")
        
        # Display non-zero balances
        print(f"\n💰 Non-Zero Balances:")
        print(f"{'─'*60}")
        print(f"{'Asset':<12} {'Free':<18} {'Locked':<18} {'Total':<18}")
        print(f"{'─'*60}")
        
        non_zero_assets = []
        
        for currency, amounts in balance['total'].items():
            try:
                # Skip if amounts is None or zero
                if amounts is None or float(amounts) <= 0:
                    continue
                    
                free = balance['free'].get(currency, 0)
                used = balance['used'].get(currency, 0)
                total = amounts
                
                # Convert None to 0 and then to float
                free = float(free if free is not None else 0)
                used = float(used if used is not None else 0)
                total = float(total if total is not None else 0)
                
                non_zero_assets.append({
                    'currency': currency,
                    'free': free,
                    'used': used,
                    'total': total
                })
                
                print(f"{currency:<12} {free:<18.8f} {used:<18.8f} {total:<18.8f}")
            except (ValueError, TypeError) as e:
                # Skip assets with invalid values
                continue
        
        if len(non_zero_assets) == 0:
            print(f"{'No assets found':<60}")
        
        print(f"{'─'*60}")
        print(f"\n📊 Summary:")
        print(f"   Total Assets with Balance: {len(non_zero_assets)}")
        print(f"   Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Try to get total value in USDT/USD if available
        if 'USDT' in balance['total'] and balance['total']['USDT'] > 0:
            print(f"   USDT Balance: {balance['total']['USDT']:.2f}")
        elif 'USD' in balance['total'] and balance['total']['USD'] > 0:
            print(f"   USD Balance: {balance['total']['USD']:.2f}")
        
        print(f"{'='*60}\n")
        
        # Ask if user wants to convert all to USDT
        if convert_to_usdt and len(non_zero_assets) > 0:
            # First show dry run
            print("\n" + "="*60)
            print("Would you like to convert all assets to USDT?")
            print("="*60)
            
            # Run dry run first
            dry_run_results = sell_all_to_usdt(exchange, non_zero_assets, dry_run=True)
            
            # Ask for confirmation
            confirm = input("\n⚠️  Do you want to execute these trades? (yes/no): ").strip().lower()
            
            if confirm in ['yes', 'y']:
                # Ask for final confirmation
                final_confirm = input("⚠️  Are you ABSOLUTELY sure? This cannot be undone! (type 'CONFIRM'): ").strip()
                
                if final_confirm == 'CONFIRM':
                    print("\n🚀 Executing trades...")
                    live_results = sell_all_to_usdt(exchange, non_zero_assets, dry_run=False)
                    
                    # Show final balance
                    print("\n🔄 Fetching updated balance...")
                    updated_balance = exchange.fetch_balance()
                    usdt_balance = updated_balance['total'].get('USDT', 0)
                    print(f"💰 Final USDT Balance: {usdt_balance:.8f}")
                else:
                    print("\n❌ Trade execution cancelled (confirmation failed)")
            else:
                print("\n❌ Trade execution cancelled")
        
        return non_zero_assets
        
    except ccxt.AuthenticationError as e:
        print(f"\n❌ Authentication Error: Invalid API credentials")
        print(f"   Details: {str(e)}")
        sys.exit(1)
    except ccxt.ExchangeError as e:
        print(f"\n❌ Exchange Error: {str(e)}")
        sys.exit(1)
    except AttributeError:
        print(f"\n❌ Error: Exchange '{exchange_name}' not supported by CCXT")
        print(f"   Available exchanges: {', '.join(ccxt.exchanges[:10])}...")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def main():
    """Main function to run the balance checker"""
    
    print("\n🔐 Universal CCXT Balance Checker")
    print("=" * 60)
    
    # Get user input
    if len(sys.argv) >= 3:
        api_key = sys.argv[1]
        secret = sys.argv[2]
        exchange_name = sys.argv[3] if len(sys.argv) > 3 else None
        password = sys.argv[4] if len(sys.argv) > 4 else None
        
        # Parse testnet argument
        force_testnet = None
        if len(sys.argv) > 5:
            testnet_arg = sys.argv[5].lower()
            if testnet_arg in ['true', 'testnet', 'yes', 'y']:
                force_testnet = True
            elif testnet_arg in ['false', 'mainnet', 'no', 'n']:
                force_testnet = False
            # else: auto-detect (None)
        
        # Parse convert to USDT argument
        convert_to_usdt = False
        if len(sys.argv) > 6:
            convert_arg = sys.argv[6].lower()
            if convert_arg in ['convert', 'sell', 'true', 'yes', 'y']:
                convert_to_usdt = True
    else:
        print("\nEnter your credentials:")
        api_key = input("API Key: ").strip()
        secret = input("Secret: ").strip()
        
        exchange_input = input("Exchange (leave blank for auto-detect): ").strip()
        exchange_name = exchange_input if exchange_input else None
        
        testnet_input = input("Network: (1) Auto-detect (2) Mainnet (3) Testnet [default: 1]: ").strip()
        if testnet_input == '2':
            force_testnet = False
        elif testnet_input == '3':
            force_testnet = True
        else:
            force_testnet = None  # Auto-detect
        
        password_input = input("Password/Passphrase (if required, else leave blank): ").strip()
        password = password_input if password_input else None
        
        convert_input = input("Convert all assets to USDT? (y/n, default: n): ").strip().lower()
        convert_to_usdt = convert_input in ['y', 'yes']
    
    # Fetch and display balance
    get_balance_info(api_key, secret, exchange_name, password, force_testnet, convert_to_usdt)

if __name__ == "__main__":
    main()
