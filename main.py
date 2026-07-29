"""
Legal RAG — FastAPI application entry point.

Wires together all agents, the orchestrator pipeline, audit logging,
and the approval gate into a single API.
"""

from __future__ import annotations

import uuid
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from config import settings
from orchestrator.pipeline import Pipeline, PipelineContext, PipelineState
from agents.retrieval_agent import RetrievalAgent
from agents.injection_classifier import InjectionClassifier
from agents.analysis_agent import AnalysisAgent
from agents.validator_agent import ValidatorAgent
from agents.tool_exec_agent import ToolExecAgent
from vectorstore.store import VectorStore
from vectorstore.ingest import ingest_document
from audit.store import AuditStore
from audit.trace import TraceReconstructor
from approval.queue import ApprovalQueue
from approval.routes import router as approval_router, init_routes
from orchestrator.context_store import PipelineContextStore
from orchestrator.session_store import ChatSessionStore
from orchestrator.query_cache import query_cache
from tools.file_extractor import extract_text_from_file
from auth.store import UserStore
from auth.routes import router as auth_router, admin_router, set_user_store, get_current_user_dep

# Import tools to register them
import tools.citation_lookup
import tools.document_export
import tools.legal_web_search

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

# --- Global instances ---
vector_store: VectorStore | None = None
audit_store: AuditStore | None = None
approval_queue: ApprovalQueue | None = None
pipeline: Pipeline | None = None
trace_reconstructor: TraceReconstructor | None = None
context_store: PipelineContextStore | None = None
session_store: ChatSessionStore | None = None
user_store: UserStore | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize all components on startup."""
    global vector_store, audit_store, approval_queue, pipeline, trace_reconstructor, context_store, session_store, user_store

    logger.info("Initializing Legal RAG system...")

    # Initialize stores
    vector_store = VectorStore()
    audit_store = AuditStore(db_path=settings.sqlite_db_path)
    approval_queue = ApprovalQueue(db_path=settings.sqlite_db_path)
    context_store = PipelineContextStore(db_path=settings.sqlite_db_path)
    session_store = ChatSessionStore(db_path=settings.sqlite_db_path)
    user_store = UserStore(db_path=settings.sqlite_db_path)
    set_user_store(user_store)

    # Seed demo users if not present
    demo_users = [
        ("lawyer1@legal.com", "Jane Doe (Senior Attorney)", "Password123", "Senior Attorney", ["Matter_101", "Matter_102"]),
        ("paralegal1@legal.com", "Alex Smith (Paralegal)", "Password123", "Paralegal", ["Matter_101"]),
        ("admin@legal.com", "Chief Compliance Auditor", "Password123", "Compliance Auditor", ["Matter_101", "Matter_102", "Matter_103"]),
    ]
    for email, name, pw, role, matters in demo_users:
        if not user_store.get_user_by_email(email):
            user_store.create_user(email=email, full_name=name, password=pw, role=role, permitted_matters=matters)

    # Evict expired contexts on startup
    context_store.evict_old(hours=24)

    # Initialize agents
    retrieval_agent = RetrievalAgent(vector_store=vector_store)
    injection_classifier = InjectionClassifier(use_llm=bool(settings.mistral_api_key))
    analysis_agent = AnalysisAgent()
    validator_agent = ValidatorAgent()

    # Tool-exec agent with explicit allowlist (privileged zone — web search is in untrusted retrieval zone)
    tool_exec_agent = ToolExecAgent(
        allowed_tools=["citation_lookup", "document_export"]
    )
    tool_exec_agent.register_tool(
        "citation_lookup",
        tools.citation_lookup.citation_lookup,
    )
    tool_exec_agent.register_tool(
        "document_export",
        tools.document_export.document_export,
    )

    # Wire the pipeline
    pipeline = Pipeline(
        retrieval_agent=retrieval_agent,
        injection_classifier=injection_classifier,
        analysis_agent=analysis_agent,
        validator_agent=validator_agent,
        tool_exec_agent=tool_exec_agent,
        approval_gate=approval_queue,
        audit_logger=audit_store,
    )

    trace_reconstructor = TraceReconstructor(audit_store)

    # Initialize approval routes with queue, pipeline, and context store
    init_routes(approval_queue, pipeline, context_store)

    logger.info("Legal RAG system initialized successfully")
    yield
    logger.info("Shutting down Legal RAG system")


from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse

app = FastAPI(
    title="Secure Legal RAG",
    description="Multi-agent RAG with structural trust boundaries for legal documents",
    version="0.1.0",
    lifespan=lifespan,
)

import os

# Mount React UI build assets if available, fallback to static
if os.path.exists("ui/dist"):
    app.mount("/assets", StaticFiles(directory="ui/dist/assets"), name="assets")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(approval_router)
app.include_router(auth_router)
app.include_router(admin_router)


@app.get("/", response_class=FileResponse)
async def serve_index():
    """Serve main web application interface."""
    if os.path.exists("ui/dist/index.html"):
        return FileResponse("ui/dist/index.html")
    return FileResponse("static/index.html")



# --- Request/Response Models ---

class QueryRequest(BaseModel):
    """User query request."""
    query: str = Field(description="The legal question to answer")
    user_id: str = Field(default="default_user", description="User identifier")
    session_id: str | None = Field(default=None, description="Chat session ID")
    permitted_matters: list[str] = Field(
        default_factory=list,
        description="Matter IDs this user can access",
    )


class QueryResponse(BaseModel):
    """Query result response."""
    trace_id: str
    status: str
    execution_path: str | None = None
    answer: str | None = None
    claims: list[dict] | None = None
    sources: dict[str, dict] | None = None
    error: str | None = None


class IngestRequest(BaseModel):
    """Document ingestion request."""
    title: str
    matter_id: str
    confidentiality_tag: str = "public"
    content: str


# --- API Endpoints ---

@app.post("/query", response_model=QueryResponse)
async def submit_query(
    request: QueryRequest,
    current_user: dict = Depends(get_current_user_dep),
):
    """Submit a user query — starts the full pipeline with token-derived user identity and ACL permissions."""
    if not pipeline:
        raise HTTPException(status_code=503, detail="System not initialized")

    # Derive identity and matter permissions strictly from verified token
    user_id = current_user["user_id"]
    permitted_matters = current_user.get("permitted_matters", [])

    if request.user_id and request.user_id != user_id:
        logger.warning(f"Client user_id '{request.user_id}' does not match authenticated token '{user_id}'. Ignoring body value.")

    if request.permitted_matters and request.permitted_matters != permitted_matters:
        logger.warning(f"Client permitted_matters '{request.permitted_matters}' does not match authenticated token matters '{permitted_matters}'. Ignoring body value.")

    # Task 6: Check query result cache
    cached_resp = query_cache.get(user_id, permitted_matters, request.query)
    if cached_resp:
        return cached_resp

    logger.info(f"New query from {user_id}: {request.query[:100]}...")

    ctx = await pipeline.run(
        user_query=request.query,
        user_id=user_id,
        user_permitted_matters=permitted_matters,
    )

    # Store context for status lookups and approval resumption
    if context_store:
        context_store.save(ctx)

    # Build response
    answer = None
    claims = None

    if ctx.analysis_result and ctx.analysis_result.answer_draft:
        answer = ctx.analysis_result.answer_draft
        claims = [c.model_dump() for c in ctx.analysis_result.claims]
    elif ctx.tool_action_result and ctx.tool_action_result.result_summary:
        out = ctx.tool_action_result.result_summary
        answer = f"### Live Legal Web Search Results (Tavily API)\n\n{out}\n\n*Verified and executed via Human-in-the-Loop compliance approval.*"
    elif ctx.state == PipelineState.AWAITING_APPROVAL:
        answer = f"Live legal web search request generated for **\"{request.query}\"**. Submitted to Approval Queue for sign-off."
    elif ctx.error:
        answer = f"Pipeline stopped: {ctx.error}"
    else:
        answer = f"Completed processing query: '{request.query}'."

    # Build sources mapping from clean_chunks
    sources = {}
    if ctx.clean_chunks:
        for chunk in ctx.clean_chunks:
            sources[chunk.chunk_id] = {
                "title": chunk.source_doc_title,
                "url": chunk.source_doc_id,
                "page_ref": chunk.page_ref,
                "is_web": chunk.matter_id == "external_web",
            }

    exec_path = getattr(ctx, "execution_path", "pipeline")

    # If session_id provided, record messages into session store
    if request.session_id and session_store:
        session_store.add_message(
            session_id=request.session_id,
            role="user",
            content=request.query,
        )
        if answer:
            session_store.add_message(
                session_id=request.session_id,
                role="assistant",
                content=answer,
                trace_id=ctx.trace_id,
                metadata={
                    "claims": claims or [],
                    "sources": sources,
                    "status": ctx.state.value,
                    "execution_path": exec_path,
                    "error": ctx.error,
                },
            )

    response_obj = QueryResponse(
        trace_id=ctx.trace_id,
        status=ctx.state.value,
        execution_path=exec_path,
        answer=answer,
        claims=claims,
        sources=sources,
        error=ctx.error,
    )

    if ctx.state == PipelineState.COMPLETE:
        query_cache.set(user_id, permitted_matters, request.query, response_obj)

    return response_obj


@app.get("/query/{trace_id}/status")
async def query_status(trace_id: str, current_user: dict = Depends(get_current_user_dep)):
    """Check pipeline status for a query."""
    ctx = context_store.get(trace_id) if context_store else None
    if not ctx:
        raise HTTPException(status_code=404, detail="Trace not found")

    return {
        "trace_id": trace_id,
        "status": ctx.state.value,
        "error": ctx.error,
        "has_result": ctx.analysis_result is not None,
        "has_tool_action": ctx.tool_action_request is not None,
    }


@app.get("/query/{trace_id}/result")
async def query_result(trace_id: str, current_user: dict = Depends(get_current_user_dep)):
    """Get the final result for a query."""
    ctx = context_store.get(trace_id) if context_store else None
    if not ctx:
        raise HTTPException(status_code=404, detail="Trace not found")

    result = {
        "trace_id": trace_id,
        "status": ctx.state.value,
        "error": ctx.error,
    }

    if ctx.analysis_result:
        result["answer"] = ctx.analysis_result.answer_draft
        result["claims"] = [c.model_dump() for c in ctx.analysis_result.claims]

    if ctx.validation_verdict:
        result["validation"] = ctx.validation_verdict.model_dump()

    if ctx.tool_action_result:
        result["tool_result"] = ctx.tool_action_result.model_dump()

    if ctx.scan_results:
        result["injection_scans"] = [s.model_dump() for s in ctx.scan_results]

    return result


@app.get("/audit/trace/{trace_id}")
async def get_audit_trace(trace_id: str, current_user: dict = Depends(get_current_user_dep)):
    """Reconstruct the full audit trace for a pipeline run."""
    if not trace_reconstructor:
        raise HTTPException(status_code=503, detail="Audit system not initialized")

    trace = trace_reconstructor.reconstruct(trace_id)
    if trace["status"] == "not_found":
        raise HTTPException(status_code=404, detail="Trace not found")

    return trace


@app.get("/audit/traces")
async def list_traces(current_user: dict = Depends(get_current_user_dep)):
    """List all audit traces."""
    if not audit_store:
        raise HTTPException(status_code=503, detail="Audit system not initialized")
    return audit_store.get_all_traces()


@app.get("/audit/export")
async def export_audit_log(format: str = "json", current_user: dict = Depends(get_current_user_dep)):
    """Export the entire audit log as JSON or CSV file."""
    if not audit_store:
        raise HTTPException(status_code=503, detail="Audit system not initialized")

    if format.lower() == "csv":
        csv_data = audit_store.export_traces_csv()
        return JSONResponse(
            content={"format": "csv", "data": csv_data},
            headers={"Content-Disposition": "attachment; filename=audit_export.csv"}
        )
    else:
        json_data = audit_store.export_traces_json()
        return JSONResponse(
            content={"format": "json", "data": json_data},
            headers={"Content-Disposition": "attachment; filename=audit_export.json"}
        )


@app.post("/ingest")
async def ingest_doc(
    request: IngestRequest,
    current_user: dict = Depends(get_current_user_dep),
):
    """Ingest a document into the vector store with matter authorization check (Task 3)."""
    if not vector_store:
        raise HTTPException(status_code=503, detail="System not initialized")

    user_matters = current_user.get("permitted_matters", [])
    user_role = current_user.get("role", "")
    if request.matter_id not in user_matters and user_role not in ("admin", "Compliance Auditor"):
        raise HTTPException(
            status_code=403,
            detail=f"User '{current_user['user_id']}' is not authorized to ingest into matter '{request.matter_id}'"
        )

    doc_id = f"doc_{uuid.uuid4().hex[:8]}"

    try:
        result = await ingest_document(
            text=request.content,
            source_doc_id=doc_id,
            source_doc_title=request.title,
            matter_id=request.matter_id,
            confidentiality_tag=request.confidentiality_tag,
            vector_store=vector_store,
        )
        return {
            "status": "success",
            "doc_id": doc_id,
            **result,
        }
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest/file")
async def ingest_file(
    file: UploadFile = File(...),
    matter_id: str = Form(...),
    confidentiality_tag: str = Form(default="public"),
    title: str | None = Form(default=None),
    current_user: dict = Depends(get_current_user_dep),
):
    """Ingest a multi-format document into vector store with matter authorization check (Task 3)."""
    if not vector_store:
        raise HTTPException(status_code=503, detail="System not initialized")

    user_matters = current_user.get("permitted_matters", [])
    user_role = current_user.get("role", "")
    if matter_id not in user_matters and user_role not in ("admin", "Compliance Auditor"):
        raise HTTPException(
            status_code=403,
            detail=f"User '{current_user['user_id']}' is not authorized to ingest into matter '{matter_id}'"
        )

    contents = await file.read()
    doc_title = title or file.filename or "Uploaded Document"

    try:
        extracted = extract_text_from_file(contents, file.filename or "doc.txt")
        doc_id = f"doc_{uuid.uuid4().hex[:8]}"

        result = await ingest_document(
            text=extracted["text"],
            source_doc_id=doc_id,
            source_doc_title=doc_title,
            matter_id=matter_id,
            confidentiality_tag=confidentiality_tag,
            vector_store=vector_store,
        )
        return {
            "status": "success",
            "doc_id": doc_id,
            "filename": file.filename,
            "chunks_count": result.get("total_chunks", 0),
            "pages_extracted": extracted.get("pages", 1),
            "file_type": extracted.get("file_type", "unknown"),
            **result,
        }
    except Exception as e:
        logger.error(f"File ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class CreateSessionRequest(BaseModel):
    title: str = "New Legal Chat"
    user_id: str | None = Field(default=None, description="Deprecated client user_id (ignored, derived from token)")
    active_matter_id: str | None = None


@app.get("/sessions")
async def list_user_sessions(current_user: dict = Depends(get_current_user_dep)):
    """List chat sessions for user derived from Bearer token."""
    if not session_store:
        raise HTTPException(status_code=503, detail="Session store not initialized")
    return session_store.list_sessions(user_id=current_user["user_id"])


@app.post("/sessions")
async def create_chat_session(
    req: CreateSessionRequest,
    current_user: dict = Depends(get_current_user_dep),
):
    """Create a new chat session bound to authenticated user."""
    if not session_store:
        raise HTTPException(status_code=503, detail="Session store not initialized")
    return session_store.create_session(
        title=req.title, user_id=current_user["user_id"], active_matter_id=req.active_matter_id
    )


@app.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    current_user: dict = Depends(get_current_user_dep),
):
    """Get messages for a chat session."""
    if not session_store:
        raise HTTPException(status_code=503, detail="Session store not initialized")
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.get("user_id") != current_user["user_id"] and current_user.get("role") not in ("admin", "Compliance Auditor"):
        raise HTTPException(status_code=403, detail="Unauthorized access to chat session")
    return {
        "session": session,
        "messages": session_store.get_messages(session_id),
    }


@app.delete("/sessions/{session_id}")
async def delete_chat_session(
    session_id: str,
    current_user: dict = Depends(get_current_user_dep),
):
    """Delete a chat session."""
    if not session_store:
        raise HTTPException(status_code=503, detail="Session store not initialized")
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.get("user_id") != current_user["user_id"] and current_user.get("role") not in ("admin", "Compliance Auditor"):
        raise HTTPException(status_code=403, detail="Unauthorized access to chat session")
    success = session_store.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "success", "session_id": session_id}


@app.get("/documents")
async def list_documents(current_user: dict = Depends(get_current_user_dep)):
    """List all ingested documents summary from vector store."""
    if not vector_store:
        raise HTTPException(status_code=503, detail="System not initialized")
    return vector_store.get_all_documents()


@app.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    current_user: dict = Depends(get_current_user_dep),
):
    """Delete a document and all its chunks from vector store."""
    if not vector_store:
        raise HTTPException(status_code=503, detail="System not initialized")
    success = vector_store.delete_document(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found or delete failed")
    return {"status": "success", "doc_id": doc_id}


@app.get("/health")
async def health():
    """Health check."""
    return {
        "status": "healthy",
        "vector_store_count": vector_store.count() if vector_store else 0,
        "audit_log_count": audit_store.count() if audit_store else 0,
    }
