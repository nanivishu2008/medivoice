import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
from ..database import get_db
from .. import crud, models, schemas

router = APIRouter(prefix="/api/retell", tags=["Retell Voice AI Integration"])


# ==========================================
# Retell Custom Function Request/Response Schemas
# ==========================================
class RetellAvailabilityRequest(BaseModel):
    specialty: Optional[str] = Field(None, description="Requested specialty (e.g. Cardiology, Dermatology)")
    doctor_id: Optional[int] = Field(None, description="Specific doctor ID if known")


class RetellBookRequest(BaseModel):
    slot_id: int = Field(..., description="ID of the appointment slot")
    patient_name: str = Field(..., min_length=2, max_length=120)
    patient_phone: str = Field(..., min_length=7, max_length=30)
    patient_email: str = Field(..., description="Patient email address")
    reason_for_visit: Optional[str] = None


class RetellLookupRequest(BaseModel):
    reference_code: str = Field(..., description="Booking reference code (e.g. MV-4A7F2B)")


class RetellConversationState(BaseModel):
    step: str = "GREETING"  # GREETING, COLLECT_SPECIALTY, SELECT_SLOT, COLLECT_NAME, COLLECT_CONTACT, COMPLETED
    specialty: Optional[str] = None
    doctor_id: Optional[int] = None
    doctor_name: Optional[str] = None
    slot_id: Optional[int] = None
    slot_time_str: Optional[str] = None
    patient_name: Optional[str] = None
    patient_phone: Optional[str] = None
    patient_email: Optional[str] = None
    reason: Optional[str] = None


class RetellChatRequest(BaseModel):
    user_message: str
    state: Optional[RetellConversationState] = None


class RetellChatResponse(BaseModel):
    ai_response: str
    next_state: RetellConversationState
    available_slots: Optional[List[Dict[str, Any]]] = None
    booking_reference: Optional[str] = None


# ==========================================
# 1. Voice AI Custom Function: Check Availability
# ==========================================
@router.post("/check-availability")
def retell_check_availability(
    payload: RetellAvailabilityRequest,
    db: Session = Depends(get_db)
):
    """
    Retell AI Custom Function: Checks available slots and returns a voice-optimized response.
    """
    doctors = crud.get_doctors(db=db, specialty=payload.specialty)
    if not doctors:
        return {
            "success": False,
            "count": 0,
            "message": f"I couldn't find any healthcare providers specializing in {payload.specialty or 'that field'}. We have specialists in Cardiology, Dermatology, Pediatrics, and General Practice.",
            "slots": []
        }

    slots = crud.get_available_slots(db=db, doctor_id=payload.doctor_id)
    if payload.specialty:
        # Filter slots matching the requested specialty
        slots = [s for s in slots if s.doctor and payload.specialty.lower() in s.doctor.specialty.lower()]

    if not slots:
        return {
            "success": True,
            "count": 0,
            "message": "Currently there are no open slots matching your request. Please check back soon or try another specialty.",
            "slots": []
        }

    # Format the top slots for speech
    formatted = []
    for s in slots[:5]:
        formatted.append({
            "slot_id": s.id,
            "doctor_id": s.doctor_id,
            "doctor_name": s.doctor.name if s.doctor else "Doctor",
            "specialty": s.doctor.specialty if s.doctor else "General",
            "start_time": s.start_time.isoformat(),
            "formatted_time": s.start_time.strftime("%A, %B %d at %I:%M %p")
        })

    times_speech = ", ".join([f"{s['formatted_time']} with {s['doctor_name']}" for s in formatted[:3]])
    voice_msg = (
        f"I found {len(formatted)} available openings. "
        f"Some of the upcoming options are: {times_speech}. "
        "Which time slot works best for you?"
    )

    return {
        "success": True,
        "count": len(formatted),
        "message": voice_msg,
        "slots": formatted
    }


# ==========================================
# 2. Voice AI Custom Function: Book Appointment
# ==========================================
@router.post("/book-appointment")
def retell_book_appointment(
    payload: RetellBookRequest,
    db: Session = Depends(get_db)
):
    """
    Retell AI Custom Function: Atomically reserves slot and confirms booking with spoken confirmation.
    """
    booking_in = schemas.BookingCreateRequest(
        slot_id=payload.slot_id,
        patient_name=payload.patient_name,
        patient_phone=payload.patient_phone,
        patient_email=payload.patient_email,
        reason_for_visit=payload.reason_for_visit
    )

    booking = crud.create_booking(db=db, booking_data=booking_in)
    slot_time = booking.slot.start_time.strftime("%A, %B %d at %I:%M %p")
    doc_name = booking.slot.doctor.name if booking.slot and booking.slot.doctor else "your doctor"

    spoken_text = (
        f"Thank you, {booking.patient_name}. Your appointment with {doc_name} on {slot_time} "
        f"is officially confirmed. Your confirmation reference code is {booking.reference_code}. "
        "We have sent full details to your email."
    )

    return {
        "success": True,
        "booking_id": booking.id,
        "reference_code": booking.reference_code,
        "patient_name": booking.patient_name,
        "doctor_name": doc_name,
        "appointment_time": slot_time,
        "spoken_confirmation": spoken_text
    }


# ==========================================
# 3. Voice AI Custom Function: Lookup Booking
# ==========================================
@router.post("/lookup-booking")
def retell_lookup_booking(
    payload: RetellLookupRequest,
    db: Session = Depends(get_db)
):
    """
    Retell AI Custom Function: Finds a booking and returns spoken status.
    """
    booking = crud.get_booking_by_reference(db=db, reference_code=payload.reference_code)
    if not booking:
        return {
            "success": False,
            "message": f"I couldn't locate any appointment with reference code {payload.reference_code}. Please verify the code and try again."
        }

    slot_time = booking.slot.start_time.strftime("%A, %B %d at %I:%M %p")
    doc_name = booking.slot.doctor.name if booking.slot and booking.slot.doctor else "Doctor"

    return {
        "success": True,
        "reference_code": booking.reference_code,
        "status": booking.status,
        "patient_name": booking.patient_name,
        "appointment_time": slot_time,
        "doctor_name": doc_name,
        "message": f"Appointment {booking.reference_code} for {booking.patient_name} with {doc_name} is currently {booking.status} for {slot_time}."
    }


# ==========================================
# 4. Multi-Turn AI Voice Questionnaire / Assistant
# ==========================================
@router.post("/chat", response_model=RetellChatResponse)
def retell_chat_conversation(
    req: RetellChatRequest,
    db: Session = Depends(get_db)
):
    """
    Intelligent conversational loop that asks questions step-by-step,
    collects patient requirements, checks real availability, and books appointments.
    """
    msg = req.user_message.strip()
    msg_lower = msg.lower()
    state = req.state or RetellConversationState()

    # Step 1: Greeting or Specialty Identification
    if state.step in ["GREETING", "COLLECT_SPECIALTY"]:
        specialty = None
        # Check against registered doctor specialties dynamically
        doctors = crud.get_doctors(db=db)
        for doc in doctors:
            if doc.specialty.lower() in msg_lower or doc.name.lower() in msg_lower:
                specialty = doc.specialty
                break

        # Check common symptom keywords
        if not specialty:
            if any(w in msg_lower for w in ["heart", "cardio", "chest", "blood pressure"]):
                specialty = "Cardiology"
            elif any(w in msg_lower for w in ["skin", "derma", "rash", "acne"]):
                specialty = "Dermatology"
            elif any(w in msg_lower for w in ["child", "pediatric", "baby", "kid"]):
                specialty = "Pediatrics"
            elif any(w in msg_lower for w in ["headache", "migraine", "neuro", "brain"]):
                specialty = "Neurology"
            elif any(w in msg_lower for w in ["general", "routine", "physician", "checkup", "flu", "cough", "fever"]):
                specialty = "General Practice"

        if not specialty:
            registered_specs = sorted(list({d.specialty for d in doctors if d.specialty}))
            specs_text = ", ".join(registered_specs) if registered_specs else "Cardiology, Dermatology, Pediatrics, and General Practice"
            return RetellChatResponse(
                ai_response=(
                    "Hello! I am your MediVoice AI healthcare assistant. "
                    f"What medical specialty or symptoms do you need assistance with? "
                    f"We currently have specialists in {specs_text}."
                ),
                next_state=RetellConversationState(step="COLLECT_SPECIALTY")
            )

        # Specialty identified: query database for slots
        slots = crud.get_available_slots(db=db)
        matched_slots = [
            s for s in slots if s.doctor and specialty.lower() in s.doctor.specialty.lower()
        ]

        if not matched_slots:
            return RetellChatResponse(
                ai_response=f"I found our {specialty} department, but there are no open slots currently. Would you like to check another specialty?",
                next_state=RetellConversationState(step="COLLECT_SPECIALTY")
            )

        formatted_slots = [
            {
                "slot_id": s.id,
                "doctor_name": s.doctor.name,
                "start_time": s.start_time.isoformat(),
                "formatted_time": s.start_time.strftime("%A, %B %d at %I:%M %p")
            }
            for s in matched_slots[:4]
        ]

        doc_name = matched_slots[0].doctor.name
        first_time = formatted_slots[0]["formatted_time"]
        second_time = formatted_slots[1]["formatted_time"] if len(formatted_slots) > 1 else None

        response_speech = (
            f"Great, I can help you book with {doc_name} ({specialty}). "
            f"The earliest opening is {first_time}"
        )
        if second_time:
            response_speech += f", or {second_time}."
        else:
            response_speech += "."
        response_speech += " Which time slot works best for you?"

        next_state = RetellConversationState(
            step="SELECT_SLOT",
            specialty=specialty,
            doctor_name=doc_name
        )

        return RetellChatResponse(
            ai_response=response_speech,
            next_state=next_state,
            available_slots=formatted_slots
        )

    # Step 2: Slot Selection
    if state.step == "SELECT_SLOT":
        # Check if user mentioned a slot ID, time, or selected one
        slot_match = None
        # Try to match slot ID directly
        numbers = re.findall(r"\b\d+\b", msg)
        if numbers:
            candidate_id = int(numbers[0])
            slot_obj = crud.get_slot_by_id(db=db, slot_id=candidate_id)
            if slot_obj and not slot_obj.is_booked:
                slot_match = slot_obj

        # If not matched by ID, pick the earliest available slot for this specialty
        if not slot_match:
            slots = crud.get_available_slots(db=db)
            if state.specialty:
                slots = [s for s in slots if s.doctor and state.specialty.lower() in s.doctor.specialty.lower()]
            if slots:
                slot_match = slots[0]

        if not slot_match:
            return RetellChatResponse(
                ai_response="I couldn't locate that slot. Please pick one of the available times listed on screen.",
                next_state=state
            )

        slot_time_formatted = slot_match.start_time.strftime("%A, %B %d at %I:%M %p")
        next_state = state.model_copy()
        next_state.step = "COLLECT_NAME"
        next_state.slot_id = slot_match.id
        next_state.slot_time_str = slot_time_formatted
        next_state.doctor_name = slot_match.doctor.name if slot_match.doctor else state.doctor_name

        return RetellChatResponse(
            ai_response=f"Selected {slot_time_formatted} with {next_state.doctor_name}. May I have your full legal name please?",
            next_state=next_state
        )

    # Step 3: Collect Patient Name
    if state.step == "COLLECT_NAME":
        name = msg.replace("my name is", "").replace("i am", "").replace("it is", "").strip().title()
        if len(name) < 2:
            return RetellChatResponse(
                ai_response="Please state your full name for the medical record.",
                next_state=state
            )

        next_state = state.model_copy()
        next_state.step = "COLLECT_CONTACT"
        next_state.patient_name = name

        return RetellChatResponse(
            ai_response=f"Thank you, {name}. What is the best phone number and email address to reach you for confirmation?",
            next_state=next_state
        )

    # Step 4: Collect Contact Info & Execute Booking
    if state.step == "COLLECT_CONTACT":
        # Extract email and phone
        email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", msg)
        phone_match = re.search(r"(\+?\d[\d\s-]{6,15}\d)", msg)

        email = email_match.group(0) if email_match else "patient@example.com"
        phone = phone_match.group(0) if phone_match else "+1-555-0199"

        if not state.slot_id:
            return RetellChatResponse(
                ai_response="It looks like the appointment time was lost. Let's restart: what specialty do you need?",
                next_state=RetellConversationState(step="COLLECT_SPECIALTY")
            )

        # Atomic booking execution
        try:
            booking_in = schemas.BookingCreateRequest(
                slot_id=state.slot_id,
                patient_name=state.patient_name or "Patient",
                patient_phone=phone,
                patient_email=email,
                reason_for_visit=f"Booked via Voice AI Assistant ({state.specialty or 'General'})"
            )
            booking = crud.create_booking(db=db, booking_data=booking_in)

            confirmation_msg = (
                f"You're all set, {booking.patient_name}! "
                f"Your appointment with {state.doctor_name} on {state.slot_time_str} is officially confirmed. "
                f"Your reference code is {booking.reference_code}. A confirmation has been sent to {booking.patient_email}."
            )

            completed_state = state.model_copy()
            completed_state.step = "COMPLETED"

            return RetellChatResponse(
                ai_response=confirmation_msg,
                next_state=completed_state,
                booking_reference=booking.reference_code
            )
        except HTTPException as he:
            return RetellChatResponse(
                ai_response=f"Sorry, {he.detail} Would you like to pick another time?",
                next_state=RetellConversationState(step="COLLECT_SPECIALTY")
            )
        except Exception as e:
            return RetellChatResponse(
                ai_response="An unexpected issue occurred while booking. Please try again or select a slot manually.",
                next_state=RetellConversationState(step="COLLECT_SPECIALTY")
            )

    # Fallback
    return RetellChatResponse(
        ai_response="How can I assist you with scheduling your appointment today?",
        next_state=RetellConversationState(step="COLLECT_SPECIALTY")
    )
