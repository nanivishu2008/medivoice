from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..database import get_db
from .. import crud, schemas

router = APIRouter(prefix="/api/bookings", tags=["Bookings"])


@router.post("", response_model=schemas.BookingResponse, status_code=status.HTTP_201_CREATED)
def create_booking(booking_in: schemas.BookingCreateRequest, db: Session = Depends(get_db)):
    """
    Book an appointment slot for a patient.
    
    Guarantees:
    - Verifies slot existence and availability in real time.
    - Prevents double-booking race conditions atomically.
    - Returns 201 Created with full booking confirmation and reference code.
    - Returns 409 Conflict if the slot has already been taken.
    """
    return crud.create_booking(db=db, booking_data=booking_in)


@router.get("/{reference_code}", response_model=schemas.BookingResponse)
def get_booking(reference_code: str, db: Session = Depends(get_db)):
    """Lookup an existing booking by its unique reference code (e.g. MV-4A7F2B)."""
    booking = crud.get_booking_by_reference(db=db, reference_code=reference_code)
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Booking '{reference_code}' was not found."
        )
    return booking


@router.post("/{reference_code}/cancel", response_model=schemas.BookingResponse)
def cancel_booking(reference_code: str, db: Session = Depends(get_db)):
    """Cancel a confirmed booking and immediately release its slot back to the public pool."""
    return crud.cancel_booking(db=db, reference_code=reference_code)
