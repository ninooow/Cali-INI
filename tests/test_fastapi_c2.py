import pytest
from fastapi.testclient import TestClient
from fastapi_app import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_system_endpoint():
    response = client.get("/system")
    assert response.status_code == 200
    json = response.json()
    assert json["status"] == "healthy"
    assert json["database"] in ("connected", "error")

def test_asset_list_endpoint():
    response = client.get(f"{app.settings.API_V1_PREFIX}/assets")
    assert response.status_code == 200
    data = response.json().get("data")
    assert isinstance(data, list)

def test_create_hourly_missing_asset():
    payload = [{"asset_id": 9999, "measured_at": "2023-01-01T00:00:00"}]
    response = client.post(f"{app.settings.API_V1_PREFIX}/telemetry/hourly", json=payload)
    assert response.status_code == 400
    assert "Asset(s) not found" in response.json().get("detail", "")
