"""
MessageEnvelope — the common wrapper for every inter-agent message.

Every message in the pipeline is wrapped in this envelope, providing:
- Unique identifiers (message_id, trace_id, turn_id) for audit trail
- Sender/recipient for routing
- Trust level (sticky: starts untrusted, only validator can upgrade to trusted)
- Typed payload via message_type discriminator
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, ConfigDict


class TrustLevel(str, Enum):
    """Trust level of a message. Starts untrusted, only the validator can upgrade."""
    UNTRUSTED = "untrusted"
    TRUSTED = "trusted"


class MessageType(str, Enum):
    """Discriminator for the payload type."""
    RETRIEVAL_RESULT = "retrieval_result"
    INJECTION_SCAN_RESULT = "injection_scan_result"
    ANALYSIS_RESULT = "analysis_result"
    VALIDATION_VERDICT = "validation_verdict"
    TOOL_ACTION_REQUEST = "tool_action_request"
    TOOL_ACTION_RESULT = "tool_action_result"
    ROUTER_DECISION = "router_decision"
    USER_QUERY = "user_query"
    PIPELINE_ERROR = "pipeline_error"


class MessageEnvelope(BaseModel):
    """
    Common envelope wrapping every inter-agent message.

    trust_level is sticky — it propagates to every downstream message derived
    from it, and can only be upgraded to 'trusted' by the validator agent after
    grounding checks pass.
    """

    model_config = ConfigDict(extra="forbid")

    message_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this message",
    )
    trace_id: str = Field(
        description="Trace ID linking all messages in a single pipeline run",
    )
    turn_id: str = Field(
        description="Turn ID for multi-turn conversations",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO8601 timestamp of message creation",
    )
    sender: str = Field(description="Component that created this message")
    recipient: str = Field(description="Intended recipient component")
    trust_level: TrustLevel = Field(
        default=TrustLevel.UNTRUSTED,
        description="Trust level — starts untrusted, only validator can upgrade",
    )
    message_type: MessageType = Field(description="Type discriminator for the payload")
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Typed payload — validated separately per message_type",
    )


def create_envelope(
    *,
    trace_id: str,
    turn_id: str,
    sender: str,
    recipient: str,
    message_type: MessageType,
    payload: dict[str, Any],
    trust_level: TrustLevel = TrustLevel.UNTRUSTED,
) -> MessageEnvelope:
    """
    Factory function to create a new MessageEnvelope with auto-generated
    message_id and timestamp.
    """
    return MessageEnvelope(
        message_id=str(uuid.uuid4()),
        trace_id=trace_id,
        turn_id=turn_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        sender=sender,
        recipient=recipient,
        trust_level=trust_level,
        message_type=message_type,
        payload=payload,
    )
