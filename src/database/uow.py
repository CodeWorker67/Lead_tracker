from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from database.repos import PaymentRepository, UserRepository


class UnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

    async def __aenter__(self) -> "UnitOfWork":
        self.session = self.session_factory()
        self.user_repo = UserRepository(session=self.session)
        self.payment_repo = PaymentRepository(session=self.session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            await self.rollback()
        await self.session.close()
