import asyncio
import os
import sys

# Ensure app is in path
sys.path.append('/app')

from app.db.database import AsyncSessionLocal
from app.models.user import User
from sqlalchemy import select
from app.core.security import EncryptionService # Import EncryptionService
from app.core.config import settings # Import settings to initialize EncryptionService

async def update_zmomz_config():
    async with AsyncSessionLocal() as session:
        # Find zmomz
        result = await session.execute(select(User).where(User.username == "zmomz"))
        user = result.scalar_one_or_none()
        if not user:
            print("User zmomz not found")
            return

        # Update Risk Config
        new_risk_config = {
            "max_open_positions_global": 2,
            "max_open_positions_per_symbol": 1,
            "max_total_exposure_usd": 1000.0,
            "max_daily_loss_usd": 500.0,
            "loss_threshold_percent": 0.0, # Changed for test
            "timer_start_condition": "after_all_dca_filled",
            "post_full_wait_minutes": 0, # Changed for test
            "max_winners_to_combine": 3,
            "use_trade_age_filter": False,
            "age_threshold_minutes": 120,
            "require_full_pyramids": True,
            "reset_timer_on_replacement": False,
            "partial_close_enabled": True,
            "min_close_notional": 10.0
        }

        # Update DCA Grid Config (Keeping default/provided structure but ensuring consistency)
        new_dca_config = {
            "levels": [
                {"gap_percent": 1.0, "weight_percent": 25.0, "tp_percent": 1.0},
                {"gap_percent": 2.0, "weight_percent": 25.0, "tp_percent": 1.0},
                {"gap_percent": 3.0, "weight_percent": 25.0, "tp_percent": 2.0},
                {"gap_percent": 4.0, "weight_percent": 25.0, "tp_percent": 2.0}
            ],
            "tp_mode": "per_leg",
            "tp_aggregate_percent": 0.0
        }
        
        user.risk_config = new_risk_config
        user.dca_grid_config = new_dca_config
        
        # Ensure webhook secret is set to known value for test scripts
        user.webhook_secret = "1b6d3edada59826e786088a2161d70b6"

        # Initialize EncryptionService
        encryption_service = EncryptionService()

        # Encrypt dummy Binance API keys
        dummy_binance_api_key = "DUMMY_BINANCE_API_KEY"
        dummy_binance_secret_key = "DUMMY_BINANCE_SECRET_KEY"
        encrypted_binance_keys = encryption_service.encrypt_keys(dummy_binance_api_key, dummy_binance_secret_key)
        
        # Add testnet flag
        encrypted_binance_keys["testnet"] = True

        # Update encrypted_api_keys for Binance
        current_encrypted_api_keys = user.encrypted_api_keys or {}
        current_encrypted_api_keys["binance"] = encrypted_binance_keys
        user.encrypted_api_keys = current_encrypted_api_keys

        session.add(user)
        await session.commit()
        await session.refresh(user)
        
        print(f"User {user.username} updated.")
        print(f"Risk Config: {user.risk_config}")
        print(f"Webhook Secret: {user.webhook_secret}")
        print(f"Encrypted API Keys: {user.encrypted_api_keys}")
        print(f"ID: {user.id}")

if __name__ == "__main__":
    asyncio.run(update_zmomz_config())
