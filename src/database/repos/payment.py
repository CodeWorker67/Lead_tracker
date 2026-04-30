from advanced_alchemy.repository import SQLAlchemyAsyncRepository

from database.models import Payment


class PaymentRepository(SQLAlchemyAsyncRepository[Payment]):  # pyright: ignore
    model_type = Payment
