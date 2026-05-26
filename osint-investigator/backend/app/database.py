from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    from app.models import investigation  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Add new columns if they don't exist (SQLite migration)
    async with engine.connect() as conn:
        for col, col_type in [("phone", "VARCHAR(30)"), ("nickname", "VARCHAR(255)")]:
            try:
                await conn.execute(text(f"ALTER TABLE investigations ADD COLUMN {col} {col_type}"))
                await conn.commit()
            except Exception:
                pass  # Column already exists
