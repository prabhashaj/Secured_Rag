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
from schemas.analysis import AnalysisResult, ActionType, ProposedAction
from schemas.validation import ValidationVerdict
from schemas.tool_action import ToolActionRequest, ToolActionResult, ToolStatus
from orchestrator.query_router import route_query, ExecutionPath
from orchestrator.trust_boundary import (
    assert_no_untrusted_to_tool_exec,
    assert_validated_before_privileged,
    assert_no_raw_text_in_tool_request,
    TrustBoundaryViolation,
)

from agents.web_retrieval_agent import WebRetrievalAgent
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
    PipelineState.RECEIVED: {PipelineState.RETRIEVING, PipelineState.CLASSIFYING},
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
    execution_path: str = "pipeline"

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
    def __init__(
        self,
        retrieval_agent,
        injection_classifier,
        analysis_agent,
        validator_agent,
        tool_exec_agent=None,
        web_retrieval_agent=None,
        approval_gate=None,
        audit_logger=None,
    ):
        self.retrieval_agent = retrieval_agent
        self.injection_classifier = injection_classifier
        self.analysis_agent = analysis_agent
        self.validator_agent = validator_agent
        self.tool_exec_agent = tool_exec_agent
        self.web_retrieval_agent = web_retrieval_agent or WebRetrievalAgent()
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

        # Router decides execution path: PIPELINE, DIRECT_LLM, or WEBSEARCH_LLM
        decision = route_query(user_query)
        ctx.execution_path = decision.path.value
        logger.info(
            f"[trace={ctx.trace_id}] Router decision: path={ctx.execution_path}, "
            f"reasoning='{decision.reasoning}'"
        )

        # Log ROUTER_DECISION envelope to audit trail
        router_envelope = create_envelope(
            trace_id=ctx.trace_id,
            turn_id=ctx.turn_id,
            sender="query-router",
            recipient="orchestrator",
            message_type=MessageType.ROUTER_DECISION,
            payload={"execution_path": ctx.execution_path, "reasoning": decision.reasoning},
            trust_level=TrustLevel.TRUSTED,
        )
        ctx.message_log.append(router_envelope)
        await self._log_to_audit(router_envelope)

        try:
            if decision.path == ExecutionPath.DIRECT_LLM:
                # Path 2: DIRECT_LLM — Scanned by InjectionClassifier -> Analyzed by AnalysisAgent -> Validated
                ctx.clean_chunks = []
                await self._stage_classify(ctx)
                await self._stage_analyze(ctx, session_memory)
                await self._stage_validate(ctx)

            elif decision.path == ExecutionPath.WEBSEARCH_LLM:
                # Path 3: WEBSEARCH_LLM — External Web Retrieval -> Scanned -> LLM Synthesized Response -> Validated -> COMPLETE
                web_chunks = await self.web_retrieval_agent.search(ctx.user_query)

                ctx.retrieval_result = RetrievalResult(
                    query=ctx.user_query,
                    chunks=web_chunks,
                )

                # Audit log web retrieval event
                retrieval_envelope = create_envelope(
                    trace_id=ctx.trace_id,
                    turn_id=ctx.turn_id,
                    sender="web-retrieval-agent",
                    recipient="orchestrator",
                    message_type=MessageType.RETRIEVAL_RESULT,
                    payload=ctx.retrieval_result.model_dump(),
                    trust_level=TrustLevel.UNTRUSTED,
                )
                ctx.message_log.append(retrieval_envelope)
                await self._log_to_audit(retrieval_envelope)

                await self._stage_classify(ctx)
                if ctx.state == PipelineState.FAILED or not ctx.clean_chunks:
                    if not ctx.error:
                        ctx.error = "Web search content failed security scan (Malicious / Injection payload detected)."
                    if ctx.state != PipelineState.FAILED:
                        ctx.transition_to(PipelineState.FAILED)
                    return ctx

                await self._stage_analyze(ctx, session_memory)
                await self._stage_validate(ctx)

            else:
                # Path 1: PIPELINE — Internal Vector RAG Pipeline over matter docs
                await self._stage_retrieve(ctx)
                await self._stage_classify(ctx)
                await self._stage_analyze(ctx, session_memory)
                await self._stage_validate(ctx)
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

    async def _stage_classify(self, ctx: PipelineContext) -> None:
        """Stage 2: Run injection classifier on user query & each chunk in isolated context.

        Performance optimizations:
        - User query: heuristic-only fast path (LLM scan only if heuristics flag suspicious)
        - Document chunks: scanned in parallel via asyncio.gather
        """
        import asyncio

        if ctx.state == PipelineState.FAILED:
            return

        ctx.transition_to(PipelineState.CLASSIFYING)

        # 1. Scan user query — heuristic fast path (skip LLM layer for clean queries)
        query_chunk = Chunk(
            chunk_id="user_query",
            source_doc_id="input_prompt",
            source_doc_title="User Input Query",
            matter_id="system",
            confidentiality_tag="public",
            text=ctx.user_query,
            embedding_score=1.0,
            page_ref="p1",
            acl_check_passed=True,
        )
        # heuristic_only=True: skips LLM round-trip when heuristics pass clean (~500-1500ms saved)
        # Suspicious results still escalate to full LLM scan inside scan()
        query_scan = await self.injection_classifier.scan(query_chunk, heuristic_only=True)
        ctx.scan_results.append(query_scan)

        if query_scan.verdict == InjectionVerdict.BLOCKED:
            logger.warning(f"[trace={ctx.trace_id}] User query BLOCKED by injection classifier")
            ctx.error = "User query failed security scan (Prompt Injection / Adversarial Payload detected)."
            ctx.transition_to(PipelineState.FAILED)
            return

        # 2. Scan retrieved document chunks — PARALLEL (asyncio.gather)
        clean_chunks = []
        if ctx.retrieval_result and ctx.retrieval_result.chunks:
            chunks_to_scan = ctx.retrieval_result.chunks

            # Fire all chunk scans in parallel
            scan_tasks = [self.injection_classifier.scan(chunk) for chunk in chunks_to_scan]
            scan_results = await asyncio.gather(*scan_tasks, return_exceptions=True)

            policy = getattr(settings, "suspicious_chunk_policy", "pass_through")

            for chunk, scan_result in zip(chunks_to_scan, scan_results):
                # Handle any scan exceptions gracefully — treat as suspicious
                if isinstance(scan_result, Exception):
                    logger.error(f"[trace={ctx.trace_id}] Scan failed for {chunk.chunk_id}: {scan_result}")
                    scan_result = InjectionScanResult(
                        chunk_id=chunk.chunk_id,
                        verdict=InjectionVerdict.SUSPICIOUS,
                        signals=[],
                        confidence=0.3,
                        action_taken=InjectionAction.PASSED_THROUGH,
                    )

                ctx.scan_results.append(scan_result)

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

                if scan_result.action_taken == InjectionAction.PASSED_THROUGH:
                    if policy == "quarantine" and scan_result.verdict == InjectionVerdict.SUSPICIOUS:
                        logger.info(
                            f"[trace={ctx.trace_id}] Quarantining suspicious chunk {chunk.chunk_id} per policy"
                        )
                        continue
                    clean_chunks.append(chunk)

        ctx.clean_chunks = clean_chunks

        if not clean_chunks and ctx.retrieval_result and len(ctx.retrieval_result.chunks) > 0:
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
                parameters={"query": ctx.user_query},
                requested_by="analysis-agent",
                validated_by="validator-agent",
                requires_human_approval=True,
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

            if ctx.tool_action_request.requires_human_approval:
                ctx.transition_to(PipelineState.AWAITING_APPROVAL)
            else:
                ctx.transition_to(PipelineState.EXECUTING_TOOL)
                await self._execute_tool(ctx)
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
