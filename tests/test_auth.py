"""
Tests for UserStore, password hashing, and authentication API.
"""

import os
import tempfile
import pytest

from auth.store import UserStore, hash_password, verify_password, generate_token, verify_token


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


def test_password_hashing():
    pw = "LegalSecret123!"
    h1, s1 = hash_password(pw)
    assert verify_password(pw, h1, s1) is True
    assert verify_password("WrongPass", h1, s1) is False


def test_jwt_token():
    user_id = "user_abc123"
    email = "lawyer@firm.com"
    token = generate_token(user_id, email)
    payload = verify_token(token)
    assert payload is not None
    assert payload["user_id"] == user_id
    assert payload["email"] == email

    assert verify_token("invalid.token") is None


def test_user_store_signup_login(temp_db):
    store = UserStore(db_path=temp_db)

    user = store.create_user(
        email="attorney@legal.com",
        full_name="Jane Doe",
        password="Password123",
        role="Senior Attorney",
        permitted_matters=["Matter_101"],
    )

    assert user["user_id"].startswith("user_")
    assert user["email"] == "attorney@legal.com"
    assert user["permitted_matters"] == ["Matter_101"]

    # Test login success
    auth_user = store.authenticate_user("attorney@legal.com", "Password123")
    assert auth_user is not None
    assert auth_user["full_name"] == "Jane Doe"

    # Test login failure
    assert store.authenticate_user("attorney@legal.com", "WrongPassword") is None
    assert store.authenticate_user("nonexistent@legal.com", "Password123") is None
