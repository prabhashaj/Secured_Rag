"""
Chat Session Store — SQLite database storage for ChatGPT/Gemini style chat sessions.

Persists chat threads, titles, active matters, and message turn history across restarts.
"""

from __future__ import annotations

import json
import sqlite3
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class ChatSessionStore:
    """SQLite-backed chat session store."""

    def __init__(self, db_path: str = "./audit.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize chat_sessions and chat_messages tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    session_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    active_matter_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    message_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    trace_id TEXT,
                    metadata_json TEXT,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id) ON DELETE CASCADE
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_session "
                "ON chat_messages(session_id, timestamp)"
            )
            conn.commit()

    def create_session(
        self,
        title: str = "New Legal Chat",
        user_id: str = "default_user",
        active_matter_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new chat session."""
        session_id = f"session_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO chat_sessions (session_id, title, user_id, active_matter_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, title, user_id, active_matter_id, now, now),
            )
            conn.commit()

        return {
            "session_id": session_id,
            "title": title,
            "user_id": user_id,
            "active_matter_id": active_matter_id,
            "created_at": now,
            "updated_at": now,
        }

    def list_sessions(self, user_id: str = "default_user") -> list[dict[str, Any]]:
        """List all chat sessions for a user ordered by updated_at descending."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM chat_sessions
                WHERE user_id = ?
                ORDER BY updated_at DESC
                """,
                (user_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Get session metadata by session_id."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM chat_sessions WHERE session_id = ?",
                (session_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def delete_session(self, session_id: str) -> bool:
        """Delete a chat session and its messages."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
            cursor = conn.execute("DELETE FROM chat_sessions WHERE session_id = ?", (session_id,))
            conn.commit()
            return cursor.rowcount > 0

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        trace_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Add a message turn to a session."""
        message_id = f"msg_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        metadata_json = json.dumps(metadata or {})

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO chat_messages (message_id, session_id, role, content, trace_id, metadata_json, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (message_id, session_id, role, content, trace_id, metadata_json, now),
            )
            # Update session's updated_at timestamp
            conn.execute(
                "UPDATE chat_sessions SET updated_at = ? WHERE session_id = ?",
                (now, session_id),
            )
            conn.commit()

        return {
            "message_id": message_id,
            "session_id": session_id,
            "role": role,
            "content": content,
            "trace_id": trace_id,
            "metadata": metadata or {},
            "timestamp": now,
        }

    def get_messages(self, session_id: str) -> list[dict[str, Any]]:
        """Get all message turns in chronological order for a session."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM chat_messages
                WHERE session_id = ?
                ORDER BY timestamp ASC
                """,
                (session_id,),
            )
            messages = []
            for row in cursor.fetchall():
                item = dict(row)
                try:
                    item["metadata"] = json.loads(item.get("metadata_json", "{}"))
                except Exception:
                    item["metadata"] = {}
                messages.append(item)
            return messages
