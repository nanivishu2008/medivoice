import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from ..database import get_db
from .. import crud, models, schemas

router = APIRouter(prefix="/api/retell", tags=["Retell Voice AI Integration"])


# ==========================================
# Request & Response Schemas
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
    step: str = "COLLECT_SPECIALTY"
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
    api_key: Optional[str] = None


class RetellChatResponse(BaseModel):
    ai_response: str
    next_state: RetellConversationState
    available_slots: Optional[List[Dict[str, Any]]] = None
    booking_reference: Optional[str] = None
    powered_by: str = "built-in"  # "gemini" or "built-in"


# ==========================================
# 1. Voice AI Custom Functions for Retell
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
# Gemini LLM Integration with Function Calling
# ==========================================
GEMINI_TOOLS = [
    {
        "function_declarations": [
            {
                "name": "get_doctors",
                "description": "List registered doctors and their medical specialties, qualifications, and bios.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "specialty": {"type": "STRING", "description": "Optional specialty filter"}
                    }
                }
            },
            {
                "name": "get_available_slots",
                "description": "Query available upcoming unbooked appointment slots for a doctor or specialty.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "doctor_id": {"type": "INTEGER", "description": "Doctor ID"},
                        "specialty": {"type": "STRING", "description": "Specialty name"}
                    }
                }
            },
            {
                "name": "book_appointment",
                "description": "Atomically books an appointment slot in the database for the patient.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "slot_id": {"type": "INTEGER", "description": "Slot ID to reserve"},
                        "patient_name": {"type": "STRING", "description": "Patient's full legal name"},
                        "patient_phone": {"type": "STRING", "description": "Contact phone number"},
                        "patient_email": {"type": "STRING", "description": "Email address for confirmation"},
                        "reason_for_visit": {"type": "STRING", "description": "Symptoms or reason for visit"}
                    },
                    "required": ["slot_id", "patient_name", "patient_phone", "patient_email"]
                }
            },
            {
                "name": "lookup_booking",
                "description": "Look up an existing appointment by reference code.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "reference_code": {"type": "STRING", "description": "Reference code (e.g. MV-4A7F2B)"}
                    },
                    "required": ["reference_code"]
                }
            }
        ]
    }
]


def execute_gemini_tool(func_name: str, args: Dict[str, Any], db: Session) -> Dict[str, Any]:
    if func_name == "get_doctors":
        docs = crud.get_doctors(db, specialty=args.get("specialty"))
        return {
            "doctors": [
                {"id": d.id, "name": d.name, "specialty": d.specialty, "qualification": d.qualification, "bio": d.bio}
                for d in docs
            ]
        }
    elif func_name == "get_available_slots":
        slots = crud.get_available_slots(db, doctor_id=args.get("doctor_id"))
        spec = args.get("specialty")
        if spec:
            slots = [s for s in slots if s.doctor and spec.lower() in s.doctor.specialty.lower()]
        return {
            "slots": [
                {
                    "slot_id": s.id,
                    "doctor_name": s.doctor.name if s.doctor else "Doctor",
                    "specialty": s.doctor.specialty if s.doctor else "General",
                    "formatted_time": s.start_time.strftime("%A, %B %d at %I:%M %p")
                }
                for s in slots[:5]
            ]
        }
    elif func_name == "book_appointment":
        try:
            booking_in = schemas.BookingCreateRequest(
                slot_id=args["slot_id"],
                patient_name=args["patient_name"],
                patient_phone=args["patient_phone"],
                patient_email=args["patient_email"],
                reason_for_visit=args.get("reason_for_visit")
            )
            b = crud.create_booking(db, booking_in)
            return {
                "success": True,
                "booking_id": b.id,
                "reference_code": b.reference_code,
                "patient_name": b.patient_name,
                "appointment_time": b.slot.start_time.strftime("%A, %B %d at %I:%M %p"),
                "doctor_name": b.slot.doctor.name if b.slot and b.slot.doctor else "Doctor"
            }
        except HTTPException as he:
            return {"success": False, "error": he.detail}
        except Exception as e:
            return {"success": False, "error": str(e)}
    elif func_name == "lookup_booking":
        b = crud.get_booking_by_reference(db, reference_code=args["reference_code"])
        if not b:
            return {"found": False}
        return {
            "found": True,
            "reference_code": b.reference_code,
            "patient_name": b.patient_name,
            "status": b.status,
            "appointment_time": b.slot.start_time.strftime("%A, %B %d at %I:%M %p"),
            "doctor_name": b.slot.doctor.name if b.slot and b.slot.doctor else "Doctor"
        }
    return {"error": f"Unknown tool {func_name}"}


async def call_gemini_api(
    user_msg: str,
    history: List[Dict[str, str]],
    api_key: str,
    db: Session
) -> Optional[Dict[str, Any]]:
    """Calls Google Gemini with multi-turn chat history and database tools."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"

    # Build contents from history
    contents = []
    for h in (history or []):
        role = "user" if h.get("role") == "user" else "model"
        contents.append({"role": role, "parts": [{"text": h.get("content", "")}]})
    contents.append({"role": "user", "parts": [{"text": user_msg}]})

    system_text = (
        "You are MediVoice AI, a warm, professional healthcare appointment scheduling voice assistant. "
        "You are conversing with a patient. "
        "Guidelines:\n"
        "1. Have a natural, empathetic conversation like an expert medical receptionist.\n"
        "2. REMEMBER every detail the patient provides throughout the chat (name, symptoms, doctor, times, phone, email).\n"
        "3. Never ask for information the patient already provided.\n"
        "4. Use your tools (get_doctors, get_available_slots, book_appointment) to check real availability and book slots.\n"
        "5. When scheduling: gather (specialty or doctor preference), then present open slots, get patient choice, then gather full name, phone number, and email. When all are present, immediately call 'book_appointment'.\n"
        "6. Keep spoken responses concise and friendly (2-3 sentences), ideal for voice playback."
    )

    payload = {
        "system_instruction": {"parts": [{"text": system_text}]},
        "contents": contents,
        "tools": GEMINI_TOOLS
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                print("Gemini API error:", resp.status_code, resp.text)
                return None

            data = resp.json()
            candidate = data.get("candidates", [{}])[0]
            content = candidate.get("content", {})
            parts = content.get("parts", [])

            # Check if Gemini called a tool
            tool_call = None
            text_reply = ""
            for p in parts:
                if "functionCall" in p:
                    tool_call = p["functionCall"]
                elif "text" in p:
                    text_reply += p["text"]

            booking_ref = None
            if tool_call:
                tool_name = tool_call.get("name")
                tool_args = tool_call.get("args", {})
                tool_result = execute_gemini_tool(tool_name, tool_args, db)

                if tool_name == "book_appointment" and tool_result.get("success"):
                    booking_ref = tool_result.get("reference_code")

                # Send tool result back to Gemini for final spoken response
                contents.append(content)
                contents.append({
                    "role": "function",
                    "parts": [{"functionResponse": {"name": tool_name, "response": tool_result}}]
                })

                followup_payload = {
                    "system_instruction": {"parts": [{"text": system_text}]},
                    "contents": contents,
                    "tools": GEMINI_TOOLS
                }
                followup_resp = await client.post(url, json=followup_payload)
                if followup_resp.status_code == 200:
                    f_data = followup_resp.json()
                    f_cand = f_data.get("candidates", [{}])[0]
                    f_parts = f_cand.get("content", {}).get("parts", [])
                    final_text = "".join([p.get("text", "") for p in f_parts])
                    return {
                        "text": final_text or text_reply,
                        "booking_reference": booking_ref
                    }

            if text_reply:
                return {
                    "text": text_reply,
                    "booking_reference": booking_ref
                }

    except Exception as e:
        print("Gemini call failed:", str(e))
        return None

    return None


# ==========================================
# Built-in Conversational Memory & Extraction Engine
# ==========================================
def extract_email(text: str) -> Optional[str]:
    m = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)
    return m.group(0).lower() if m else None


def extract_phone(text: str) -> Optional[str]:
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
            cleaned = re.split(r"[,.!?\n]|and |phone|email", raw, flags=re.IGNORECASE)[0].strip()
            if len(cleaned) >= 2:
                return cleaned.title()

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
async def retell_chat_conversation(
    req: RetellChatRequest,
    db: Session = Depends(get_db)
):
    """
    Intelligent conversational voice assistant with Gemini AI capability
    and built-in conversational memory across all dialogue turns.
    """
    msg = req.user_message.strip()
    msg_lower = msg.lower()
    state = req.state.model_copy() if req.state else RetellConversationState()
    doctors = crud.get_doctors(db=db)

    # 1. Check if Gemini API Key is available
    api_key = req.api_key or os.getenv("GEMINI_API_KEY")
    if api_key and api_key.strip():
        gemini_result = await call_gemini_api(msg, req.history or [], api_key.strip(), db)
        if gemini_result and gemini_result.get("text"):
            return RetellChatResponse(
                ai_response=gemini_result["text"],
                next_state=state,
                booking_reference=gemini_result.get("booking_reference"),
                powered_by="gemini"
            )

    # 2. Built-in Entity Memory Tracker (Remembers details across all turns)
    email_found = extract_email(msg)
    if email_found:
        state.patient_email = email_found

    phone_found = extract_phone(msg)
    if phone_found:
        state.patient_phone = phone_found

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
        if any(w in msg_lower for w in ["first", "earliest", "1st"]):
            slot_match = available_slots[0]
        elif any(w in msg_lower for w in ["second", "2nd"]) and len(available_slots) > 1:
            slot_match = available_slots[1]
        elif any(w in msg_lower for w in ["third", "3rd"]) and len(available_slots) > 2:
            slot_match = available_slots[2]

    if slot_match:
        state.slot_id = slot_match.id
        state.slot_time_str = slot_match.start_time.strftime("%A, %B %d at %I:%M %p")
        if slot_match.doctor:
            state.doctor_name = slot_match.doctor.name
            state.specialty = slot_match.doctor.specialty
            state.doctor_id = slot_match.doctor.id

    # 3. Informational inquiries
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

    # 4. Check for Reference Code lookup
    ref_match = re.search(r"MV-[A-Z0-9]{6}", msg.upper())
    if ref_match:
        ref_code = ref_match.group(0)
        booking = crud.get_booking_by_reference(db=db, reference_code=ref_code)
        if booking:
            time_str = booking.slot.start_time.strftime("%A, %B %d at %I:%M %p")
            doc_str = booking.slot.doctor.name if booking.slot and booking.slot.doctor else "Doctor"
            return RetellChatResponse(
                ai_response=f"I found your booking {ref_code}! You are scheduled with {doc_str} on {time_str} (Status: {booking.status}).",
                next_state=state
            )

    # 5. Progressive Follow-Up & Dynamic Booking
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
                f"A full confirmation notice has been dispatched to {booking.patient_email}."
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

    # Missing Contact info
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
            ai_response=f"Perfect! I have held {state.slot_time_str} with {state.doctor_name}. May I have your full legal name please?",
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

    # Initial or Fallback
    state.step = "COLLECT_SPECIALTY"
    specs_list = sorted(list({d.specialty for d in doctors if d.specialty}))
    specs_str = ", ".join(specs_list) if specs_list else "Cardiology, Dermatology, Pediatrics, and General Practice"

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
