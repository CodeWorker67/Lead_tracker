import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BIGINT, DateTime, ForeignKeyConstraint, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Payment(Base):
    """Платёж привязан к паре (telegram user_id, bot_id) как и строка users."""

    __tablename__ = "payments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "bot_id"],
            ["users.user_id", "users.bot_id"],
            ondelete="CASCADE",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[int] = mapped_column(BIGINT, nullable=False)
    bot_id: Mapped[int] = mapped_column(BIGINT, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
