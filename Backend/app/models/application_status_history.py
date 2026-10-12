from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Text,
    DateTime,
    ForeignKey
)
from sqlalchemy.sql import func
from Backend.app.database import Base
class ApplicationStatusHistory(Base):
    __tablename__ = "application_status_history"
    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True
    )
    application_id = Column(
        BigInteger,
        ForeignKey(
            "applications.id",
            ondelete="CASCADE"
        ),
        nullable=False
    )
    old_status = Column(
        String(50)
    )
    new_status = Column(
        String(50),
        nullable=False
    )
    changed_by = Column(
        BigInteger,
        ForeignKey(
            "users.id",
            ondelete="RESTRICT"
        ),
        nullable=False
    )
    remarks = Column(
        Text
    )
    changed_at = Column(
        DateTime,
        server_default=func.now()
    )