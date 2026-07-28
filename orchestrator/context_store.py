"""
Pipeline Context Store — SQLite persistence + LRU cache for PipelineContext.

Persists pipeline state and contexts so tool executions can be resumed after
human approval even across process restarts. Automatically evicts old terminal contexts.
"""

from __future__ import annotations

import json
import sqlite3
import logging
from collections import OrderedDict
from datetime import datetime, timezone, timedelta
from typing import Any

from orchestrator.pipeline import PipelineContext, PipelineState
from schemas.retrieval import RetrievalResult, Chunk
from schemas.injection import InjectionScanResult
from schemas.analysis import AnalysisResult
from schemas.validation import ValidationVerdict
from schemas.tool_action import ToolActionRequest, ToolActionResult
from schemas.envelope import MessageEnvelope

logger = logging.getLogger(__name__)


class PipelineContextStore:
    """
    SQLite-backed store for PipelineContext with an in-memory LRU cache.
    """

    def __init__(self, db_path: str = "./audit.db", max_cache_size: int = 100):
        self.db_path = db_path
        self.max_cache_size = max_cache_size
        self._cache: OrderedDict[str, PipelineContext] = OrderedDict()
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the pipeline_contexts table."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pipeline_contexts (
                    trace_id TEXT PRIMARY KEY,
                    turn_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    user_query TEXT NOT NULL,
                    user_permitted_matters TEXT NOT NULL,
                    retrieval_result_json TEXT,
                    scan_results_json TEXT,
                    clean_chunks_json TEXT,
                    analysis_result_json TEXT,
                    validation_verdict_json TEXT,
                    tool_action_request_json TEXT,
                    tool_action_result_json TEXT,
                    message_log_json TEXT,
                    error TEXT,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_context_updated "
                "ON pipeline_contexts(updated_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_context_state "
                "ON pipeline_contexts(state)"
            )
            conn.commit()

    def save(self, ctx: PipelineContext) -> None:
        """Save or update a PipelineContext in SQLite and update LRU cache."""
        now = datetime.now(timezone.utc).isoformat()

        # Update LRU cache
        if ctx.trace_id in self._cache:
            self._cache.move_to_end(ctx.trace_id)
        self._cache[ctx.trace_id] = ctx
        if len(self._cache) > self.max_cache_size:
            self._cache.popitem(last=False)

        # Serialize fields
        retrieval_json = (
            json.dumps(ctx.retrieval_result.model_dump())
            if ctx.retrieval_result
            else None
        )
        scans_json = json.dumps([s.model_dump() for s in ctx.scan_results])
        clean_chunks_json = json.dumps([c.model_dump() for c in ctx.clean_chunks])
        analysis_json = (
            json.dumps(ctx.analysis_result.model_dump())
            if ctx.analysis_result
            else None
        )
        validation_json = (
            json.dumps(ctx.validation_verdict.model_dump())
            if ctx.validation_verdict
            else None
        )
        tool_req_json = (
            json.dumps(ctx.tool_action_request.model_dump())
            if ctx.tool_action_request
            else None
        )
        tool_res_json = (
            json.dumps(ctx.tool_action_result.model_dump())
            if ctx.tool_action_result
            else None
        )
        msg_log_json = json.dumps([m.model_dump() for m in ctx.message_log])

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO pipeline_contexts (
                    trace_id, turn_id, state, user_id, user_query,
                    user_permitted_matters, retrieval_result_json, scan_results_json,
                    clean_chunks_json, analysis_result_json, validation_verdict_json,
                    tool_action_request_json, tool_action_result_json, message_log_json,
                    error, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(trace_id) DO UPDATE SET
                    turn_id=excluded.turn_id,
                    state=excluded.state,
                    user_id=excluded.user_id,
                    user_query=excluded.user_query,
                    user_permitted_matters=excluded.user_permitted_matters,
                    retrieval_result_json=excluded.retrieval_result_json,
                    scan_results_json=excluded.scan_results_json,
                    clean_chunks_json=excluded.clean_chunks_json,
                    analysis_result_json=excluded.analysis_result_json,
                    validation_verdict_json=excluded.validation_verdict_json,
                    tool_action_request_json=excluded.tool_action_request_json,
                    tool_action_result_json=excluded.tool_action_result_json,
                    message_log_json=excluded.message_log_json,
                    error=excluded.error,
                    updated_at=excluded.updated_at
                """,
                (
                    ctx.trace_id,
                    ctx.turn_id,
                    ctx.state.value if isinstance(ctx.state, PipelineState) else str(ctx.state),
                    ctx.user_id,
                    ctx.user_query,
                    json.dumps(ctx.user_permitted_matters),
                    retrieval_json,
                    scans_json,
                    clean_chunks_json,
                    analysis_json,
                    validation_json,
                    tool_req_json,
                    tool_res_json,
                    msg_log_json,
                    ctx.error,
                    now,
                ),
            )
            conn.commit()

    def get(self, trace_id: str) -> PipelineContext | None:
        """Get PipelineContext by trace_id (LRU cache check first, then SQLite)."""
        if trace_id in self._cache:
            self._cache.move_to_end(trace_id)
            return self._cache[trace_id]

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM pipeline_contexts WHERE trace_id = ?", (trace_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None

        ctx = self._row_to_context(row)
        if ctx:
            self._cache[trace_id] = ctx
            if len(self._cache) > self.max_cache_size:
                self._cache.popitem(last=False)
        return ctx

    def evict_old(self, hours: int = 24) -> int:
        """
        Purge contexts for traces that reached terminal states (COMPLETE, FAILED)
        more than `hours` ago. Returns count of purged records.
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                DELETE FROM pipeline_contexts
                WHERE state IN ('complete', 'failed') AND updated_at < ?
                """,
                (cutoff,),
            )
            count = cursor.rowcount
            conn.commit()

        # Remove evicted trace_ids from in-memory cache if present
        keys_to_remove = [
            k for k, v in self._cache.items()
            if v.state in (PipelineState.COMPLETE, PipelineState.FAILED)
        ]
        for k in keys_to_remove:
            self._cache.pop(k, None)

        logger.info(f"Evicted {count} expired pipeline contexts older than {hours}h")
        return count

    def _row_to_context(self, row: sqlite3.Row) -> PipelineContext:
        """Convert a database row back to a PipelineContext object."""
        state = PipelineState(row["state"])

        retrieval_result = None
        if row["retrieval_result_json"]:
            retrieval_result = RetrievalResult.model_validate(
                json.loads(row["retrieval_result_json"])
            )

        scan_results = []
        if row["scan_results_json"]:
            scan_results = [
                InjectionScanResult.model_validate(s)
                for s in json.loads(row["scan_results_json"])
            ]

        clean_chunks = []
        if row["clean_chunks_json"]:
            clean_chunks = [
                Chunk.model_validate(c)
                for c in json.loads(row["clean_chunks_json"])
            ]

        analysis_result = None
        if row["analysis_result_json"]:
            analysis_result = AnalysisResult.model_validate(
                json.loads(row["analysis_result_json"])
            )

        validation_verdict = None
        if row["validation_verdict_json"]:
            validation_verdict = ValidationVerdict.model_validate(
                json.loads(row["validation_verdict_json"])
            )

        tool_action_request = None
        if row["tool_action_request_json"]:
            tool_action_request = ToolActionRequest.model_validate(
                json.loads(row["tool_action_request_json"])
            )

        tool_action_result = None
        if row["tool_action_result_json"]:
            tool_action_result = ToolActionResult.model_validate(
                json.loads(row["tool_action_result_json"])
            )

        message_log = []
        if row["message_log_json"]:
            message_log = [
                MessageEnvelope.model_validate(m)
                for m in json.loads(row["message_log_json"])
            ]

        return PipelineContext(
            trace_id=row["trace_id"],
            turn_id=row["turn_id"],
            state=state,
            user_id=row["user_id"],
            user_query=row["user_query"],
            user_permitted_matters=json.loads(row["user_permitted_matters"]),
            retrieval_result=retrieval_result,
            scan_results=scan_results,
            clean_chunks=clean_chunks,
            analysis_result=analysis_result,
            validation_verdict=validation_verdict,
            tool_action_request=tool_action_request,
            tool_action_result=tool_action_result,
            message_log=message_log,
            error=row["error"],
        )
