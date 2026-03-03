"""API integration tests using FastAPI TestClient."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True, scope="session")
def ensure_db():
    """Ensure the test database is generated before any API tests run."""
    import os
    db_path = os.path.join(os.path.dirname(__file__), "..", "data", "physio.db")
    if not os.path.exists(db_path):
        from app.synthetic.mock_engine import build_database
        build_database(db_path=db_path, n_patients=50, seed=42)
    yield


class TestListPatients:
    def test_returns_50_patients(self):
        resp = client.get("/api/patients")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 50

    def test_each_patient_has_risk_level(self):
        resp = client.get("/api/patients")
        data = resp.json()
        for p in data:
            assert "risk_level" in p
            assert p["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    def test_each_patient_has_dhs_score(self):
        resp = client.get("/api/patients")
        data = resp.json()
        for p in data:
            assert "dhs_score" in p
            assert isinstance(p["dhs_score"], float)

    def test_each_patient_has_name(self):
        resp = client.get("/api/patients")
        data = resp.json()
        for p in data:
            assert "name" in p
            assert len(p["name"]) > 0


class TestGetPatient:
    def test_patient_detail_returns_history(self):
        resp = client.get("/api/patients/1")
        assert resp.status_code == 200
        data = resp.json()
        assert "history" in data
        assert len(data["history"]) == 7

    def test_history_has_correct_fields(self):
        resp = client.get("/api/patients/1")
        data = resp.json()
        for record in data["history"]:
            assert "dhs_score" in record
            assert "news2_score" in record
            assert "risk_level" in record

    def test_nonexistent_patient_returns_404(self):
        resp = client.get("/api/patients/9999")
        assert resp.status_code == 404

    def test_patient_has_ward(self):
        resp = client.get("/api/patients/1")
        data = resp.json()
        assert "ward" in data
        assert len(data["ward"]) > 0


class TestCalculateDHS:
    def test_high_risk_payload_returns_critical(self):
        resp = client.post("/api/calculate-dhs", json={
            "respiratory_rate": 28.0,
            "spo2": 88.0,
            "systolic_bp": 88.0,
            "heart_rate": 128.0,
            "temperature": 38.5,
            "clinical_note": "acutely distressed, diaphoretic",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["risk_level"] in ("HIGH", "CRITICAL")

    def test_negative_note_triggers_alert(self):
        resp = client.post("/api/calculate-dhs", json={
            "respiratory_rate": 16.0,
            "spo2": 97.0,
            "systolic_bp": 120.0,
            "heart_rate": 72.0,
            "temperature": 37.0,
            "clinical_note": "confused, agitated, laboured breathing",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["alert_triggered"] is True

    def test_stable_patient_no_alert(self):
        resp = client.post("/api/calculate-dhs", json={
            "respiratory_rate": 16.0,
            "spo2": 98.0,
            "systolic_bp": 122.0,
            "heart_rate": 72.0,
            "temperature": 37.0,
            "clinical_note": "alert and oriented, tolerating diet well",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["alert_triggered"] is False
        assert data["risk_level"] == "LOW"

    def test_response_has_breakdown(self):
        resp = client.post("/api/calculate-dhs", json={
            "respiratory_rate": 16.0,
            "spo2": 97.0,
            "systolic_bp": 120.0,
            "heart_rate": 72.0,
            "temperature": 37.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "breakdown" in data
        assert "rr_score" in data["breakdown"]

    def test_invalid_payload_returns_422(self):
        resp = client.post("/api/calculate-dhs", json={"invalid": "data"})
        assert resp.status_code == 422

    def test_default_consciousness_is_alert(self):
        resp = client.post("/api/calculate-dhs", json={
            "respiratory_rate": 16.0,
            "spo2": 98.0,
            "systolic_bp": 120.0,
            "heart_rate": 72.0,
            "temperature": 37.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["breakdown"]["consciousness_score"] == 0


class TestStats:
    def test_stats_returns_active_alerts_int(self):
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "active_alerts" in data
        assert isinstance(data["active_alerts"], int)
        assert data["active_alerts"] >= 0

    def test_stats_has_risk_distribution(self):
        resp = client.get("/api/stats")
        data = resp.json()
        assert "risk_distribution" in data
        assert isinstance(data["risk_distribution"], dict)

    def test_stats_has_total_patients(self):
        resp = client.get("/api/stats")
        data = resp.json()
        assert "total_patients" in data
        assert data["total_patients"] == 50

    def test_stats_has_avg_dhs(self):
        resp = client.get("/api/stats")
        data = resp.json()
        assert "avg_dhs_score" in data
        assert isinstance(data["avg_dhs_score"], float)


class TestDashboard:
    def test_root_returns_html(self):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
