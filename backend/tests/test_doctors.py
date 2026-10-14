from fastapi.testclient import TestClient


def test_list_doctors_empty(client: TestClient):
    """When no doctors are seeded, return an empty list with 200 OK."""
    response = client.get("/api/doctors")
    assert response.status_code == 200
    assert response.json() == []


def test_list_doctors_with_data(client: TestClient, sample_doctor):
    """List doctors returns registered doctors."""
    response = client.get("/api/doctors")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Dr. Jane Watson"
    assert data[0]["specialty"] == "Neurology"


def test_filter_doctors_by_specialty(client: TestClient, sample_doctor):
    """Filtering by matching and non-matching specialty."""
    # Match
    res_match = client.get("/api/doctors?specialty=neuro")
    assert res_match.status_code == 200
    assert len(res_match.json()) == 1

    # No match
    res_no_match = client.get("/api/doctors?specialty=cardio")
    assert res_no_match.status_code == 200
    assert len(res_no_match.json()) == 0


def test_get_doctor_by_id(client: TestClient, sample_doctor):
    """Retrieve doctor by primary key."""
    response = client.get(f"/api/doctors/{sample_doctor.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == sample_doctor.id
    assert data["qualification"] == "MD, PhD"


def test_get_doctor_not_found(client: TestClient):
    """Requesting non-existent doctor returns 404."""
    response = client.get("/api/doctors/9999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
