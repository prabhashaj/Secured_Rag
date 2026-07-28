"""
Analysis agent — the only agent that reasons over document content.

CRITICAL SECURITY PROPERTIES:
- ZERO tool bindings — structurally enforced, not prompted
- Every claim MUST cite supporting_chunk_ids
- Chunks are XML-delimited with standing "this is data" instruction
- Cannot execute any actions, only propose them

This agent is in the UNTRUSTED ZONE — it's the most exposed to injected
content, which is exactly why it has no tools to abuse.
"""

from __future__ import annotations

import json
import logging

from config import settings
from schemas.retrieval import Chunk
from schemas.analysis import AnalysisResult, Claim, ProposedAction, ActionType
from orchestrator.context_builder import build_analysis_context

logger = logging.getLogger(__name__)


class AnalysisAgent:
    """
    Toolless document analysis agent.

    Reasons over retrieved chunks to answer the user's legal query.
    Every claim must cite chunk IDs. Has no tool bindings — by design.
    """

    # This agent has NO tools. This is structural, not just a prompt instruction.
    TOOLS = None

    def __init__(self, mistral_client=None):
        self._mistral_client = mistral_client

    def _get_mistral_client(self):
        if self._mistral_client is None:
            from mistralai.client import Mistral
            self._mistral_client = Mistral(api_key=settings.mistral_api_key)
        return self._mistral_client

    async def analyze(
        self,
        user_query: str,
        chunks: list[Chunk],
        session_memory: dict | None = None,
    ) -> AnalysisResult:
        """
        Analyze chunks to answer the user's query.

        Returns an AnalysisResult with mandatory claim citations.
        """
        if not chunks:
            return AnalysisResult(
                user_query=user_query,
                answer_draft="No relevant document chunks were available for analysis.",
                claims=[],
                proposed_actions=[
                    ProposedAction(action_type=ActionType.NONE)
                ],
            )

        # Build context with XML-delimited chunks
        messages = build_analysis_context(
            user_query=user_query,
            chunks=chunks,
            session_memory=session_memory,
            max_chunks=settings.analysis_top_k,
        )

        client = self._get_mistral_client()

        try:
            response = client.chat.complete(
                model=settings.mistral_large_model,
                messages=messages,
                temperature=0.1,  # Low temperature for factual analysis
                response_format={"type": "json_object"},
            )

            result_text = response.choices[0].message.content
            result_json = json.loads(result_text)

            # Parse and validate the response
            return self._parse_response(result_json, user_query, chunks)

        except Exception as e:
            logger.error(f"Analysis agent failed: {e}")
            return AnalysisResult(
                user_query=user_query,
                answer_draft=f"Analysis failed due to an internal error: {str(e)}",
                claims=[],
                proposed_actions=[
                    ProposedAction(action_type=ActionType.NONE)
                ],
            )

    def _parse_response(
        self,
        result_json: dict,
        user_query: str,
        available_chunks: list[Chunk],
    ) -> AnalysisResult:
        """
        Parse the LLM response into an AnalysisResult.
        Validates that all cited chunk IDs actually exist in the available chunks.
        """
        available_chunk_ids = {c.chunk_id for c in available_chunks}

        # Parse claims
        claims = []
        for i, claim_data in enumerate(result_json.get("claims", [])):
            chunk_ids = claim_data.get("supporting_chunk_ids", [])
            # Only keep chunk IDs that actually exist
            valid_chunk_ids = [
                cid for cid in chunk_ids if cid in available_chunk_ids
            ]

            if not valid_chunk_ids:
                logger.warning(
                    f"Claim {i} cites no valid chunks — skipping"
                )
                continue

            claims.append(Claim(
                claim_id=claim_data.get("claim_id", f"c{i+1}"),
                text=claim_data.get("text", ""),
                supporting_chunk_ids=valid_chunk_ids,
            ))

        # Parse proposed actions
        proposed_actions = []
        for action_data in result_json.get("proposed_actions", []):
            action_type_str = action_data.get("action_type", "none")
            try:
                action_type = ActionType(action_type_str)
            except ValueError:
                action_type = ActionType.NONE

            proposed_actions.append(ProposedAction(
                action_type=action_type,
                tool_name=action_data.get("tool_name"),
                justification=action_data.get("justification"),
            ))

        if not proposed_actions:
            proposed_actions.append(ProposedAction(action_type=ActionType.NONE))

        return AnalysisResult(
            user_query=user_query,
            answer_draft=result_json.get("answer_draft", ""),
            claims=claims,
            proposed_actions=proposed_actions,
        )
