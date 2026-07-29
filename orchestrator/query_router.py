"""
Query Router — Dynamic execution path decider for Lexicon AI.

Analyzes user input to route execution to one of 3 paths:
1. PIPELINE: Internal Vector RAG Pipeline (default for legal queries & matter docs)
2. DIRECT_LLM: Direct LLM Synthesis (for greetings, system inquiries, HITL/tools questions)
3. WEBSEARCH_LLM: Legal Web Search + LLM (for public dockets, statutory lookups, SEC filings)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class ExecutionPath(str, Enum):
    PIPELINE = "pipeline"           # Internal Vector RAG Pipeline
    DIRECT_LLM = "direct_llm"       # Direct LLM Knowledge & Synthesis
    WEBSEARCH_LLM = "websearch_llm" # Legal Web Search + LLM


@dataclass
class RouterDecision:
    path: ExecutionPath
    reasoning: str


# Triggers for WEBSEARCH_LLM (external legal research requests)
WEBSEARCH_PATTERNS = [
    r"\b(websearch|web\s*search)\b",
    r"\b(sec\s*filing|sec\s*filings)\b",
    r"\b(public\s*docket|court\s*docket|docket)\b",
    r"\b(statute\s*lookup|statutory\s*code|statute|constitution|act|code|laws?\s+of)\b",
    r"\b(search\s+external|search\s+online|google|legal\s*web|look\s*up|india|indian|foreign\s+law|share\s+the\s+laws)\b",
    r"\b\d+\s+u\.?s\.?c\.?\b",  # e.g., 15 U.S.C. 78j
    r"\b(merger\s*guidelines|ftc|doj|regulatory\s*updates?|case\s*law|appellate)\b",
]

# Triggers for DIRECT_LLM (greetings, HITL inquiries, tool inquiries, out-of-domain topics, affirmations)
DIRECT_LLM_PATTERNS = [
    r"^(hi|hello|hey|greetings|good\s*(morning|afternoon|evening)|howdy)\b",
    r"^what\s+can\s+you\s+(do|assist|help)",
    r"human[\s-]in[\s-]the[\s-]loop|\bhitl\b|approval\s+queue",
    r"what\s+(are\s+the\s+)?tools|list\s+(all\s+)?tools|tools\s+we\s+are\s+using",
    # Out-of-domain / non-matter general topics (recipes, sports, games, weather, etc.)
    r"\b(cricket|maggi|recipe|cooking|food|football|basketball|weather|movie|jokes?|song|music|game)\b",
    # Affirmative / continuation keywords (yes, ok, proceed, approve, etc.)
    r"^(yes|yeah|yep|ok|okay|sure|proceed|approve|go\s*ahead|do\s*it|do\s*so)\b",
]


def route_query(user_query: str) -> RouterDecision:
    """
    Decide the execution path for a user query:
    - WEBSEARCH_LLM: External legal web search + LLM
    - DIRECT_LLM: Direct LLM reasoning for system/greeting inquiries
    - PIPELINE: Internal RAG vector search over matter documents (default)
    """
    query_clean = user_query.strip().lower()

    # 1. Check for external web search path
    for pattern in WEBSEARCH_PATTERNS:
        if re.search(pattern, query_clean):
            return RouterDecision(
                path=ExecutionPath.WEBSEARCH_LLM,
                reasoning=f"Matched external research pattern '{pattern}'",
            )

    # 2. Check for direct LLM system/greeting path
    for pattern in DIRECT_LLM_PATTERNS:
        if re.search(pattern, query_clean):
            return RouterDecision(
                path=ExecutionPath.DIRECT_LLM,
                reasoning=f"Direct LLM reasoning: matched system/greeting pattern '{pattern}'",
            )

    # 3. Default to PIPELINE for legal queries & matter document RAG
    return RouterDecision(
        path=ExecutionPath.PIPELINE,
        reasoning="Legal matter query — routing to Internal Vector RAG Pipeline",
    )
