"""
Trust boundary enforcement — hard gates checked by the orchestrator
before every pipeline transition.

These are the two non-negotiable architecture rules:
  Rule 1: No agent that reads raw document text may call a tool.
  Rule 3: A validator agent is the only path between untrusted and privileged zones.

These gates are STRUCTURAL — they exist in code, not in prompts.
They must be unit-tested independently before any agent code is wired up.
"""

from __future__ import annotations

from schemas.envelope import MessageEnvelope, TrustLevel, MessageType
from schemas.validation import ValidationVerdict


class TrustBoundaryViolation(Exception):
    """Raised when a trust boundary rule is violated."""

    def __init__(self, rule: str, detail: str):
        self.rule = rule
        self.detail = detail
        super().__init__(f"TRUST BOUNDARY VIOLATION [{rule}]: {detail}")


# --- The agents classified by zone ---

# Untrusted zone: agents that read raw document text — NO tool access
UNTRUSTED_ZONE_AGENTS = frozenset({
    "retrieval-agent",
    "injection-classifier",
    "analysis-agent",
})

# Privileged zone: agents that can execute tools
PRIVILEGED_ZONE_AGENTS = frozenset({
    "tool-exec-agent",
})

# Gateway: the only agent that can bridge untrusted → trusted
VALIDATOR_AGENT = "validator-agent"

# Message types that carry raw document text
RAW_TEXT_MESSAGE_TYPES = frozenset({
    MessageType.RETRIEVAL_RESULT,
})

# Fields that must NEVER appear in tool-exec agent's payload
FORBIDDEN_FIELDS_IN_TOOL_REQUEST = frozenset({"text", "chunk_text", "raw_text"})


def assert_no_untrusted_to_tool_exec(envelope: MessageEnvelope) -> None:
    """
    RULE 1 + RULE 3: No message with trust_level=untrusted may be routed
    to the tool-exec agent. It must pass through the validator first.

    Raises TrustBoundaryViolation if violated.
    """
    if (
        envelope.recipient in PRIVILEGED_ZONE_AGENTS
        and envelope.trust_level == TrustLevel.UNTRUSTED
    ):
        raise TrustBoundaryViolation(
            rule="RULE_1_AND_3",
            detail=(
                f"Message {envelope.message_id} has trust_level=untrusted "
                f"but is routed to privileged agent '{envelope.recipient}'. "
                f"It must pass through the validator agent first."
            ),
        )


def assert_validated_before_privileged(
    envelope: MessageEnvelope,
    validation_verdict: ValidationVerdict | None,
) -> None:
    """
    RULE 3: Any message reaching a privileged agent must have been validated.
    The validation verdict must show grounded=True and no unauthorized actions.

    Raises TrustBoundaryViolation if violated.
    """
    if envelope.recipient not in PRIVILEGED_ZONE_AGENTS:
        return  # Not targeting a privileged agent — no check needed

    if validation_verdict is None:
        raise TrustBoundaryViolation(
            rule="RULE_3_NO_VALIDATION",
            detail=(
                f"Message {envelope.message_id} is routed to privileged agent "
                f"'{envelope.recipient}' but has no validation verdict."
            ),
        )

    if not validation_verdict.grounded:
        raise TrustBoundaryViolation(
            rule="RULE_3_UNGROUNDED",
            detail=(
                f"Message {envelope.message_id} failed grounding check. "
                f"Ungrounded claims: {validation_verdict.ungrounded_claims}"
            ),
        )

    if validation_verdict.unauthorized_action_detected:
        raise TrustBoundaryViolation(
            rule="RULE_3_UNAUTHORIZED_ACTION",
            detail=(
                f"Message {envelope.message_id} contains an unauthorized action "
                f"that was not implied by the user's query."
            ),
        )

    if validation_verdict.trust_level_after_validation != TrustLevel.TRUSTED:
        raise TrustBoundaryViolation(
            rule="RULE_3_NOT_TRUSTED",
            detail=(
                f"Message {envelope.message_id} was validated but trust_level "
                f"is '{validation_verdict.trust_level_after_validation}', not 'trusted'."
            ),
        )


def assert_no_raw_text_in_tool_request(payload: dict) -> None:
    """
    Ensure that a tool_action_request payload does not contain any raw chunk text.
    The tool-exec agent must never see document content.

    Raises TrustBoundaryViolation if raw text fields are found.
    """
    _check_dict_for_forbidden_fields(payload, path="payload")


def _check_dict_for_forbidden_fields(d: dict, path: str) -> None:
    """Recursively check a dict for forbidden field names."""
    for key, value in d.items():
        if key in FORBIDDEN_FIELDS_IN_TOOL_REQUEST:
            raise TrustBoundaryViolation(
                rule="RULE_1_RAW_TEXT_IN_TOOL_REQUEST",
                detail=(
                    f"Field '{key}' found at '{path}.{key}' in tool_action_request. "
                    f"The tool-exec agent must never receive raw document text."
                ),
            )
        if isinstance(value, dict):
            _check_dict_for_forbidden_fields(value, f"{path}.{key}")
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    _check_dict_for_forbidden_fields(item, f"{path}.{key}[{i}]")


def assert_untrusted_agent_has_no_tools(agent_name: str, tools: list | None) -> None:
    """
    RULE 1: Agents in the untrusted zone must have zero tool bindings.

    Raises TrustBoundaryViolation if an untrusted-zone agent is given tools.
    """
    if agent_name in UNTRUSTED_ZONE_AGENTS and tools:
        raise TrustBoundaryViolation(
            rule="RULE_1_TOOLS_ON_UNTRUSTED",
            detail=(
                f"Agent '{agent_name}' is in the untrusted zone but was given "
                f"tools: {tools}. Untrusted-zone agents must have zero tool bindings."
            ),
        )
