"""
Approval queue — SQLite-backed human approval gate.

Any tool_action_request with requires_human_approval=True must pass
through this queue before the tool-exec agent executes it.
"""

from __future__ import annotations

import json
import sqlite3
import logging
import uuid
from datetime import datetime, timezone

from schemas.tool_action import ToolActionRequest

logger = logging.getLogger(__name__)


class ApprovalQueue:
    """SQLite-backed approval queue for human-in-the-loop tool execution."""

    def __init__(self, db_path: str = "./approval.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the approval queue table."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS approval_queue (
                    approval_id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    parameters TEXT NOT NULL,
                    requested_by TEXT NOT NULL,
                    validated_by TEXT NOT NULL,
                    originating_chunk_ids TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    resolved_at TEXT,
                    resolved_by TEXT,
                    rejection_reason TEXT
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_approval_status "
                "ON approval_queue(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_approval_trace "
                "ON approval_queue(trace_id)"
            )
            conn.commit()

    async def enqueue(
        self,
        trace_id: str,
        tool_action_request: ToolActionRequest,
    ) -> str:
        """
        Add a tool action request to the approval queue.
        Returns the approval_id.
        """
        approval_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO approval_queue
                (approval_id, trace_id, tool_name, parameters, requested_by,
                 validated_by, originating_chunk_ids, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
                """,
                (
                    approval_id,
                    trace_id,
                    tool_action_request.tool_name,
                    json.dumps(tool_action_request.parameters),
                    tool_action_request.requested_by,
                    tool_action_request.validated_by,
                    json.dumps(tool_action_request.originating_chunk_ids),
                    now,
                ),
            )
            conn.commit()

        logger.info(
            f"Enqueued approval request {approval_id} for tool "
            f"'{tool_action_request.tool_name}' (trace: {trace_id})"
        )
        return approval_id

    def approve(self, approval_id: str, approver: str) -> bool:
        """Approve a pending request."""
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            result = conn.execute(
                """
                UPDATE approval_queue
                SET status = 'approved', resolved_at = ?, resolved_by = ?
                WHERE approval_id = ? AND status = 'pending'
                """,
                (now, approver, approval_id),
            )
            conn.commit()
            if result.rowcount > 0:
                logger.info(f"Approval {approval_id} approved by {approver}")
                return True
            return False

    def reject(
        self, approval_id: str, approver: str, reason: str = ""
    ) -> bool:
        """Reject a pending request."""
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            result = conn.execute(
                """
                UPDATE approval_queue
                SET status = 'rejected', resolved_at = ?, resolved_by = ?,
                    rejection_reason = ?
                WHERE approval_id = ? AND status = 'pending'
                """,
                (now, approver, reason, approval_id),
            )
            conn.commit()
            if result.rowcount > 0:
                logger.info(
                    f"Approval {approval_id} rejected by {approver}: {reason}"
                )
                return True
            return False

    def get_pending(self) -> list[dict]:
        """Get all pending approval requests."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM approval_queue
                WHERE status = 'pending'
                ORDER BY created_at ASC
                """
            )
            return [dict(row) for row in cursor.fetchall()]

    def list_pending(self) -> list[dict]:
        """Alias for get_pending."""
        return self.get_pending()

    def get_by_id(self, approval_id: str) -> dict | None:
        """Get a specific approval request."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM approval_queue WHERE approval_id = ?",
                (approval_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_by_trace(self, trace_id: str) -> list[dict]:
        """Get all approval requests for a trace."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM approval_queue WHERE trace_id = ? ORDER BY created_at",
                (trace_id,),
            )
            return [dict(row) for row in cursor.fetchall()]
