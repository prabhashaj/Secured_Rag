# Secure multi-agent legal document RAG — system design

## 1. Design principles

1. **Trust follows data, not roles.** Any agent that reads untrusted document content is untrusted for the rest of that turn, regardless of what task it's nominally performing.
2. **Privilege separation is structural, not prompted.** An agent that can call write/send/modify tools must never also be the agent that ingests raw document text. This is enforced by the orchestrator's routing, not by asking a model nicely to behave.
3. **Every hop between agents is a schema, not free text.** Structured, typed messages shrink the space where an injected instruction can hide.
4. **Assume detection fails sometimes.** Injection classifiers and prompt hardening reduce the *rate* of successful injection; they don't eliminate it. The system must be safe even when a classifier misses something — that's what the privilege boundary and human-approval gate are for.
5. **Everything is attributable.** Every retrieved chunk, every agent decision, every tool call carries enough metadata to reconstruct "why did the system do that" after the fact — a hard requirement for legal/compliance review.

---

## 2. Component responsibilities

| Component | Reads | Can call tools? | Purpose |
|---|---|---|---|
| **Orchestrator** | User query, agent outputs (structured only) | No | Routes work between agents, enforces workflow order, never sees raw document text directly |
| **Retrieval agent** | Vector index, document metadata | Search/query tools only | Retrieves candidate chunks, applies ACL/matter-wall filtering at query time |
| **Injection classifier** | Retrieved chunk text | No | Lightweight, separate-context scan of each chunk before it reaches the analysis agent |
| **Analysis agent** | Retrieved chunks, user query | No | Summarizes, compares clauses, flags risk — the agent most exposed to injected content, deliberately toolless |
| **Validator/critic agent** | Analysis agent's output + the source chunks it cited | No | Grounds every claim in cited source text, checks that no unrequested action snuck into the output |
| **Tool-exec agent** | Orchestrator-approved action requests only (not raw document text) | Yes, narrow allowlist per instance | The only component that can send, write, modify, or submit anything |
| **Human approval gate** | Proposed tool call + justification | N/A | Required checkpoint for any action with external or binding effect |

---

## 3. Agent-to-agent message schema

All inter-agent messages share a common envelope. This lets the orchestrator log, replay, and validate every hop uniformly.

### 3.1 Envelope (wraps every message)

```json
{
  "message_id": "uuid",
  "trace_id": "uuid",
  "turn_id": "uuid",
  "timestamp": "2026-07-28T10:15:00Z",
  "sender": "retrieval-agent",
  "recipient": "orchestrator",
  "trust_level": "untrusted",
  "message_type": "retrieval_result",
  "payload": { },
  "signature": "hmac-sha256(...)"
}
```

- `trust_level` is set once by the orchestrator when a message is spawned from raw document content, and it is **sticky** — it propagates to every downstream message derived from it, and can only be downgraded to `trusted` by the validator agent after grounding checks pass.
- `signature` lets the orchestrator detect a message that was tampered with in transit between agent processes (relevant if agents run as separate services).

### 3.2 Retrieval result (retrieval agent → orchestrator → classifier)

```json
{
  "message_type": "retrieval_result",
  "payload": {
    "query": "string",
    "chunks": [
      {
        "chunk_id": "doc123_chunk045",
        "source_doc_id": "doc123",
        "source_doc_title": "string",
        "matter_id": "string",
        "confidentiality_tag": "privileged | confidential | public",
        "text": "string",
        "embedding_score": 0.87,
        "page_ref": "p.12",
        "acl_check_passed": true
      }
    ]
  }
}
```

Note: `text` is the **only** free-text field, and everything downstream must treat it as opaque data — never as instructions. This is enforced at the prompt-construction layer, not just documented here (see §5).

### 3.3 Injection scan result (classifier → orchestrator)

```json
{
  "message_type": "injection_scan_result",
  "payload": {
    "chunk_id": "doc123_chunk045",
    "verdict": "clean | suspicious | blocked",
    "signals": ["instruction_like_phrase", "hidden_unicode", "role_play_marker"],
    "confidence": 0.94,
    "action_taken": "passed_through | quarantined"
  }
}
```

`signals` is a closed enum, not free text — this prevents the classifier's own output from becoming a second injection surface.

### 3.4 Analysis result (analysis agent → validator)

```json
{
  "message_type": "analysis_result",
  "payload": {
    "user_query": "string",
    "answer_draft": "string",
    "claims": [
      {
        "claim_id": "c1",
        "text": "string",
        "supporting_chunk_ids": ["doc123_chunk045"]
      }
    ],
    "proposed_actions": [
      {
        "action_type": "none | tool_request",
        "tool_name": "string | null",
        "justification": "string | null"
      }
    ]
  }
}
```

Requiring every claim to cite a `supporting_chunk_id` is what makes grounding checkable mechanically rather than by re-reading prose.

### 3.5 Validation verdict (validator → orchestrator)

```json
{
  "message_type": "validation_verdict",
  "payload": {
    "grounded": true,
    "ungrounded_claims": [],
    "unauthorized_action_detected": false,
    "trust_level_after_validation": "trusted",
    "notes": "string"
  }
}
```

Only messages with `unauthorized_action_detected: false` and `grounded: true` are allowed to reach the tool-exec agent or the user.

### 3.6 Tool action request (orchestrator → tool-exec agent)

```json
{
  "message_type": "tool_action_request",
  "payload": {
    "tool_name": "string",
    "parameters": { },
    "requested_by": "analysis-agent",
    "validated_by": "validator-agent",
    "requires_human_approval": true,
    "originating_chunk_ids": ["doc123_chunk045"]
  }
}
```

`originating_chunk_ids` is what makes the audit trail complete: if a tool call turns out to be wrong, you can trace it back to the exact source text that motivated it.

### 3.7 Tool action result (tool-exec agent → orchestrator)

```json
{
  "message_type": "tool_action_result",
  "payload": {
    "tool_name": "string",
    "status": "success | failed | rejected_by_human",
    "result_summary": "string",
    "executed_at": "2026-07-28T10:16:02Z"
  }
}
```

---

## 4. Trust boundary enforcement

Two structural rules, enforced in code at the orchestrator level, not by prompting:

1. **No message with `trust_level: untrusted` may be routed directly to the tool-exec agent.** It must pass through the validator agent first and come out with `trust_level_after_validation: trusted`.
2. **The tool-exec agent's context window never includes raw chunk text.** It only receives the structured `tool_action_request` payload above. Even if an injection attempt somehow survives the classifier and the validator, the tool-exec agent has nothing in its context that looks like document content to be confused by.

---

## 5. Defense-in-depth mapped to the pipeline

| Stage | Control | Failure mode it catches |
|---|---|---|
| Ingestion | Static scan for injection patterns, hidden Unicode, HTML comments; quarantine (not silent strip) | Obvious injected instructions baked into a document at upload time |
| Retrieval | ACL/matter-wall filtering in the vector query itself | Cross-matter data leakage, confidentiality breach |
| Post-retrieval | Dedicated injection classifier, separate context from the task model | Injected instructions that survived ingestion-time scanning |
| Prompt construction | Retrieved text wrapped in explicit delimiters with a system instruction that it is data, not instructions | Model treating chunk content as commands |
| Analysis | Toolless agent — no tools to abuse even if compromised | Successful injection with no blast radius |
| Post-analysis | Validator agent grounds every claim against cited chunks | Hallucinated clauses, unauthorized proposed actions |
| Pre-execution | Structural trust-boundary rule + human approval gate for binding/external actions | Any injection that survived every prior layer |
| Always | Full audit log of every hop with `trace_id` | Post-incident reconstruction, compliance review |

---

## 6. Legal-specific controls

- **Ethical wall enforcement at the retrieval query**, not the UI — a user's permitted matter IDs are injected into the vector store filter itself, so a compromised or injected instruction cannot retrieve out-of-scope documents by asking nicely.
- **Confidentiality tagging propagates with the chunk** through every message in §3, so downstream agents and logs always know the sensitivity of what they're handling.
- **No agent output constituting legal advice or modifying a binding document ships without human sign-off** — this is the `requires_human_approval: true` flag in §3.6, made non-optional for a defined set of `tool_name` values (e.g. `submit_filing`, `send_redline`, `execute_signature`).
- **Immutable audit trail**: log raw retrieval results, classifier verdicts, and validation verdicts, not just the final answer — needed to reconstruct what the system actually saw.

---

## 7. Addendum: context, harness, and memory

These three concerns cut across every component in §2 and deserve explicit treatment rather than being left implicit in each agent's prompt.

### 7.1 Context handling

- **Isolate by design.** Each agent receives the minimum context it needs, assembled fresh per call — not the full conversation history passed down indiscriminately. The injection classifier (§2, §3.3) runs with no chat history at all, so an injected instruction can't lean on prior turns to appear legitimate.
- **Delimit untrusted text explicitly, every call.** Retrieved chunk text is wrapped in clearly marked blocks with a standing instruction that content inside them is data, never instructions — re-asserted at every context assembly, not stated once and assumed to persist.
- **Use hierarchical retrieval, not flat chunk-dumping.** Maintain a document-level and section-level summary index above the chunk index. Hand the analysis agent the relevant section summary plus the 3-5 highest-relevance chunks within it, not everything that matched the embedding search. Re-rank after retrieval before anything enters a prompt.
- **Provenance travels with text, never gets stripped to save space.** `chunk_id`, `source_doc_id`, `page_ref` (§3.2) stay attached through every hop; truncate content before you'd ever truncate metadata.
- **Cross-turn replay is deliberate, not automatic.** Replay the user-facing conversation and a compact summary of prior findings; let retrieval/analysis re-derive detail from source chunks rather than trusting a stale summary that may have drifted.

### 7.2 Harness (orchestration layer)

For the security-critical path, use a **fixed state machine, not a free-form agent loop.** The sequence retrieve → classify → analyze → validate → (maybe) act is not something an LLM's own judgment should be allowed to reorder or skip — that judgment is exactly what an injection attack targets.

- **Model the pipeline as an explicit graph with fixed edges**, implemented in code the orchestrator runs — not decided by a model's output at runtime. A durable-execution framework or graph-based orchestration library can help, but the transition logic must live in code you control and can unit-test.
- **Each edge in §4's two rules is a hard gate**, checked before the next stage runs — not a soft preference expressed in a prompt.
- **Isolate execution environments by trust level.** Ideally the untrusted-zone agents (retrieval, classifier, analysis) run in a different process/container/service identity than the tool-exec agent, so a full compromise of one can't reach the other's credentials directly.
- **Wrap every tool call in a harness**: allowlist check → parameter validation against the `tool_action_request` schema (§3.6) → rate limit → execute → log result. No agent gets a general "call any tool with any args" capability.
- **Retries are idempotent.** Anything that writes gets an idempotency key so a retried call after a timeout can't double-submit a filing.
- **Adversarial test suite from day one.** Seeded documents with known injection patterns, run through the full pipeline on every change, asserting both that the classifier catches them and that a simulated bypass still can't reach a privileged tool call with `trust_level: untrusted`.

### 7.3 Memory management

Split into three categories — conflating them is where systems get into trouble.

- **Working memory (per-turn).** Retrieval results, classifier verdicts, analysis draft — lives only for the duration of one query, passed via the schemas in §3, persisted only to the audit log, never silently promoted to long-term memory.
- **Session memory (per-conversation).** Store compact structured facts ("user is analyzing Matter #4521, focused on indemnification clauses") rather than raw transcripts — saves context budget and stops injected content from an earlier turn's document from persisting verbatim into later prompts.
- **Long-term / cross-session memory — highest risk, most caution:**
  - Treat writes to long-term memory as tool calls, subject to the same validator gating as any other action (§2, validator agent). No agent writes to persistent memory just because it decided to.
  - Never let raw untrusted chunk text flow into long-term memory that later loads into a privileged agent's context — store the validated, grounded *claim*, not the excerpt that produced it. Otherwise a document planted today becomes a delayed-fuse injection vector replayed into a privileged context in a future session.
  - Scope memory by matter/client, same as retrieval ACLs (§6) — a memory layer that mixes context across matters defeats the ethical-wall filtering done at retrieval time.
  - Apply explicit retention and redaction policy, with a deletion path, matching legal data retention requirements.
  - Compact periodically rather than let memory grow unbounded — long sessions both degrade quality (context dilution) and increase attack surface.

## 8. Suggested next steps

- A concrete threat-model table (attack vector → mitigation layer → residual risk) if you want to walk this through a security review.
- The injection-classifier prompt/spec itself.
- A reference implementation of the orchestrator's routing logic (the code that enforces §4's two rules).
- A concrete state-machine spec for the harness (§7.2), or a memory-write schema that plugs into the message envelope (§3.1).
