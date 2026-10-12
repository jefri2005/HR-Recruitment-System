from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Text,
    Date,
    Time,
    DateTime,
    ForeignKey,
    Enum
)
from sqlalchemy.sql import func
from Backend.app.database import Base
class Interview(Base):
    __tablename__ = "interviews"

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
    interview_date = Column(
        Date,
        nullable=False
    )
    interview_time = Column(
        Time,
        nullable=False
    )
    interview_type = Column(
        Enum(
            "ONLINE",
            "PHONE",
            "IN_PERSON"
        ),
        nullable=False
    )
    interviewer = Column(
        String(150)
    )
    meeting_link = Column(
        String(500)
    )
    location = Column(
        String(300)
    )
    notes = Column(
        Text
    )
    feedback = Column(
        Text
    )
    result = Column(
        Enum(
            "PENDING",
            "PASSED",
            "FAILED",
            "RESCHEDULED",
            "CANCELLED"
        ),
        default="PENDING"
    )
    created_at = Column(
        DateTime,
        server_default=func.now()
    )
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now()
    )