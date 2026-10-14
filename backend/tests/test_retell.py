from fastapi.testclient import TestClient


def test_retell_check_availability(client: TestClient, sample_slot):
    """Voice AI custom function returns available slots and spoken summary."""
    payload = {
        "specialty": "Neurology"
    }
    res = client.post("/api/retell/check-availability", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["count"] >= 1
    assert "slots" in data
    assert "works best for you" in data["message"].lower()


def test_retell_book_appointment(client: TestClient, sample_slot):
    """Voice AI custom function books appointment and produces spoken confirmation."""
    payload = {
        "slot_id": sample_slot.id,
        "patient_name": "Maya Lin",
        "patient_phone": "+1-555-0987",
        "patient_email": "maya.lin@example.com",
        "reason_for_visit": "Frequent headaches"
    }
    res = client.post("/api/retell/book-appointment", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "MV-" in data["reference_code"]
    assert "confirmed" in data["spoken_confirmation"].lower()


def test_retell_lookup_booking(client: TestClient, sample_slot):
    """Voice AI looks up existing appointment by reference code."""
    # First create a booking
    book_res = client.post("/api/retell/book-appointment", json={
        "slot_id": sample_slot.id,
        "patient_name": "David Copperfield",
        "patient_phone": "555-9988",
        "patient_email": "david@example.com"
    })
    ref_code = book_res.json()["reference_code"]

    # Lookup
    lookup_res = client.post("/api/retell/lookup-booking", json={"reference_code": ref_code})
    assert lookup_res.status_code == 200
    assert lookup_res.json()["success"] is True
    assert lookup_res.json()["status"] == "CONFIRMED"


def test_retell_multi_turn_chat_flow(client: TestClient, sample_slot):
    """
    Simulates the AI assistant conducting a conversational questionnaire with the patient:
    Turn 1: Greeting & asks for medical specialty
    Turn 2: Patient mentions symptoms/specialty -> AI presents slots
    Turn 3: Patient selects slot -> AI asks for full name
    Turn 4: Patient gives name -> AI asks for contact info
    Turn 5: Patient gives contact info -> AI completes booking and returns confirmation code!
    """
    # Turn 1: Greeting
    t1 = client.post("/api/retell/chat", json={"user_message": "Hello"})
    assert t1.status_code == 200
    d1 = t1.json()
    assert d1["next_state"]["step"] == "COLLECT_SPECIALTY"
    assert "what medical specialty" in d1["ai_response"].lower()

    # Turn 2: User provides specialty
    t2 = client.post("/api/retell/chat", json={
        "user_message": "I need help with my migraines and neurology",
        "state": d1["next_state"]
    })
    assert t2.status_code == 200
    d2 = t2.json()
    assert d2["next_state"]["step"] == "SELECT_SLOT"
    assert "which time slot" in d2["ai_response"].lower()

    # Turn 3: User selects slot
    t3 = client.post("/api/retell/chat", json={
        "user_message": f"Slot {sample_slot.id}",
        "state": d2["next_state"]
    })
    assert t3.status_code == 200
    d3 = t3.json()
    assert d3["next_state"]["step"] == "COLLECT_NAME"
    assert "full legal name" in d3["ai_response"].lower()

    # Turn 4: User gives name
    t4 = client.post("/api/retell/chat", json={
        "user_message": "My name is Samantha Reed",
        "state": d3["next_state"]
    })
    assert t4.status_code == 200
    d4 = t4.json()
    assert d4["next_state"]["step"] == "COLLECT_CONTACT"
    assert "phone number and email" in d4["ai_response"].lower()

    # Turn 5: User gives contact details
    t5 = client.post("/api/retell/chat", json={
        "user_message": "Call me at 555-4321 and email is samantha.reed@example.com",
        "state": d4["next_state"]
    })
    assert t5.status_code == 200
    d5 = t5.json()
    assert d5["next_state"]["step"] == "COMPLETED"
    assert "officially confirmed" in d5["ai_response"].lower()
    assert d5["booking_reference"].startswith("MV-")
