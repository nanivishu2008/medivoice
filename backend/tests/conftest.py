from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Doctor, AppointmentSlot, Booking

# Use an in-memory SQLite database configured with StaticPool for thread-safe test isolation
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Provides a pristine database schema for each individual test function."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Provides a FastAPI TestClient configured to use the test database session."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def sample_doctor(db_session):
    """Fixture creating a test doctor."""
    doctor = Doctor(
        name="Dr. Jane Watson",
        specialty="Neurology",
        qualification="MD, PhD",
        bio="Experienced neurologist with expertise in migraine management."
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return doctor


@pytest.fixture(scope="function")
def sample_slot(db_session, sample_doctor):
    """Fixture creating a future available appointment slot."""
    start_dt = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=2, hours=10)
    end_dt = start_dt + timedelta(minutes=45)
    slot = AppointmentSlot(
        doctor_id=sample_doctor.id,
        start_time=start_dt,
        end_time=end_dt,
        is_booked=False
    )
    db_session.add(slot)
    db_session.commit()
    db_session.refresh(slot)
    return slot
