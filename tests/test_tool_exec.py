"""
Tool execution and approval gate tests.
"""

import os
import pytest
import tempfile

from schemas.tool_action import ToolActionRequest, ToolStatus
from agents.tool_exec_agent import ToolExecAgent
from approval.queue import ApprovalQueue


@pytest.fixture
def tool_agent():
    """Create a tool-exec agent with test tools."""
    agent = ToolExecAgent(allowed_tools=["citation_lookup", "document_export"])

    async def mock_citation_lookup(params):
        return f"Found: {params.get('doc_id', 'unknown')}"

    async def mock_export(params):
        return f"Exported: {params.get('filename', 'test.json')}"

    agent.register_tool("citation_lookup", mock_citation_lookup)
    agent.register_tool("document_export", mock_export)
    return agent


@pytest.fixture
def approval_db():
    """Create a temporary approval database."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    queue = ApprovalQueue(db_path=path)
    yield queue
    try:
        os.unlink(path)
    except PermissionError:
        pass  # Windows file lock


class TestToolExecAgent:
    """Test the tool-exec agent with allowlist enforcement."""

    @pytest.mark.asyncio
    async def test_allowed_tool_executes(self, tool_agent):
        """An allowed tool should execute successfully."""
        request = ToolActionRequest(
            tool_name="citation_lookup",
            parameters={"doc_id": "doc1"},
            requested_by="analysis-agent",
            validated_by="validator-agent",
        )
        result = await tool_agent.execute(request)
        assert result.status == ToolStatus.SUCCESS
        assert "doc1" in result.result_summary

    @pytest.mark.asyncio
    async def test_disallowed_tool_blocked(self, tool_agent):
        """A tool not in the allowlist should be rejected."""
        request = ToolActionRequest(
            tool_name="send_email",
            parameters={"to": "test@test.com"},
            requested_by="analysis-agent",
            validated_by="validator-agent",
        )
        result = await tool_agent.execute(request)
        assert result.status == ToolStatus.FAILED
        assert "not allowed" in result.result_summary

    @pytest.mark.asyncio
    async def test_rate_limiting(self, tool_agent):
        """Tools should be rate-limited."""
        # Set a low rate limit
        tool_agent._rate_limits["citation_lookup"] = 1

        request = ToolActionRequest(
            tool_name="citation_lookup",
            parameters={"doc_id": "doc1"},
            requested_by="analysis-agent",
            validated_by="validator-agent",
        )

        result1 = await tool_agent.execute(request)
        assert result1.status == ToolStatus.SUCCESS

        # Different params to avoid idempotency
        request2 = ToolActionRequest(
            tool_name="citation_lookup",
            parameters={"doc_id": "doc2"},
            requested_by="analysis-agent",
            validated_by="validator-agent",
        )
        result2 = await tool_agent.execute(request2)
        assert result2.status == ToolStatus.FAILED
        assert "Rate limit" in result2.result_summary

    @pytest.mark.asyncio
    async def test_idempotency(self, tool_agent):
        """Duplicate calls should not double-execute."""
        request = ToolActionRequest(
            tool_name="citation_lookup",
            parameters={"doc_id": "doc1"},
            requested_by="analysis-agent",
            validated_by="validator-agent",
        )

        result1 = await tool_agent.execute(request)
        result2 = await tool_agent.execute(request)

        assert result1.status == ToolStatus.SUCCESS
        assert result2.status == ToolStatus.SUCCESS
        assert "Duplicate" in result2.result_summary

    def test_cannot_register_unlisted_tool(self):
        """Cannot register a tool that's not in the allowlist."""
        agent = ToolExecAgent(allowed_tools=["citation_lookup"])

        with pytest.raises(ValueError):
            agent.register_tool("send_email", lambda params: None)


class TestApprovalQueue:
    """Test the human approval gate."""

    @pytest.mark.asyncio
    async def test_enqueue_and_retrieve(self, approval_db):
        """Enqueue a request and retrieve it."""
        request = ToolActionRequest(
            tool_name="document_export",
            parameters={"filename": "test.json"},
            requested_by="analysis-agent",
            validated_by="validator-agent",
            originating_chunk_ids=["chunk1"],
        )

        approval_id = await approval_db.enqueue("trace-1", request)
        assert approval_id

        pending = approval_db.get_pending()
        assert len(pending) == 1
        assert pending[0]["tool_name"] == "document_export"
        assert pending[0]["status"] == "pending"

    @pytest.mark.asyncio
    async def test_approve(self, approval_db):
        """Approving a request changes its status."""
        request = ToolActionRequest(
            tool_name="document_export",
            parameters={},
            requested_by="analysis-agent",
            validated_by="validator-agent",
        )
        approval_id = await approval_db.enqueue("trace-1", request)

        result = approval_db.approve(approval_id, "admin")
        assert result is True

        # Should no longer be pending
        pending = approval_db.get_pending()
        assert len(pending) == 0

        # Should be approved in the record
        record = approval_db.get_by_id(approval_id)
        assert record["status"] == "approved"

    @pytest.mark.asyncio
    async def test_reject(self, approval_db):
        """Rejecting a request records the reason."""
        request = ToolActionRequest(
            tool_name="document_export",
            parameters={},
            requested_by="analysis-agent",
            validated_by="validator-agent",
        )
        approval_id = await approval_db.enqueue("trace-1", request)

        result = approval_db.reject(approval_id, "admin", "Not authorized")
        assert result is True

        record = approval_db.get_by_id(approval_id)
        assert record["status"] == "rejected"
        assert record["rejection_reason"] == "Not authorized"

    @pytest.mark.asyncio
    async def test_cannot_approve_twice(self, approval_db):
        """Cannot approve an already-approved request."""
        request = ToolActionRequest(
            tool_name="document_export",
            parameters={},
            requested_by="analysis-agent",
            validated_by="validator-agent",
        )
        approval_id = await approval_db.enqueue("trace-1", request)

        approval_db.approve(approval_id, "admin")
        result = approval_db.approve(approval_id, "admin2")
        assert result is False  # Already approved

    @pytest.mark.asyncio
    async def test_get_by_trace(self, approval_db):
        """Retrieve approvals by trace_id."""
        request = ToolActionRequest(
            tool_name="document_export",
            parameters={},
            requested_by="analysis-agent",
            validated_by="validator-agent",
        )
        await approval_db.enqueue("trace-A", request)
        await approval_db.enqueue("trace-A", request)
        await approval_db.enqueue("trace-B", request)

        trace_a = approval_db.get_by_trace("trace-A")
        assert len(trace_a) == 2

        trace_b = approval_db.get_by_trace("trace-B")
        assert len(trace_b) == 1
