import pytest
from unittest.mock import AsyncMock, MagicMock
from orchestrator.query_router import route_query, ExecutionPath


@pytest.mark.asyncio
async def test_route_query_bare_affirmative_never_approves():
    """Non-negotiable #3 assertion: bare affirmative 'yes' routes to direct_llm regardless of context."""
    for text in ["yes", "ok", "proceed", "approve", "go ahead", "do it"]:
        res = await route_query(text, conversation_context=[{"role": "assistant", "content": "Action pending approval"}])
        assert res.path == ExecutionPath.DIRECT_LLM
        assert "security policy" in res.reasoning.lower() or "affirmative" in res.reasoning.lower()


@pytest.mark.asyncio
async def test_route_query_direct_websearch_request():
    """LLM router classifies direct web search requests to websearch_llm."""
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content='{"path": "websearch_llm", "reasoning": "External legal research request"}'))
    ]
    mock_client.chat.complete_async.return_value = mock_response

    res = await route_query("Search SEC filings for merger guidelines", mistral_client=mock_client)
    assert res.path == ExecutionPath.WEBSEARCH_LLM


@pytest.mark.asyncio
async def test_route_query_followup_with_conversation_context():
    """Follow-up query 'then search the web about that' resolves via conversation context."""
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content='{"path": "websearch_llm", "reasoning": "Resolved follow-up using conversation context"}'))
    ]
    mock_client.chat.complete_async.return_value = mock_response

    history = [
        {"role": "user", "content": "Look up acquisitions for Matter 101"},
        {"role": "assistant", "content": "No internal document found for that matter."}
    ]

    res = await route_query("then search the web about that", conversation_context=history, mistral_client=mock_client)
    assert res.path == ExecutionPath.WEBSEARCH_LLM
    # Verify build_router_context passed history to client
    assert mock_client.chat.complete_async.called


@pytest.mark.asyncio
async def test_route_query_fallback_on_api_error():
    """On API error, router falls back safely to PIPELINE path."""
    mock_client = AsyncMock()
    mock_client.chat.complete_async.side_effect = RuntimeError("API timeout")

    res = await route_query("Any complex legal question", mistral_client=mock_client)
    assert res.path == ExecutionPath.PIPELINE
    assert "default" in res.reasoning.lower() or "pipeline" in res.reasoning.lower()
