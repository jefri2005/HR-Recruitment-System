from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Text,
    Numeric,
    Integer,
    Date,
    DateTime,
    ForeignKey,
    Enum
)
from sqlalchemy.sql import func
from Backend.app.database import Base
class Job(Base):
    __tablename__ = "jobs"
    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True
    )
    title = Column(
        String(200),
        nullable=False
    )
    department = Column(
        String(100),
        nullable=False
    )
    location = Column(
        String(150),
        nullable=False
    )
    employment_type = Column(
        Enum(
            "FULL_TIME",
            "PART_TIME",
            "CONTRACT",
            "INTERNSHIP"
        ),
        default="FULL_TIME"
    )
    experience_min = Column(
        Numeric(4, 2),
        default=0
    )
    experience_max = Column(
        Numeric(4, 2)
    )
    salary_min = Column(
        Numeric(12, 2)
    )
    salary_max = Column(
        Numeric(12, 2)
    )
    required_skills = Column(Text)
    description = Column(
        Text,
        nullable=False
    )
    responsibilities = Column(Text)
    qualifications = Column(Text)
    vacancies = Column(
        Integer,
        default=1
    )
    application_deadline = Column(Date)
    status = Column(
        Enum(
            "DRAFT",
            "ACTIVE",
            "CLOSED"
        ),
        default="DRAFT"
    )
    created_by = Column(
        BigInteger,
        ForeignKey(
            "users.id",
            ondelete="RESTRICT"
        ),
        nullable=False
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