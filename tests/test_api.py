from fastapi.testclient import TestClient

from app.api.main import app


client = TestClient(app)


def test_root_returns_service_metadata():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "name": "Hubstar AI",
        "status": "ok",
        "docs": "/docs",
    }


def test_health_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_swagger_docs_are_available():
    response = client.get("/docs")

    assert response.status_code == 200
    assert "swagger-ui" in response.text.lower()
