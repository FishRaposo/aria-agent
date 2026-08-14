"""Provider-neutral span/trace primitives.

A minimal canonical trace schema (``Span``/``SpanType``/``SpanStatus``), latency
helpers (``Timer``, ``span``), generic transport DTOs (``TraceSpan``, ``CostRecord``)
and a collector emitter (``emit_span``). Spans align with
``aria.internal.vendor_core.logging.correlation_id_var`` so any service can produce traces an
observability backend (e.g. AgentTrace) can ingest.
"""

import time
import uuid
from contextlib import contextmanager
from enum import Enum
from typing import Any, Iterator, Optional

from pydantic import BaseModel, Field

from aria.internal.vendor_core.logging import correlation_id_var


class SpanType(str, Enum):
    """Coarse classification of a unit of traced work."""

    LLM = "llm"
    TOOL = "tool"
    RETRIEVAL = "retrieval"
    DECISION = "decision"
    OTHER = "other"


class SpanStatus(str, Enum):
    """Terminal status of a span."""

    OK = "ok"
    ERROR = "error"


def new_trace_id() -> str:
    """Generate a new opaque trace id."""
    return uuid.uuid4().hex


class Span(BaseModel):
    """A single timed unit of work within a trace."""

    span_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    trace_id: str
    parent_span_id: Optional[str] = None
    name: str
    span_type: SpanType = SpanType.OTHER
    status: SpanStatus = SpanStatus.OK
    start_ms: float = 0.0
    end_ms: Optional[float] = None
    attributes: dict[str, Any] = Field(default_factory=dict)

    @property
    def duration_ms(self) -> Optional[float]:
        if self.end_ms is None:
            return None
        return self.end_ms - self.start_ms

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class TraceSpan(BaseModel):
    """Generic transport DTO for a span emitted to a collector."""

    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    name: str
    span_type: str = SpanType.OTHER.value
    status: str = SpanStatus.OK.value
    start_ms: float = 0.0
    end_ms: Optional[float] = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class CostRecord(BaseModel):
    """Generic cost/latency record for an LLM (or other) operation."""

    trace_id: Optional[str] = None
    model: str
    provider: Optional[str] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0.0
    latency_ms: float = 0.0


class Timer:
    """Context manager capturing elapsed wall-clock time in milliseconds."""

    def __init__(self) -> None:
        self._start = 0.0
        self._end: Optional[float] = None

    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        self._end = None
        return self

    def __exit__(self, *exc: Any) -> None:
        self._end = time.perf_counter()

    @property
    def elapsed_ms(self) -> float:
        end = self._end if self._end is not None else time.perf_counter()
        return (end - self._start) * 1000.0


@contextmanager
def span(
    name: str,
    *,
    span_type: SpanType = SpanType.OTHER,
    trace_id: Optional[str] = None,
    parent_span_id: Optional[str] = None,
) -> Iterator[Span]:
    """Time a block of code, yielding a ``Span`` finalized on exit.

    Uses the active correlation id as the trace id when none is supplied.
    """
    resolved_trace = trace_id or correlation_id_var.get() or new_trace_id()
    current = Span(
        trace_id=resolved_trace,
        parent_span_id=parent_span_id,
        name=name,
        span_type=span_type,
        start_ms=time.perf_counter() * 1000.0,
    )
    try:
        yield current
    except Exception:
        current.status = SpanStatus.ERROR
        raise
    finally:
        current.end_ms = time.perf_counter() * 1000.0


async def emit_span(collector_url: str, payload: Span) -> None:
    """POST a span to a collector endpoint via the shared async HTTP client."""
    from aria.internal.vendor_core.clients import BaseHTTPClient

    client = BaseHTTPClient()
    try:
        await client.post(collector_url, json=payload.to_dict())
    finally:
        await client.close()
