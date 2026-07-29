"""
Document ingestion — chunks documents and embeds them via Mistral Embed.

Includes ingestion-time injection scanning (heuristic patterns) to
flag suspicious content before it enters the vector store.
"""

from __future__ import annotations

import logging
import re
import uuid

from config import settings

logger = logging.getLogger(__name__)

# Injection patterns for ingestion-time scanning
INJECTION_PATTERNS = [
    # Instruction-like phrases
    (r"(?i)ignore\s+(all\s+)?(prior|previous|above)\s+instructions?", "instruction_like_phrase"),
    (r"(?i)you\s+are\s+now\s+a?\s*", "instruction_like_phrase"),
    (r"(?i)your\s+new\s+(role|instructions?|task)", "instruction_like_phrase"),
    (r"(?i)disregard\s+(all\s+)?(prior|above|previous)", "instruction_like_phrase"),
    (r"(?i)forget\s+(everything|all|your)\s+(you|instructions?|training)", "instruction_like_phrase"),
    # Role-play markers
    (r"(?i)pretend\s+(you\s+are|to\s+be)", "role_play_marker"),
    (r"(?i)act\s+as\s+(if|a|an|the)", "role_play_marker"),
    (r"(?i)you\s+must\s+(always|never|now)", "role_play_marker"),
    # System prompt markers
    (r"(?i)(^|\n)\s*system\s*:", "system_prompt_marker"),
    (r"(?i)###\s*system", "system_prompt_marker"),
    (r"(?i)<<\s*SYS\s*>>", "system_prompt_marker"),
    (r"(?i)\[INST\]", "system_prompt_marker"),
    # XML escape attempts
    (r"</document_chunk>", "xml_escape_attempt"),
    (r"</text_to_classify>", "xml_escape_attempt"),
    (r"</session_context>", "xml_escape_attempt"),
    # Prompt leak attempts
    (r"(?i)reveal\s+(your|the)\s+(system\s+)?(prompt|instructions?)", "prompt_leak_attempt"),
    (r"(?i)what\s+(are|is)\s+your\s+(system\s+)?(prompt|instructions?)", "prompt_leak_attempt"),
]

# Hidden Unicode patterns
UNICODE_PATTERNS = [
    (r"[\u200b\u200c\u200d\u2060\ufeff]", "hidden_unicode"),  # Zero-width chars
    (r"[\u202a-\u202e\u2066-\u2069]", "hidden_unicode"),  # Bidi overrides
]


def scan_for_injection_patterns(text: str) -> list[dict]:
    """
    Quick heuristic scan for injection patterns.
    Returns list of {pattern_type, match} dicts.
    Used at both ingestion-time and by the injection classifier.
    """
    findings = []
    for pattern, signal_type in INJECTION_PATTERNS:
        matches = re.findall(pattern, text)
        if matches:
            findings.append({
                "signal_type": signal_type,
                "pattern": pattern,
                "match_count": len(matches),
            })

    for pattern, signal_type in UNICODE_PATTERNS:
        matches = re.findall(pattern, text)
        if matches:
            findings.append({
                "signal_type": signal_type,
                "pattern": "unicode",
                "match_count": len(matches),
            })

    return findings


def chunk_document(
    text: str,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
) -> list[dict]:
    """
    Split a document into overlapping chunks.
    Returns list of {text, start_char, end_char, page_ref} dicts.
    """
    chunks = []
    # Simple paragraph-based chunking with fallback to character-based
    paragraphs = text.split("\n\n")

    current_chunk = ""
    current_start = 0
    char_pos = 0
    page_num = 1

    for para in paragraphs:
        # Track page breaks
        if "\f" in para:
            page_num += 1

        if len(current_chunk) + len(para) + 2 <= chunk_size:
            current_chunk += para + "\n\n"
        else:
            if current_chunk.strip():
                chunks.append({
                    "text": current_chunk.strip(),
                    "start_char": current_start,
                    "end_char": current_start + len(current_chunk),
                    "page_ref": f"p.{page_num}",
                })

            # Overlap: keep the last chunk_overlap characters
            if current_chunk and chunk_overlap > 0:
                overlap_text = current_chunk[-chunk_overlap:]
                current_chunk = overlap_text + para + "\n\n"
            else:
                current_chunk = para + "\n\n"
            current_start = char_pos

        char_pos += len(para) + 2

    # Don't forget the last chunk
    if current_chunk.strip():
        chunks.append({
            "text": current_chunk.strip(),
            "start_char": current_start,
            "end_char": current_start + len(current_chunk),
            "page_ref": f"p.{page_num}",
        })

    return chunks


async def embed_texts(texts: list[str], client=None) -> list[list[float]]:
    """
    Embed texts using the Mistral Embed API.
    If no client is provided, creates one.
    """
    if client is None:
        from mistralai.client import Mistral
        client = Mistral(api_key=settings.mistral_api_key)

    response = client.embeddings.create(
        model=settings.mistral_embed_model,
        inputs=texts,
    )
    return [item.embedding for item in response.data]


async def ingest_document(
    text: str,
    source_doc_id: str,
    source_doc_title: str,
    matter_id: str,
    confidentiality_tag: str,
    vector_store=None,
    mistral_client=None,
) -> dict:
    """
    Ingest a document: chunk it, scan for injections, embed, and store.

    Returns a summary of the ingestion including any flagged chunks.
    """
    from vectorstore.store import VectorStore

    if vector_store is None:
        vector_store = VectorStore()

    # Step 1: Chunk the document
    raw_chunks = chunk_document(text)
    logger.info(f"Document '{source_doc_title}' chunked into {len(raw_chunks)} chunks")

    # Step 2: Scan each chunk for injection patterns (heuristic, fast)
    flagged_chunks = []
    clean_chunks = []
    for i, chunk_data in enumerate(raw_chunks):
        findings = scan_for_injection_patterns(chunk_data["text"])
        chunk_id = f"{source_doc_id}_chunk{i:04d}"

        chunk_meta = {
            **chunk_data,
            "chunk_id": chunk_id,
            "source_doc_id": source_doc_id,
            "source_doc_title": source_doc_title,
            "matter_id": matter_id,
            "confidentiality_tag": confidentiality_tag,
            "injection_findings": findings,
            "injection_flagged": len(findings) > 0,
        }

        if findings:
            flagged_chunks.append(chunk_meta)
            logger.warning(
                f"Chunk {chunk_id} flagged at ingestion: "
                f"{[f['signal_type'] for f in findings]}"
            )
        clean_chunks.append(chunk_meta)

    # Step 3: Embed all chunks (flagged ones are stored but marked)
    texts = [c["text"] for c in clean_chunks]
    embeddings = await embed_texts(texts, client=mistral_client)

    # Step 4: Store in vector store with metadata
    chunk_ids = [c["chunk_id"] for c in clean_chunks]
    metadatas = [
        {
            "source_doc_id": c["source_doc_id"],
            "source_doc_title": c["source_doc_title"],
            "matter_id": c["matter_id"],
            "confidentiality_tag": c["confidentiality_tag"],
            "page_ref": c["page_ref"],
            "injection_flagged": str(c["injection_flagged"]),
        }
        for c in clean_chunks
    ]

    vector_store.add_chunks(
        chunk_ids=chunk_ids,
        texts=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    return {
        "source_doc_id": source_doc_id,
        "total_chunks": len(clean_chunks),
        "flagged_chunks": len(flagged_chunks),
        "flagged_details": [
            {
                "chunk_id": c["chunk_id"],
                "signals": [f["signal_type"] for f in c["injection_findings"]],
            }
            for c in flagged_chunks
        ],
    }
