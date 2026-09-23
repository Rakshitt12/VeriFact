"""Unit and integration tests for Part 1 - Backend Foundation."""

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.config.settings import settings


@pytest.fixture
def client():
    """Test client fixture."""
    return TestClient(app)


def test_root_endpoint(client):
    """Test root endpoint returns online status and app name."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["name"] == settings.APP_NAME


def test_health_check_endpoint(client):
    """Test /api/health endpoint."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app_name"] == settings.APP_NAME
    assert data["environment"] == settings.APP_ENV


def test_config_endpoint(client):
    """Test /api/config endpoint returns scoring weights and thresholds."""
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "scoring_weights" in data
    assert "classification_thresholds" in data
    assert sum(data["scoring_weights"].values()) == pytest.approx(1.0)
    assert data["classification_thresholds"]["strongly_supported"] == 90


def test_analyze_endpoint_valid_text(client):
    """Test /api/analyze with valid text input."""
    payload = {
        "input_type": "text",
        "content": "The central government announced a 10 rupee reduction in petrol prices."
    }
    response = client.post("/api/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "request_id" in data
    assert data["input_type"] == "text"
    assert len(data["claims"]) == 1
    assert data["overall_classification"] == "INSUFFICIENT EVIDENCE"
    assert len(data["limitations"]) > 0


def test_analyze_endpoint_valid_url(client, monkeypatch):
    """Test /api/analyze with valid URL input."""
    from backend.ingestion.models import NormalizedArticle
    
    mock_article = NormalizedArticle(
        source_type="url",
        original_input="https://www.example.com/news/petrol-price-cut-announced",
        url="https://www.example.com/news/petrol-price-cut-announced",
        canonical_url="https://www.example.com/news/petrol-price-cut-announced",
        title="Petrol Price Cut Announced",
        body="The government has announced a reduction in petrol prices across all states.",
        publisher="Example News",
        author="Jane Reporter",
        published_at="2026-09-23T10:00:00Z",
        domain="example.com",
        description="A major fuel rate change announced today.",
        extraction_method="mocked_extraction"
    )
    monkeypatch.setattr("backend.api.routes.ingest_input", lambda input_type, content: mock_article)

    payload = {
        "input_type": "url",
        "content": "https://www.example.com/news/petrol-price-cut-announced"
    }
    response = client.post("/api/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["input_type"] == "url"
    assert data["input_summary"]["url"] == payload["content"]
    assert data["input_summary"]["title"] == "Petrol Price Cut Announced"



def test_verify_alias_endpoint(client):
    """Test /api/verify behaves identically to /api/analyze."""
    payload = {
        "input_type": "text",
        "content": "The central government announced a 10 rupee reduction in petrol prices."
    }
    response = client.post("/api/verify", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "request_id" in data
    assert data["overall_classification"] == "INSUFFICIENT EVIDENCE"


def test_analyze_endpoint_too_short(client):
    """Test input shorter than minimum length returns 400."""
    payload = {
        "input_type": "text",
        "content": "Too short"
    }
    response = client.post("/api/analyze", json=payload)
    assert response.status_code == 400
    assert "too short" in response.json()["detail"].lower()


def test_analyze_endpoint_invalid_input_type(client):
    """Test unsupported input_type returns 422."""
    payload = {
        "input_type": "invalid_type",
        "content": "Valid length content that should fail on input type."
    }
    response = client.post("/api/analyze", json=payload)
    assert response.status_code == 422
    assert response.json()["error"] == "VALIDATION_ERROR"
