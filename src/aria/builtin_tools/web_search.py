"""Web search tool — real when configured, deterministic mock offline.

Offline-first: with no ``ARIA_SEARCH_API_URL`` configured the tool returns a
deterministic simulated result (no network). When a search endpoint is
configured it performs a real HTTP GET via ``aria.internal.vendor_core.clients.BaseHTTPClient``
and gracefully falls back to the mock on any failure. This is a ``safe``
permission-level tool (read-only retrieval).
"""

import asyncio
import os

from loguru import logger
from pydantic import BaseModel, Field

# Deterministic offline knowledge base. Keyword -> canned result.
_MOCK_RESULTS = {
    "python": (
        "Python is a high-level programming language created by "
        "Guido van Rossum in 1991."
    ),
    "rag": (
        "RAG (Retrieval-Augmented Generation) combines information retrieval "
        "with text generation."
    ),
    "agent": (
        "An AI agent perceives its environment and takes actions to achieve "
        "goals, often by calling tools in a reason-and-act loop."
    ),
    "fastapi": (
        "FastAPI is a modern, async Python web framework built on Starlette "
        "and Pydantic."
    ),
    "celery": (
        "Celery is a distributed task queue for running asynchronous jobs "
        "via a message broker such as Redis."
    ),
}
_DEFAULT_RESULT = "No relevant results found for that query."


class WebSearchInput(BaseModel):
    query: str = Field(description="The search query string")


def _mock_search(query: str) -> str:
    """Deterministic offline lookup over the canned knowledge base."""
    query_lower = query.lower()
    for key, value in _MOCK_RESULTS.items():
        if key in query_lower:
            return f"Web search result: {value}"
    return f"Web search result: {_DEFAULT_RESULT}"


async def _real_search(query: str, api_url: str) -> str:
    """Perform a real HTTP search via the shared async client."""
    from aria.internal.vendor_core.clients import BaseHTTPClient

    client = BaseHTTPClient(timeout=10.0)
    try:
        response = await client.get(api_url, params={"q": query})
        data = response.json()
        # Best-effort extraction across a couple of common shapes.
        if isinstance(data, dict):
            snippet = (
                data.get("answer")
                or data.get("abstract")
                or (data.get("results") or [{}])[0].get("snippet")
                or str(data)[:500]
            )
        else:
            snippet = str(data)[:500]
        return f"Web search result: {snippet}"
    finally:
        await client.close()


def web_search(query: str) -> str:
    """Search the web (real when configured, deterministic mock otherwise)."""
    api_url = os.environ.get("ARIA_SEARCH_API_URL")
    if not api_url:
        return _mock_search(query)
    try:
        return asyncio.run(_real_search(query, api_url))
    except Exception as exc:  # noqa: BLE001 - degrade gracefully to mock
        logger.warning("web_search real call failed ({}); using mock", exc)
        return _mock_search(query)
