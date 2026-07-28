# Secure Multi-Agent Legal Document RAG

A security-hardened, multi-agent Retrieval-Augmented Generation (RAG) pipeline for querying and analyzing legal documents. The system enforces **structural privilege separation**, uses **typed schemas** for all inter-agent communication, and produces a **complete audit trail** for every query.

## Architecture

```
User → Orchestrator → Retrieval Agent → Injection Classifier → Analysis Agent → Validator → Tool-Exec Agent → External Tools
         (router)       (ACL-filtered)    (isolated context)     (toolless)      (grounding)   (allowlisted)
```

### Security Boundaries

| Zone | Agents | Can Call Tools? |
|------|--------|----------------|
| **Untrusted** | Retrieval, Injection Classifier, Analysis | ❌ Never |
| **Gateway** | Validator | ❌ (only upgrades trust level) |
| **Privileged** | Tool-Exec | ✅ Allowlisted only |

### Non-Negotiable Rules (enforced in code, not prompts)

1. **No agent that reads raw document text may call tools** — structural separation
2. **All inter-agent messages use typed Pydantic schemas** — no free-text blobs
3. **Validator is the only path to the privileged zone** — grounding + intent check
4. **Tool calls with external effects require human approval** — approval gate UI
5. **ACL filtering happens in the vector query itself** — not post-filtered
6. **Every hop is logged** with trace_id for full reconstruction

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Set up environment
cp .env.example .env
# Edit .env with your MISTRAL_API_KEY

# Run tests (97 tests)
pytest tests/ -v

# Start the server
uvicorn main:app --reload --port 8000
```

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/query` | Submit a legal query |
| `GET` | `/query/{trace_id}/status` | Check pipeline status |
| `GET` | `/query/{trace_id}/result` | Get full result with citations |
| `POST` | `/ingest` | Ingest a document |
| `GET` | `/approvals` | Human approval gate UI |
| `POST` | `/approvals/{id}/approve` | Approve a tool action |
| `POST` | `/approvals/{id}/reject` | Reject a tool action |
| `GET` | `/audit/trace/{trace_id}` | Full audit trace reconstruction |
| `GET` | `/health` | Health check |

## Project Structure

```
legal-rag/
├── schemas/             # Pydantic models (envelope, retrieval, injection, analysis, validation, tool_action)
├── orchestrator/        # State machine pipeline + trust boundary enforcement
├── agents/              # Agent implementations (retrieval, classifier, analysis, validator, tool-exec)
├── vectorstore/         # ChromaDB wrapper with ACL filtering
├── tools/               # Tool definitions with allowlist registry
├── approval/            # Human approval queue + web UI
├── audit/               # Append-only audit log + trace reconstruction
├── tests/               # 97 tests including adversarial regression suite
└── sample_docs/         # Test documents (clean, injected, privileged)
```

## Tech Stack

- **Python 3.12** + FastAPI + Pydantic v2
- **Mistral AI** — Large (analysis/validation) + Small (injection classifier) + Embed (embeddings)
- **ChromaDB** — Vector store with metadata filtering for ACL
- **SQLite** — Audit log + approval queue (append-only)
