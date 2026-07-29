"""
Configuration for the Legal RAG system.
Loads settings from environment variables / .env file.
"""

from typing import Literal
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Tavily Web Search API
    tavily_api_key: str = Field(
        default="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",
        description="Tavily Web Search API key",
    )

    # Mistral AI
    mistral_api_key: str = Field(..., description="Mistral API key — required, no default")
    mistral_large_model: str = Field(
        default="mistral-large-latest",
        description="Model for analysis and validation agents",
    )
    mistral_small_model: str = Field(
        default="mistral-small-latest",
        description="Model for injection classifier",
    )
    mistral_embed_model: str = Field(
        default="mistral-embed",
        description="Model for document embeddings",
    )

    # ChromaDB
    chroma_persist_dir: str = Field(
        default="./chroma_data",
        description="Directory for ChromaDB persistence",
    )

    # SQLite
    sqlite_db_path: str = Field(
        default="./audit.db",
        description="Path to SQLite database for audit log and approval queue",
    )

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")

    # Retrieval
    retrieval_top_k: int = Field(
        default=10, description="Number of chunks to retrieve from vector store"
    )
    analysis_top_k: int = Field(
        default=5, description="Number of top chunks to pass to analysis agent"
    )

    # Injection classifier
    injection_block_threshold: float = Field(
        default=0.8,
        description="Confidence threshold above which a chunk is blocked",
    )
    injection_suspicious_threshold: float = Field(
        default=0.4,
        description="Confidence threshold above which a chunk is flagged suspicious",
    )
    suspicious_chunk_policy: Literal["pass_through", "flag_in_answer", "quarantine"] = Field(
        default="pass_through",
        description="Policy for handling chunks flagged suspicious by injection classifier",
    )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


# Singleton instance
settings = Settings()
