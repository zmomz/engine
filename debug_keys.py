import asyncio
import sys
import os
from sqlalchemy import select

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.db.database import AsyncSessionLocal
from app.models.user import User

async def check_keys():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.username == "zmomz"))
        user = result.scalars().first()
        if user:
            print(f"User: {user.username}")
            print(f"Encrypted Keys Type: {type(user.encrypted_api_keys)}")
            if isinstance(user.encrypted_api_keys, dict):
                print(f"Keys in encrypted_api_keys: {list(user.encrypted_api_keys.keys())}")
            else:
                print("encrypted_api_keys is not a dict")
        else:
            print("User not found")

if __name__ == "__main__":
    asyncio.run(check_keys())
