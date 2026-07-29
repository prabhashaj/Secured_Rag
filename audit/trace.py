"""
Trace reconstruction — rebuild the full path of a pipeline run.

Given a trace_id, reconstructs:
query → retrieved chunks → classifier verdicts → analysis claims →
validation verdict → tool action (if any) → result
"""

from __future__ import annotations

from audit.store import AuditStore


class TraceReconstructor:
    """Reconstructs the full pipeline path from audit log entries."""

    def __init__(self, audit_store: AuditStore):
        self.audit_store = audit_store

    def reconstruct(self, trace_id: str) -> dict:
        """
        Reconstruct the full trace for display/review.

        Returns a structured summary of every hop in the pipeline.
        """
        messages = self.audit_store.get_trace(trace_id)

        if not messages:
            return {
                "trace_id": trace_id,
                "status": "not_found",
                "stages": [],
            }

        stages = []
        has_injection_risk = False
        security_verdict = "clean"
        user_query_preview = ""
        overall_trust = "trusted"
        has_retrieval = False
        has_websearch = False

        for msg in messages:
            msg_type = msg["message_type"]
            payload = msg["payload"]
            trust_lvl = msg["trust_level"]

            if msg_type == "retrieval_result":
                has_retrieval = True
                user_query_preview = payload.get("query", "")
            elif msg_type == "tool_action_request" and payload.get("tool_name") == "legal_web_search":
                has_websearch = True
            elif msg_type == "injection_scan_result":
                verdict = payload.get("verdict")
                if verdict in ("suspicious", "blocked"):
                    has_injection_risk = True
                    security_verdict = verdict

            if trust_lvl == "untrusted":
                overall_trust = "untrusted"

            stage = {
                "step": len(stages) + 1,
                "timestamp": msg["timestamp"],
                "sender": msg["sender"],
                "recipient": msg["recipient"],
                "message_type": msg_type,
                "trust_level": trust_lvl,
                "message_id": msg["message_id"],
                "payload_summary": self._summarize_payload(msg_type, payload),
            }
            stages.append(stage)

        execution_path = (
            "websearch_llm" if has_websearch else
            "pipeline" if has_retrieval else
            "direct_llm"
        )

        return {
            "trace_id": trace_id,
            "status": "complete" if stages else "empty",
            "started_at": messages[0]["timestamp"] if messages else None,
            "ended_at": messages[-1]["timestamp"] if messages else None,
            "total_steps": len(stages),
            "user_query": user_query_preview,
            "security_verdict": security_verdict,
            "has_injection_risk": has_injection_risk,
            "overall_trust": overall_trust,
            "execution_path": execution_path,
            "stages": stages,
        }

    @staticmethod
    def _summarize_payload(message_type: str, payload: dict) -> dict:
        """Create a concise summary of a payload for display."""
        if message_type == "retrieval_result":
            chunks = payload.get("chunks", [])
            return {
                "query": payload.get("query", ""),
                "chunks_retrieved": len(chunks),
                "chunk_ids": [c.get("chunk_id") for c in chunks],
            }
        elif message_type == "injection_scan_result":
            return {
                "chunk_id": payload.get("chunk_id"),
                "verdict": payload.get("verdict"),
                "signals": payload.get("signals", []),
                "confidence": payload.get("confidence"),
                "action": payload.get("action_taken"),
            }
        elif message_type == "analysis_result":
            claims = payload.get("claims", [])
            actions = payload.get("proposed_actions", [])
            return {
                "answer_preview": payload.get("answer_draft", "")[:200],
                "num_claims": len(claims),
                "claim_ids": [c.get("claim_id") for c in claims],
                "proposed_actions": [
                    a.get("action_type") for a in actions
                ],
            }
        elif message_type == "validation_verdict":
            return {
                "grounded": payload.get("grounded"),
                "unauthorized_action": payload.get("unauthorized_action_detected"),
                "trust_level": payload.get("trust_level_after_validation"),
                "ungrounded_claims": payload.get("ungrounded_claims", []),
            }
        elif message_type == "tool_action_request":
            return {
                "tool": payload.get("tool_name"),
                "requires_approval": payload.get("requires_human_approval"),
                "validated_by": payload.get("validated_by"),
            }
        elif message_type == "tool_action_result":
            return {
                "tool": payload.get("tool_name"),
                "status": payload.get("status"),
                "summary": payload.get("result_summary", "")[:200],
            }
        else:
            return payload
