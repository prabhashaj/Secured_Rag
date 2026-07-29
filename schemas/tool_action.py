"""
Tool action schemas — request and result for tool execution.

The tool-exec agent receives ONLY these structured payloads — never raw
chunk text. originating_chunk_ids provides the audit trail back to source.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, ConfigDict


class ToolStatus(str, Enum):
    """Outcome of a tool execution."""
    SUCCESS = "success"
    FAILED = "failed"
    REJECTED_BY_HUMAN = "rejected_by_human"
    AWAITING_APPROVAL = "awaiting_approval"


class ToolActionRequest(BaseModel):
    """
    Payload for tool_action_request messages.

    This is the ONLY thing the tool-exec agent sees — no raw document text.
    """

    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(description="Name of the tool to execute")
    parameters: dict = Field(
        default_factory=dict,
        description="Parameters for the tool call",
    )
    requested_by: str = Field(
        description="Agent that originally proposed this action"
    )
    validated_by: str = Field(
        description="Validator agent that approved this action"
    )
    requires_human_approval: bool = Field(
        default=True,
        description="Whether human approval is required before execution",
    )
    originating_chunk_ids: list[str] = Field(
        default_factory=list,
        description="Source chunk IDs for audit trail traceability",
    )


class ToolActionResult(BaseModel):
    """Payload for tool_action_result messages."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(description="Name of the executed tool")
    status: ToolStatus = Field(description="Outcome of the execution")
    result_summary: str = Field(
        default="",
        description="Summary of the tool execution result",
    )
    executed_at: str = Field(
        description="ISO8601 timestamp of execution",
    )

    @property
    def output(self) -> str:
        return self.result_summary
