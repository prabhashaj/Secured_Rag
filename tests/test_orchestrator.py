"""
Orchestrator pipeline tests — verifies the state machine transitions
follow allowed paths and that invalid transitions are rejected.
"""

import pytest

from orchestrator.pipeline import (
    PipelineState,
    PipelineContext,
    InvalidTransition,
    ALLOWED_TRANSITIONS,
)


class TestPipelineState:
    """Test the pipeline state machine transition rules."""

    def test_valid_transitions(self):
        """All documented transitions should succeed."""
        valid_paths = [
            (PipelineState.RECEIVED, PipelineState.RETRIEVING),
            (PipelineState.RETRIEVING, PipelineState.CLASSIFYING),
            (PipelineState.RETRIEVING, PipelineState.FAILED),
            (PipelineState.CLASSIFYING, PipelineState.ANALYZING),
            (PipelineState.CLASSIFYING, PipelineState.FAILED),
            (PipelineState.ANALYZING, PipelineState.VALIDATING),
            (PipelineState.ANALYZING, PipelineState.FAILED),
            (PipelineState.VALIDATING, PipelineState.COMPLETE),
            (PipelineState.VALIDATING, PipelineState.AWAITING_APPROVAL),
            (PipelineState.VALIDATING, PipelineState.FAILED),
            (PipelineState.AWAITING_APPROVAL, PipelineState.EXECUTING_TOOL),
            (PipelineState.AWAITING_APPROVAL, PipelineState.COMPLETE),
            (PipelineState.AWAITING_APPROVAL, PipelineState.FAILED),
            (PipelineState.EXECUTING_TOOL, PipelineState.COMPLETE),
            (PipelineState.EXECUTING_TOOL, PipelineState.FAILED),
        ]
        for from_state, to_state in valid_paths:
            ctx = PipelineContext()
            ctx.state = from_state
            ctx.transition_to(to_state)
            assert ctx.state == to_state

    def test_invalid_transitions_raise(self):
        """Disallowed transitions should raise InvalidTransition."""
        invalid_paths = [
            # Can't skip stages
            (PipelineState.RECEIVED, PipelineState.ANALYZING),
            (PipelineState.RECEIVED, PipelineState.VALIDATING),
            (PipelineState.RECEIVED, PipelineState.COMPLETE),
            (PipelineState.RETRIEVING, PipelineState.ANALYZING),
            (PipelineState.CLASSIFYING, PipelineState.VALIDATING),
            # Can't go backwards
            (PipelineState.ANALYZING, PipelineState.RETRIEVING),
            (PipelineState.VALIDATING, PipelineState.ANALYZING),
            (PipelineState.COMPLETE, PipelineState.RECEIVED),
            # Can't leave terminal states
            (PipelineState.COMPLETE, PipelineState.RETRIEVING),
            (PipelineState.FAILED, PipelineState.RECEIVED),
            (PipelineState.FAILED, PipelineState.RETRIEVING),
            # Can't skip validator to reach tool-exec
            (PipelineState.ANALYZING, PipelineState.EXECUTING_TOOL),
            (PipelineState.ANALYZING, PipelineState.AWAITING_APPROVAL),
            # Can't skip directly to tool-exec from classifying
            (PipelineState.CLASSIFYING, PipelineState.EXECUTING_TOOL),
        ]
        for from_state, to_state in invalid_paths:
            ctx = PipelineContext()
            ctx.state = from_state
            with pytest.raises(InvalidTransition):
                ctx.transition_to(to_state)

    def test_cannot_skip_validator_to_tool_exec(self):
        """
        CRITICAL: The state machine structurally prevents skipping the
        validator to reach tool execution. There is no edge from
        ANALYZING → EXECUTING_TOOL or ANALYZING → AWAITING_APPROVAL.
        """
        # Verify the transition graph doesn't have these edges
        assert PipelineState.EXECUTING_TOOL not in ALLOWED_TRANSITIONS[PipelineState.ANALYZING]
        assert PipelineState.AWAITING_APPROVAL not in ALLOWED_TRANSITIONS[PipelineState.ANALYZING]
        assert PipelineState.EXECUTING_TOOL not in ALLOWED_TRANSITIONS[PipelineState.CLASSIFYING]

    def test_terminal_states_have_no_outgoing_transitions(self):
        """COMPLETE and FAILED are terminal — no transitions out."""
        assert ALLOWED_TRANSITIONS[PipelineState.COMPLETE] == set()
        assert ALLOWED_TRANSITIONS[PipelineState.FAILED] == set()

    def test_full_happy_path(self):
        """Walk through the full successful path without tool execution."""
        ctx = PipelineContext()
        assert ctx.state == PipelineState.RECEIVED

        ctx.transition_to(PipelineState.RETRIEVING)
        assert ctx.state == PipelineState.RETRIEVING

        ctx.transition_to(PipelineState.CLASSIFYING)
        assert ctx.state == PipelineState.CLASSIFYING

        ctx.transition_to(PipelineState.ANALYZING)
        assert ctx.state == PipelineState.ANALYZING

        ctx.transition_to(PipelineState.VALIDATING)
        assert ctx.state == PipelineState.VALIDATING

        ctx.transition_to(PipelineState.COMPLETE)
        assert ctx.state == PipelineState.COMPLETE

    def test_full_path_with_tool_execution(self):
        """Walk through the full path with tool execution and approval."""
        ctx = PipelineContext()
        ctx.transition_to(PipelineState.RETRIEVING)
        ctx.transition_to(PipelineState.CLASSIFYING)
        ctx.transition_to(PipelineState.ANALYZING)
        ctx.transition_to(PipelineState.VALIDATING)
        ctx.transition_to(PipelineState.AWAITING_APPROVAL)
        ctx.transition_to(PipelineState.EXECUTING_TOOL)
        ctx.transition_to(PipelineState.COMPLETE)
        assert ctx.state == PipelineState.COMPLETE

    def test_human_rejection_path(self):
        """Human rejects the tool action — goes to COMPLETE (with rejection)."""
        ctx = PipelineContext()
        ctx.transition_to(PipelineState.RETRIEVING)
        ctx.transition_to(PipelineState.CLASSIFYING)
        ctx.transition_to(PipelineState.ANALYZING)
        ctx.transition_to(PipelineState.VALIDATING)
        ctx.transition_to(PipelineState.AWAITING_APPROVAL)
        ctx.transition_to(PipelineState.COMPLETE)  # Rejected by human
        assert ctx.state == PipelineState.COMPLETE

    def test_classification_failure_path(self):
        """All chunks blocked — pipeline fails at classification."""
        ctx = PipelineContext()
        ctx.transition_to(PipelineState.RETRIEVING)
        ctx.transition_to(PipelineState.CLASSIFYING)
        ctx.transition_to(PipelineState.FAILED)
        assert ctx.state == PipelineState.FAILED


class TestPipelineContext:
    """Test the PipelineContext working memory."""

    def test_auto_generated_ids(self):
        """trace_id and turn_id are auto-generated."""
        ctx = PipelineContext()
        assert ctx.trace_id
        assert ctx.turn_id
        assert ctx.trace_id != ctx.turn_id

    def test_initial_state(self):
        """Initial state is RECEIVED."""
        ctx = PipelineContext()
        assert ctx.state == PipelineState.RECEIVED

    def test_working_data_starts_empty(self):
        """Working data fields start as None/empty."""
        ctx = PipelineContext()
        assert ctx.retrieval_result is None
        assert ctx.scan_results == []
        assert ctx.clean_chunks == []
        assert ctx.analysis_result is None
        assert ctx.validation_verdict is None
        assert ctx.tool_action_request is None
        assert ctx.tool_action_result is None
        assert ctx.message_log == []
        assert ctx.error is None
