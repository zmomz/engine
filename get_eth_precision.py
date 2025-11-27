import asyncio
import os
from decimal import Decimal
from app.services.exchange_abstraction.binance_connector import BinanceConnector
from app.core.security import EncryptionService

async def get_eth_usdt_precision():
    # Assuming user 'maaz' API keys are valid and configured in the database
    # For this script, we'll use the hardcoded keys, which were verified by verify_exchange_keys.py
    api_key = "tB8ISxF1MaNEnOEZXu1GM1L8VNwYgOtDYmdmzLgclMeo4jrUwPC7NZWjQhelLoBU"
    secret_key = "CPjmcbTrdtixNet1c9c6AztJUVTNyuLSZ2Ba9cR88WVvfrBwdEXlL2VKtuhQjw5L"
    
    connector = BinanceConnector(api_key=api_key, secret_key=secret_key, testnet=True, default_type="spot")
    
    print("Fetching precision rules for ETH/USDT...")
    precision_rules = await connector.get_precision_rules()
    
    eth_usdt_rules = precision_rules.get("ETH/USDT")
    if not eth_usdt_rules:
        print("ETH/USDT precision rules not found.")
        return

    print(f"ETH/USDT Precision Rules: ")
    for key, value in eth_usdt_rules.items():
        print(f"  {key}: {value}")
        
    await connector.exchange.close()

if __name__ == "__main__":
    asyncio.run(get_eth_usdt_precision())
