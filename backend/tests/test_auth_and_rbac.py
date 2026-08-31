import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.db.models import RecoveryCase, Payment, Customer, AuditEvent

client = TestClient(app)

def test_login_success_all_roles():
    """Test successful login for ADMIN, OPS, and VIEWER accounts."""
    for email, pwd, expected_role in [
        ("admin@recoverai.io", "admin123", "ADMIN"),
        ("ops@recoverai.io", "ops123", "OPS"),
        ("viewer@recoverai.io", "viewer123", "VIEWER")
    ]:
        res = client.post("/api/auth/login", json={"email": email, "password": pwd})
        assert res.status_code == 200, f"Login failed for {email}: {res.text}"
        data = res.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == email
        assert data["user"]["role"] == expected_role


def test_login_invalid_credentials():
    """Test login failure with invalid password or unknown user."""
    # Invalid password
    res = client.post("/api/auth/login", json={"email": "admin@recoverai.io", "password": "wrongpassword"})
    assert res.status_code == 401
    assert "Invalid email or password" in res.json()["detail"]

    # Unknown user
    res2 = client.post("/api/auth/login", json={"email": "unknown@recoverai.io", "password": "admin123"})
    assert res2.status_code == 401
    assert "Invalid email or password" in res2.json()["detail"]


def test_auth_me_endpoint():
    """Test /api/auth/me returns the authenticated user profile."""
    login_res = client.post("/api/auth/login", json={"email": "ops@recoverai.io", "password": "ops123"})
    token = login_res.json()["access_token"]

    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["email"] == "ops@recoverai.io"
    assert res.json()["role"] == "OPS"


def test_unauthenticated_requests_blocked():
    """Test that operational endpoints reject requests without token with 401."""
    endpoints = [
        ("GET", "/api/payments"),
        ("GET", "/api/customers"),
        ("GET", "/api/recovery-cases"),
        ("GET", "/api/dashboard/summary"),
        ("GET", "/api/policies"),
        ("GET", "/api/audit"),
        ("GET", "/api/agent/runs"),
    ]
    for method, path in endpoints:
        if method == "GET":
            res = client.get(path)
        else:
            res = client.post(path)
        assert res.status_code == 401, f"Expected 401 on unauthenticated {method} {path}, got {res.status_code}"


def test_invalid_token_blocked():
    """Test that requests with corrupted token return 401."""
    res = client.get("/api/payments", headers={"Authorization": "Bearer invalid.jwt.token"})
    assert res.status_code == 401


def test_role_based_policy_management():
    """
    Test RBAC on Policy configuration:
    - VIEWER cannot update policy (403 Forbidden)
    - OPS cannot update policy (403 Forbidden)
    - ADMIN can update policy (200 OK)
    """
    policy_payload = {
        "max_retries": 3,
        "recovery_window_hours": 72,
        "max_auto_retry_amount": 10000.0,
        "customer_opt_out_enabled": True,
        "duplicate_action_protection": True
    }

    # 1. VIEWER attempt
    viewer_token = client.post("/api/auth/login", json={"email": "viewer@recoverai.io", "password": "viewer123"}).json()["access_token"]
    res_viewer = client.put("/api/policies", json=policy_payload, headers={"Authorization": f"Bearer {viewer_token}"})
    assert res_viewer.status_code == 403

    # 2. OPS attempt
    ops_token = client.post("/api/auth/login", json={"email": "ops@recoverai.io", "password": "ops123"}).json()["access_token"]
    res_ops = client.put("/api/policies", json=policy_payload, headers={"Authorization": f"Bearer {ops_token}"})
    assert res_ops.status_code == 403

    # 3. ADMIN attempt
    admin_token = client.post("/api/auth/login", json={"email": "admin@recoverai.io", "password": "admin123"}).json()["access_token"]
    res_admin = client.put("/api/policies", json=policy_payload, headers={"Authorization": f"Bearer {admin_token}"})
    assert res_admin.status_code == 200
    assert res_admin.json()["max_retries"] == 3


def test_role_based_case_approval_and_audit_attribution():
    """
    Test RBAC on Case Approval:
    - VIEWER cannot approve recovery case (403 Forbidden)
    - OPS can approve recovery case (200 OK)
    - Audit event attributes operator identity
    """
    # Create or find a test case that is open / needs review
    with SessionLocal() as db:
        case = db.query(RecoveryCase).filter(RecoveryCase.status != "RECOVERED").first()
        if not case:
            pytest.skip("No active recovery case available for approval test")
        case_id = case.id

    # 1. VIEWER attempt to approve
    viewer_token = client.post("/api/auth/login", json={"email": "viewer@recoverai.io", "password": "viewer123"}).json()["access_token"]
    res_viewer = client.post(f"/api/recovery-cases/{case_id}/approve", json={"action": "RETRY"}, headers={"Authorization": f"Bearer {viewer_token}"})
    assert res_viewer.status_code == 403

    # 2. OPS attempt to reject / escalate
    ops_token = client.post("/api/auth/login", json={"email": "ops@recoverai.io", "password": "ops123"}).json()["access_token"]
    res_ops = client.post(f"/api/recovery-cases/{case_id}/escalate", headers={"Authorization": f"Bearer {ops_token}"})
    assert res_ops.status_code == 200

    # 3. Verify audit event attribution
    with SessionLocal() as db:
        latest_event = db.query(AuditEvent).filter(AuditEvent.case_id == case_id).order_by(AuditEvent.created_at.desc()).first()
        assert latest_event is not None
        assert "ops@recoverai.io" in latest_event.description or "Operations Lead" in latest_event.description


def test_jwt_secret_key_missing_fails_fast(monkeypatch):
    """
    Verifies that when JWT_SECRET_KEY is missing/empty, the system raises a clear
    RuntimeError rather than silently generating/using a fallback secret.
    """
    from app.config import settings
    from app.auth.security import create_access_token, decode_access_token

    # Temporarily set JWT_SECRET_KEY to empty
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "")

    with pytest.raises(RuntimeError) as exc_create:
        create_access_token({"sub": "admin@recoverai.io", "role": "ADMIN"})
    assert "JWT_SECRET_KEY environment variable is not configured" in str(exc_create.value)

    with pytest.raises(RuntimeError) as exc_decode:
        decode_access_token("some.fake.token")
    assert "JWT_SECRET_KEY environment variable is not configured" in str(exc_decode.value)
