"""
Retrieval agent — queries the vector store with ACL filtering.

This agent is in the UNTRUSTED ZONE:
- Has NO tool bindings (read-only by design)
- Returns chunks with trust_level: untrusted
- ACL filtering is structural — built into the query
"""

from __future__ import annotations

import logging

from config import settings
from schemas.retrieval import RetrievalResult
from vectorstore.store import VectorStore

logger = logging.getLogger(__name__)


class RetrievalAgent:
    """
    Queries the vector store with ACL-filtered search.

    Untrusted zone — no tools. ACL enforcement is in the query itself.
    """

    def __init__(self, vector_store: VectorStore | None = None, mistral_client=None):
        self.vector_store = vector_store or VectorStore()
        self._mistral_client = mistral_client

    def _get_mistral_client(self):
        if self._mistral_client is None:
            from mistralai.client import Mistral
            self._mistral_client = Mistral(api_key=settings.mistral_api_key)
        return self._mistral_client

    async def retrieve(
        self,
        query: str,
        user_permitted_matters: list[str],
        top_k: int | None = None,
    ) -> RetrievalResult:
        """
        Retrieve relevant chunks for a query, filtered by user's ACL.

        The ACL filter is part of the vector store query — unauthorized
        chunks are never retrieved in the first place.
        """
        top_k = top_k or settings.retrieval_top_k

        if not user_permitted_matters:
            logger.warning("User has no permitted matters — returning empty results")
            return RetrievalResult(query=query, chunks=[])

        # Embed the query
        try:
            import asyncio
            client = self._get_mistral_client()
            # Offload synchronous Mistral SDK call to thread pool
            response = await asyncio.to_thread(
                client.embeddings.create,
                model=settings.mistral_embed_model,
                inputs=[query],
            )
            query_embedding = response.data[0].embedding
        except Exception as e:
            logger.error(f"Failed to embed query: {e}")
            return RetrievalResult(query=query, chunks=[])

        # Query vector store with ACL filter
        chunks = self.vector_store.query(
            query_embedding=query_embedding,
            user_permitted_matters=user_permitted_matters,
            top_k=top_k,
        )

        logger.info(
            f"Retrieved {len(chunks)} chunks for query '{query[:50]}...' "
            f"(ACL: {user_permitted_matters})"
        )

        return RetrievalResult(query=query, chunks=chunks)
