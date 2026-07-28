"""
Validation verdict schemas — produced by the validator agent.

The validator is the ONLY path between the untrusted zone and the privileged
zone. Only it can upgrade trust_level to 'trusted'.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, ConfigDict

from schemas.envelope import TrustLevel


class ValidationVerdict(BaseModel):
    """
    Payload for validation_verdict messages.

    Only when grounded=True AND unauthorized_action_detected=False can
    trust_level_after_validation be set to 'trusted'.
    """

    model_config = ConfigDict(extra="forbid")

    grounded: bool = Field(
        description="Whether all claims are grounded in cited source chunks"
    )
    ungrounded_claims: list[str] = Field(
        default_factory=list,
        description="IDs of claims that failed grounding check",
    )
    unauthorized_action_detected: bool = Field(
        description="Whether any proposed action wasn't implied by the user's query"
    )
    trust_level_after_validation: TrustLevel = Field(
        description="Trust level after validation — only 'trusted' if fully grounded and no unauthorized actions"
    )
    notes: str = Field(
        default="",
        description="Validator notes on the verdict",
    )
