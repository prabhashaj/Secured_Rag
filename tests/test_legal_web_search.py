"""
Unit tests for legal_web_search tool.
"""

import pytest
from tools.legal_web_search import legal_web_search
from tools.tool_registry import get_tool, validate_parameters


@pytest.mark.asyncio
async def test_legal_web_search_tool_registration():
    tool = get_tool("legal_web_search")
    assert tool is not None
    assert tool.requires_human_approval is False
    assert validate_parameters("legal_web_search", {"query": "SEC release 34-92120"}) is True


@pytest.mark.asyncio
async def test_legal_web_search_execution():
    result = await legal_web_search({"query": "15 U.S. Code § 78j", "category": "statutory"})
    assert "Tavily Legal Search Results" in result or "External Tavily" in result
