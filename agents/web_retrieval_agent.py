"""
Web Retrieval Agent — Untrusted retrieval agent for external legal web research.

SECURITY PROPERTIES:
- Operates strictly in the UNTRUSTED ZONE (same trust level as VectorStore RetrievalAgent)
- Has NO tool bindings to privileged execution agents or approval queues
- Performs HTTP fetch to Tavily search API and wraps result snippets as Chunks
- Never sees or interprets search results itself — returned snippets become Chunk objects
  and flow through InjectionClassifier, AnalysisAgent, and ValidatorAgent unmodified.
"""

from __future__ import annotations

import json
import logging
import uuid
from urllib.parse import urlparse
import httpx

from config import settings
from schemas.retrieval import Chunk
from orchestrator.context_builder import build_web_search_formulation_context

logger = logging.getLogger(__name__)


AUTHORITATIVE_DOMAINS = [
    "gov", "gov.in", "nic.in", "supremecourt.gov", "sci.gov.in",
    "indiankanoon.org", "prsindia.org", "sec.gov", "law.cornell.edu",
    "justia.com", "courtlistener.com", "officialgazette.gov.ph",
    "oyez.org", "federalregister.gov", "legislative.gov.in", "ecourts.gov.in"
]

DISALLOWED_DOMAINS = [
    "unacademy.com", "byjus.com", "scribd.com", "brainly.in",
    "quora.com", "coursehero.com", "chegg.com"
]


def is_authoritative_domain(domain: str) -> bool:
    d = domain.lower()
    return any(d == auth or d.endswith("." + auth) or d.endswith(auth) for auth in AUTHORITATIVE_DOMAINS)


def is_disallowed_domain(domain: str) -> bool:
    d = domain.lower()
    return any(d == dis or d.endswith("." + dis) for dis in DISALLOWED_DOMAINS)


class WebRetrievalAgent:
    """Untrusted zone retrieval agent for external web search snippets."""

    def __init__(self, tavily_api_key: str | None = None, mistral_client=None):
        self.api_key = tavily_api_key or settings.tavily_api_key
        self._client: httpx.AsyncClient | None = None
        self._mistral_client = mistral_client

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=15.0)
        return self._client

    def _formulate_query(self, user_query: str) -> str:
        """Formulate a high-precision search query using §5 prompt."""
        if not settings.mistral_api_key:
            return user_query
        try:
            from mistralai.client import Mistral
            if self._mistral_client is None:
                self._mistral_client = Mistral(api_key=settings.mistral_api_key)
            messages = build_web_search_formulation_context(user_query)
            resp = self._mistral_client.chat.complete(
                model=settings.mistral_model,
                messages=messages,
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content.strip()
            data = json.loads(raw)
            return data.get("query", user_query)
        except Exception as e:
            logger.debug(f"Web query formulation fallback to raw query: {e}")
            return user_query

    async def search(self, query: str, max_results: int = 5) -> list[Chunk]:
        """
        Execute external legal web search via Tavily API and return Chunks.
        All returned chunks are in the UNTRUSTED zone with matter_id='external_web'.
        """
        search_query = self._formulate_query(query)
        logger.info(f"WebRetrievalAgent searching formulated query='{search_query[:100]}...'")

        raw_results = []
        answer_text = ""

        if self.api_key:
            try:
                client = self._get_client()
                resp = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": self.api_key,
                        "query": search_query,
                        "search_depth": "advanced",
                        "max_results": max_results * 2,
                        "include_answer": True,
                    },
                )
                if resp.status_code == 200:
                    t_data = resp.json()
                    raw_results = t_data.get("results", [])
                    answer_text = t_data.get("answer", "")
            except Exception as e:
                logger.error(f"WebRetrievalAgent Tavily request exception: {e}")

        # Fallback to legal_web_search if direct Tavily call returned no results
        if not raw_results:
            try:
                import tools.legal_web_search
                fallback_res = await tools.legal_web_search.legal_web_search({"query": search_query})
                answer_text = fallback_res
            except Exception as e:
                logger.error(f"Fallback web search error: {e}")

        web_chunks: list[Chunk] = []

        if raw_results:
            # Filter out non-authoritative content aggregators (unacademy, byjus, scribd, etc.)
            filtered_results = []
            for res in raw_results:
                url = res.get("url", "")
                parsed_url = urlparse(url)
                domain = parsed_url.netloc or ""
                if domain.startswith("www."):
                    domain = domain[4:]
                if not is_disallowed_domain(domain):
                    filtered_results.append((res, domain))

            # Prioritize authoritative legal domains
            filtered_results.sort(key=lambda item: 0 if is_authoritative_domain(item[1]) else 1)
            selected_results = filtered_results[:max_results]

            for idx, (res, domain) in enumerate(selected_results, 1):
                url = res.get("url", "https://web.source")
                title = res.get("title", "Legal Web Snippet")
                content = res.get("content", "").strip()

                is_auth = is_authoritative_domain(domain)
                authority_label = "[Official Legal Source]" if is_auth else "[General Web Source]"
                display_title = f"{authority_label} {title or domain}"

                w_chunk = Chunk(
                    chunk_id=f"web_{uuid.uuid4().hex[:8]}",
                    source_doc_id=url,
                    source_doc_title=display_title,
                    matter_id="external_web",
                    confidentiality_tag="public",
                    page_ref=url,
                    text=f"Source URL: {url}\nWebsite Domain: {domain}\nAuthority Level: {'Authoritative Primary Legal Source' if is_auth else 'General Web Resource'}\nDocument Title: {title}\nContent Snippet: {content}",
                    embedding_score=1.0,
                    acl_check_passed=True,
                )
                web_chunks.append(w_chunk)
        else:
            web_chunks.append(
                Chunk(
                    chunk_id=f"web_{uuid.uuid4().hex[:8]}",
                    source_doc_id="https://api.tavily.com",
                    source_doc_title="[Official Legal Source] Online Legal Search",
                    matter_id="external_web",
                    confidentiality_tag="public",
                    page_ref="live_web",
                    text=answer_text or f"Web search executed for '{search_query}'.",
                    embedding_score=1.0,
                    acl_check_passed=True,
                )
            )

        return web_chunks
