"""
Validator agent — the ONLY path between untrusted and privileged zones.

Performs two critical checks:
1. GROUNDING CHECK: verifies every claim is supported by its cited chunks
2. INTENT CHECK: verifies no proposed action exceeds the user's actual request

Only the validator can upgrade trust_level to 'trusted'.
"""

from __future__ import annotations

import json
import logging

from config import settings
from schemas.retrieval import Chunk
from schemas.analysis import AnalysisResult, ActionType
from schemas.validation import ValidationVerdict
from schemas.envelope import TrustLevel
from orchestrator.context_builder import build_validator_context

logger = logging.getLogger(__name__)


class ValidatorAgent:
    """
    Validator/critic agent — the trust gateway.

    Checks grounding of claims and legitimacy of proposed actions.
    Only it can confer 'trusted' status on pipeline outputs.
    """

    def __init__(self, mistral_client=None):
        self._mistral_client = mistral_client

    def _get_mistral_client(self):
        if self._mistral_client is None:
            from mistralai.client import Mistral
            self._mistral_client = Mistral(api_key=settings.mistral_api_key)
        return self._mistral_client

    async def validate(
        self,
        analysis_result: AnalysisResult,
        chunks: list[Chunk],
        user_query: str,
    ) -> ValidationVerdict:
        """
        Validate the analysis result:
        1. Ground every claim against its cited source chunks
        2. Check that no proposed action exceeds the user's intent

        Only produces trust_level='trusted' when both checks pass.
        """
        if not analysis_result.claims:
            # No claims to validate — pass through as trusted
            return ValidationVerdict(
                grounded=True,
                ungrounded_claims=[],
                unauthorized_action_detected=False,
                trust_level_after_validation=TrustLevel.TRUSTED,
                notes="No claims to validate.",
            )

        # Build a lookup for chunks by ID
        chunk_map = {c.chunk_id: c for c in chunks}

        # Get only the chunks that are actually cited
        cited_chunk_ids = set()
        for claim in analysis_result.claims:
            cited_chunk_ids.update(claim.supporting_chunk_ids)

        cited_chunks = [
            chunk_map[cid]
            for cid in cited_chunk_ids
            if cid in chunk_map
        ]

        # Check for missing chunk references first
        missing_chunks = cited_chunk_ids - set(chunk_map.keys())
        if missing_chunks:
            logger.warning(f"Claims cite non-existent chunks: {missing_chunks}")

        # Build validator context
        messages = build_validator_context(
            analysis_result=analysis_result,
            cited_chunks=cited_chunks,
            user_query=user_query,
        )

        try:
            client = self._get_mistral_client()
            response = client.chat.complete(
                model=settings.mistral_large_model,
                messages=messages,
                temperature=0.0,  # Deterministic for validation
                response_format={"type": "json_object"},
            )

            result_text = response.choices[0].message.content
            result_json = json.loads(result_text)

            return self._parse_verdict(result_json, missing_chunks)

        except Exception as e:
            logger.error(f"Validator agent failed: {e}")
            # On failure, fail SAFE — do NOT trust
            return ValidationVerdict(
                grounded=False,
                ungrounded_claims=[c.claim_id for c in analysis_result.claims],
                unauthorized_action_detected=False,
                trust_level_after_validation=TrustLevel.UNTRUSTED,
                notes=f"Validation failed due to error: {str(e)}",
            )

    def _parse_verdict(
        self,
        result_json: dict,
        missing_chunks: set[str],
    ) -> ValidationVerdict:
        """Parse the LLM verdict into a ValidationVerdict."""
        grounded = result_json.get("grounded", False)
        ungrounded_claims = result_json.get("ungrounded_claims", [])
        unauthorized = result_json.get("unauthorized_action_detected", False)

        # If there are missing chunk references, claims citing them are ungrounded
        if missing_chunks:
            grounded = False
            ungrounded_claims.append(
                f"[missing_chunks: {', '.join(missing_chunks)}]"
            )

        # Trust level logic: only trusted if BOTH checks pass
        if grounded and not unauthorized:
            trust_level = TrustLevel.TRUSTED
        else:
            trust_level = TrustLevel.UNTRUSTED

        notes = result_json.get("notes", "")

        return ValidationVerdict(
            grounded=grounded,
            ungrounded_claims=ungrounded_claims,
            unauthorized_action_detected=unauthorized,
            trust_level_after_validation=trust_level,
            notes=notes,
        )
