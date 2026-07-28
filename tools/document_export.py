"""
Document export tool — write operation that requires human approval.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from tools.tool_registry import register_tool


@register_tool(
    name="document_export",
    description="Export analysis results to a file",
    parameter_schema={
        "filename": {"type": "string", "required": True, "description": "Export filename"},
        "content": {"type": "string", "required": True, "description": "Content to export"},
        "format": {"type": "string", "required": False, "description": "Export format (json/txt)"},
    },
    requires_human_approval=True,  # Write operation — requires approval
)
async def document_export(parameters: dict) -> str:
    """Export analysis to a file. Write operation — requires human approval."""
    filename = parameters.get("filename", "export.json")
    content = parameters.get("content", "")
    fmt = parameters.get("format", "json")

    export_dir = "./exports"
    os.makedirs(export_dir, exist_ok=True)

    filepath = os.path.join(export_dir, filename)

    if fmt == "json":
        with open(filepath, "w") as f:
            json.dump({
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "content": content,
            }, f, indent=2)
    else:
        with open(filepath, "w") as f:
            f.write(content)

    return f"Exported to {filepath}"
