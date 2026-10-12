
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Load environment variables from the .env file
load_dotenv()

# Read the database connection URL
DATABASE_URL = os.getenv("DATABASE_URL")

# Stop startup with a clear error if the URL is missing
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is missing. Please check your .env file."
    )

# Create the SQLAlchemy database engine
engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True
)

# Create a database session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base class for all SQLAlchemy models
Base = declarative_base()


# Dependency for FastAPI database sessions
def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()