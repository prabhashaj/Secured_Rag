"""
Unit tests for query_router.py ExecutionPath routing (PIPELINE, DIRECT_LLM, WEBSEARCH_LLM).
"""

import pytest
from orchestrator.query_router import route_query, ExecutionPath


def test_route_query_pipeline_path():
    for text in [
        "What are termination notice requirements under Matter_101?",
        "Summarize liability caps in the uploaded contract.",
        "Check indemnification clause in matter_102 filings.",
        "What is indemnification?",
        "Can you help me fill a legal notice?"
    ]:
        res = route_query(text)
        assert res.path == ExecutionPath.PIPELINE
        assert "pipeline" in res.reasoning.lower() or "legal" in res.reasoning.lower()


def test_route_query_direct_llm_path():
    for text in [
        "Hello!",
        "Explain how Human-in-the-Loop works.",
        "What tools are we using?"
    ]:
        res = route_query(text)
        assert res.path == ExecutionPath.DIRECT_LLM
        assert "direct" in res.reasoning.lower()


def test_route_query_websearch_llm_path():
    for text in [
        "Please websearch statutory code 15 U.S.C. 78j",
        "Search SEC filings for Section 13 disclosure rules",
        "Look up public dockets on recent Supreme Court privacy cases"
    ]:
        res = route_query(text)
        assert res.path == ExecutionPath.WEBSEARCH_LLM
        assert "external" in res.reasoning.lower()
