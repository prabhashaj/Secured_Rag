"""
Tests for Auth, Admin Matter Controls, Token Hardening & Data Endpoint ACLs (Tasks 1, 2, 3, 5).
"""

import os
import tempfile
import time
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth.store import UserStore, generate_token, verify_token
from auth.routes import router as auth_router, admin_router, set_user_store
from main import app as main_app


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    try:
        if os.path.exists(path):
            os.remove(path)
    except PermissionError:
        pass


@pytest.fixture
def auth_client(temp_db):
    store = UserStore(db_path=temp_db)
    set_user_store(store)

    test_app = FastAPI()
    test_app.include_router(auth_router)
    test_app.include_router(admin_router)

    client = TestClient(test_app)
    return {"store": store, "client": client}


def test_signup_matters_cannot_be_self_assigned(auth_client):
    """Task 1: Signup ignores client-supplied permitted_matters and assigns default ['general']."""
    client = auth_client["client"]
    res = client.post(
        "/auth/signup",
        json={
            "email": "lawyer@firm.com",
            "full_name": "Lawyer One",
            "password": "Password123",
            "permitted_matters": ["Matter_999_HACK"],  # Client payload attempt
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["permitted_matters"] == ["general"]
    assert "Matter_999_HACK" not in data["permitted_matters"]


def test_admin_update_user_matters(auth_client):
    """Task 1: Admin endpoint updates permitted_matters for a user, non-admin gets 403."""
    store = auth_client["store"]
    client = auth_client["client"]

    # Create admin and standard user
    admin = store.create_user("admin@legal.com", "Admin User", "Pass123", role="admin", permitted_matters=["Matter_101"])
    user = store.create_user("user@legal.com", "Std User", "Pass123", role="Senior Attorney", permitted_matters=["general"])

    # Standard user attempts to update their own or another user's matters -> 403
    res = client.post(
        f"/admin/users/{user['user_id']}/matters",
        json={"permitted_matters": ["Matter_101", "Matter_102"]},
        headers={"Authorization": f"Bearer {user['token']}"},
    )
    assert res.status_code == 403

    # Admin updates user matters -> 200 SUCCESS
    res = client.post(
        f"/admin/users/{user['user_id']}/matters",
        json={"permitted_matters": ["Matter_101", "Matter_102"]},
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["permitted_matters"] == ["Matter_101", "Matter_102"]


def test_token_expiration_and_revocation(auth_client):
    """Task 5: Expired tokens, tampered signatures, and logged-out tokens are rejected."""
    store = auth_client["store"]
    client = auth_client["client"]

    user = store.create_user("user_tok@legal.com", "Tok User", "Pass123")
    token = user["token"]

    # Valid token -> /auth/me returns 200
    res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200

    # Tampered signature -> 401
    tampered = token[:-4] + "ffff"
    res = client.get("/auth/me", headers={"Authorization": f"Bearer {tampered}"})
    assert res.status_code == 401

    # Expired token -> 401
    expired_token = generate_token(user["user_id"], user["email"], expires_in_seconds=-10)
    res = client.get("/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert res.status_code == 401

    # Logout / Revocation -> 401
    res_logout = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert res_logout.status_code == 200

    res_after_logout = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_after_logout.status_code == 401


def test_unauthenticated_data_endpoints_return_401():
    """Task 2: Assert data endpoints return 401 without valid bearer token."""
    with TestClient(main_app) as client:
        # /query without token -> 401
        res = client.post("/query", json={"query": "test query"})
        assert res.status_code == 401

        # /ingest without token -> 401
        res = client.post("/ingest", json={"title": "doc", "matter_id": "Matter_101", "content": "text"})
        assert res.status_code == 401

        # /sessions without token -> 401
        res = client.get("/sessions")
        assert res.status_code == 401

        # /documents without token -> 401
        res = client.get("/documents")
        assert res.status_code == 401

        # /audit/traces without token -> 401
        res = client.get("/audit/traces")
        assert res.status_code == 401


def test_ingest_matter_authorization_check(temp_db):
    """Task 3: User with access to Matter_101 cannot ingest into Matter_102 -> 403 Forbidden."""
    store = UserStore(db_path=temp_db)

    with TestClient(main_app) as client:
        set_user_store(store)
        user101 = store.create_user("user101@legal.com", "User 101", "Pass123", permitted_matters=["Matter_101"])

        # Attempt ingest to unauthorized Matter_102 -> 403
        res = client.post(
            "/ingest",
            json={
                "title": "Secret Doc",
                "matter_id": "Matter_102",
                "content": "Confidential matter content",
            },
            headers={"Authorization": f"Bearer {user101['token']}"},
        )
        assert res.status_code == 403
        assert "not authorized to ingest" in res.json()["detail"]
