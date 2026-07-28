"""
Approval routes — FastAPI endpoints for the human approval gate UI.
"""

from __future__ import annotations

import json
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from approval.queue import ApprovalQueue

router = APIRouter(prefix="/approvals", tags=["approvals"])
templates = Jinja2Templates(directory="approval/templates")

# Will be initialized by main.py
_queue: ApprovalQueue | None = None


def init_routes(queue: ApprovalQueue) -> None:
    """Initialize routes with the approval queue instance."""
    global _queue
    _queue = queue


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
    """Approve a pending tool action request."""
    if not _queue:
        return {"error": "Queue not initialized"}

    success = _queue.approve(approval_id, approver)
    return RedirectResponse(url="/approvals", status_code=303)


@router.post("/{approval_id}/reject")
async def reject_request(
    approval_id: str,
    approver: str = Form(default="admin"),
    reason: str = Form(default=""),
):
    """Reject a pending tool action request."""
    if not _queue:
        return {"error": "Queue not initialized"}

    success = _queue.reject(approval_id, approver, reason)
    return RedirectResponse(url="/approvals", status_code=303)
