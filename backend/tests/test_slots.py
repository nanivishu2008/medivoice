from fastapi.testclient import TestClient


def test_list_available_slots(client: TestClient, sample_slot):
    """Available slot should be retrieved."""
    response = client.get("/api/slots")
    assert response.status_code == 200
    slots = response.json()
    assert len(slots) >= 1
    target = next((s for s in slots if s["id"] == sample_slot.id), None)
    assert target is not None
    assert target["is_booked"] is False
    assert target["doctor"]["name"] == "Dr. Jane Watson"


def test_filter_slots_by_doctor(client: TestClient, sample_doctor, sample_slot):
    """Slots can be filtered by doctor ID."""
    # Existing doctor
    res = client.get(f"/api/slots?doctor_id={sample_doctor.id}")
    assert res.status_code == 200
    assert len(res.json()) >= 1

    # Non-existent doctor
    res_empty = client.get("/api/slots?doctor_id=99999")
    assert res_empty.status_code == 200
    assert len(res_empty.json()) == 0


def test_get_slot_by_id(client: TestClient, sample_slot):
    """Retrieve slot by ID."""
    response = client.get(f"/api/slots/{sample_slot.id}")
    assert response.status_code == 200
    assert response.json()["id"] == sample_slot.id


def test_get_slot_not_found(client: TestClient):
    """Querying non-existent slot returns 404."""
    response = client.get("/api/slots/88888")
    assert response.status_code == 404
