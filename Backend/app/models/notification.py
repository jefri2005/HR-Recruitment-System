from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey
)
from sqlalchemy.sql import func
from Backend.app.database import Base
class Notification(Base):
    __tablename__ = "notifications"
    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True
    )
    user_id = Column(
        BigInteger,
        ForeignKey(
            "users.id",
            ondelete="CASCADE"
        ),
        nullable=False
    )
    title = Column(
        String(200),
        nullable=False
    )
    message = Column(
        Text,
        nullable=False
    )
    type = Column(
        String(50)
    )
    is_read = Column(
        Boolean,
        default=False
    )
    created_at = Column(
        DateTime,
        server_default=func.now()
    )