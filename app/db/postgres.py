from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings

# Create async database engine
# settings.database_url holds the URL from .env (e.g. postgresql+asyncpg://postgres:password@localhost:5432/intellifix)
engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True
)

# Async session maker
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_db():
    """Dependency for getting async database sessions."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
