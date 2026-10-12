from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Text,
    Date,
    Integer,
    Numeric,
    ForeignKey,
    DateTime
)
from sqlalchemy.sql import func
from Backend.app.database import Base
class Candidate(Base):
    __tablename__ = "candidates"
    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True
    )
    user_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )
    date_of_birth = Column(Date)
    gender = Column(String(30))
    phone = Column(String(20))
    address = Column(Text)
    city = Column(String(100))
    qualification = Column(String(150))
    college = Column(String(200))
    graduation_year = Column(Integer)
    skills = Column(Text)
    experience_years = Column(
        Numeric(4, 2),
        default=0
    )
    previous_company = Column(String(200))
    previous_job_title = Column(String(150))
    resume_path = Column(String(500))
    profile_image = Column(String(500))
    created_at = Column(
        DateTime,
        server_default=func.now()
    )
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now()
    )