import asyncio
from sqlalchemy import text
from app.db.database import engine

async def create_table():
    sql = open('/tmp/create_dca_table.sql').read()
    async with engine.begin() as conn:
        await conn.execute(text(sql))
    print("Table created successfully!")

if __name__ == "__main__":
    asyncio.run(create_table())
