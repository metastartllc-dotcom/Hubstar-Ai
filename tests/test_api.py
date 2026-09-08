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


def test_health_allows_configured_frontend_origins():
    for origin in ("http://127.0.0.1:3000", "http://localhost:3000"):
        response = client.get("/health", headers={"Origin": origin})

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin


def test_health_does_not_allow_unconfigured_origin():
    response = client.get(
        "/health",
        headers={"Origin": "http://example.com"},
    )

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_get_cors_preflight_is_allowed():
    origin = "http://127.0.0.1:3000"
    response = client.options(
        "/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert response.headers["access-control-allow-methods"] == "GET"


def test_post_cors_preflight_is_rejected():
    response = client.options(
        "/health",
        headers={
            "Origin": "http://127.0.0.1:3000",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 400
    assert response.headers["access-control-allow-methods"] == "GET"
