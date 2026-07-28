"""
Analysis result schemas — produced by the toolless analysis agent.

Every claim MUST cite supporting_chunk_ids — this is what makes grounding
checkable mechanically by the validator rather than by re-reading prose.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, ConfigDict, model_validator


class ActionType(str, Enum):
    """Type of action proposed by the analysis agent."""
    NONE = "none"
    TOOL_REQUEST = "tool_request"


class Claim(BaseModel):
    """
    A single claim extracted from the analysis.
    Must cite at least one supporting chunk — uncited claims are structurally invalid.
    """

    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(description="Unique identifier for this claim")
    text: str = Field(description="The claim text")
    supporting_chunk_ids: list[str] = Field(
        min_length=1,
        description="Chunk IDs supporting this claim — at least one required",
    )


class ProposedAction(BaseModel):
    """An action proposed by the analysis agent (if any)."""

    model_config = ConfigDict(extra="forbid")

    action_type: ActionType = Field(description="Type of action")
    tool_name: str | None = Field(
        default=None,
        description="Tool to invoke (required if action_type is tool_request)",
    )
    justification: str | None = Field(
        default=None,
        description="Why this action is warranted",
    )

    @model_validator(mode="after")
    def validate_tool_request(self) -> "ProposedAction":
        """If action_type is tool_request, tool_name must be provided."""
        if self.action_type == ActionType.TOOL_REQUEST and not self.tool_name:
            raise ValueError(
                "tool_name is required when action_type is 'tool_request'"
            )
        return self


class AnalysisResult(BaseModel):
    """Payload for analysis_result messages."""

    model_config = ConfigDict(extra="forbid")

    user_query: str = Field(description="The original user query")
    answer_draft: str = Field(description="Draft answer to the user's query")
    claims: list[Claim] = Field(
        default_factory=list,
        description="Claims with mandatory chunk citations",
    )
    proposed_actions: list[ProposedAction] = Field(
        default_factory=list,
        description="Actions proposed by the analysis (if any)",
    )
