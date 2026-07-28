"""
Audit log store — append-only SQLite log indexed by trace_id.

Stores the full envelope of every message in the pipeline.
No UPDATE or DELETE operations are exposed — append-only by design.
"""

from __future__ import annotations

import json
import sqlite3
import logging

from schemas.envelope import MessageEnvelope

logger = logging.getLogger(__name__)


class AuditStore:
    """Append-only audit log backed by SQLite."""

    def __init__(self, db_path: str = "./audit.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the audit log table."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trace_id TEXT NOT NULL,
                    turn_id TEXT NOT NULL,
                    message_id TEXT NOT NULL UNIQUE,
                    timestamp TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    recipient TEXT NOT NULL,
                    message_type TEXT NOT NULL,
                    trust_level TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_trace "
                "ON audit_log(trace_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_timestamp "
                "ON audit_log(timestamp)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_message_type "
                "ON audit_log(message_type)"
            )
            conn.commit()

    async def log_message(self, envelope: MessageEnvelope) -> None:
        """
        Append a message envelope to the audit log.
        This is INSERT-ONLY — no UPDATE or DELETE operations.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO audit_log
                    (trace_id, turn_id, message_id, timestamp, sender,
                     recipient, message_type, trust_level, payload_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        envelope.trace_id,
                        envelope.turn_id,
                        envelope.message_id,
                        envelope.timestamp,
                        envelope.sender,
                        envelope.recipient,
                        envelope.message_type.value,
                        envelope.trust_level.value,
                        json.dumps(envelope.payload),
                    ),
                )
                conn.commit()
        except sqlite3.IntegrityError:
            logger.warning(
                f"Duplicate message_id {envelope.message_id} — skipping"
            )
        except Exception as e:
            logger.error(f"Failed to log message {envelope.message_id}: {e}")
            raise

    def get_trace(self, trace_id: str) -> list[dict]:
        """
        Reconstruct the full trace for a given trace_id.
        Returns all messages in chronological order.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM audit_log
                WHERE trace_id = ?
                ORDER BY timestamp ASC, id ASC
                """,
                (trace_id,),
            )
            rows = cursor.fetchall()

        return [
            {
                "id": row["id"],
                "trace_id": row["trace_id"],
                "turn_id": row["turn_id"],
                "message_id": row["message_id"],
                "timestamp": row["timestamp"],
                "sender": row["sender"],
                "recipient": row["recipient"],
                "message_type": row["message_type"],
                "trust_level": row["trust_level"],
                "payload": json.loads(row["payload_json"]),
            }
            for row in rows
        ]

    def get_all_traces(self) -> list[dict]:
        """Get a summary of all traces."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT trace_id, 
                       MIN(timestamp) as started_at,
                       MAX(timestamp) as ended_at,
                       COUNT(*) as message_count,
                       GROUP_CONCAT(DISTINCT message_type) as message_types
                FROM audit_log
                GROUP BY trace_id
                ORDER BY started_at DESC
                """
            )
            return [dict(row) for row in cursor.fetchall()]

    def count(self) -> int:
        """Count total audit log entries."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM audit_log")
            return cursor.fetchone()[0]
