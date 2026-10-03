import pytest
from fastapi.testclient import TestClient
from fastapi_app import app, init_db
from database import Base, engine

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    # Recreate tables for a clean test environment
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    init_db()
    yield
    Base.metadata.drop_all(bind=engine)

client = TestClient(app)

def test_list_incidents_initially_empty():
    resp = client.get("/api/v1/reliability/incidents")
    assert resp.status_code == 200
    assert resp.json()["data"] == []

def test_create_and_retrieve_incident():
    payload = [{
        "ar_no": "AR-001",
        "plant": "PlantA",
        "risk_score": 5.0,
        "source_type": "MANUAL"
    }]
    create_resp = client.post("/api/v1/reliability/incidents", json=payload)
    assert create_resp.status_code == 201
    created = create_resp.json()["data"]
    assert len(created) == 1
    incident_id = created[0]["incident_id"]
    get_resp = client.get(f"/api/v1/reliability/incidents/{incident_id}")
    assert get_resp.status_code == 200
    incident = get_resp.json()
    assert incident["ar_no"] == "AR-001"
    assert incident["plant"] == "PlantA"
