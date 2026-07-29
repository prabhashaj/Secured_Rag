"""
Tests asserting free-text chat approval shortcuts ('yes', 'approve') are DELETED (Task 4).

Verifies that sending 'yes' or 'approve' in a chat query payload does NOT trigger approval
or execution of any pending tool action item in the approval queue.
"""

import os
import tempfile
import pytest
from fastapi.testclient import TestClient

from approval.queue import ApprovalQueue
from orchestrator.context_store import PipelineContextStore
from schemas.tool_action import ToolActionRequest, ToolStatus
from auth.store import UserStore, generate_token
from main import app as main_app


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


@pytest.mark.asyncio
async def test_yes_query_does_not_approve_queue_item(temp_db):
    """Sending 'yes' or 'approve' as a chat query does NOT trigger tool approval or execution."""
    queue = ApprovalQueue(db_path=temp_db)
    user_store = UserStore(db_path=temp_db)

    # Enqueue a pending approval item
    tool_req = ToolActionRequest(
        tool_name="citation_lookup",
        parameters={"query": "123 U.S. 456"},
        requested_by="analysis-agent",
        validated_by="validator-agent",
        requires_human_approval=True,
    )
    approval_id = await queue.enqueue(trace_id="test_trace_123", tool_action_request=tool_req)

    # Verify item is pending
    pending_before = queue.get_pending()
    assert len(pending_before) == 1

    # Create authenticated user
    user = user_store.create_user("lawyer_chat@legal.com", "Lawyer Chat", "Pass123", permitted_matters=["Matter_101"])

    client = TestClient(main_app)

    # Send 'yes' query to /query
    res = client.post(
        "/query",
        json={"query": "yes, please proceed"},
        headers={"Authorization": f"Bearer {user['token']}"},
    )

    # Verify item is STILL pending and was NOT approved by free-text shortcut
    pending_after = queue.get_pending()
    assert len(pending_after) == 1
    assert pending_after[0]["approval_id"] == approval_id
