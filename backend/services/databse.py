from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from services.config import settings  # перевір, щоб шлях був саме такий

# 1. Створюємо двигун
engine = create_async_engine(
    str(settings.DATABASE_URL),
    echo=True,
    future=True
)

# 2. Фабрика сесій
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

# 3. Базовий клас
class Base(DeclarativeBase):
    pass

# --- ОСЬ ЦІЄЇ ФУНКЦІЇ У ТЕБЕ НЕ ВИСТАЧАЄ ---
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