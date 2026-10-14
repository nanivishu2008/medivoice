from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from ..database import get_db
from .. import crud, schemas

router = APIRouter(prefix="/api/doctors", tags=["Doctors"])


@router.get("", response_model=List[schemas.DoctorResponse])
def list_doctors(
    specialty: Optional[str] = Query(None, description="Filter doctors by specialty (e.g. Cardiology)"),
    db: Session = Depends(get_db)
):
    """Retrieve list of registered healthcare providers, optionally filtered by medical specialty."""
    return crud.get_doctors(db=db, specialty=specialty)


@router.get("/specialties", response_model=List[str])
def list_specialties(db: Session = Depends(get_db)):
    """Retrieve all unique specialties currently represented by registered doctors."""
    doctors = crud.get_doctors(db=db)
    specialties = sorted(list({doc.specialty for doc in doctors if doc.specialty}))
    return specialties


@router.get("/{doctor_id}", response_model=schemas.DoctorResponse)
def get_doctor(doctor_id: int, db: Session = Depends(get_db)):
    """Retrieve full details of a specific doctor."""
    doctor = crud.get_doctor_by_id(db=db, doctor_id=doctor_id)
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Doctor with ID {doctor_id} not found."
        )
    return doctor
