from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from ..database import get_db
from .. import crud, schemas

router = APIRouter(prefix="/api/slots", tags=["Appointment Slots"])


@router.get("", response_model=List[schemas.SlotWithDoctorResponse])
def list_available_slots(
    doctor_id: Optional[int] = Query(None, description="Filter available slots by doctor ID"),
    from_date: Optional[datetime] = Query(None, description="Filter slots starting from this datetime"),
    db: Session = Depends(get_db)
):
    """
    Query available, unbooked appointment slots from the database.
    Slot availability is never hardcoded; it is computed dynamically from the database.
    """
    return crud.get_available_slots(db=db, doctor_id=doctor_id, from_time=from_date)


@router.get("/{slot_id}", response_model=schemas.SlotWithDoctorResponse)
def get_slot(slot_id: int, db: Session = Depends(get_db)):
    """Retrieve details for a specific slot."""
    slot = crud.get_slot_by_id(db=db, slot_id=slot_id)
    if not slot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Slot with ID {slot_id} not found."
        )
    return slot
