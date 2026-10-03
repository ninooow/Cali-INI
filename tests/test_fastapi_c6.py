import pytest
from fastapi.testclient import TestClient
from datetime import datetime

from fastapi_app import app
from database import SessionLocal, init_db

client = TestClient(app)

@pytest.fixture(scope="function")
def db_session():
    # Ensure fresh DB for each test
    init_db()
    session = SessionLocal()
    yield session
    session.close()

def test_user_crud(db_session):
    # Initially, list users should be empty
    resp = client.get("/api/v1/users")
    assert resp.status_code == 200
    assert resp.json()["data"] == []

    # Create a new user
    user_payload = {
        "username": "jdoe",
        "display_name": "John Doe",
        "email": "jdoe@example.com",
        "employee_id": "E123",
        "role": "operator",
        "discipline": "mechanical",
        "is_active": True,
    }
    resp = client.post("/api/v1/users", json=user_payload)
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data[0]["username"] == "jdoe"
    user_id = data[0]["user_id"]

    # Retrieve the created user
    resp = client.get(f"/api/v1/users/{user_id}")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["username"] == "jdoe"
    assert detail["display_name"] == "John Doe"

    # Update the user
    update_payload = {
        "display_name": "John D.",
        "email": "john.d@example.com",
        "is_active": False,
    }
    resp = client.patch(f"/api/v1/users/{user_id}", json=update_payload)
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["display_name"] == "John D."
    assert updated["email"] == "john.d@example.com"
    assert updated["is_active"] is False
