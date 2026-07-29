"""
Query Result Cache — Short-TTL in-memory cache for repeated/similar legal research queries.

Keyed on (user_id, tuple(sorted(permitted_matters)), normalized_query) with default 60-second TTL.
Prevents redundant LLM synthesis and vector retrievals within active legal chat sessions.
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class QueryResultCache:
    """In-memory query result cache with per-item TTL expiration."""

    def __init__(self, default_ttl_seconds: float = 60.0):
        self.default_ttl = default_ttl_seconds
        self._cache: dict[tuple[str, tuple[str, ...], str], tuple[float, Any]] = {}

    def _make_key(self, user_id: str, permitted_matters: list[str], query: str) -> tuple[str, tuple[str, ...], str]:
        normalized_query = query.strip().lower()
        matters_key = tuple(sorted(permitted_matters))
        return (user_id, matters_key, normalized_query)

    def get(self, user_id: str, permitted_matters: list[str], query: str) -> Any | None:
        """Retrieve cached query response if present and unexpired."""
        key = self._make_key(user_id, permitted_matters, query)
        if key not in self._cache:
            return None

        expiry_time, data = self._cache[key]
        if time.time() > expiry_time:
            del self._cache[key]
            return None

        logger.info(f"Cache HIT for user '{user_id}' query='{query[:50]}'")
        return data

    def set(
        self,
        user_id: str,
        permitted_matters: list[str],
        query: str,
        value: Any,
        ttl_seconds: float | None = None,
    ) -> None:
        """Store query response in cache with TTL."""
        key = self._make_key(user_id, permitted_matters, query)
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        expiry_time = time.time() + ttl
        self._cache[key] = (expiry_time, value)

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()


# Global query result cache instance
query_cache = QueryResultCache(default_ttl_seconds=60.0)
