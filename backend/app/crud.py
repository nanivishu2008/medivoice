from datetime import datetime, timezone
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload
from . import models, schemas


def get_doctors(db: Session, specialty: Optional[str] = None) -> List[models.Doctor]:
    """Retrieve all doctors, optionally filtered by medical specialty (case-insensitive)."""
    query = db.query(models.Doctor)
    if specialty:
        query = query.filter(models.Doctor.specialty.ilike(f"%{specialty}%"))
    return query.order_by(models.Doctor.name.asc()).all()


def get_doctor_by_id(db: Session, doctor_id: int) -> Optional[models.Doctor]:
    """Retrieve a single doctor by primary key."""
    return db.query(models.Doctor).filter(models.Doctor.id == doctor_id).first()


def get_available_slots(
    db: Session,
    doctor_id: Optional[int] = None,
    from_time: Optional[datetime] = None
) -> List[models.AppointmentSlot]:
    """
    Retrieve upcoming slots that are not booked yet.
    Eager-loads doctor relationship to avoid N+1 query overhead.
    """
    query = (
        db.query(models.AppointmentSlot)
        .options(joinedload(models.AppointmentSlot.doctor))
        .filter(models.AppointmentSlot.is_booked == False)
    )

    if from_time:
        query = query.filter(models.AppointmentSlot.start_time >= from_time)
    else:
        # Default to now onwards
        query = query.filter(models.AppointmentSlot.start_time >= datetime.now(timezone.utc).replace(tzinfo=None))

    if doctor_id:
        query = query.filter(models.AppointmentSlot.doctor_id == doctor_id)

    return query.order_by(models.AppointmentSlot.start_time.asc()).all()


def get_slot_by_id(db: Session, slot_id: int) -> Optional[models.AppointmentSlot]:
    """Retrieve a specific slot by ID."""
    return (
        db.query(models.AppointmentSlot)
        .options(joinedload(models.AppointmentSlot.doctor))
        .filter(models.AppointmentSlot.id == slot_id)
        .first()
    )


def create_booking(db: Session, booking_data: schemas.BookingCreateRequest) -> models.Booking:
    """
    Atomically reserves an appointment slot and creates the patient booking.
    
    CONCURRENCY & SAFETY DESIGN:
    1. Verify that the requested slot exists and is not currently booked.
    2. Attempt state mutation (is_booked = True) and insert Booking record.
    3. Rely on database-level UNIQUE(slot_id) constraint in Booking table to catch
       any concurrent collision where two requests pass the initial read check.
    4. Explicitly roll back the transaction on any failure to guarantee no dirty reads.
    5. Never return a success response unless db.commit() has successfully completed.
    """
    # Step 1: Pre-check slot existence and status
    slot = (
        db.query(models.AppointmentSlot)
        .options(joinedload(models.AppointmentSlot.doctor))
        .filter(models.AppointmentSlot.id == booking_data.slot_id)
        .first()
    )

    if not slot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appointment slot ID {booking_data.slot_id} does not exist."
        )

    if slot.is_booked:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This appointment slot has already been reserved. Please select a different time."
        )

    # Step 2: Stage mutations
    slot.is_booked = True

    new_booking = models.Booking(
        slot_id=slot.id,
        patient_name=booking_data.patient_name.strip(),
        patient_phone=booking_data.patient_phone.strip(),
        patient_email=booking_data.patient_email.strip().lower(),
        reason_for_visit=booking_data.reason_for_visit.strip() if booking_data.reason_for_visit else None,
        status="CONFIRMED"
    )

    db.add(new_booking)

    # Step 3: Atomic commit with collision handling
    try:
        db.commit()
        db.refresh(new_booking)
        return new_booking
    except IntegrityError:
        # Caught if a parallel worker committed a booking for the same slot milliseconds earlier
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conflict: This slot was booked concurrently by another user. Your request was aborted."
        )
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database transaction failed: {str(exc)}"
        )


def get_booking_by_reference(db: Session, reference_code: str) -> Optional[models.Booking]:
    """Find a booking by its human-readable reference code."""
    return (
        db.query(models.Booking)
        .options(
            joinedload(models.Booking.slot).joinedload(models.AppointmentSlot.doctor)
        )
        .filter(models.Booking.reference_code == reference_code.strip().upper())
        .first()
    )


def cancel_booking(db: Session, reference_code: str) -> models.Booking:
    """
    Cancels a booking and frees up the associated appointment slot for new bookings.
    """
    booking = get_booking_by_reference(db, reference_code)
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Booking with reference '{reference_code}' was not found."
        )

    if booking.status == "CANCELLED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This booking is already cancelled."
        )

    try:
        booking.status = "CANCELLED"
        # Release the slot back to the available pool
        if booking.slot:
            booking.slot.is_booked = False

        db.commit()
        db.refresh(booking)
        return booking
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel booking: {str(exc)}"
        )
