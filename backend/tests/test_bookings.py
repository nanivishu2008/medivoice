from fastapi.testclient import TestClient


def test_create_booking_success(client: TestClient, sample_slot):
    """Booking a valid, available slot succeeds and marks slot as booked."""
    payload = {
        "slot_id": sample_slot.id,
        "patient_name": "Eleanor Vance",
        "patient_phone": "+1-555-0143",
        "patient_email": "eleanor.vance@example.com",
        "reason_for_visit": "Persistent migraine symptoms"
    }

    response = client.post("/api/bookings", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "CONFIRMED"
    assert data["patient_name"] == "Eleanor Vance"
    assert data["slot"]["id"] == sample_slot.id
    assert data["slot"]["is_booked"] is True
    assert "reference_code" in data
    assert data["reference_code"].startswith("MV-")


def test_prevent_double_booking_same_slot(client: TestClient, sample_slot):
    """
    CRITICAL REQUIREMENT:
    Prevent two requests from successfully booking the same appointment slot.
    The first request must succeed (201); the second must fail with 409 Conflict.
    """
    payload_1 = {
        "slot_id": sample_slot.id,
        "patient_name": "Patient Alpha",
        "patient_phone": "555-0101",
        "patient_email": "alpha@example.com",
        "reason_for_visit": "First booking attempt"
    }

    payload_2 = {
        "slot_id": sample_slot.id,
        "patient_name": "Patient Beta",
        "patient_phone": "555-0102",
        "patient_email": "beta@example.com",
        "reason_for_visit": "Second booking attempt on same slot"
    }

    # First attempt: succeeds
    res_1 = client.post("/api/bookings", json=payload_1)
    assert res_1.status_code == 201
    assert res_1.json()["patient_name"] == "Patient Alpha"

    # Second attempt on the exact same slot: rejected
    res_2 = client.post("/api/bookings", json=payload_2)
    assert res_2.status_code == 409
    error_msg = res_2.json()["detail"].lower()
    assert "already been reserved" in error_msg or "conflict" in error_msg


def test_booking_validation_errors(client: TestClient, sample_slot):
    """Input validation enforces valid emails, required fields, and lengths."""
    # Invalid email
    bad_email_payload = {
        "slot_id": sample_slot.id,
        "patient_name": "John Doe",
        "patient_phone": "555-0123",
        "patient_email": "not-an-email",
        "reason_for_visit": "Checkup"
    }
    res = client.post("/api/bookings", json=bad_email_payload)
    assert res.status_code == 422

    # Missing patient name
    missing_name_payload = {
        "slot_id": sample_slot.id,
        "patient_phone": "555-0123",
        "patient_email": "john@example.com"
    }
    res_missing = client.post("/api/bookings", json=missing_name_payload)
    assert res_missing.status_code == 422


def test_booking_nonexistent_slot(client: TestClient):
    """Attempting to book a slot that does not exist returns 404."""
    payload = {
        "slot_id": 999999,
        "patient_name": "Ghost Patient",
        "patient_phone": "555-0000",
        "patient_email": "ghost@example.com"
    }
    res = client.post("/api/bookings", json=payload)
    assert res.status_code == 404
    assert "does not exist" in res.json()["detail"].lower()


def test_lookup_booking_by_reference(client: TestClient, sample_slot):
    """Bookings can be retrieved using their unique reference code."""
    payload = {
        "slot_id": sample_slot.id,
        "patient_name": "Sarah Connor",
        "patient_phone": "555-0199",
        "patient_email": "sconnor@example.com"
    }
    create_res = client.post("/api/bookings", json=payload)
    ref_code = create_res.json()["reference_code"]

    get_res = client.get(f"/api/bookings/{ref_code}")
    assert get_res.status_code == 200
    assert get_res.json()["reference_code"] == ref_code
    assert get_res.json()["patient_name"] == "Sarah Connor"


def test_cancel_booking_releases_slot(client: TestClient, sample_slot):
    """Cancelling a booking marks status as CANCELLED and frees up the slot."""
    payload = {
        "slot_id": sample_slot.id,
        "patient_name": "Kyle Reese",
        "patient_phone": "555-0188",
        "patient_email": "kreese@example.com"
    }
    create_res = client.post("/api/bookings", json=payload)
    ref_code = create_res.json()["reference_code"]

    # Cancel the booking
    cancel_res = client.post(f"/api/bookings/{ref_code}/cancel")
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "CANCELLED"

    # Verify slot is available again
    slot_res = client.get(f"/api/slots/{sample_slot.id}")
    assert slot_res.status_code == 200
    assert slot_res.json()["is_booked"] is False
