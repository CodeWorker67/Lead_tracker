from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import settings
from database.uow import UnitOfWork

engine = create_async_engine(
    settings.postgres_dsn,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=False,
)

SessionFactory = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_session() -> AsyncGenerator[AsyncSession]:
    async with SessionFactory() as session:
        yield session


async def get_uow() -> AsyncGenerator[UnitOfWork]:
    async with UnitOfWork(session_factory=SessionFactory) as uow:
        yield uow
