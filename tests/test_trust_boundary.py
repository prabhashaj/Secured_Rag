"""
Trust boundary enforcement tests — the CRITICAL tests that verify
the structural security guarantees of the system.

These tests must pass BEFORE any agent code is wired up.
They test the hard gates in isolation with mock messages.
"""

import pytest

from schemas.envelope import (
    MessageEnvelope,
    TrustLevel,
    MessageType,
    create_envelope,
)
from schemas.validation import ValidationVerdict
from orchestrator.trust_boundary import (
    TrustBoundaryViolation,
    assert_no_untrusted_to_tool_exec,
    assert_validated_before_privileged,
    assert_no_raw_text_in_tool_request,
    assert_untrusted_agent_has_no_tools,
    UNTRUSTED_ZONE_AGENTS,
    PRIVILEGED_ZONE_AGENTS,
)


def _make_envelope(
    recipient: str = "orchestrator",
    trust_level: TrustLevel = TrustLevel.UNTRUSTED,
    message_type: MessageType = MessageType.RETRIEVAL_RESULT,
) -> MessageEnvelope:
    """Helper to create test envelopes."""
    return create_envelope(
        trace_id="test-trace",
        turn_id="test-turn",
        sender="test-sender",
        recipient=recipient,
        message_type=message_type,
        payload={},
        trust_level=trust_level,
    )


def _make_verdict(
    grounded: bool = True,
    unauthorized: bool = False,
    trust_level: TrustLevel = TrustLevel.TRUSTED,
) -> ValidationVerdict:
    """Helper to create test validation verdicts."""
    return ValidationVerdict(
        grounded=grounded,
        ungrounded_claims=[],
        unauthorized_action_detected=unauthorized,
        trust_level_after_validation=trust_level,
    )


# ============================================================
# RULE 1 + 3: No untrusted message may reach tool-exec agent
# ============================================================

class TestUntrustedToToolExec:
    """Test that untrusted messages cannot reach privileged agents."""

    def test_untrusted_message_to_tool_exec_raises(self):
        """CRITICAL: An untrusted message must NEVER reach tool-exec-agent."""
        envelope = _make_envelope(
            recipient="tool-exec-agent",
            trust_level=TrustLevel.UNTRUSTED,
        )
        with pytest.raises(TrustBoundaryViolation) as exc_info:
            assert_no_untrusted_to_tool_exec(envelope)
        assert "RULE_1_AND_3" in str(exc_info.value)

    def test_trusted_message_to_tool_exec_passes(self):
        """A trusted message may reach the tool-exec agent."""
        envelope = _make_envelope(
            recipient="tool-exec-agent",
            trust_level=TrustLevel.TRUSTED,
        )
        # Should not raise
        assert_no_untrusted_to_tool_exec(envelope)

    def test_untrusted_message_to_non_privileged_passes(self):
        """Untrusted messages to non-privileged agents are fine."""
        for agent in ["orchestrator", "analysis-agent", "validator-agent"]:
            envelope = _make_envelope(
                recipient=agent,
                trust_level=TrustLevel.UNTRUSTED,
            )
            # Should not raise
            assert_no_untrusted_to_tool_exec(envelope)

    def test_all_privileged_agents_are_guarded(self):
        """Every agent in PRIVILEGED_ZONE_AGENTS is protected."""
        for agent in PRIVILEGED_ZONE_AGENTS:
            envelope = _make_envelope(
                recipient=agent,
                trust_level=TrustLevel.UNTRUSTED,
            )
            with pytest.raises(TrustBoundaryViolation):
                assert_no_untrusted_to_tool_exec(envelope)


# ============================================================
# RULE 3: Validator is the only path to privileged zone
# ============================================================

class TestValidatedBeforePrivileged:
    """Test that validation is required before reaching privileged agents."""

    def test_no_validation_verdict_raises(self):
        """A message without any validation verdict cannot reach privileged agents."""
        envelope = _make_envelope(recipient="tool-exec-agent")
        with pytest.raises(TrustBoundaryViolation) as exc_info:
            assert_validated_before_privileged(envelope, None)
        assert "RULE_3_NO_VALIDATION" in str(exc_info.value)

    def test_ungrounded_verdict_raises(self):
        """A message with ungrounded claims cannot reach privileged agents."""
        envelope = _make_envelope(recipient="tool-exec-agent")
        verdict = _make_verdict(grounded=False, trust_level=TrustLevel.UNTRUSTED)
        with pytest.raises(TrustBoundaryViolation) as exc_info:
            assert_validated_before_privileged(envelope, verdict)
        assert "RULE_3_UNGROUNDED" in str(exc_info.value)

    def test_unauthorized_action_raises(self):
        """A message with unauthorized actions cannot reach privileged agents."""
        envelope = _make_envelope(recipient="tool-exec-agent")
        verdict = _make_verdict(
            unauthorized=True, trust_level=TrustLevel.UNTRUSTED
        )
        with pytest.raises(TrustBoundaryViolation) as exc_info:
            assert_validated_before_privileged(envelope, verdict)
        assert "RULE_3_UNAUTHORIZED_ACTION" in str(exc_info.value)

    def test_untrusted_after_validation_raises(self):
        """Even if grounded, trust_level must be 'trusted' after validation."""
        envelope = _make_envelope(recipient="tool-exec-agent")
        verdict = _make_verdict(trust_level=TrustLevel.UNTRUSTED)
        with pytest.raises(TrustBoundaryViolation) as exc_info:
            assert_validated_before_privileged(envelope, verdict)
        assert "RULE_3_NOT_TRUSTED" in str(exc_info.value)

    def test_fully_validated_passes(self):
        """A fully validated, grounded, trusted message passes all checks."""
        envelope = _make_envelope(recipient="tool-exec-agent")
        verdict = _make_verdict(
            grounded=True,
            unauthorized=False,
            trust_level=TrustLevel.TRUSTED,
        )
        # Should not raise
        assert_validated_before_privileged(envelope, verdict)

    def test_non_privileged_skips_check(self):
        """Messages to non-privileged agents skip the validation check."""
        envelope = _make_envelope(recipient="analysis-agent")
        # Should not raise even without a verdict
        assert_validated_before_privileged(envelope, None)


# ============================================================
# No raw text in tool requests
# ============================================================

class TestNoRawTextInToolRequest:
    """Test that tool requests never contain raw document text."""

    def test_clean_payload_passes(self):
        """A payload without raw text fields passes."""
        payload = {
            "tool_name": "citation_lookup",
            "parameters": {"doc_id": "doc1", "page": "5"},
            "requested_by": "analysis-agent",
            "validated_by": "validator-agent",
        }
        # Should not raise
        assert_no_raw_text_in_tool_request(payload)

    def test_payload_with_text_field_raises(self):
        """A payload containing a 'text' field raises."""
        payload = {
            "tool_name": "citation_lookup",
            "parameters": {},
            "text": "This is raw document text that should not be here",
        }
        with pytest.raises(TrustBoundaryViolation) as exc_info:
            assert_no_raw_text_in_tool_request(payload)
        assert "RULE_1_RAW_TEXT_IN_TOOL_REQUEST" in str(exc_info.value)

    def test_nested_text_field_raises(self):
        """A nested 'text' field in parameters also raises."""
        payload = {
            "tool_name": "citation_lookup",
            "parameters": {
                "text": "sneaky raw text in parameters",
            },
        }
        with pytest.raises(TrustBoundaryViolation) as exc_info:
            assert_no_raw_text_in_tool_request(payload)
        assert "RULE_1_RAW_TEXT_IN_TOOL_REQUEST" in str(exc_info.value)

    def test_deeply_nested_text_field_raises(self):
        """Deeply nested raw text fields are also caught."""
        payload = {
            "tool_name": "citation_lookup",
            "parameters": {
                "nested": {
                    "deep": {
                        "chunk_text": "deeply hidden raw text",
                    }
                }
            },
        }
        with pytest.raises(TrustBoundaryViolation) as exc_info:
            assert_no_raw_text_in_tool_request(payload)
        assert "RULE_1_RAW_TEXT_IN_TOOL_REQUEST" in str(exc_info.value)

    def test_text_in_list_of_dicts_raises(self):
        """Raw text in a list of dicts is also caught."""
        payload = {
            "tool_name": "test",
            "items": [
                {"id": "1"},
                {"raw_text": "injection attempt"},
            ],
        }
        with pytest.raises(TrustBoundaryViolation):
            assert_no_raw_text_in_tool_request(payload)


# ============================================================
# RULE 1: Untrusted agents have no tools
# ============================================================

class TestUntrustedAgentNoTools:
    """Test that untrusted-zone agents cannot be given tools."""

    def test_untrusted_agent_with_tools_raises(self):
        """Giving tools to an untrusted agent raises."""
        for agent in UNTRUSTED_ZONE_AGENTS:
            with pytest.raises(TrustBoundaryViolation) as exc_info:
                assert_untrusted_agent_has_no_tools(
                    agent, ["citation_lookup"]
                )
            assert "RULE_1_TOOLS_ON_UNTRUSTED" in str(exc_info.value)

    def test_untrusted_agent_without_tools_passes(self):
        """An untrusted agent with no tools passes."""
        for agent in UNTRUSTED_ZONE_AGENTS:
            # Should not raise
            assert_untrusted_agent_has_no_tools(agent, None)
            assert_untrusted_agent_has_no_tools(agent, [])

    def test_privileged_agent_with_tools_passes(self):
        """Privileged agents are allowed to have tools."""
        for agent in PRIVILEGED_ZONE_AGENTS:
            # Should not raise
            assert_untrusted_agent_has_no_tools(
                agent, ["citation_lookup"]
            )
