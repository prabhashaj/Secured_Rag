"""
Query Router — Dynamic execution path decider for Lexicon AI.

Selects entry point ONLY (pipeline, direct_llm, websearch_llm).
Every path still passes through document classification and validation.

CRITICAL RULE:
A short affirmative message on its own ("yes", "ok", "proceed", "approve", "go ahead")
is NEVER, by itself, evidence of intent to approve any action. It routes to "direct_llm".
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from enum import Enum

from config import settings
from orchestrator.context_builder import build_router_context

logger = logging.getLogger(__name__)


class ExecutionPath(str, Enum):
    PIPELINE = "pipeline"           # Internal Vector RAG Pipeline over matter docs
    DIRECT_LLM = "direct_llm"       # Direct LLM (greetings, system questions, out-of-domain)
    WEBSEARCH_LLM = "websearch_llm" # External Legal Web Search + LLM


@dataclass
class RouterDecision:
    path: ExecutionPath
    reasoning: str


# Affirmative messages must always route to direct_llm per security non-negotiable #3
AFFIRMATIVE_PATTERN = r"^(yes|yeah|yep|ok|okay|sure|proceed|approve|go\s*ahead|do\s*it|do\s*so)[\.!\?]*$"


async def route_query(
    user_query: str,
    conversation_context: list[dict] | None = None,
    mistral_client=None,
) -> RouterDecision:
    """
    Classify user message into an execution path using LLM reasoning with conversation memory:
    - PIPELINE: Matter documents in vector RAG (default fallback)
    - DIRECT_LLM: Greeting / system inquiry / out-of-domain / affirmative text
    - WEBSEARCH_LLM: External legal research
    """
    query_clean = user_query.strip().lower()

    # CRITICAL SECURITY RULE (Non-negotiable #3): Affirmative words on their own route to direct_llm
    if re.match(AFFIRMATIVE_PATTERN, query_clean):
        return RouterDecision(
            path=ExecutionPath.DIRECT_LLM,
            reasoning="Short affirmative message routed to direct_llm per security policy — approval requires explicit endpoint",
        )

    # Use LLM classifier for intent routing if API key is present
    if settings.mistral_api_key:
        try:
            from mistralai.client import Mistral
            client = mistral_client or Mistral(api_key=settings.mistral_api_key)
            model_name = getattr(settings, "mistral_model", getattr(settings, "mistral_small_model", "mistral-small-latest"))
            messages = build_router_context(user_query, conversation_context)
            resp = await client.chat.complete_async(
                model=model_name,
                messages=messages,
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content.strip()
            data = json.loads(raw)
            p_str = data.get("path", "pipeline")
            reasoning = data.get("reasoning", "LLM router classification")

            try:
                selected_path = ExecutionPath(p_str)
            except ValueError:
                selected_path = ExecutionPath.PIPELINE

            return RouterDecision(
                path=selected_path,
                reasoning=reasoning,
            )
        except Exception as e:
            logger.warning(f"LLM query router call failed: {e}. Falling back to PIPELINE.")

    # Safest default fallback on failure or missing API key
    return RouterDecision(
        path=ExecutionPath.PIPELINE,
        reasoning="Legal matter query — routing to Internal Vector RAG Pipeline (default)",
    )
