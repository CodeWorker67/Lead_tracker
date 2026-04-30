import uuid

from advanced_alchemy.repository import SQLAlchemyAsyncRepository

from database.models import User


class UserRepository(SQLAlchemyAsyncRepository[User]):  # pyright: ignore
    model_type = User

    async def get_by_telegram_and_bot(
        self, user_id: int, bot_id: int
    ) -> User | None:
        return await self.get_one_or_none(user_id=user_id, bot_id=bot_id)

    async def get_by_dashboard_id(self, dashboard_id: uuid.UUID) -> User | None:
        return await self.get_one_or_none(id=dashboard_id)
