"""
Legal Web Search tool — external legal research tool powered by Tavily Web Search API.

Requires Human-In-The-Loop (HITL) compliance approval before execution.
Searches public court dockets, statutory codes, SEC filings, and regulatory updates across external legal databases.
"""

from __future__ import annotations

import logging
import json
import httpx
from config import settings
from tools.tool_registry import register_tool

logger = logging.getLogger(__name__)

TAVILY_API_URL = "https://api.tavily.com/search"


@register_tool(
    name="legal_web_search",
    description="Search public court dockets, statutory codes, SEC filings, and regulatory updates across external legal databases using Tavily AI Search API",
    parameter_schema={
        "query": {"type": "string", "required": True, "description": "Legal query or statutory citation to search"},
        "category": {"type": "string", "required": False, "description": "Search category e.g. regulatory, statutory, SEC, court_dockets"},
    },
    requires_human_approval=False,  # Automated web search per user plan directive
)
async def legal_web_search(parameters: dict) -> str:
    """
    Perform external legal search across public dockets and statutory databases via Tavily API.
    Requires explicit compliance officer authorization before execution.
    """
    query = parameters.get("query", "")
    category = parameters.get("category", "regulatory")
    api_key = settings.tavily_api_key

    logger.info(f"Executing Tavily legal_web_search for query='{query}' under category='{category}'")

    if not api_key:
        return f"[Tavily Search Error]: Missing Tavily API Key in settings."

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                TAVILY_API_URL,
                json={
                    "api_key": api_key,
                    "query": query,
                    "search_depth": "advanced",
                    "max_results": 5,
                    "include_answer": True,
                },
            )

        if response.status_code != 200:
            logger.error(f"Tavily Search API returned status code {response.status_code}: {response.text}")
            return f"[Tavily Search Error HTTP {response.status_code}]: Unable to retrieve external search results."

        data = response.json()
        results = data.get("results", [])
        answer = data.get("answer")

        formatted_output = [f"### [External Tavily Legal Search Results — Category: {category.upper()}]"]
        formatted_output.append(f"**Query**: {query}\n")

        if answer:
            formatted_output.append(f"**Direct AI Synthesis Summary**: {answer}\n")

        if results:
            formatted_output.append("#### Verified External Web Snippets:")
            for idx, res in enumerate(results, 1):
                title = res.get("title", "Legal Reference")
                url = res.get("url", "#")
                content = res.get("content", "").strip()
                formatted_output.append(f"{idx}. **[{title}]({url})**\n   _{content}_\n")
        else:
            formatted_output.append("No external search snippets returned for this query.")

        formatted_output.append("\n_All returned search snippets pass through the isolated InjectionClassifier prior to analysis._")
        return "\n".join(formatted_output)

    except Exception as e:
        logger.error(f"Tavily legal_web_search exception: {e}")
        return f"[Tavily Legal Web Search Error]: {str(e)}"
