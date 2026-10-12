
from sqlalchemy import (
    Column,
    BigInteger,
    Text,
    DateTime,
    ForeignKey,
    Enum,
    UniqueConstraint
)
from sqlalchemy.sql import func
from Backend.app.database import Base


class Application(Base):
    __tablename__ = "applications"

    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True
    )

    candidate_id = Column(
        BigInteger,
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False
    )

    job_id = Column(
        BigInteger,
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False
    )

    status = Column(
        Enum(
            "APPLIED",
            "UNDER_REVIEW",
            "SHORTLISTED",
            "REJECTED",
            "INTERVIEW_SCHEDULED",
            "SELECTED",
            "HIRED",
            "WITHDRAWN"
        ),
        default="APPLIED",
        nullable=False
    )

    cover_letter = Column(Text)

    applied_at = Column(
        DateTime,
        server_default=func.now()
    )

    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "candidate_id",
            "job_id",
            name="uq_candidate_job"
        ),
    )