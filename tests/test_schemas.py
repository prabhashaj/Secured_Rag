"""
Schema validation tests — ensures all schemas accept valid data,
reject malformed data, and reject extra fields.

These tests run FIRST, before any agent code exists.
"""

import pytest
from pydantic import ValidationError

from schemas.envelope import (
    MessageEnvelope,
    TrustLevel,
    MessageType,
    create_envelope,
)
from schemas.retrieval import RetrievalResult, Chunk, ConfidentialityTag
from schemas.injection import (
    InjectionScanResult,
    InjectionVerdict,
    InjectionSignal,
    InjectionAction,
)
from schemas.analysis import AnalysisResult, Claim, ProposedAction, ActionType
from schemas.validation import ValidationVerdict
from schemas.tool_action import ToolActionRequest, ToolActionResult, ToolStatus


# ---------- Envelope ----------

class TestMessageEnvelope:
    def test_valid_envelope(self):
        env = MessageEnvelope(
            trace_id="trace-1",
            turn_id="turn-1",
            sender="test-agent",
            recipient="orchestrator",
            message_type=MessageType.RETRIEVAL_RESULT,
            payload={"query": "test"},
        )
        assert env.trust_level == TrustLevel.UNTRUSTED  # Default
        assert env.message_id  # Auto-generated
        assert env.timestamp  # Auto-generated

    def test_envelope_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            MessageEnvelope(
                trace_id="t1",
                turn_id="t1",
                sender="x",
                recipient="y",
                message_type=MessageType.RETRIEVAL_RESULT,
                unexpected_field="should_fail",
            )

    def test_envelope_requires_trace_id(self):
        with pytest.raises(ValidationError):
            MessageEnvelope(
                turn_id="t1",
                sender="x",
                recipient="y",
                message_type=MessageType.RETRIEVAL_RESULT,
            )

    def test_create_envelope_factory(self):
        env = create_envelope(
            trace_id="trace-1",
            turn_id="turn-1",
            sender="agent-a",
            recipient="agent-b",
            message_type=MessageType.ANALYSIS_RESULT,
            payload={"user_query": "test"},
        )
        assert env.trust_level == TrustLevel.UNTRUSTED
        assert env.sender == "agent-a"
        assert env.message_type == MessageType.ANALYSIS_RESULT

    def test_trust_level_enum(self):
        assert TrustLevel.UNTRUSTED == "untrusted"
        assert TrustLevel.TRUSTED == "trusted"


# ---------- Retrieval ----------

class TestRetrievalResult:
    def test_valid_chunk(self):
        chunk = Chunk(
            chunk_id="doc1_chunk1",
            source_doc_id="doc1",
            source_doc_title="Test Contract",
            matter_id="matter-001",
            confidentiality_tag=ConfidentialityTag.CONFIDENTIAL,
            text="This is a test clause.",
            embedding_score=0.87,
            page_ref="p.3",
            acl_check_passed=True,
        )
        assert chunk.chunk_id == "doc1_chunk1"

    def test_chunk_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            Chunk(
                chunk_id="c1",
                source_doc_id="d1",
                source_doc_title="T",
                matter_id="m1",
                confidentiality_tag=ConfidentialityTag.PUBLIC,
                text="test",
                embedding_score=0.5,
                page_ref="p.1",
                acl_check_passed=True,
                extra_field="nope",
            )

    def test_chunk_embedding_score_bounds(self):
        with pytest.raises(ValidationError):
            Chunk(
                chunk_id="c1",
                source_doc_id="d1",
                source_doc_title="T",
                matter_id="m1",
                confidentiality_tag=ConfidentialityTag.PUBLIC,
                text="test",
                embedding_score=1.5,  # Out of range
                page_ref="p.1",
                acl_check_passed=True,
            )

    def test_valid_retrieval_result(self):
        result = RetrievalResult(
            query="What are the indemnification terms?",
            chunks=[
                Chunk(
                    chunk_id="c1",
                    source_doc_id="d1",
                    source_doc_title="Contract A",
                    matter_id="m1",
                    confidentiality_tag=ConfidentialityTag.CONFIDENTIAL,
                    text="Indemnification clause text here",
                    embedding_score=0.92,
                    page_ref="p.5",
                    acl_check_passed=True,
                )
            ],
        )
        assert len(result.chunks) == 1


# ---------- Injection ----------

class TestInjectionScanResult:
    def test_valid_clean_result(self):
        result = InjectionScanResult(
            chunk_id="c1",
            verdict=InjectionVerdict.CLEAN,
            signals=[],
            confidence=0.95,
            action_taken=InjectionAction.PASSED_THROUGH,
        )
        assert result.verdict == InjectionVerdict.CLEAN

    def test_valid_blocked_result(self):
        result = InjectionScanResult(
            chunk_id="c2",
            verdict=InjectionVerdict.BLOCKED,
            signals=[
                InjectionSignal.INSTRUCTION_LIKE_PHRASE,
                InjectionSignal.ROLE_PLAY_MARKER,
            ],
            confidence=0.92,
            action_taken=InjectionAction.QUARANTINED,
        )
        assert len(result.signals) == 2

    def test_rejects_invalid_verdict(self):
        with pytest.raises(ValidationError):
            InjectionScanResult(
                chunk_id="c1",
                verdict="maybe_bad",  # Not in enum
                signals=[],
                confidence=0.5,
                action_taken=InjectionAction.PASSED_THROUGH,
            )

    def test_rejects_invalid_signal(self):
        with pytest.raises(ValidationError):
            InjectionScanResult(
                chunk_id="c1",
                verdict=InjectionVerdict.SUSPICIOUS,
                signals=["free_text_signal"],  # Not in enum
                confidence=0.5,
                action_taken=InjectionAction.PASSED_THROUGH,
            )


# ---------- Analysis ----------

class TestAnalysisResult:
    def test_valid_analysis(self):
        result = AnalysisResult(
            user_query="What are the indemnification terms?",
            answer_draft="The contract contains...",
            claims=[
                Claim(
                    claim_id="c1",
                    text="The indemnification cap is $1M",
                    supporting_chunk_ids=["doc1_chunk5"],
                )
            ],
            proposed_actions=[
                ProposedAction(action_type=ActionType.NONE)
            ],
        )
        assert len(result.claims) == 1

    def test_claim_requires_supporting_chunks(self):
        with pytest.raises(ValidationError):
            Claim(
                claim_id="c1",
                text="Unsupported claim",
                supporting_chunk_ids=[],  # Must have at least one
            )

    def test_tool_request_requires_tool_name(self):
        with pytest.raises(ValidationError):
            ProposedAction(
                action_type=ActionType.TOOL_REQUEST,
                tool_name=None,  # Required for tool_request
            )

    def test_none_action_no_tool_needed(self):
        action = ProposedAction(action_type=ActionType.NONE)
        assert action.tool_name is None


# ---------- Validation ----------

class TestValidationVerdict:
    def test_valid_trusted_verdict(self):
        verdict = ValidationVerdict(
            grounded=True,
            ungrounded_claims=[],
            unauthorized_action_detected=False,
            trust_level_after_validation=TrustLevel.TRUSTED,
            notes="All claims verified",
        )
        assert verdict.trust_level_after_validation == TrustLevel.TRUSTED

    def test_valid_untrusted_verdict(self):
        verdict = ValidationVerdict(
            grounded=False,
            ungrounded_claims=["c2"],
            unauthorized_action_detected=False,
            trust_level_after_validation=TrustLevel.UNTRUSTED,
            notes="Claim c2 not supported by source",
        )
        assert not verdict.grounded


# ---------- Tool Action ----------

class TestToolAction:
    def test_valid_tool_request(self):
        req = ToolActionRequest(
            tool_name="citation_lookup",
            parameters={"doc_id": "doc1", "page": "5"},
            requested_by="analysis-agent",
            validated_by="validator-agent",
            requires_human_approval=True,
            originating_chunk_ids=["doc1_chunk5"],
        )
        assert req.requires_human_approval

    def test_tool_request_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            ToolActionRequest(
                tool_name="citation_lookup",
                parameters={},
                requested_by="analysis-agent",
                validated_by="validator-agent",
                text="raw document text should not be here",  # Extra field!
            )

    def test_valid_tool_result(self):
        result = ToolActionResult(
            tool_name="citation_lookup",
            status=ToolStatus.SUCCESS,
            result_summary="Found citation on page 5",
            executed_at="2026-07-28T10:16:02Z",
        )
        assert result.status == ToolStatus.SUCCESS

    def test_rejected_result(self):
        result = ToolActionResult(
            tool_name="document_export",
            status=ToolStatus.REJECTED_BY_HUMAN,
            result_summary="Human reviewer rejected the export",
            executed_at="2026-07-28T10:20:00Z",
        )
        assert result.status == ToolStatus.REJECTED_BY_HUMAN
