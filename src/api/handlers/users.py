from datetime import datetime
from typing import Annotated

from api.schemas import UserBotPostback, UserPostbackCreate, UserResponse
from database.core import get_uow
from database.models import User
from database.uow import UnitOfWork
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserResponse)
async def postback_create_user(
    data: UserPostbackCreate, uow: Annotated[UnitOfWork, Depends(get_uow)]
) -> UserResponse:
    existing = await uow.user_repo.get_by_telegram_and_bot(data.user_id, data.bot_id)
    if existing:
        logger.info(
            "User already registered for bot: telegram_user={} bot={}",
            data.user_id,
            data.bot_id,
        )
        return UserResponse.model_validate(existing)

    user = User(
        user_id=data.user_id,
        username=data.username,
        full_name=data.full_name,
        source=data.source,
        bot_id=data.bot_id,
        bot_name=data.bot_name,
    )
    user = await uow.user_repo.add(user)
    await uow.commit()
    logger.info("User row created: {} bot={}", user.id, data.bot_id)
    return UserResponse.model_validate(user)


@router.post("/trial", response_model=UserResponse)
async def postback_trial(
    data: UserBotPostback, uow: Annotated[UnitOfWork, Depends(get_uow)]
) -> UserResponse:
    user = await uow.user_repo.get_by_telegram_and_bot(data.user_id, data.bot_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found for this bot")

    user.trial_at = datetime.now()
    await uow.commit()
    logger.info("trial_at set for user {} (telegram {})", user.id, data.user_id)
    return UserResponse.model_validate(user)


@router.post("/connected", response_model=UserResponse)
async def postback_connected(
    data: UserBotPostback, uow: Annotated[UnitOfWork, Depends(get_uow)]
) -> UserResponse:
    user = await uow.user_repo.get_by_telegram_and_bot(data.user_id, data.bot_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found for this bot")

    user.connected_at = datetime.now()
    await uow.commit()
    logger.info("connected_at set for user {} (telegram {})", user.id, data.user_id)
    return UserResponse.model_validate(user)
