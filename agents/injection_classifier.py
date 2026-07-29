"""
Injection classifier — scans each chunk for prompt injection attempts.

CRITICAL ISOLATION:
- Runs in its own context with NO chat history
- Each chunk is scanned independently (no shared state between chunks)
- Returns a closed enum verdict, never free text
- Two layers: fast heuristic regex + Mistral Small LLM scan

This agent is in the UNTRUSTED ZONE — no tool bindings.
"""

from __future__ import annotations

import json
import logging

from config import settings
from schemas.retrieval import Chunk
from schemas.injection import (
    InjectionScanResult,
    InjectionVerdict,
    InjectionSignal,
    InjectionAction,
)
from orchestrator.context_builder import build_classifier_context
from vectorstore.ingest import scan_for_injection_patterns

logger = logging.getLogger(__name__)

# Map from heuristic signal types to enum values
SIGNAL_TYPE_MAP = {
    "instruction_like_phrase": InjectionSignal.INSTRUCTION_LIKE_PHRASE,
    "hidden_unicode": InjectionSignal.HIDDEN_UNICODE,
    "role_play_marker": InjectionSignal.ROLE_PLAY_MARKER,
    "system_prompt_marker": InjectionSignal.SYSTEM_PROMPT_MARKER,
    "xml_escape_attempt": InjectionSignal.XML_ESCAPE_ATTEMPT,
    "prompt_leak_attempt": InjectionSignal.PROMPT_LEAK_ATTEMPT,
}

# Valid signal names for parsing LLM output
VALID_SIGNAL_NAMES = {s.value for s in InjectionSignal}


class InjectionClassifier:
    """
    Two-layer injection classifier.

    Layer 1: Fast regex/heuristic scan (no LLM call)
    Layer 2: Mistral Small LLM scan (for chunks that pass heuristics)

    Each chunk is scanned in ISOLATED CONTEXT — no chat history, no prior turns.
    """

    def __init__(self, mistral_client=None, use_llm: bool = True):
        self._mistral_client = mistral_client
        self.use_llm = use_llm

    def _get_mistral_client(self):
        if self._mistral_client is None:
            from mistralai.client import Mistral
            self._mistral_client = Mistral(api_key=settings.mistral_api_key)
        return self._mistral_client

    async def scan(self, chunk: Chunk, heuristic_only: bool = False) -> InjectionScanResult:
        """
        Scan a single chunk for injection attempts.
        Each scan runs in isolated context — no shared state between chunks.

        Args:
            heuristic_only: If True, skip LLM layer-2 scan when heuristics pass clean.
                           Suspicious heuristic results still escalate to LLM for confirmation.
                           Used for user query fast-path to reduce latency.
        """
        # Layer 1: Fast heuristic scan
        heuristic_result = self._heuristic_scan(chunk)

        if heuristic_result.verdict == InjectionVerdict.BLOCKED:
            logger.warning(
                f"Chunk {chunk.chunk_id} BLOCKED by heuristic scan: "
                f"{[s.value for s in heuristic_result.signals]}"
            )
            return heuristic_result

        # Fast path: if heuristic_only and heuristic says clean, skip LLM round-trip
        if heuristic_only and heuristic_result.verdict == InjectionVerdict.CLEAN:
            return heuristic_result

        # Layer 2: LLM scan (for chunks that passed or were suspicious)
        if self.use_llm and heuristic_result.verdict != InjectionVerdict.BLOCKED:
            try:
                llm_result = await self._llm_scan(chunk)
                # Merge signals from both layers
                merged_signals = list(
                    set(heuristic_result.signals) | set(llm_result.signals)
                )
                # Take the more severe verdict
                final_verdict = self._merge_verdicts(
                    heuristic_result.verdict, llm_result.verdict
                )
                final_confidence = max(
                    heuristic_result.confidence, llm_result.confidence
                )
                action = (
                    InjectionAction.QUARANTINED
                    if final_verdict == InjectionVerdict.BLOCKED
                    else InjectionAction.PASSED_THROUGH
                )

                return InjectionScanResult(
                    chunk_id=chunk.chunk_id,
                    verdict=final_verdict,
                    signals=merged_signals,
                    confidence=final_confidence,
                    action_taken=action,
                )
            except Exception as e:
                logger.error(
                    f"LLM scan failed for chunk {chunk.chunk_id}: {e}. "
                    f"Falling back to heuristic result."
                )
                return heuristic_result

        return heuristic_result

    def _heuristic_scan(self, chunk: Chunk) -> InjectionScanResult:
        """Layer 1: Fast regex/heuristic scan."""
        findings = scan_for_injection_patterns(chunk.text)

        if not findings:
            return InjectionScanResult(
                chunk_id=chunk.chunk_id,
                verdict=InjectionVerdict.CLEAN,
                signals=[],
                confidence=0.9,
                action_taken=InjectionAction.PASSED_THROUGH,
            )

        # Convert findings to enum signals
        signals = []
        for finding in findings:
            signal_type = finding["signal_type"]
            if signal_type in SIGNAL_TYPE_MAP:
                signals.append(SIGNAL_TYPE_MAP[signal_type])

        signals = list(set(signals))  # Deduplicate

        # Determine severity
        # Multiple signal types or high-confidence patterns → block
        if len(signals) >= 2 or any(
            s in (
                InjectionSignal.SYSTEM_PROMPT_MARKER,
                InjectionSignal.XML_ESCAPE_ATTEMPT,
            )
            for s in signals
        ):
            verdict = InjectionVerdict.BLOCKED
            confidence = 0.85
            action = InjectionAction.QUARANTINED
        else:
            verdict = InjectionVerdict.SUSPICIOUS
            confidence = 0.6
            action = InjectionAction.PASSED_THROUGH

        return InjectionScanResult(
            chunk_id=chunk.chunk_id,
            verdict=verdict,
            signals=signals,
            confidence=confidence,
            action_taken=action,
        )

    async def _llm_scan(self, chunk: Chunk) -> InjectionScanResult:
        """
        Layer 2: Mistral Small LLM scan.

        ISOLATED CONTEXT: No chat history, no prior turns.
        Single chunk in, structured verdict out.
        """
        messages = build_classifier_context(chunk)
        client = self._get_mistral_client()

        import asyncio
        # Offload synchronous Mistral SDK call to thread pool
        response = await asyncio.to_thread(
            client.chat.complete,
            model=settings.mistral_small_model,
            messages=messages,
            temperature=0.0,  # Deterministic for security classification
            response_format={"type": "json_object"},
        )

        # Parse the LLM response
        try:
            result_text = response.choices[0].message.content
            result_json = json.loads(result_text)

            verdict_str = result_json.get("verdict", "clean").lower()
            verdict = InjectionVerdict(verdict_str) if verdict_str in {
                v.value for v in InjectionVerdict
            } else InjectionVerdict.CLEAN

            raw_signals = result_json.get("signals", [])
            signals = [
                InjectionSignal(s) for s in raw_signals
                if s in VALID_SIGNAL_NAMES
            ]

            confidence = float(result_json.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))

            action = (
                InjectionAction.QUARANTINED
                if verdict == InjectionVerdict.BLOCKED
                else InjectionAction.PASSED_THROUGH
            )

            return InjectionScanResult(
                chunk_id=chunk.chunk_id,
                verdict=verdict,
                signals=signals,
                confidence=confidence,
                action_taken=action,
            )

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(
                f"Failed to parse LLM classifier response for {chunk.chunk_id}: {e}"
            )
            # On parse failure, return suspicious (fail cautiously)
            return InjectionScanResult(
                chunk_id=chunk.chunk_id,
                verdict=InjectionVerdict.SUSPICIOUS,
                signals=[],
                confidence=0.3,
                action_taken=InjectionAction.PASSED_THROUGH,
            )

    @staticmethod
    def _merge_verdicts(
        v1: InjectionVerdict, v2: InjectionVerdict
    ) -> InjectionVerdict:
        """Take the more severe of two verdicts."""
        severity = {
            InjectionVerdict.CLEAN: 0,
            InjectionVerdict.SUSPICIOUS: 1,
            InjectionVerdict.BLOCKED: 2,
        }
        return v1 if severity[v1] >= severity[v2] else v2
