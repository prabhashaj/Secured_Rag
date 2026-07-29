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


# Affirmative messages must always route to direct_llm
AFFIRMATIVE_PATTERN = r"^(yes|yeah|yep|ok|okay|sure|proceed|approve|go\s*ahead|do\s*it|do\s*so)[\.!\?]*$"

# Web search triggers
WEBSEARCH_PATTERNS = [
    r"\b(websearch|web\s*search)\b",
    r"\b(sec\s*filing|sec\s*filings)\b",
    r"\b(public\s*docket|court\s*docket|docket)\b",
    r"\b(statute\s*lookup|statutory\s*code|statute|constitution|act|code|laws?\s+of)\b",
    r"\b(search\s+external|search\s+online|google|legal\s*web|look\s*up|india|indian|foreign\s+law|share\s+the\s+laws)\b",
    r"\b\d+\s+u\.?s\.?c\.?\b",
    r"\b(merger\s*guidelines|ftc|doj|regulatory\s*updates?|case\s*law|appellate)\b",
]

# Direct LLM triggers
DIRECT_LLM_PATTERNS = [
    r"^(hi|hello|hey|greetings|good\s*(morning|afternoon|evening)|howdy)\b",
    r"^what\s+can\s+you\s+(do|assist|help)",
    r"human[\s-]in[\s-]the[\s-]loop|\bhitl\b|approval\s+queue",
    r"what\s+(are\s+the\s+)?tools|list\s+(all\s+)?tools|tools\s+we\s+are\s+using",
    r"\b(cricket|maggi|recipe|cooking|food|football|basketball|weather|movie|jokes?|song|music|game)\b",
]


def route_query(user_query: str) -> RouterDecision:
    """
    Classify user message into an execution path:
    - PIPELINE: Matter documents in vector RAG
    - DIRECT_LLM: Greeting / system inquiry / out-of-domain / affirmative text
    - WEBSEARCH_LLM: External legal research
    """
    query_clean = user_query.strip().lower()

    # CRITICAL SECURITY RULE: Affirmative words on their own route to direct_llm
    if re.match(AFFIRMATIVE_PATTERN, query_clean):
        return RouterDecision(
            path=ExecutionPath.DIRECT_LLM,
            reasoning="Short affirmative message routed to direct_llm per security policy — approval requires explicit endpoint",
        )

    # Fast pattern routing
    for pattern in WEBSEARCH_PATTERNS:
        if re.search(pattern, query_clean):
            return RouterDecision(
                path=ExecutionPath.WEBSEARCH_LLM,
                reasoning=f"Matched external legal research pattern '{pattern}'",
            )

    for pattern in DIRECT_LLM_PATTERNS:
        if re.search(pattern, query_clean):
            return RouterDecision(
                path=ExecutionPath.DIRECT_LLM,
                reasoning=f"Matched direct LLM pattern '{pattern}'",
            )

    # Default to PIPELINE (safest default)
    return RouterDecision(
        path=ExecutionPath.PIPELINE,
        reasoning="Legal matter query — routing to Internal Vector RAG Pipeline",
    )
