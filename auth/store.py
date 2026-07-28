"""
Auth Store — SQLite-backed User Management & Authentication System.

Provides salted PBKDF2 password hashing, JWT bearer token issuance,
user profile persistence, and matter access permission controls.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Secret key for token signing
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "legal_rag_super_secret_jwt_key_2026")


def hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    """Hash password using PBKDF2 HMAC SHA256 with random salt."""
    if salt is None:
        salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    salt_b64 = base64.b64encode(salt).decode("utf-8")
    hash_b64 = base64.b64encode(dk).decode("utf-8")
    return hash_b64, salt_b64


def verify_password(password: str, hash_b64: str, salt_b64: str) -> bool:
    """Verify password against stored PBKDF2 hash and salt."""
    try:
        salt = base64.b64decode(salt_b64.encode("utf-8"))
        computed_hash, _ = hash_password(password, salt)
        return computed_hash == hash_b64
    except Exception:
        return False


def generate_token(user_id: str, email: str) -> str:
    """Generate a lightweight signed bearer token."""
    payload = {
        "user_id": user_id,
        "email": email,
        "iat": datetime.now(timezone.utc).timestamp(),
    }
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
    sig = hmac.new(
        SECRET_KEY.encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return f"{payload_b64}.{sig}"


def verify_token(token: str) -> dict[str, Any] | None:
    """Verify signed bearer token and return payload if valid."""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, sig = parts
        expected_sig = hmac.new(
            SECRET_KEY.encode("utf-8"),
            payload_b64.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        if expected_sig != sig:
            return None
        # Add base64 padding if needed
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload_bytes = base64.urlsafe_b64decode(padded)
        return json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        return None


class UserStore:
    """SQLite-backed user accounts and profile store."""

    def __init__(self, db_path: str = "./audit.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize users table."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    full_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    password_salt TEXT NOT NULL,
                    role TEXT NOT NULL,
                    permitted_matters_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.commit()

    def create_user(
        self,
        email: str,
        full_name: str,
        password: str,
        role: str = "Senior Attorney",
        permitted_matters: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a new user account."""
        email_clean = email.strip().lower()
        hash_b64, salt_b64 = hash_password(password)
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        matters = permitted_matters if permitted_matters is not None else ["Matter_101", "Matter_102"]
        now = datetime.now(timezone.utc).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO users (user_id, email, full_name, password_hash, password_salt, role, permitted_matters_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, email_clean, full_name, hash_b64, salt_b64, role, json.dumps(matters), now),
            )
            conn.commit()

        token = generate_token(user_id, email_clean)
        return {
            "user_id": user_id,
            "email": email_clean,
            "full_name": full_name,
            "role": role,
            "permitted_matters": matters,
            "token": token,
            "created_at": now,
        }

    def authenticate_user(self, email: str, password: str) -> dict[str, Any] | None:
        """Authenticate user by email and password."""
        email_clean = email.strip().lower()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM users WHERE email = ?", (email_clean,))
            row = cursor.fetchone()
            if not row:
                return None

            user = dict(row)
            if not verify_password(password, user["password_hash"], user["password_salt"]):
                return None

            matters = json.loads(user.get("permitted_matters_json", "[]"))
            token = generate_token(user["user_id"], email_clean)

            return {
                "user_id": user["user_id"],
                "email": user["email"],
                "full_name": user["full_name"],
                "role": user["role"],
                "permitted_matters": matters,
                "token": token,
                "created_at": user["created_at"],
            }

    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        """Get user profile by user_id."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if not row:
                return None
            u = dict(row)
            return {
                "user_id": u["user_id"],
                "email": u["email"],
                "full_name": u["full_name"],
                "role": u["role"],
                "permitted_matters": json.loads(u.get("permitted_matters_json", "[]")),
                "created_at": u["created_at"],
            }

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        """Get user profile by email."""
        email_clean = email.strip().lower()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM users WHERE email = ?", (email_clean,))
            row = cursor.fetchone()
            if not row:
                return None
            u = dict(row)
            return {
                "user_id": u["user_id"],
                "email": u["email"],
                "full_name": u["full_name"],
                "role": u["role"],
                "permitted_matters": json.loads(u.get("permitted_matters_json", "[]")),
                "created_at": u["created_at"],
            }
