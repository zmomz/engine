import asyncio
from sqlalchemy import text
from app.db.database import engine

async def add_missing_column():
    async with engine.begin() as conn:
        # Check if column exists
        result = await conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='position_groups' 
            AND column_name='tp_pyramid_percent'
        """))
        exists = result.fetchone() is not None
        
        if exists:
            print("Column tp_pyramid_percent already exists!")
        else:
            print("Adding tp_pyramid_percent column...")
            await conn.execute(text("""
                ALTER TABLE position_groups 
                ADD COLUMN tp_pyramid_percent NUMERIC
            """))
            print("Column added successfully!")

if __name__ == "__main__":
    asyncio.run(add_missing_column())
