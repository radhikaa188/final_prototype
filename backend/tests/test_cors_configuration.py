import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.auth.init_users import seed_default_users

@pytest.fixture(scope="module")
def client():
    with SessionLocal() as db:
        seed_default_users(db)
    return TestClient(app)

def test_production_vercel_preflight_cors(client: TestClient):
    """
    Verifies that preflight OPTIONS request from the production Vercel frontend
    succeeds with proper CORS headers.
    """
    headers = {
        "Origin": "https://frontend-six-tau-27.vercel.app",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,authorization"
    }
    response = client.options("/api/auth/login", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://frontend-six-tau-27.vercel.app"
    assert response.headers.get("access-control-allow-credentials") == "true"
    assert "POST" in response.headers.get("access-control-allow-methods", "")
    assert "content-type" in response.headers.get("access-control-allow-headers", "").lower()

def test_production_vercel_login_post_cors(client: TestClient):
    """
    Verifies that POST /api/auth/login from the production Vercel frontend
    succeeds and contains the exact allow-origin header.
    """
    headers = {
        "Origin": "https://frontend-six-tau-27.vercel.app",
        "Content-Type": "application/json"
    }
    response = client.post("/api/auth/login", json={"email": "admin@recoverai.io", "password": "admin123"}, headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://frontend-six-tau-27.vercel.app"
    assert response.headers.get("access-control-allow-credentials") == "true"
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == "admin@recoverai.io"

def test_localhost_analytics_and_login_preflight_with_client_headers(client: TestClient):
    """
    Verifies that preflight OPTIONS requests for both /api/auth/login and /api/analytics/summary
    succeed when the frontend sends its full set of custom headers (cache-control, pragma, etc.).
    """
    headers = {
        "Origin": "http://localhost:5174",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "authorization,cache-control,content-type,pragma"
    }
    # Test analytics preflight
    res_analytics = client.options("/api/analytics/summary", headers=headers)
    assert res_analytics.status_code == 200
    assert res_analytics.headers.get("access-control-allow-origin") == "http://localhost:5174"
    assert res_analytics.headers.get("access-control-allow-credentials") == "true"

    # Test login preflight
    headers["Access-Control-Request-Method"] = "POST"
    res_login = client.options("/api/auth/login", headers=headers)
    assert res_login.status_code == 200
    assert res_login.headers.get("access-control-allow-origin") == "http://localhost:5174"
    assert res_login.headers.get("access-control-allow-credentials") == "true"

def test_localhost_development_cors(client: TestClient):
    """
    Verifies that local development origins (localhost:5173, localhost:5174, and 127.0.0.1 variants)
    continue to work seamlessly.
    """
    for origin in ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://127.0.0.1:5174"]:
        headers = {
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,cache-control,content-type,pragma"
        }
        response = client.options("/api/dashboard/funnel", headers=headers)
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == origin
        assert response.headers.get("access-control-allow-credentials") == "true"

def test_unauthorized_arbitrary_origin_blocked(client: TestClient):
    """
    Verifies that arbitrary / untrusted origins do not receive CORS authorization headers.
    """
    headers = {
        "Origin": "https://unauthorized-attacker-site.com",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type"
    }
    response = client.options("/api/auth/login", headers=headers)
    # When origin is not in allow_origins, Access-Control-Allow-Origin header is omitted
    assert response.headers.get("access-control-allow-origin") is None
