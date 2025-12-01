import asyncio
import sys
import os
from sqlalchemy import select
import json

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.db.database import AsyncSessionLocal
from app.models.user import User

async def get_user_configs():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.username == "zmomz"))
        user = result.scalars().first()
        if user:
            print(f"User: {user.username}")
            print(f"User ID: {user.id}")
            print(f"Exchange (default): {user.exchange}")
            print(f"Configured Exchanges: {user.configured_exchanges}")
            print(f"Webhook Secret Set: {bool(user.webhook_secret)}")
            print(f"Risk Config: {json.dumps(user.risk_config, indent=2)}")
            print(f"DCA Grid Config: {json.dumps(user.dca_grid_config, indent=2)}")
        else:
            print("User not found")

if __name__ == "__main__":
    asyncio.run(get_user_configs())
