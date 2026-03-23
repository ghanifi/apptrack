from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

_engine_kwargs: dict = {"echo": False}
if "sqlite" in settings.DATABASE_URL:
    from sqlalchemy.pool import StaticPool
    _engine_kwargs["poolclass"] = StaticPool
else:
    _engine_kwargs.update(
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_recycle=300,
        pool_timeout=30,
    )

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
