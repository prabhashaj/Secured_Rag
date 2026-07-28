"""
Audit log tests — verifies append-only behavior and trace reconstruction.
"""

import os
import pytest
import tempfile

from schemas.envelope import MessageType, TrustLevel, create_envelope
from audit.store import AuditStore
from audit.trace import TraceReconstructor


@pytest.fixture
def audit_db():
    """Create a temporary audit database."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    store = AuditStore(db_path=path)
    yield store
    # Close any open SQLite connections before cleanup (Windows file locking)
    try:
        os.unlink(path)
    except PermissionError:
        pass  # Windows file lock — temp file will be cleaned up by OS


class TestAuditStore:
    """Test the append-only audit log."""

    @pytest.mark.asyncio
    async def test_log_and_retrieve(self, audit_db):
        """Log a message and retrieve it by trace_id."""
        envelope = create_envelope(
            trace_id="trace-001",
            turn_id="turn-001",
            sender="retrieval-agent",
            recipient="orchestrator",
            message_type=MessageType.RETRIEVAL_RESULT,
            payload={"query": "test", "chunks": []},
        )

        await audit_db.log_message(envelope)

        trace = audit_db.get_trace("trace-001")
        assert len(trace) == 1
        assert trace[0]["trace_id"] == "trace-001"
        assert trace[0]["sender"] == "retrieval-agent"

    @pytest.mark.asyncio
    async def test_multiple_messages_same_trace(self, audit_db):
        """Multiple messages for the same trace are retrievable."""
        for i, msg_type in enumerate([
            MessageType.RETRIEVAL_RESULT,
            MessageType.INJECTION_SCAN_RESULT,
            MessageType.ANALYSIS_RESULT,
            MessageType.VALIDATION_VERDICT,
        ]):
            envelope = create_envelope(
                trace_id="trace-002",
                turn_id="turn-001",
                sender=f"agent-{i}",
                recipient="orchestrator",
                message_type=msg_type,
                payload={},
            )
            await audit_db.log_message(envelope)

        trace = audit_db.get_trace("trace-002")
        assert len(trace) == 4

    @pytest.mark.asyncio
    async def test_duplicate_message_id_skipped(self, audit_db):
        """Duplicate message_id should not cause an error."""
        envelope = create_envelope(
            trace_id="trace-003",
            turn_id="turn-001",
            sender="agent",
            recipient="orchestrator",
            message_type=MessageType.RETRIEVAL_RESULT,
            payload={},
        )

        await audit_db.log_message(envelope)
        # Second insert with same message_id should be silently skipped
        await audit_db.log_message(envelope)

        trace = audit_db.get_trace("trace-003")
        assert len(trace) == 1

    @pytest.mark.asyncio
    async def test_different_traces_isolated(self, audit_db):
        """Messages from different traces don't mix."""
        for trace_id in ["trace-A", "trace-B"]:
            envelope = create_envelope(
                trace_id=trace_id,
                turn_id="turn-001",
                sender="agent",
                recipient="orchestrator",
                message_type=MessageType.RETRIEVAL_RESULT,
                payload={},
            )
            await audit_db.log_message(envelope)

        assert len(audit_db.get_trace("trace-A")) == 1
        assert len(audit_db.get_trace("trace-B")) == 1
        assert len(audit_db.get_trace("trace-C")) == 0

    @pytest.mark.asyncio
    async def test_count(self, audit_db):
        """Count returns total entries."""
        assert audit_db.count() == 0

        envelope = create_envelope(
            trace_id="trace-count",
            turn_id="turn-001",
            sender="agent",
            recipient="orchestrator",
            message_type=MessageType.RETRIEVAL_RESULT,
            payload={},
        )
        await audit_db.log_message(envelope)
        assert audit_db.count() == 1


class TestTraceReconstructor:
    """Test the trace reconstruction logic."""

    @pytest.mark.asyncio
    async def test_reconstruct_full_trace(self, audit_db):
        """Reconstruct a multi-stage trace."""
        stages = [
            ("retrieval-agent", MessageType.RETRIEVAL_RESULT),
            ("injection-classifier", MessageType.INJECTION_SCAN_RESULT),
            ("analysis-agent", MessageType.ANALYSIS_RESULT),
            ("validator-agent", MessageType.VALIDATION_VERDICT),
        ]

        for sender, msg_type in stages:
            envelope = create_envelope(
                trace_id="trace-full",
                turn_id="turn-001",
                sender=sender,
                recipient="orchestrator",
                message_type=msg_type,
                payload={},
            )
            await audit_db.log_message(envelope)

        reconstructor = TraceReconstructor(audit_db)
        trace = reconstructor.reconstruct("trace-full")

        assert trace["trace_id"] == "trace-full"
        assert trace["total_steps"] == 4
        assert len(trace["stages"]) == 4

    @pytest.mark.asyncio
    async def test_reconstruct_not_found(self, audit_db):
        """Reconstructing a non-existent trace returns not_found."""
        reconstructor = TraceReconstructor(audit_db)
        trace = reconstructor.reconstruct("nonexistent")
        assert trace["status"] == "not_found"
