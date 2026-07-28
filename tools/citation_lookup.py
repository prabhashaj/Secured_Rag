"""
Citation lookup tool — read-only tool for looking up document citations.

This is a read-only tool that does NOT require human approval.
"""

from __future__ import annotations

from tools.tool_registry import register_tool


@register_tool(
    name="citation_lookup",
    description="Look up a specific citation or page reference in a document",
    parameter_schema={
        "doc_id": {"type": "string", "required": True, "description": "Document ID"},
        "page_ref": {"type": "string", "required": False, "description": "Page reference"},
    },
    requires_human_approval=False,  # Read-only — no approval needed
)
async def citation_lookup(parameters: dict) -> str:
    """Look up a citation. Read-only operation."""
    doc_id = parameters.get("doc_id", "unknown")
    page_ref = parameters.get("page_ref", "")

    # In a real implementation, this would query the document store
    return f"Citation found: Document {doc_id}, {page_ref}"
