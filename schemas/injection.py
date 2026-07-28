"""
Injection scan result schemas — returned by the injection classifier.

The classifier runs in isolated context (no chat history) and returns
a closed enum verdict — never free text. This prevents the classifier's
own output from becoming a second injection surface.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, ConfigDict


class InjectionVerdict(str, Enum):
    """Classifier verdict — closed enum, never free text."""
    CLEAN = "clean"
    SUSPICIOUS = "suspicious"
    BLOCKED = "blocked"


class InjectionSignal(str, Enum):
    """
    Closed enum of injection signal types.
    Using an enum prevents the classifier output from becoming an injection surface.
    """
    INSTRUCTION_LIKE_PHRASE = "instruction_like_phrase"
    HIDDEN_UNICODE = "hidden_unicode"
    ROLE_PLAY_MARKER = "role_play_marker"
    SYSTEM_PROMPT_MARKER = "system_prompt_marker"
    XML_ESCAPE_ATTEMPT = "xml_escape_attempt"
    PROMPT_LEAK_ATTEMPT = "prompt_leak_attempt"


class InjectionAction(str, Enum):
    """Action taken on the chunk after classification."""
    PASSED_THROUGH = "passed_through"
    QUARANTINED = "quarantined"


class InjectionScanResult(BaseModel):
    """Payload for injection_scan_result messages."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(description="ID of the scanned chunk")
    verdict: InjectionVerdict = Field(description="Classification verdict")
    signals: list[InjectionSignal] = Field(
        default_factory=list,
        description="Detected injection signal types (closed enum)",
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Classifier confidence in the verdict",
    )
    action_taken: InjectionAction = Field(
        description="Action taken on this chunk",
    )
