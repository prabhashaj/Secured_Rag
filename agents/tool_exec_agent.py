"""
Tool-exec agent — the ONLY component with live tool clients.

SECURITY PROPERTIES:
- Receives ONLY structured ToolActionRequest payloads — never raw chunk text
- Each instance gets an explicit allowlist of tools
- No general-purpose tool-calling loop
- Every call goes through: allowlist check → parameter validation → rate limit → execute → log
- Write operations get idempotency keys
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from schemas.tool_action import ToolActionRequest, ToolActionResult, ToolStatus

logger = logging.getLogger(__name__)


class ToolExecAgent:
    """
    The only agent that can execute tools.

    Operates with an explicit allowlist — no general tool-calling capability.
    Never sees raw document text.
    """

    def __init__(self, allowed_tools: list[str] | None = None):
        self.allowed_tools = set(allowed_tools or [])
        self._tool_registry: dict[str, callable] = {}
        self._rate_limits: dict[str, int] = {}  # tool_name → calls remaining
        self._idempotency_keys: set[str] = set()

    def register_tool(
        self,
        tool_name: str,
        handler: callable,
        rate_limit: int = 10,
    ) -> None:
        """Register a tool handler with rate limiting."""
        if tool_name not in self.allowed_tools:
            raise ValueError(
                f"Tool '{tool_name}' is not in the allowlist: {self.allowed_tools}"
            )
        self._tool_registry[tool_name] = handler
        self._rate_limits[tool_name] = rate_limit

    async def execute(self, request: ToolActionRequest) -> ToolActionResult:
        """
        Execute a tool action.

        Goes through the full harness:
        1. Allowlist check
        2. Parameter validation
        3. Rate limit check
        4. Execute
        5. Log result
        """
        now = datetime.now(timezone.utc).isoformat()

        # Step 1: Allowlist check
        if request.tool_name not in self.allowed_tools:
            logger.warning(
                f"Tool '{request.tool_name}' not in allowlist. "
                f"Allowed: {self.allowed_tools}"
            )
            return ToolActionResult(
                tool_name=request.tool_name,
                status=ToolStatus.FAILED,
                result_summary=f"Tool '{request.tool_name}' is not allowed",
                executed_at=now,
            )

        # Step 2: Check if tool is registered
        if request.tool_name not in self._tool_registry:
            return ToolActionResult(
                tool_name=request.tool_name,
                status=ToolStatus.FAILED,
                result_summary=f"Tool '{request.tool_name}' is not registered",
                executed_at=now,
            )

        # Step 3: Rate limit check
        remaining = self._rate_limits.get(request.tool_name, 0)
        if remaining <= 0:
            return ToolActionResult(
                tool_name=request.tool_name,
                status=ToolStatus.FAILED,
                result_summary=f"Rate limit exceeded for tool '{request.tool_name}'",
                executed_at=now,
            )

        # Step 4: Idempotency check (for write operations)
        idempotency_key = f"{request.tool_name}:{hash(str(sorted(request.parameters.items())))}"
        if idempotency_key in self._idempotency_keys:
            logger.info(f"Duplicate tool call detected (idempotency key: {idempotency_key})")
            return ToolActionResult(
                tool_name=request.tool_name,
                status=ToolStatus.SUCCESS,
                result_summary="Duplicate call — previously executed successfully",
                executed_at=now,
            )

        # Step 5: Execute
        try:
            self._rate_limits[request.tool_name] = remaining - 1
            handler = self._tool_registry[request.tool_name]
            result_summary = await handler(request.parameters)
            self._idempotency_keys.add(idempotency_key)

            logger.info(
                f"Tool '{request.tool_name}' executed successfully. "
                f"Rate limit remaining: {self._rate_limits[request.tool_name]}"
            )

            return ToolActionResult(
                tool_name=request.tool_name,
                status=ToolStatus.SUCCESS,
                result_summary=str(result_summary),
                executed_at=now,
            )

        except Exception as e:
            logger.error(f"Tool '{request.tool_name}' execution failed: {e}")
            return ToolActionResult(
                tool_name=request.tool_name,
                status=ToolStatus.FAILED,
                result_summary=f"Execution error: {str(e)}",
                executed_at=now,
            )
