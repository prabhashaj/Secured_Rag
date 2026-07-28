"""
Session memory schemas — compact structured facts per conversation.

Stores structured facts (active matter ID, topic focus), NOT raw transcripts.
This prevents injected content from earlier turns persisting verbatim into
later prompts.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, ConfigDict


class SessionMemory(BaseModel):
    """
    Per-conversation session memory.

    Stores compact structured facts — never raw transcripts or chunk text.
    """

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(description="Unique session identifier")
    active_matter_id: str | None = Field(
        default=None,
        description="Currently active legal matter ID",
    )
    topic_focus: str | None = Field(
        default=None,
        description="Current topic focus (e.g., 'indemnification clauses')",
    )
    prior_findings_summary: str = Field(
        default="",
        description="Compact summary of prior findings — not raw agent outputs",
    )
    user_permitted_matters: list[str] = Field(
        default_factory=list,
        description="Matter IDs this user is permitted to access",
    )
    conversation_turns: list[ConversationTurn] = Field(
        default_factory=list,
        description="User-facing conversation history (queries + answers only)",
    )


class ConversationTurn(BaseModel):
    """A single user-facing conversation turn."""

    model_config = ConfigDict(extra="forbid")

    turn_id: str = Field(description="Turn identifier")
    user_query: str = Field(description="The user's query")
    answer_summary: str = Field(
        default="",
        description="Compact summary of the answer (not the full analysis output)",
    )
    trace_id: str = Field(description="Trace ID for this turn's pipeline run")


# Fix forward reference — ConversationTurn is used in SessionMemory
SessionMemory.model_rebuild()
