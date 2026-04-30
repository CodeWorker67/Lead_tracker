from typing import Annotated

from api.schemas import PaymentCreate, PaymentResponse
from database.core import get_uow
from database.models import Payment
from database.uow import UnitOfWork
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/", response_model=PaymentResponse)
async def create_payment(
    data: PaymentCreate, uow: Annotated[UnitOfWork, Depends(get_uow)]
) -> PaymentResponse:
    user = await uow.user_repo.get_by_telegram_and_bot(data.user_id, data.bot_id)
    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found for this bot; send POST /users/ first",
        )

    payment = Payment(
        user_id=data.user_id,
        bot_id=data.bot_id,
        amount=data.amount,
    )
    payment = await uow.payment_repo.add(payment)
    await uow.commit()
    logger.info(
        "Payment created: {} user {} bot {}",
        payment.id,
        payment.user_id,
        payment.bot_id,
    )
    return PaymentResponse.model_validate(payment)
