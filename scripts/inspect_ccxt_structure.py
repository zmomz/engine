import asyncio
import ccxt.async_support as ccxt
import json

API_KEY = "tB8ISxF1MaNEnOEZXu1GM1L8VNwYgOtDYmdmzLgclMeo4jrUwPC7NZWjQhelLoBU"
SECRET_KEY = "CPjmcbTrdtixNet1c9c6AztJUVTNyuLSZ2Ba9cR88WVvfrBwdEXlL2VKtuhQjw5L"

async def inspect_markets():
    exchange = ccxt.binance({
        'apiKey': API_KEY,
        'secret': SECRET_KEY,
        'options': {'defaultType': 'spot'},
    })
    exchange.set_sandbox_mode(True)
    
    try:
        markets = await exchange.load_markets()
        btc_usdt = markets['BTC/USDT']
        print(json.dumps(btc_usdt, indent=2, default=str))
    finally:
        await exchange.close()

if __name__ == "__main__":
    asyncio.run(inspect_markets())