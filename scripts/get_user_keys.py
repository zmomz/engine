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
    import argparse

    parser = argparse.ArgumentParser(description="Get encrypted API keys for a user.")
    parser.add_argument("--username", type=str, required=True, help="The username to retrieve API keys for.")
    args = parser.parse_args()

    asyncio.run(get_user_keys(args.username))
