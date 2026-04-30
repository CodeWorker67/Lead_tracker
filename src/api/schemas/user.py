import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserPostbackCreate(BaseModel):
    """Первый заход / регистрация в боте."""

    user_id: int = Field(..., description="Telegram user id")
    username: str | None = None
    full_name: str | None = None
    source: str | None = None
    bot_id: int
    bot_name: str | None = None


class UserBotPostback(BaseModel):
    """Идентификация пары пользователь + бот для постбеков триала / подключения."""

    user_id: int
    bot_id: int


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: int
    username: str | None = None
    full_name: str | None = None
    source: str | None = None
    created_at: datetime
    bot_id: int
    bot_name: str | None = None
    updated_at: datetime
    trial_at: datetime | None = None
    connected_at: datetime | None = None
