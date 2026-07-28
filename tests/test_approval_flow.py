"""
Tests for the human approval gate flow and pipeline resumption.

Verifies:
1. Approve route calls pipeline.execute_approved_tool(ctx) and tool result status is SUCCESS.
2. Reject route transitions pipeline to COMPLETE with status REJECTED_BY_HUMAN and tool is not executed.
3. Missing context returns 404 error response on approval attempt.
4. PipelineContextStore persistence across restart / new instance.
"""

import pytest
import tempfile
import os
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from approval.queue import ApprovalQueue
from approval.routes import router as approval_router, init_routes
from orchestrator.pipeline import Pipeline, PipelineContext, PipelineState
from orchestrator.context_store import PipelineContextStore
from schemas.tool_action import ToolActionRequest, ToolActionResult, ToolStatus
from schemas.analysis import AnalysisResult, ProposedAction, ActionType
from schemas.validation import ValidationVerdict
from agents.tool_exec_agent import ToolExecAgent


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
def approval_setup(temp_db):
    queue = ApprovalQueue(db_path=temp_db)
    context_store = PipelineContextStore(db_path=temp_db)

    # Tool exec agent with dummy tool
    tool_agent = ToolExecAgent(allowed_tools=["citation_lookup"])
    mock_tool = AsyncMock(return_value={"citation": "123 U.S. 456"})
    tool_agent.register_tool("citation_lookup", mock_tool)

    # Mock agents for pipeline
    pipeline = Pipeline(
        retrieval_agent=MagicMock(),
        injection_classifier=MagicMock(),
        analysis_agent=MagicMock(),
        validator_agent=MagicMock(),
        tool_exec_agent=tool_agent,
        approval_gate=queue,
    )

    # Fastapi app for testing routes
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(approval_router)

    init_routes(queue, pipeline, context_store)

    client = TestClient(app)
    return {
        "queue": queue,
        "context_store": context_store,
        "pipeline": pipeline,
        "mock_tool": mock_tool,
        "client": client,
    }


@pytest.mark.asyncio
async def test_approve_route_executes_tool(approval_setup):
    """Approving an enqueued tool request via route actually executes the tool."""
    client = approval_setup["client"]
    queue = approval_setup["queue"]
    context_store = approval_setup["context_store"]
    mock_tool = approval_setup["mock_tool"]

    ctx = PipelineContext(
        user_query="Find citation for landmark case",
        user_id="test_user",
        state=PipelineState.AWAITING_APPROVAL,
    )
    ctx.tool_action_request = ToolActionRequest(
        tool_name="citation_lookup",
        parameters={"query": "landmark case"},
        requested_by="analysis-agent",
        validated_by="validator-agent",
        requires_human_approval=True,
    )

    context_store.save(ctx)
    approval_id = await queue.enqueue(
        trace_id=ctx.trace_id,
        tool_action_request=ctx.tool_action_request,
    )

    # POST to /approvals/{id}/approve
    response = client.post(
        f"/approvals/{approval_id}/approve",
        data={"approver": "legal_admin"},
        follow_redirects=False,
    )

    assert response.status_code == 303

    # Fetch updated context from store
    updated_ctx = context_store.get(ctx.trace_id)
    assert updated_ctx is not None
    assert updated_ctx.state == PipelineState.COMPLETE
    assert updated_ctx.tool_action_result is not None
    assert updated_ctx.tool_action_result.status == ToolStatus.SUCCESS

    # Verify tool execution mock was called
    mock_tool.assert_called_once()


@pytest.mark.asyncio
async def test_reject_route_cancels_tool(approval_setup):
    """Rejecting an enqueued request updates state without executing the tool."""
    client = approval_setup["client"]
    queue = approval_setup["queue"]
    context_store = approval_setup["context_store"]
    mock_tool = approval_setup["mock_tool"]

    ctx = PipelineContext(
        user_query="Run privileged action",
        user_id="test_user",
        state=PipelineState.AWAITING_APPROVAL,
    )
    ctx.tool_action_request = ToolActionRequest(
        tool_name="citation_lookup",
        parameters={"query": "test"},
        requested_by="analysis-agent",
        validated_by="validator-agent",
        requires_human_approval=True,
    )

    context_store.save(ctx)
    approval_id = await queue.enqueue(
        trace_id=ctx.trace_id,
        tool_action_request=ctx.tool_action_request,
    )

    # POST to /approvals/{id}/reject
    response = client.post(
        f"/approvals/{approval_id}/reject",
        data={"approver": "security_admin", "reason": "unauthorized parameter"},
        follow_redirects=False,
    )

    assert response.status_code == 303

    # Fetch updated context
    updated_ctx = context_store.get(ctx.trace_id)
    assert updated_ctx is not None
    assert updated_ctx.state == PipelineState.COMPLETE
    assert updated_ctx.tool_action_result is not None
    assert updated_ctx.tool_action_result.status == ToolStatus.REJECTED_BY_HUMAN
    assert "security_admin" in updated_ctx.tool_action_result.result_summary

    # Ensure tool execution was NEVER called
    mock_tool.assert_not_called()


@pytest.mark.asyncio
async def test_approve_route_missing_context_returns_404(approval_setup):
    """Approving a request when context is missing returns HTTP 404."""
    client = approval_setup["client"]
    queue = approval_setup["queue"]

    tool_req = ToolActionRequest(
        tool_name="citation_lookup",
        parameters={},
        requested_by="analysis-agent",
        validated_by="validator-agent",
        requires_human_approval=True,
    )
    approval_id = await queue.enqueue(
        trace_id="non_existent_trace_123",
        tool_action_request=tool_req,
    )

    response = client.post(
        f"/approvals/{approval_id}/approve",
        data={"approver": "admin"},
    )
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert "non_existent_trace_123" in data["error"]


@pytest.mark.asyncio
async def test_context_store_persistence_and_eviction(temp_db):
    """Test SQLite persistence and eviction in PipelineContextStore."""
    store = PipelineContextStore(db_path=temp_db, max_cache_size=2)

    ctx1 = PipelineContext(trace_id="t1", state=PipelineState.COMPLETE)
    ctx2 = PipelineContext(trace_id="t2", state=PipelineState.FAILED)
    ctx3 = PipelineContext(trace_id="t3", state=PipelineState.AWAITING_APPROVAL)

    store.save(ctx1)
    store.save(ctx2)
    store.save(ctx3)

    # Cache max size is 2, so t1 will be retrieved from DB
    reloaded_t1 = store.get("t1")
    assert reloaded_t1 is not None
    assert reloaded_t1.state == PipelineState.COMPLETE

    # Verify eviction function (should not evict fresh records < 24h)
    purged = store.evict_old(hours=24)
    assert purged == 0
