import asyncio

# Ensure models are imported so they register with the metadata
import services.user  # noqa: F401
from services.databse import engine, Base


async def reset_db():
    print("Connecting to DB and dropping all tables...")
    async with engine.begin() as conn:
        # Drop all tables
        await conn.run_sync(Base.metadata.drop_all)
        print("Dropped all tables")
        # Recreate tables (models must be imported above)
        await conn.run_sync(Base.metadata.create_all)
        print("Recreated all tables")


if __name__ == '__main__':
    asyncio.run(reset_db())
