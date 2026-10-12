from sqlalchemy import Column, BigInteger, String, Boolean, DateTime, Enum
from sqlalchemy.sql import func
from Backend.app.database import Base
class User(Base):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    full_name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(
        Enum("HR", "CANDIDATE"),
        nullable=False
    )
    phone = Column(String(20))
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(
        DateTime,
        server_default=func.now()
    )
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now()
    )