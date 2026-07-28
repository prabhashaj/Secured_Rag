"""
ChromaDB vector store wrapper with ACL-filtered queries.

ACL enforcement happens IN THE QUERY ITSELF — not post-filtered.
A user's permitted matter IDs are injected into the ChromaDB where-filter,
so unauthorized chunks are never retrieved in the first place.
"""

from __future__ import annotations

import logging
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from config import settings
from schemas.retrieval import Chunk, ConfidentialityTag

logger = logging.getLogger(__name__)

# Embedding dimension for Mistral Embed
EMBEDDING_DIMENSION = 1024


class VectorStore:
    """ChromaDB wrapper with mandatory ACL filtering at query time."""

    def __init__(self, persist_dir: str | None = None, collection_name: str = "legal_docs"):
        self.persist_dir = persist_dir or settings.chroma_persist_dir
        self.collection_name = collection_name
        self._client: Optional[chromadb.ClientAPI] = None
        self._collection = None

    def _get_client(self) -> chromadb.ClientAPI:
        if self._client is None:
            self._client = chromadb.PersistentClient(
                path=self.persist_dir,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        return self._client

    def _get_collection(self):
        if self._collection is None:
            client = self._get_client()
            self._collection = client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def add_chunks(
        self,
        chunk_ids: list[str],
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
    ) -> None:
        """
        Add pre-embedded chunks to the vector store.

        Each chunk's metadata MUST include:
        - matter_id: for ACL filtering
        - source_doc_id: for provenance
        - source_doc_title: for display
        - confidentiality_tag: for sensitivity tracking
        - page_ref: for citation
        """
        collection = self._get_collection()
        collection.add(
            ids=chunk_ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )
        logger.info(f"Added {len(chunk_ids)} chunks to vector store")

    def query(
        self,
        query_embedding: list[float],
        user_permitted_matters: list[str],
        top_k: int = 10,
    ) -> list[Chunk]:
        """
        Query the vector store with ACL filtering BUILT INTO THE QUERY.

        The where-filter ensures only chunks from permitted matters are
        returned. This is the structural ACL enforcement — a user cannot
        retrieve chunks from matters they don't have access to, regardless
        of what they ask for or what an injection instructs.
        """
        if not user_permitted_matters:
            logger.warning("No permitted matters — returning empty results")
            return []

        collection = self._get_collection()

        # ACL filter is part of the query — not post-filtering
        where_filter = {
            "matter_id": {"$in": user_permitted_matters}
        }

        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=min(top_k, collection.count()) if collection.count() > 0 else top_k,
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            logger.error(f"Vector store query failed: {e}")
            return []

        if not results or not results.get("ids") or not results["ids"][0]:
            return []

        chunks = []
        for i, chunk_id in enumerate(results["ids"][0]):
            metadata = results["metadatas"][0][i] if results.get("metadatas") else {}
            text = results["documents"][0][i] if results.get("documents") else ""
            # ChromaDB returns distances, convert to similarity score (cosine)
            distance = results["distances"][0][i] if results.get("distances") else 0.0
            similarity = max(0.0, min(1.0, 1.0 - distance))

            try:
                conf_tag = ConfidentialityTag(
                    metadata.get("confidentiality_tag", "public")
                )
            except ValueError:
                conf_tag = ConfidentialityTag.PUBLIC

            chunk = Chunk(
                chunk_id=chunk_id,
                source_doc_id=metadata.get("source_doc_id", "unknown"),
                source_doc_title=metadata.get("source_doc_title", "Unknown"),
                matter_id=metadata.get("matter_id", "unknown"),
                confidentiality_tag=conf_tag,
                text=text,
                embedding_score=round(similarity, 4),
                page_ref=metadata.get("page_ref", ""),
                acl_check_passed=True,  # Passed because the query filter allowed it
            )
            chunks.append(chunk)

        # Sort by embedding score (highest first)
        chunks.sort(key=lambda c: c.embedding_score, reverse=True)
        return chunks

    def delete_collection(self) -> None:
        """Delete the entire collection (for testing)."""
        client = self._get_client()
        try:
            client.delete_collection(self.collection_name)
            self._collection = None
        except Exception:
            pass

    def count(self) -> int:
        """Return the number of chunks in the collection."""
        try:
            return self._get_collection().count()
        except Exception:
            return 0

    def get_all_documents(self) -> list[dict]:
        """Get unique documents summary stored in the vector store."""
        try:
            collection = self._get_collection()
            if collection.count() == 0:
                return []
            res = collection.get(include=["metadatas"])
            if not res or not res.get("metadatas"):
                return []

            docs_map: dict[str, dict] = {}
            for meta in res["metadatas"]:
                if not meta:
                    continue
                doc_id = meta.get("source_doc_id", "unknown")
                if doc_id not in docs_map:
                    docs_map[doc_id] = {
                        "source_doc_id": doc_id,
                        "source_doc_title": meta.get("source_doc_title", "Untitled Document"),
                        "matter_id": meta.get("matter_id", "General"),
                        "confidentiality_tag": meta.get("confidentiality_tag", "public"),
                        "chunks_count": 0,
                        "injection_flagged": False,
                    }
                docs_map[doc_id]["chunks_count"] += 1
                if meta.get("injection_flagged") in ("True", True):
                    docs_map[doc_id]["injection_flagged"] = True

            return list(docs_map.values())
        except Exception as e:
            logger.error(f"Failed to fetch documents from vector store: {e}")
            return []

    def delete_document(self, source_doc_id: str) -> bool:
        """Delete all chunks belonging to a specific source_doc_id."""
        try:
            collection = self._get_collection()
            collection.delete(where={"source_doc_id": source_doc_id})
            return True
        except Exception as e:
            logger.error(f"Failed to delete document {source_doc_id}: {e}")
            return False
