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

from config import settings

logger = logging.getLogger(__name__)

# Secret key for token signing — required setting, fails loudly if missing
SECRET_KEY = getattr(settings, "jwt_secret_key", None) or os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY environment variable / setting is required and cannot be empty.")


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


def generate_token(user_id: str, email: str, expires_in_seconds: int = 86400) -> str:
    """Generate a lightweight signed bearer token with unique JTI and exp expiration claim (24h)."""
    now = datetime.now(timezone.utc).timestamp()
    payload = {
        "jti": str(uuid.uuid4()),
        "user_id": user_id,
        "email": email,
        "iat": now,
        "exp": now + expires_in_seconds,
    }
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
    sig = hmac.new(
        SECRET_KEY.encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return f"{payload_b64}.{sig}"


def verify_token(token: str, user_store: UserStore | None = None) -> dict[str, Any] | None:
    """Verify signed bearer token with constant-time signature comparison, exp check, and revocation check."""
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

        # Task 5: Constant-time signature comparison
        if not hmac.compare_digest(expected_sig, sig):
            logger.warning("Token verification failed: invalid signature")
            return None

        # Add base64 padding if needed
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload_bytes = base64.urlsafe_b64decode(padded)
        payload = json.loads(payload_bytes.decode("utf-8"))

        # Task 5: Token expiry check
        now = datetime.now(timezone.utc).timestamp()
        if "exp" in payload and now > payload["exp"]:
            logger.warning(f"Token for user {payload.get('user_id')} has expired")
            return None

        # Task 5: Token revocation check
        if user_store and user_store.is_token_revoked(sig):
            logger.warning(f"Token for user {payload.get('user_id')} has been revoked")
            return None

        return payload
    except Exception as e:
        logger.warning(f"Token validation error: {e}")
        return None


class UserStore:
    """SQLite-backed user accounts, profile store, and token revocation tracker."""

    def __init__(self, db_path: str = "./audit.db"):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)

    def _init_db(self) -> None:
        """Initialize users and revoked_tokens tables."""
        with self._get_conn() as conn:
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
            conn.execute("""
                CREATE TABLE IF NOT EXISTS revoked_tokens (
                    token_sig TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    revoked_at TEXT NOT NULL
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
        """Create a new user account (Task 1: Default to ['general'] if permitted_matters not admin-supplied)."""
        email_clean = email.strip().lower()
        hash_b64, salt_b64 = hash_password(password)
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        matters = permitted_matters if permitted_matters is not None else ["general"]
        now = datetime.now(timezone.utc).isoformat()

        with self._get_conn() as conn:
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
        with self._get_conn() as conn:
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
        with self._get_conn() as conn:
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
        with self._get_conn() as conn:
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

    def update_user_matters(self, user_id: str, permitted_matters: list[str]) -> bool:
        """Admin endpoint method to update user's permitted matters (Task 1)."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "UPDATE users SET permitted_matters_json = ? WHERE user_id = ?",
                (json.dumps(permitted_matters), user_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def revoke_token(self, token: str) -> bool:
        """Revoke a bearer token by storing its signature signature hash (Task 5)."""
        try:
            parts = token.split(".")
            if len(parts) != 2:
                return False
            payload_b64, sig = parts
            payload = verify_token(token)
            user_id = payload.get("user_id", "unknown") if payload else "unknown"
            now = datetime.now(timezone.utc).isoformat()

            with self._get_conn() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO revoked_tokens (token_sig, user_id, revoked_at) VALUES (?, ?, ?)",
                    (sig, user_id, now),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to revoke token: {e}")
            return False

    def is_token_revoked(self, sig_or_token: str) -> bool:
        """Check if token signature is in revoked_tokens table (Task 5)."""
        sig = sig_or_token.split(".")[-1] if "." in sig_or_token else sig_or_token
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT 1 FROM revoked_tokens WHERE token_sig = ?", (sig,))
            return cursor.fetchone() is not None
