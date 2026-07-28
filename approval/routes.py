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
    """List pending human approvals."""
    if not _queue:
        return HTMLResponse("<h1>Approval queue not initialized</h1>", status_code=500)

    pending = _queue.get_pending()
    # Parse JSON fields for display
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
