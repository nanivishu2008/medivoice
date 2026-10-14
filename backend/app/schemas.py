from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ==========================================
# Doctor Schemas
# ==========================================
class DoctorBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=120, description="Full name of the doctor")
    specialty: str = Field(..., min_length=2, max_length=100, description="Medical specialty (e.g. Cardiology)")
    qualification: str = Field(..., min_length=2, max_length=120, description="Credentials (e.g. MD, MBBS)")
    bio: Optional[str] = Field(None, max_length=500, description="Brief professional biography")


class DoctorResponse(DoctorBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Slot Schemas
# ==========================================
class SlotBase(BaseModel):
    doctor_id: int
    start_time: datetime
    end_time: datetime
    is_booked: bool


class SlotResponse(SlotBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class SlotWithDoctorResponse(SlotResponse):
    doctor: DoctorResponse
    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Booking Schemas
# ==========================================
class BookingCreateRequest(BaseModel):
    slot_id: int = Field(..., gt=0, description="Unique ID of the appointment slot to reserve")
    patient_name: str = Field(..., min_length=2, max_length=120, description="Full legal name of the patient")
    patient_phone: str = Field(..., min_length=7, max_length=30, description="Contact phone number")
    patient_email: EmailStr = Field(..., description="Valid email address for appointment confirmation")
    reason_for_visit: Optional[str] = Field(None, max_length=300, description="Optional symptoms or visit purpose")


class BookingResponse(BaseModel):
    id: int
    reference_code: str
    slot_id: int
    patient_name: str
    patient_phone: str
    patient_email: str
    reason_for_visit: Optional[str]
    status: str
    created_at: datetime
    slot: SlotWithDoctorResponse

    model_config = ConfigDict(from_attributes=True)


class BookingSimpleResponse(BaseModel):
    id: int
    reference_code: str
    status: str
    message: str
