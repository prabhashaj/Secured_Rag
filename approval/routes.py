"""
Approval routes — FastAPI endpoints for the human approval gate UI.
"""

from __future__ import annotations

import json
from typing import Any
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from approval.queue import ApprovalQueue
from schemas.tool_action import ToolActionResult, ToolStatus
from orchestrator.pipeline import PipelineState

router = APIRouter(prefix="/approvals", tags=["approvals"])
templates = Jinja2Templates(directory="approval/templates")

# Globals initialized by main.py
_queue: ApprovalQueue | None = None
_pipeline: Any | None = None
_context_store: Any | None = None


def init_routes(
    queue: ApprovalQueue,
    pipeline: Any | None = None,
    context_store: Any | None = None,
) -> None:
    """Initialize routes with approval queue, pipeline, and context store instances."""
    global _queue, _pipeline, _context_store
    _queue = queue
    _pipeline = pipeline
    _context_store = context_store


@router.get("", response_class=HTMLResponse)
async def list_approvals(request: Request):
    """List pending human approvals (HTML template)."""
    if not _queue:
        return HTMLResponse("<h1>Approval queue not initialized</h1>", status_code=500)

    pending = _queue.get_pending()
    for item in pending:
        try:
            item["parameters_parsed"] = json.loads(item.get("parameters", "{}"))
        except (json.JSONDecodeError, TypeError):
            item["parameters_parsed"] = {}
        try:
            item["chunk_ids_parsed"] = json.loads(
                item.get("originating_chunk_ids", "[]")
            )
        except (json.JSONDecodeError, TypeError):
            item["chunk_ids_parsed"] = []

    return templates.TemplateResponse(
        "approval.html",
        {"request": request, "approvals": pending},
    )


@router.get("/api/pending", response_class=JSONResponse)
async def list_pending_approvals_api():
    """List pending human approvals as JSON for React frontend UI."""
    if not _queue:
        return JSONResponse(content=[])

    pending = _queue.get_pending()
    results = []
    for item in pending:
        item_dict = dict(item)
        try:
            item_dict["parameters_parsed"] = json.loads(item_dict.get("parameters", "{}"))
        except (json.JSONDecodeError, TypeError):
            item_dict["parameters_parsed"] = {}
        try:
            item_dict["chunk_ids_parsed"] = json.loads(
                item_dict.get("originating_chunk_ids", "[]")
            )
        except (json.JSONDecodeError, TypeError):
            item_dict["chunk_ids_parsed"] = []
        results.append(item_dict)

    return JSONResponse(content=results)


@router.post("/api/trace/{trace_id}/approve", response_class=JSONResponse)
async def approve_by_trace_api(trace_id: str, approver: str = "admin"):
    """Approve pending tool action by trace_id and execute live tool."""
    record = None
    if _queue:
        records = _queue.get_by_trace(trace_id)
        if records:
            record = records[-1]
            _queue.approve(record["approval_id"], approver)

    ctx = _context_store.get(trace_id) if _context_store else None

    # Fallback context reconstruction from SQLite if context not in RAM
    if not ctx and record:
        from schemas.tool_action import ToolActionRequest
        from orchestrator.pipeline import PipelineContext, PipelineState
        params_parsed = json.loads(record.get("parameters", "{}"))
        ctx = PipelineContext(
            user_query=params_parsed.get("query", "Legal web search"),
            user_id="default_user",
            user_permitted_matters=["Matter_101"],
            trace_id=trace_id,
        )
        ctx.tool_action_request = ToolActionRequest(
            tool_name=record.get("tool_name", "legal_web_search"),
            parameters=params_parsed,
            requested_by=record.get("requested_by", "analysis-agent"),
            validated_by=record.get("validated_by", "validator-agent"),
            requires_human_approval=True,
            originating_chunk_ids=json.loads(record.get("originating_chunk_ids", "[]")),
        )
        ctx.transition_to(PipelineState.AWAITING_APPROVAL)

    if ctx and _pipeline:
        await _pipeline.execute_approved_tool(ctx)
        if _context_store:
            _context_store.save(ctx)

        out = ctx.tool_action_result.output if ctx.tool_action_result else "Tool execution completed."
        answer_markdown = (
            f"### Live Legal Web Search Results (Tavily API)\n\n"
            f"{out}\n\n"
            f"*Verified and executed via Human-in-the-Loop compliance approval.*"
        )

        return JSONResponse(content={
            "status": "approved",
            "trace_id": trace_id,
            "output": out,
            "answer": answer_markdown,
        })

    return JSONResponse(status_code=404, content={"error": f"Trace '{trace_id}' could not be executed"})


@router.post("/api/{approval_id}/approve", response_class=JSONResponse)
async def approve_request_api(approval_id: str, approver: str = "admin"):
    """JSON API endpoint to approve a pending tool request."""
    if not _queue:
        return JSONResponse(status_code=500, content={"error": "Queue not initialized"})

    record = _queue.get_by_id(approval_id)
    if not record:
        return JSONResponse(
            status_code=404, content={"error": f"Approval request '{approval_id}' not found"}
        )

    success = _queue.approve(approval_id, approver)
    if not success:
        return JSONResponse(
            status_code=400,
            content={"error": f"Failed to approve request '{approval_id}'"},
        )

    trace_id = record["trace_id"]
    ctx = _context_store.get(trace_id) if _context_store else None

    if ctx and _pipeline:
        await _pipeline.execute_approved_tool(ctx)
        if _context_store:
            _context_store.save(ctx)
        out = ctx.tool_action_result.output if ctx.tool_action_result else "Tool execution completed."
        return JSONResponse(content={"status": "approved", "output": out, "trace_id": trace_id})

    return JSONResponse(content={"status": "approved", "trace_id": trace_id})


@router.post("/api/{approval_id}/reject", response_class=JSONResponse)
async def reject_request_api(approval_id: str, approver: str = "admin", reason: str = ""):
    """JSON API endpoint to reject a pending tool request."""
    if not _queue:
        return JSONResponse(status_code=500, content={"error": "Queue not initialized"})

    record = _queue.get_by_id(approval_id)
    if not record:
        return JSONResponse(
            status_code=404, content={"error": f"Approval request '{approval_id}' not found"}
        )

    success = _queue.reject(approval_id, approver, reason)
    if not success:
        return JSONResponse(
            status_code=400,
            content={"error": f"Failed to reject request '{approval_id}'"},
        )

    trace_id = record["trace_id"]
    ctx = _context_store.get(trace_id) if _context_store else None

    if ctx:
        tool_name = (
            ctx.tool_action_request.tool_name
            if ctx.tool_action_request
            else "unknown"
        )
        from datetime import datetime, timezone
        ctx.tool_action_result = ToolActionResult(
            tool_name=tool_name,
            status=ToolStatus.REJECTED_BY_HUMAN,
            result_summary=f"Rejected by human ({approver}): {reason}",
            executed_at=datetime.now(timezone.utc).isoformat(),
        )
        ctx.transition_to(PipelineState.COMPLETE)
        if _context_store:
            _context_store.save(ctx)

    return JSONResponse(content={"status": "rejected", "trace_id": trace_id})


@router.post("/{approval_id}/approve")
async def approve_request(approval_id: str, approver: str = Form(default="admin")):
    """Approve a pending tool action request and resume pipeline execution."""
    if not _queue:
        return JSONResponse(status_code=500, content={"error": "Queue not initialized"})

    record = _queue.get_by_id(approval_id)
    if not record:
        return JSONResponse(
            status_code=404, content={"error": f"Approval request '{approval_id}' not found"}
        )

    success = _queue.approve(approval_id, approver)
    if not success:
        return JSONResponse(
            status_code=400,
            content={"error": f"Failed to approve request '{approval_id}' (may already be resolved)"},
        )

    trace_id = record["trace_id"]
    ctx = _context_store.get(trace_id) if _context_store else None

    if not ctx:
        return JSONResponse(
            status_code=404,
            content={"error": f"Pipeline context not found for trace_id '{trace_id}'"},
        )

    if _pipeline:
        await _pipeline.execute_approved_tool(ctx)

    if _context_store:
        _context_store.save(ctx)

    return RedirectResponse(url="/approvals", status_code=303)


@router.post("/{approval_id}/reject")
async def reject_request(
    approval_id: str,
    approver: str = Form(default="admin"),
    reason: str = Form(default=""),
):
    """Reject a pending tool action request and finalize pipeline state."""
    if not _queue:
        return JSONResponse(status_code=500, content={"error": "Queue not initialized"})

    record = _queue.get_by_id(approval_id)
    if not record:
        return JSONResponse(
            status_code=404, content={"error": f"Approval request '{approval_id}' not found"}
        )

    success = _queue.reject(approval_id, approver, reason)
    if not success:
        return JSONResponse(
            status_code=400,
            content={"error": f"Failed to reject request '{approval_id}' (may already be resolved)"},
        )

    trace_id = record["trace_id"]
    ctx = _context_store.get(trace_id) if _context_store else None

    if ctx:
        tool_name = (
            ctx.tool_action_request.tool_name
            if ctx.tool_action_request
            else "unknown"
        )
        from datetime import datetime, timezone
        ctx.tool_action_result = ToolActionResult(
            tool_name=tool_name,
            status=ToolStatus.REJECTED_BY_HUMAN,
            result_summary=f"Rejected by human ({approver}): {reason}",
            executed_at=datetime.now(timezone.utc).isoformat(),
        )
        ctx.transition_to(PipelineState.COMPLETE)
        if _context_store:
            _context_store.save(ctx)

    return RedirectResponse(url="/approvals", status_code=303)
