import asyncio
import os
import sys
import json
from sqlalchemy import select # Added this import

sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.db.database import AsyncSessionLocal
from app.models.user import User

async def get_user_keys(username: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.username == username))
        user = result.scalars().first()

        if not user:
            print(f"User '{username}' not found.")
            return

        print(f"Encrypted API Keys for {username}:")
        print(json.dumps(user.encrypted_api_keys, indent=2))

if __name__ == "__main__":
    target_username = "zmomz"
    asyncio.run(get_user_keys(target_username))
