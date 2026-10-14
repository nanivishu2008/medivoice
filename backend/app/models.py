import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from .database import Base


def generate_reference_code() -> str:
    """Generate a clean, readable 8-character booking reference code (e.g. MV-4A7F2B)."""
    return f"MV-{uuid.uuid4().hex[:6].upper()}"


class Doctor(Base):
    """Healthcare provider with specialty and availability profiles."""
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    specialty = Column(String(100), nullable=False, index=True)
    qualification = Column(String(120), nullable=False)
    bio = Column(String(500), nullable=True)

    # Relationships
    slots = relationship("AppointmentSlot", back_populates="doctor", cascade="all, delete-orphan")


class AppointmentSlot(Base):
    """
    Discrete calendar slot for a doctor.
    'is_booked' provides an indexed flag for fast queries on available times.
    """
    __tablename__ = "appointment_slots"

    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False, index=True)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=False)
    is_booked = Column(Boolean, default=False, nullable=False, index=True)

    # Relationships
    doctor = relationship("Doctor", back_populates="slots")
    booking = relationship("Booking", back_populates="slot", uselist=False)


class Booking(Base):
    """
    Confirmed patient appointment.
    
    CRITICAL: slot_id is UNIQUE.
    This database-level unique constraint prevents two concurrent requests from
    ever inserting duplicate bookings for the same slot.
    """
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    reference_code = Column(String(32), default=generate_reference_code, unique=True, nullable=False, index=True)
    slot_id = Column(Integer, ForeignKey("appointment_slots.id", ondelete="RESTRICT"), nullable=False, unique=True)
    patient_name = Column(String(120), nullable=False)
    patient_phone = Column(String(30), nullable=False)
    patient_email = Column(String(120), nullable=False)
    reason_for_visit = Column(String(300), nullable=True)
    status = Column(String(20), default="CONFIRMED", nullable=False)  # CONFIRMED, CANCELLED
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    slot = relationship("AppointmentSlot", back_populates="booking")

    __table_args__ = (
        UniqueConstraint("slot_id", name="uq_booking_slot_id"),
    )
