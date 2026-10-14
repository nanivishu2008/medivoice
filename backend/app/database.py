import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Default to a local SQLite database file in the backend directory
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./medivoice.db")

# SQLite requires 'check_same_thread': False when used in multi-threaded environments like FastAPI
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency yielding a scoped database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
