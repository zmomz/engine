import asyncio
import ccxt.async_support as ccxt

API_KEY = "tB8ISxF1MaNEnOEZXu1GM1L8VNwYgOtDYmdmzLgclMeo4jrUwPC7NZWjQhelLoBU"
SECRET_KEY = "CPjmcbTrdtixNet1c9c6AztJUVTNyuLSZ2Ba9cR88WVvfrBwdEXlL2VKtuhQjw5L"

async def test_keys(market_type):
    print(f"Testing {market_type}...")
    exchange = ccxt.binance({
        'apiKey': API_KEY,
        'secret': SECRET_KEY,
        'options': {
            'defaultType': market_type,
        },
    })
    exchange.set_sandbox_mode(True)
    
    try:
        balance = await exchange.fetch_balance()
        print(f"SUCCESS: Fetched {market_type} balance.")
        # print(balance)
    except Exception as e:
        print(f"FAILED: Could not fetch {market_type} balance. Error: {e}")
    finally:
        await exchange.close()

async def main():
    await test_keys('future')
    await test_keys('spot')

if __name__ == "__main__":
    asyncio.run(main())