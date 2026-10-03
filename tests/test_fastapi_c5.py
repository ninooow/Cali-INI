import pytest
from fastapi.testclient import TestClient
from datetime import datetime

from fastapi_app import app
from database import SessionLocal, init_db
from models.core import Asset

client = TestClient(app)

@pytest.fixture(scope="function")
def db_session():
    # Ensure fresh DB for each test
    init_db()
    session = SessionLocal()
    yield session
    session.close()

def create_asset(session, tag="TEST-001"):
    asset = Asset(
        tag_number=tag,
        asset_name=tag,
        plant_code="PL01",
        equipment_type="Pump",
        equipment_class="ClassA",
        discipline="Mechanical",
        criticality="HIGH",
        core_mode="hourly",
        fla_amp=100.0,
        is_active=True,
    )
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return asset

def test_ticket_lifecycle(db_session):
    asset = create_asset(db_session)
    resp = client.get("/api/v1/workflow/tickets")
    assert resp.status_code == 200
    assert resp.json()["data"] == []
    ticket_payload = {
        "ticket_id": "TICKET-001",
        "asset_id": asset.asset_id,
        "opened_at": datetime.utcnow().isoformat(),
        "condition_state": "NORMAL",
        "priority": "MEDIUM",
        "owner_role": "Operator",
        "ticket_state": "OPEN",
        "action_status": "NOT_STARTED",
        "normal_streak": 0,
    }
    resp = client.post("/api/v1/workflow/tickets", json=ticket_payload)
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data[0]["ticket_id"] == "TICKET-001"
    resp = client.get(f"/api/v1/workflow/tickets/{ticket_payload['ticket_id']}")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["ticket_id"] == "TICKET-001"
    assert detail["ticket_state"] == "OPEN"
    update_payload = {
        "ticket_state": "IN_PROGRESS",
        "operator_comment": "Checked valve",
        "operator_decision": "MONITOR",
        "last_operator_name": "John Doe",
    }
    resp = client.patch(f"/api/v1/workflow/tickets/{ticket_payload['ticket_id']}", json=update_payload)
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["ticket_state"] == "IN_PROGRESS"
    assert updated["operator_comment"] == "Checked valve"
    assert updated["operator_decision"] == "MONITOR"
    resp = client.get(f"/api/v1/workflow/tickets/{ticket_payload['ticket_id']}/audit_logs")
    assert resp.status_code == 200
    logs = resp.json()["data"]
    assert any(log["new_ticket_state"] == "IN_PROGRESS" for log in logs)
