# Tests for the FastAPI REST API.

import pytest
from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)


def test_root():
    """Root endpoint serves the QC Overview HTML page."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert b"ARIA" in resp.content


def test_health():
    """Health check must return ok."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_summary():
    """Summary must return total_records."""
    resp = client.get("/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_records" in data
    assert data["total_records"] > 0


def test_qc_status():
    """QC status endpoint must return a list."""
    resp = client.get("/qc/status")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
