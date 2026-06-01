from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from services.config import settings  # ensure the import path is correct

# 1. Create the async engine
engine = create_async_engine(
    str(settings.DATABASE_URL),
    echo=True,
    future=True
)

# 2. Session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

# 3. Base declarative class
class Base(DeclarativeBase):
    pass

# Database session dependency for FastAPI endpoints
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()