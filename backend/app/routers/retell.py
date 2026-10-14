import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from ..database import get_db
from .. import crud, models, schemas

router = APIRouter(prefix="/api/retell", tags=["Retell Voice AI Integration"])


# ==========================================
# Schemas
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
    step: str = "COLLECT_SPECIALTY"  # COLLECT_SPECIALTY, SELECT_SLOT, COLLECT_NAME, COLLECT_CONTACT, COMPLETED
    specialty: Optional[str] = None
    doctor_id: Optional[int] = None
    doctor_name: Optional[str] = None
    slot_id: Optional[int] = None
    slot_time_str: Optional[str] = None
    patient_name: Optional[str] = None
    patient_phone: Optional[str] = None
    patient_email: Optional[str] = None
    reason: Optional[str] = None
    confirmed_reference: Optional[str] = None


class RetellChatRequest(BaseModel):
    user_message: str
    state: Optional[RetellConversationState] = None
    history: Optional[List[Dict[str, str]]] = None


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
    """Voice AI custom function to retrieve and speak available slots."""
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
        slots = [s for s in slots if s.doctor and payload.specialty.lower() in s.doctor.specialty.lower()]

    if not slots:
        return {
            "success": True,
            "count": 0,
            "message": "Currently there are no open slots matching your request. Please check back soon or try another specialty.",
            "slots": []
        }

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
    """Voice AI custom function to atomically book slot and return spoken confirmation."""
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
    """Voice AI custom function to look up booking status."""
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
# Helper: Conversational Entity & Intent Extraction
# ==========================================
def extract_email(text: str) -> Optional[str]:
    m = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)
    return m.group(0).lower() if m else None


def extract_phone(text: str) -> Optional[str]:
    # Match standard local, US, or international formats (e.g. 555-4321, (555) 123-4567, +1-555...)
    m = re.search(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3}[-.\s]?\d{3,4}|\b\d{7,15}\b", text)
    if m:
        return m.group(0).strip()
    digits = re.findall(r"\d", text)
    if len(digits) >= 7:
        return "".join(digits[:15])
    return None


def extract_name(text: str, current_name: Optional[str] = None) -> Optional[str]:
    if current_name:
        return current_name

    lower = text.lower()
    for trigger in ["my name is", "i am", "name is", "call me", "this is"]:
        if trigger in lower:
            idx = lower.find(trigger) + len(trigger)
            raw = text[idx:].strip()
            # Clean punctuation and extra words
            cleaned = re.split(r"[,.!?\n]|and |phone|email|my phone", raw, flags=re.IGNORECASE)[0].strip()
            if len(cleaned) >= 2:
                return cleaned.title()

    # If the message looks like just a 2-3 word name
    words = text.strip().split()
    if 2 <= len(words) <= 3 and all(w.isalpha() for w in words):
        stopwords = {"hello", "hi", "yes", "no", "please", "book", "appointment", "doctor", "slot"}
        if not any(w.lower() in stopwords for w in words):
            return text.strip().title()

    return None


# ==========================================
# 4. Multi-Turn Conversational Voice Assistant
# ==========================================
@router.post("/chat", response_model=RetellChatResponse)
def retell_chat_conversation(
    req: RetellChatRequest,
    db: Session = Depends(get_db)
):
    """
    Intelligent, context-aware conversational loop that remembers history,
    answers open-ended questions, asks relevant follow-up questions,
    and guides the user all the way to a confirmed database booking.
    """
    msg = req.user_message.strip()
    msg_lower = msg.lower()
    state = req.state.model_copy() if req.state else RetellConversationState()
    doctors = crud.get_doctors(db=db)

    # 1. Update Memory Entities across the message
    # Email
    email_found = extract_email(msg)
    if email_found:
        state.patient_email = email_found

    # Phone
    phone_found = extract_phone(msg)
    if phone_found:
        state.patient_phone = phone_found

    # Name
    name_found = extract_name(msg, state.patient_name)
    if name_found and not state.patient_name:
        state.patient_name = name_found

    # Doctor preference by name
    for doc in doctors:
        doc_surname = doc.name.split()[-1].lower()
        if doc.name.lower() in msg_lower or doc_surname in msg_lower:
            state.doctor_id = doc.id
            state.doctor_name = doc.name
            state.specialty = doc.specialty
            break

    # Specialty / Symptoms preference
    if not state.specialty:
        for doc in doctors:
            if doc.specialty.lower() in msg_lower:
                state.specialty = doc.specialty
                state.doctor_id = doc.id
                state.doctor_name = doc.name
                break

    if not state.specialty:
        if any(w in msg_lower for w in ["heart", "cardio", "chest", "blood pressure"]):
            state.specialty = "Cardiology"
        elif any(w in msg_lower for w in ["skin", "derma", "rash", "acne", "mole"]):
            state.specialty = "Dermatology"
        elif any(w in msg_lower for w in ["child", "pediatric", "kid", "baby", "infant"]):
            state.specialty = "Pediatrics"
        elif any(w in msg_lower for w in ["headache", "migraine", "brain", "neuro"]):
            state.specialty = "Neurology"
        elif any(w in msg_lower for w in ["cough", "cold", "flu", "fever", "stomach", "general", "checkup", "physician"]):
            state.specialty = "General Practice"

    # Match slot selection
    # Check if user mentioned an exact slot ID or time (e.g. "Slot 14", "9:00 AM", "morning", "first one")
    available_slots = crud.get_available_slots(db=db, doctor_id=state.doctor_id)
    if state.specialty and not state.doctor_id:
        available_slots = [s for s in available_slots if s.doctor and state.specialty.lower() in s.doctor.specialty.lower()]

    slot_match = None
    numbers = re.findall(r"\b\d+\b", msg)
    if numbers:
        for num_str in numbers:
            cand_id = int(num_str)
            target = next((s for s in available_slots if s.id == cand_id), None)
            if target:
                slot_match = target
                break

    if not slot_match and available_slots:
        if "first" in msg_lower or "earliest" in msg_lower or "1st" in msg_lower:
            slot_match = available_slots[0]
        elif "second" in msg_lower or "2nd" in msg_lower and len(available_slots) > 1:
            slot_match = available_slots[1]
        elif "third" in msg_lower or "3rd" in msg_lower and len(available_slots) > 2:
            slot_match = available_slots[2]

    if slot_match:
        state.slot_id = slot_match.id
        state.slot_time_str = slot_match.start_time.strftime("%A, %B %d at %I:%M %p")
        if slot_match.doctor:
            state.doctor_name = slot_match.doctor.name
            state.specialty = slot_match.doctor.specialty
            state.doctor_id = slot_match.doctor.id

    # 2. Check if user is asking general informational questions
    if any(q in msg_lower for q in ["who are the doctors", "list doctors", "what doctors", "available doctors", "show doctors"]):
        doc_summaries = [f"{d.name} ({d.specialty} - {d.qualification})" for d in doctors]
        reply = (
            "Here are our available healthcare providers: " + "; ".join(doc_summaries) + ". "
            "Which doctor or specialty would you like to schedule an appointment with?"
        )
        return RetellChatResponse(ai_response=reply, next_state=state)

    if any(q in msg_lower for q in ["who is", "tell me about"]) and state.doctor_name:
        doc = next((d for d in doctors if d.id == state.doctor_id), None)
        if doc and doc.bio:
            return RetellChatResponse(
                ai_response=f"{doc.name} specializes in {doc.specialty} with credentials {doc.qualification}. {doc.bio} Would you like to check their open appointment times?",
                next_state=state
            )

    # 3. Check for Reference Code lookup (e.g. "My reference is MV-123456")
    ref_match = re.search(r"MV-[A-Z0-9]{6}", msg.upper())
    if ref_match:
        ref_code = ref_match.group(0)
        booking = crud.get_booking_by_reference(db=db, reference_code=ref_code)
        if booking:
            time_str = booking.slot.start_time.strftime("%A, %B %d at %I:%M %p")
            doc_str = booking.slot.doctor.name if booking.slot and booking.slot.doctor else "Doctor"
            return RetellChatResponse(
                ai_response=f"I found your booking {ref_code}! You are scheduled with {doc_str} on {time_str} (Status: {booking.status}). Would you like to keep or reschedule this?",
                next_state=state
            )

    # 4. Step Progression & Next Follow-Up Question
    # Check if we are ready to book (we have: slot_id, patient_name, phone, email)
    if state.slot_id and state.patient_name and state.patient_phone and state.patient_email:
        try:
            booking_in = schemas.BookingCreateRequest(
                slot_id=state.slot_id,
                patient_name=state.patient_name,
                patient_phone=state.patient_phone,
                patient_email=state.patient_email,
                reason_for_visit=state.reason or f"Appointment for {state.specialty or 'General Consultation'}"
            )
            booking = crud.create_booking(db=db, booking_data=booking_in)
            state.confirmed_reference = booking.reference_code
            state.step = "COMPLETED"

            final_reply = (
                f"You're all booked, {booking.patient_name}! "
                f"Your appointment with {state.doctor_name or 'your doctor'} on {state.slot_time_str} is officially confirmed. "
                f"Your reference confirmation code is {booking.reference_code}. "
                f"A full confirmation notice has been dispatched to {booking.patient_email}. "
                "Is there anything else I can assist you with today?"
            )
            return RetellChatResponse(
                ai_response=final_reply,
                next_state=state,
                booking_reference=booking.reference_code
            )
        except HTTPException as he:
            state.slot_id = None
            return RetellChatResponse(
                ai_response=f"Sorry, {he.detail} Let's pick another time that works for you.",
                next_state=state
            )

    # Missing Contact info (Phone or Email)
    if state.slot_id and state.patient_name:
        state.step = "COLLECT_CONTACT"
        missing = []
        if not state.patient_phone:
            missing.append("phone number")
        if not state.patient_email:
            missing.append("email address")
        return RetellChatResponse(
            ai_response=f"Thank you, {state.patient_name}. What is the best {' and '.join(missing)} for your confirmation notice?",
            next_state=state
        )

    # Missing Patient Name
    if state.slot_id and not state.patient_name:
        state.step = "COLLECT_NAME"
        return RetellChatResponse(
            ai_response=f"Perfect! I have held {state.slot_time_str} with {state.doctor_name}. May I have your full legal name for the patient record?",
            next_state=state
        )

    # Have Specialty/Doctor but Missing Slot selection
    if state.specialty or state.doctor_name:
        state.step = "SELECT_SLOT"
        slots_to_show = available_slots[:4]
        if not slots_to_show:
            return RetellChatResponse(
                ai_response=f"I checked with {state.doctor_name or state.specialty}, but there are currently no unbooked slots available. Would you like to check another provider or date?",
                next_state=state
            )

        slot_options_text = ", ".join([s.start_time.strftime("%A, %B %d at %I:%M %p") for s in slots_to_show[:3]])
        formatted_slots = [
            {
                "slot_id": s.id,
                "doctor_name": s.doctor.name if s.doctor else "Doctor",
                "start_time": s.start_time.isoformat(),
                "formatted_time": s.start_time.strftime("%A, %B %d at %I:%M %p")
            }
            for s in slots_to_show
        ]

        reply = (
            f"For {state.doctor_name or state.specialty}, upcoming openings are: {slot_options_text}. "
            "Which time slot works best for you, or do you prefer a specific morning or afternoon time?"
        )
        return RetellChatResponse(
            ai_response=reply,
            next_state=state,
            available_slots=formatted_slots
        )

    # Initial or Fallback: Ask for Specialty or Symptoms
    state.step = "COLLECT_SPECIALTY"
    specs_list = sorted(list({d.specialty for d in doctors if d.specialty}))
    specs_str = ", ".join(specs_list) if specs_list else "Cardiology, Dermatology, Pediatrics, and General Practice"
    
    # Context-aware response instead of static repetition
    if any(g in msg_lower for g in ["hi", "hello", "hey", "good morning", "good evening"]):
        greeting_reply = (
            f"Hello! I am your MediVoice AI appointment assistant. "
            f"I can help schedule you directly with our specialists in {specs_str}. "
            "What medical specialty or symptoms are you looking for today?"
        )
    else:
        greeting_reply = (
            f"I can certainly help you book that. "
            f"Could you tell me what medical specialty or symptoms you are experiencing? "
            f"We have doctors available in {specs_str}."
        )

    return RetellChatResponse(ai_response=greeting_reply, next_state=state)
