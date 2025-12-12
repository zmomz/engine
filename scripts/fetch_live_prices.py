#!/usr/bin/env python3
"""
Fetch live prices from Binance and Bybit exchanges for test planning
This script helps create realistic test orders that will actually fill
"""

import asyncio
import sys
from decimal import Decimal

sys.path.insert(0, '/app/backend')

from app.services.exchange_abstraction.binance_connector import BinanceConnector
from app.services.exchange_abstraction.bybit_connector import BybitConnector


async def fetch_live_prices():
    """Fetch current prices from both exchanges"""
    print("\n" + "=" * 70)
    print("  LIVE EXCHANGE PRICES - For Test Planning")
    print("=" * 70)
    print()

    # Initialize clients (using testnet)
    # Note: API keys can be dummy values for testnet price fetching
    binance_client = BinanceConnector(
        api_key="dummy_key",
        secret_key="dummy_secret",
        testnet=True
    )

    bybit_client = BybitConnector(
        api_key="dummy_key",
        secret_key="dummy_secret",
        testnet=True
    )

    # Configured pairs (CCXT format: BTC/USDT)
    binance_pairs = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT', 'ADA/USDT', 'TRX/USDT', 'LINK/USDT']
    bybit_pairs = ['SOL/USDT', 'DOGE/USDT', 'DOT/USDT', 'MATIC/USDT']

    print("📊 BINANCE TESTNET PRICES")
    print("-" * 70)

    binance_prices = {}
    for symbol in binance_pairs:
        try:
            # Use get_current_price which returns a float
            price = await binance_client.get_current_price(symbol)
            # Convert symbol to TradingView format (BTC/USDT -> BTCUSDT)
            tv_symbol = symbol.replace('/', '')
            binance_prices[tv_symbol] = price

            # Calculate strategic prices
            above = price * 1.001  # 0.1% above (likely to fill on dips)
            below = price * 0.999  # 0.1% below (likely to fill on pumps)
            way_above = price * 1.05  # 5% above (for losing positions)
            way_below = price * 0.95  # 5% below (for losing positions)

            print(f"\n{tv_symbol:12} Current: ${price:,.4f}")
            print(f"  ├─ 0.1% Above:  ${above:,.4f}  (Quick fill on dip)")
            print(f"  ├─ 0.1% Below:  ${below:,.4f}  (Quick fill on pump)")
            print(f"  ├─ 5% Above:    ${way_above:,.4f}  (Create losing position)")
            print(f"  └─ 5% Below:    ${way_below:,.4f}  (Create winning position)")

        except Exception as e:
            print(f"\n{symbol:12} ❌ Error: {e}")

    print("\n" + "=" * 70)
    print("\n📊 BYBIT TESTNET PRICES")
    print("-" * 70)

    bybit_prices = {}
    for symbol in bybit_pairs:
        try:
            # Use get_current_price which returns a float
            price = await bybit_client.get_current_price(symbol)
            # Convert symbol to TradingView format (SOL/USDT -> SOLUSDT)
            tv_symbol = symbol.replace('/', '')
            bybit_prices[tv_symbol] = price

            above = price * 1.001
            below = price * 0.999
            way_above = price * 1.05
            way_below = price * 0.95

            print(f"\n{tv_symbol:12} Current: ${price:,.4f}")
            print(f"  ├─ 0.1% Above:  ${above:,.4f}  (Quick fill on dip)")
            print(f"  ├─ 0.1% Below:  ${below:,.4f}  (Quick fill on pump)")
            print(f"  ├─ 5% Above:    ${way_above:,.4f}  (Create losing position)")
            print(f"  └─ 5% Below:    ${way_below:,.4f}  (Create winning position)")

        except Exception as e:
            print(f"\n{symbol:12} ❌ Error: {e}")

    print("\n" + "=" * 70)
    print("\n💡 TESTING STRATEGIES")
    print("=" * 70)
    print("""
1. REALISTIC ORDER FILLS (Use 0.1% above/below):
   - Place entry slightly below current price → fills when price dips
   - Place entry slightly above current price → fills when price pumps
   - Use BOTH to ensure at least one fills within minutes

2. CREATE LOSING POSITIONS (Use 5% above):
   - For Risk Engine testing
   - Entry price 5% above market → immediate -5% loss
   - Risk engine will mark as eligible after threshold

3. CREATE WINNING POSITIONS (Use 5% below):
   - For Risk Engine offset testing
   - Entry price 5% below market → immediate +5% profit
   - Can be used to offset losing positions

4. TAKE-PROFIT TESTING:
   - Use market orders with current price for instant fill
   - TP orders will be placed automatically
   - Monitor with verify_exchange_positions.py

5. MARKET ORDERS:
   - Use exact current price for immediate fill
   - Best for testing DCA fills and TP creation
   - Verify fills within seconds

6. BRACKET STRATEGY (Recommended):
   - Send TWO signals per pair:
     Signal A: entry = current_price * 0.999 (0.1% below)
     Signal B: entry = current_price * 1.001 (0.1% above)
   - ONE will definitely fill as price moves
   - Guarantees real order fills for testing
""")

    print("\n" + "=" * 70)
    print("\n📝 EXAMPLE TEST COMMANDS")
    print("=" * 70)

    # Generate example commands for one Binance and one Bybit pair
    if binance_prices:
        btc_price = binance_prices.get('BTCUSDT', 50000)
        print(f"""
# Example: BTC Position with Bracket Strategy
# Current Price: ${btc_price:,.2f}

# Signal 1: Entry 0.1% below (likely fills on small pump)
docker compose exec app python3 scripts/simulate_webhook.py \\
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \\
  --secret ecd78c38d5ec54b4cd892735d0423671 \\
  --exchange binance \\
  --symbol BTCUSDT \\
  --timeframe 60 \\
  --side long \\
  --action buy \\
  --entry-price {btc_price * 0.999:.2f} \\
  --order-size 0.001

# Signal 2: Entry 0.1% above (likely fills on small dip)
docker compose exec app python3 scripts/simulate_webhook.py \\
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \\
  --secret ecd78c38d5ec54b4cd892735d0423671 \\
  --exchange binance \\
  --symbol ETHUSDT \\
  --timeframe 60 \\
  --side long \\
  --action buy \\
  --entry-price {binance_prices.get('ETHUSDT', 3000) * 1.001:.2f} \\
  --order-size 0.01
""")

    if bybit_prices:
        sol_price = bybit_prices.get('SOLUSDT', 100)
        print(f"""
# Example: SOL Position for Risk Engine Testing
# Current Price: ${sol_price:,.2f}

# Losing Position (5% above market - immediate loss)
docker compose exec app python3 scripts/simulate_webhook.py \\
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \\
  --secret ecd78c38d5ec54b4cd892735d0423671 \\
  --exchange bybit \\
  --symbol SOLUSDT \\
  --timeframe 60 \\
  --side long \\
  --action buy \\
  --entry-price {sol_price * 1.05:.2f} \\
  --order-size 0.1

# Winning Position (5% below market - immediate profit)
docker compose exec app python3 scripts/simulate_webhook.py \\
  --user-id f937c6cb-f9f9-4d25-be19-db9bf596d7e1 \\
  --secret ecd78c38d5ec54b4cd892735d0423671 \\
  --exchange bybit \\
  --symbol DOGEUSDT \\
  --timeframe 60 \\
  --side long \\
  --action buy \\
  --entry-price {bybit_prices.get('DOGEUSDT', 0.1) * 0.95:.4f} \\
  --order-size 100
""")

    print("\n" + "=" * 70)
    print("✅ Price fetch complete!")
    print("=" * 70)
    print("\nUse these prices to create realistic test orders that will actually fill.")
    print()

    # Close clients
    await binance_client.close()
    await bybit_client.close()


async def main():
    await fetch_live_prices()


if __name__ == "__main__":
    asyncio.run(main())
