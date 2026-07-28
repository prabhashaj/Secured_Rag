"""
Tool registry — defines available tools with their schemas and handlers.

Each tool has:
- A name (must match the allowlist)
- A parameter schema
- Whether it requires human approval
- A handler function
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Any


@dataclass
class ToolDefinition:
    """Definition of a registered tool."""
    name: str
    description: str
    parameter_schema: dict[str, Any]
    requires_human_approval: bool
    handler: Callable


# Global tool registry
TOOL_DEFINITIONS: dict[str, ToolDefinition] = {}


def register_tool(
    name: str,
    description: str,
    parameter_schema: dict[str, Any],
    requires_human_approval: bool = True,
) -> Callable:
    """Decorator to register a tool handler."""
    def decorator(func: Callable) -> Callable:
        TOOL_DEFINITIONS[name] = ToolDefinition(
            name=name,
            description=description,
            parameter_schema=parameter_schema,
            requires_human_approval=requires_human_approval,
            handler=func,
        )
        return func
    return decorator


def get_tool(name: str) -> ToolDefinition | None:
    """Get a tool definition by name."""
    return TOOL_DEFINITIONS.get(name)


def list_tools() -> list[str]:
    """List all registered tool names."""
    return list(TOOL_DEFINITIONS.keys())


def validate_parameters(tool_name: str, parameters: dict) -> bool:
    """Validate parameters against the tool's schema."""
    tool = get_tool(tool_name)
    if not tool:
        return False

    required_params = {
        k for k, v in tool.parameter_schema.items()
        if isinstance(v, dict) and v.get("required", False)
    }

    return required_params.issubset(set(parameters.keys()))
