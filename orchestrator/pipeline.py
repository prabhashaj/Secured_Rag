"""
Pipeline — explicit state machine for the agent pipeline.

The sequence retrieve → classify → analyze → validate → (maybe) act is
hard-coded in this state machine. No LLM decides what comes next.
This is the single most important harness decision.

The pipeline enforces trust boundary rules at every transition via
the gates in trust_boundary.py.
"""

from __future__ import annotations

import logging
import uuid
from enum import Enum
from dataclasses import dataclass, field
from typing import Any

from schemas.envelope import (
    MessageEnvelope,
    MessageType,
    TrustLevel,
    create_envelope,
)
from schemas.retrieval import RetrievalResult, Chunk
from schemas.injection import InjectionScanResult, InjectionVerdict, InjectionAction
from schemas.analysis import AnalysisResult, ActionType
from schemas.validation import ValidationVerdict
from schemas.tool_action import ToolActionRequest, ToolActionResult, ToolStatus
from orchestrator.trust_boundary import (
    assert_no_untrusted_to_tool_exec,
    assert_validated_before_privileged,
    assert_no_raw_text_in_tool_request,
    TrustBoundaryViolation,
)

from config import settings

logger = logging.getLogger(__name__)


class PipelineState(str, Enum):
    """Explicit states of the pipeline state machine."""
    RECEIVED = "received"
    RETRIEVING = "retrieving"
    CLASSIFYING = "classifying"
    ANALYZING = "analyzing"
    VALIDATING = "validating"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING_TOOL = "executing_tool"
    COMPLETE = "complete"
    FAILED = "failed"


# Hard-coded allowed transitions — no LLM can alter this graph
ALLOWED_TRANSITIONS: dict[PipelineState, set[PipelineState]] = {
    PipelineState.RECEIVED: {PipelineState.RETRIEVING},
    PipelineState.RETRIEVING: {PipelineState.CLASSIFYING, PipelineState.FAILED},
    PipelineState.CLASSIFYING: {PipelineState.ANALYZING, PipelineState.FAILED},
    PipelineState.ANALYZING: {PipelineState.VALIDATING, PipelineState.FAILED},
    PipelineState.VALIDATING: {
        PipelineState.COMPLETE,
        PipelineState.AWAITING_APPROVAL,
        PipelineState.FAILED,
    },
    PipelineState.AWAITING_APPROVAL: {
        PipelineState.EXECUTING_TOOL,
        PipelineState.COMPLETE,  # If rejected by human
        PipelineState.FAILED,
    },
    PipelineState.EXECUTING_TOOL: {PipelineState.COMPLETE, PipelineState.FAILED},
    PipelineState.COMPLETE: set(),  # Terminal
    PipelineState.FAILED: set(),  # Terminal
}


class InvalidTransition(Exception):
    """Raised when attempting an invalid state transition."""
    pass


@dataclass
class PipelineContext:
    """
    Working memory for a single pipeline run (per-turn).

    Lives only for the duration of one query. Persisted to audit log
    only — never promoted to anything longer-lived.
    """
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    turn_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: PipelineState = PipelineState.RECEIVED
    user_query: str = ""
    user_id: str = ""
    user_permitted_matters: list[str] = field(default_factory=list)

    # Working data — populated as the pipeline progresses
    retrieval_result: RetrievalResult | None = None
    scan_results: list[InjectionScanResult] = field(default_factory=list)
    clean_chunks: list[Chunk] = field(default_factory=list)
    analysis_result: AnalysisResult | None = None
    validation_verdict: ValidationVerdict | None = None
    tool_action_request: ToolActionRequest | None = None
    tool_action_result: ToolActionResult | None = None

    # Audit trail — every message envelope
    message_log: list[MessageEnvelope] = field(default_factory=list)
    error: str | None = None

    def transition_to(self, new_state: PipelineState) -> None:
        """
        Transition to a new state, enforcing the allowed-transitions graph.
        Raises InvalidTransition if the transition is not allowed.
        """
        allowed = ALLOWED_TRANSITIONS.get(self.state, set())
        if new_state not in allowed:
            raise InvalidTransition(
                f"Cannot transition from {self.state} to {new_state}. "
                f"Allowed transitions: {allowed}"
            )
        logger.info(
            f"[trace={self.trace_id}] Pipeline transition: "
            f"{self.state} → {new_state}"
        )
        self.state = new_state


class Pipeline:
    """
    Orchestrator — drives the pipeline as an explicit state machine.

    Each agent is injected as a callable. The pipeline controls:
    1. The order agents are called (fixed, not LLM-decided)
    2. Trust boundary enforcement at every transition
    3. Message envelope creation and audit logging
    """

    def __init__(
        self,
        retrieval_agent,
        injection_classifier,
        analysis_agent,
        validator_agent,
        tool_exec_agent=None,
        approval_gate=None,
        audit_logger=None,
    ):
        self.retrieval_agent = retrieval_agent
        self.injection_classifier = injection_classifier
        self.analysis_agent = analysis_agent
        self.validator_agent = validator_agent
        self.tool_exec_agent = tool_exec_agent
        self.approval_gate = approval_gate
        self.audit_logger = audit_logger

    async def run(
        self,
        user_query: str,
        user_id: str,
        user_permitted_matters: list[str],
        session_memory: dict | None = None,
    ) -> PipelineContext:
        """
        Run the full pipeline for a user query.
        Returns the PipelineContext with all working data and audit trail.
        """
        ctx = PipelineContext(
            user_query=user_query,
            user_id=user_id,
            user_permitted_matters=user_permitted_matters,
        )

        try:
            # Stage 1: Retrieve
            await self._stage_retrieve(ctx)

            # Stage 2: Classify (injection scan)
            await self._stage_classify(ctx)

            # Stage 3: Analyze
            await self._stage_analyze(ctx, session_memory)

            # Stage 4: Validate
            await self._stage_validate(ctx)

            # Stage 5: Tool execution (if requested and validated)
            await self._stage_tool_exec(ctx)

        except TrustBoundaryViolation as e:
            logger.error(f"[trace={ctx.trace_id}] Trust boundary violation: {e}")
            ctx.error = str(e)
            ctx.state = PipelineState.FAILED
        except Exception as e:
            logger.error(f"[trace={ctx.trace_id}] Pipeline error: {e}")
            ctx.error = str(e)
            ctx.state = PipelineState.FAILED

        return ctx

    async def _stage_retrieve(self, ctx: PipelineContext) -> None:
        """Stage 1: Retrieve chunks with ACL filtering."""
        ctx.transition_to(PipelineState.RETRIEVING)

        retrieval_result = await self.retrieval_agent.retrieve(
            query=ctx.user_query,
            user_permitted_matters=ctx.user_permitted_matters,
        )
        ctx.retrieval_result = retrieval_result

        # Create and log the envelope
        envelope = create_envelope(
            trace_id=ctx.trace_id,
            turn_id=ctx.turn_id,
            sender="retrieval-agent",
            recipient="orchestrator",
            message_type=MessageType.RETRIEVAL_RESULT,
            payload=retrieval_result.model_dump(),
            trust_level=TrustLevel.UNTRUSTED,  # Always untrusted — contains raw text
        )
        ctx.message_log.append(envelope)
        await self._log_to_audit(envelope)

        if not retrieval_result.chunks:
            ctx.error = "No chunks retrieved"
            ctx.transition_to(PipelineState.FAILED)

    async def _stage_classify(self, ctx: PipelineContext) -> None:
        """Stage 2: Run injection classifier on each chunk in isolated context."""
        if ctx.state == PipelineState.FAILED:
            return

        ctx.transition_to(PipelineState.CLASSIFYING)

        clean_chunks = []
        for chunk in ctx.retrieval_result.chunks:
            # Each chunk scanned independently — no shared context
            scan_result = await self.injection_classifier.scan(chunk)
            ctx.scan_results.append(scan_result)

            # Log each scan
            envelope = create_envelope(
                trace_id=ctx.trace_id,
                turn_id=ctx.turn_id,
                sender="injection-classifier",
                recipient="orchestrator",
                message_type=MessageType.INJECTION_SCAN_RESULT,
                payload=scan_result.model_dump(),
                trust_level=TrustLevel.UNTRUSTED,
            )
            ctx.message_log.append(envelope)
            await self._log_to_audit(envelope)

            # Handle suspicious chunk policy
            policy = getattr(settings, "suspicious_chunk_policy", "pass_through")

            if scan_result.action_taken == InjectionAction.PASSED_THROUGH:
                if policy == "quarantine" and scan_result.verdict == InjectionVerdict.SUSPICIOUS:
                    logger.info(
                        f"[trace={ctx.trace_id}] Quarantining suspicious chunk {chunk.chunk_id} per policy"
                    )
                    continue
                clean_chunks.append(chunk)

        ctx.clean_chunks = clean_chunks

        if not clean_chunks:
            ctx.error = "All chunks were blocked by injection classifier"
            ctx.transition_to(PipelineState.FAILED)

    async def _stage_analyze(
        self, ctx: PipelineContext, session_memory: dict | None
    ) -> None:
        """Stage 3: Toolless analysis agent reasons over clean chunks."""
        if ctx.state == PipelineState.FAILED:
            return

        ctx.transition_to(PipelineState.ANALYZING)

        analysis_result = await self.analysis_agent.analyze(
            user_query=ctx.user_query,
            chunks=ctx.clean_chunks,
            session_memory=session_memory,
        )

        policy = getattr(settings, "suspicious_chunk_policy", "pass_through")
        if policy == "flag_in_answer" and analysis_result and analysis_result.answer_draft:
            suspicious_ids = [
                s.chunk_id for s in ctx.scan_results
                if s.verdict == InjectionVerdict.SUSPICIOUS
            ]
            if suspicious_ids:
                banner = (
                    f"\n\n[WARNING: This answer draws on content flagged as potentially suspicious "
                    f"(chunk_id: {', '.join(suspicious_ids)}) — verify independently]"
                )
                analysis_result.answer_draft += banner

        ctx.analysis_result = analysis_result

        envelope = create_envelope(
            trace_id=ctx.trace_id,
            turn_id=ctx.turn_id,
            sender="analysis-agent",
            recipient="validator-agent",
            message_type=MessageType.ANALYSIS_RESULT,
            payload=analysis_result.model_dump(),
            trust_level=TrustLevel.UNTRUSTED,  # Still untrusted until validated
        )
        ctx.message_log.append(envelope)
        await self._log_to_audit(envelope)

    async def _stage_validate(self, ctx: PipelineContext) -> None:
        """Stage 4: Validator checks grounding and intent."""
        if ctx.state == PipelineState.FAILED:
            return

        ctx.transition_to(PipelineState.VALIDATING)

        validation_verdict = await self.validator_agent.validate(
            analysis_result=ctx.analysis_result,
            chunks=ctx.clean_chunks,
            user_query=ctx.user_query,
        )
        ctx.validation_verdict = validation_verdict

        envelope = create_envelope(
            trace_id=ctx.trace_id,
            turn_id=ctx.turn_id,
            sender="validator-agent",
            recipient="orchestrator",
            message_type=MessageType.VALIDATION_VERDICT,
            payload=validation_verdict.model_dump(),
            trust_level=TrustLevel(validation_verdict.trust_level_after_validation),
        )
        ctx.message_log.append(envelope)
        await self._log_to_audit(envelope)

        # Check if validation failed
        if not validation_verdict.grounded or validation_verdict.unauthorized_action_detected:
            ctx.error = (
                f"Validation failed: grounded={validation_verdict.grounded}, "
                f"unauthorized_action={validation_verdict.unauthorized_action_detected}"
            )
            ctx.transition_to(PipelineState.FAILED)
            return

        # Check if there are tool actions to execute
        has_tool_request = any(
            a.action_type == ActionType.TOOL_REQUEST
            for a in (ctx.analysis_result.proposed_actions or [])
        )

        if has_tool_request and self.tool_exec_agent:
            # Build tool action request
            action = next(
                a for a in ctx.analysis_result.proposed_actions
                if a.action_type == ActionType.TOOL_REQUEST
            )

            # Collect originating chunk IDs from claims
            originating_chunk_ids = []
            for claim in ctx.analysis_result.claims:
                originating_chunk_ids.extend(claim.supporting_chunk_ids)

            ctx.tool_action_request = ToolActionRequest(
                tool_name=action.tool_name,
                parameters={},
                requested_by="analysis-agent",
                validated_by="validator-agent",
                requires_human_approval=True,  # Always require approval for v1
                originating_chunk_ids=list(set(originating_chunk_ids)),
            )

            # --- TRUST BOUNDARY CHECK ---
            # Build envelope for tool request
            tool_envelope = create_envelope(
                trace_id=ctx.trace_id,
                turn_id=ctx.turn_id,
                sender="orchestrator",
                recipient="tool-exec-agent",
                message_type=MessageType.TOOL_ACTION_REQUEST,
                payload=ctx.tool_action_request.model_dump(),
                trust_level=TrustLevel(
                    validation_verdict.trust_level_after_validation
                ),
            )

            # Enforce trust boundary gates BEFORE routing to tool-exec
            assert_no_untrusted_to_tool_exec(tool_envelope)
            assert_validated_before_privileged(tool_envelope, validation_verdict)
            assert_no_raw_text_in_tool_request(
                ctx.tool_action_request.model_dump()
            )

            ctx.message_log.append(tool_envelope)
            await self._log_to_audit(tool_envelope)

            ctx.transition_to(PipelineState.AWAITING_APPROVAL)
        else:
            ctx.transition_to(PipelineState.COMPLETE)

    async def _stage_tool_exec(self, ctx: PipelineContext) -> None:
        """Stage 5: Tool execution with human approval gate."""
        if ctx.state != PipelineState.AWAITING_APPROVAL:
            return

        if not self.tool_exec_agent or not ctx.tool_action_request:
            ctx.transition_to(PipelineState.COMPLETE)
            return

        # Human approval gate
        if ctx.tool_action_request.requires_human_approval:
            if self.approval_gate:
                approval_id = await self.approval_gate.enqueue(
                    trace_id=ctx.trace_id,
                    tool_action_request=ctx.tool_action_request,
                )
                # In async mode, we return here and resume after approval
                # For now, the approval status is checked by the API layer
                return
            else:
                logger.warning(
                    f"[trace={ctx.trace_id}] No approval gate configured, "
                    f"but human approval is required. Blocking execution."
                )
                ctx.error = "Human approval required but no approval gate configured"
                ctx.transition_to(PipelineState.FAILED)
                return

        # Execute the tool (only reached if approval not required)
        await self._execute_tool(ctx)

    async def execute_approved_tool(self, ctx: PipelineContext) -> None:
        """Called after human approval to execute the tool."""
        ctx.transition_to(PipelineState.EXECUTING_TOOL)
        await self._execute_tool(ctx)

    async def _execute_tool(self, ctx: PipelineContext) -> None:
        """Actually execute the tool via the tool-exec agent."""
        if ctx.state not in (
            PipelineState.AWAITING_APPROVAL,
            PipelineState.EXECUTING_TOOL,
        ):
            ctx.transition_to(PipelineState.EXECUTING_TOOL)

        result = await self.tool_exec_agent.execute(ctx.tool_action_request)
        ctx.tool_action_result = result

        envelope = create_envelope(
            trace_id=ctx.trace_id,
            turn_id=ctx.turn_id,
            sender="tool-exec-agent",
            recipient="orchestrator",
            message_type=MessageType.TOOL_ACTION_RESULT,
            payload=result.model_dump(),
            trust_level=TrustLevel.TRUSTED,
        )
        ctx.message_log.append(envelope)
        await self._log_to_audit(envelope)

        ctx.transition_to(PipelineState.COMPLETE)

    async def _log_to_audit(self, envelope: MessageEnvelope) -> None:
        """Log an envelope to the audit store if one is configured."""
        if self.audit_logger:
            try:
                await self.audit_logger.log_message(envelope)
            except Exception as e:
                logger.error(
                    f"[trace={envelope.trace_id}] Failed to log to audit: {e}"
                )
