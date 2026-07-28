"""
Tests for ChatSessionStore.
"""

import pytest
import tempfile
import os

from orchestrator.session_store import ChatSessionStore


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


def test_session_store_crud(temp_db):
    store = ChatSessionStore(db_path=temp_db)

    # Create session
    session = store.create_session(title="Contract Analysis", user_id="u1", active_matter_id="M_99")
    assert session["session_id"].startswith("session_")
    session_id = session["session_id"]

    # List sessions
    sessions = store.list_sessions(user_id="u1")
    assert len(sessions) == 1
    assert sessions[0]["title"] == "Contract Analysis"

    # Add messages
    m1 = store.add_message(session_id, role="user", content="Analyze indemnity clause")
    m2 = store.add_message(session_id, role="assistant", content="The indemnity clause requires...", trace_id="trace_123")

    messages = store.get_messages(session_id)
    assert len(messages) == 2
    assert messages[0]["content"] == "Analyze indemnity clause"
    assert messages[1]["trace_id"] == "trace_123"

    # Delete session
    deleted = store.delete_session(session_id)
    assert deleted is True
    assert len(store.list_sessions("u1")) == 0
