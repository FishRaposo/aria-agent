"""ARIA tool routing — LLM-based (sim/real) with a deterministic keyword fallback.

Two strategies select which tool (if any) an agent should call for a query:

* :class:`KeywordRouter` — deterministic regex/keyword matching. Always available,
  no keys, no network. Used as the offline default and as the fallback whenever
  LLM routing yields nothing usable.
* :class:`LLMRouter` — wraps an LLM to choose a tool and extract arguments. It
  follows the offline-first / real-when-keyed pattern: a ``mocked_response``
  short-circuits to a deterministic simulated decision, otherwise the real
  provider path runs via ``aria.internal.vendor_core.llm.LLMClientFactory`` with a graceful
  fallback to the keyword router on ImportError / no key / any failure.

Both return a :class:`RouteDecision` so the agent loop is router-agnostic.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from loguru import logger


@dataclass
class RouteDecision:
    """The result of routing a query to a tool (or to a direct response)."""

    tool: Optional[str]
    arguments: Dict[str, Any] = field(default_factory=dict)
    strategy: str = "keyword"
    rationale: str = ""
    context_consumed: bool = False

    @property
    def is_tool(self) -> bool:
        return self.tool is not None


_NUM = r"(-?\d+(?:\.\d+)?)"


class KeywordRouter:
    """Deterministic keyword/regex tool routing."""

    strategy = "keyword"

    def __init__(self, tool_names: Optional[List[str]] = None):
        # The full set of routable tools; used to validate LLM choices too.
        self.tool_names = set(
            tool_names
            or [
                "calculator",
                "web_search",
                "file_reader",
                "task_creator",
                "email_draft",
            ]
        )

    @staticmethod
    def _extract_email(query: str) -> Optional[str]:
        match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", query)
        return match.group(0) if match else None

    def route(self, query: str, context: Optional[list] = None) -> RouteDecision:
        lowered = query.lower()

        if (
            "calculate" in lowered
            or "compute" in lowered
            or re.search(rf"{_NUM}\s*[+\-*/]\s*{_NUM}", query)
        ):
            expr_match = re.search(rf"{_NUM}\s*[+\-*/]\s*{_NUM}", query)
            expression = expr_match.group(0) if expr_match else "0"
            return RouteDecision(
                tool="calculator",
                arguments={"expression": expression},
                strategy=self.strategy,
                rationale="matched arithmetic keyword/pattern",
            )

        if "email" in lowered or "draft" in lowered:
            return RouteDecision(
                tool="email_draft",
                arguments={
                    "recipient": self._extract_email(query) or "team@example.com",
                    "subject": query[:80],
                    "body": query,
                },
                strategy=self.strategy,
                rationale="matched email keyword",
            )

        # Task intent is checked before file/search so phrases like
        # "create a task to file the report" route to task_creator, not file_reader.
        if (
            any(k in lowered for k in ("task", "todo", "remind"))
            or "create a" in lowered
        ):
            return RouteDecision(
                tool="task_creator",
                arguments={"title": query[:80], "description": query},
                strategy=self.strategy,
                rationale="matched task keyword",
            )

        if any(k in lowered for k in ("search", "find", "look up", "lookup")):
            return RouteDecision(
                tool="web_search",
                arguments={"query": query},
                strategy=self.strategy,
                rationale="matched search keyword",
            )

        # File reading needs an explicit read/open verb (not a bare "file").
        if "read" in lowered or "open" in lowered or "file" in lowered:
            path_match = re.search(r'["\']?([\w./\\-]+\.\w+)["\']?', query)
            path = path_match.group(1) if path_match else "notes.txt"
            return RouteDecision(
                tool="file_reader",
                arguments={"filepath": path},
                strategy=self.strategy,
                rationale="matched file/read keyword",
            )

        return RouteDecision(
            tool=None, strategy=self.strategy, rationale="no keyword match"
        )


def _simulate_route(query: str, fallback: KeywordRouter) -> str:
    """Build a deterministic JSON routing decision (the sim LLM response).

    Mirrors what a well-behaved LLM router would return, derived from the
    keyword router so the simulation stays consistent and testable.
    """
    decision = fallback.route(query)
    return json.dumps({"tool": decision.tool, "arguments": decision.arguments})


class LLMRouter:
    """LLM-backed router with a deterministic simulation default."""

    strategy = "llm"

    _PROMPT = (
        "You are a tool router. Given the user query and the list of available "
        'tools, respond with a JSON object {{"tool": <name-or-null>, '
        '"arguments": {{...}}}}. Follow the supplied conversation context, '
        "including system instructions. Available tools: {tools}. "
        "Context: {context}. Query: {query}"
    )

    def __init__(
        self,
        llm_client=None,
        model: str = "gpt-4o-mini",
        keyword_fallback: Optional[KeywordRouter] = None,
        simulate: bool = True,
    ):
        self.llm_client = llm_client
        self.model = model
        self.fallback = keyword_fallback or KeywordRouter()
        # When no real client/keys are available we simulate deterministically.
        self.simulate = simulate

    def route(
        self,
        query: str,
        context: Optional[list] = None,
        cost_tracker=None,
    ) -> RouteDecision:
        prompt = self._PROMPT.format(
            tools=sorted(self.fallback.tool_names),
            context=json.dumps(context or [], ensure_ascii=False),
            query=query,
        )
        mocked = _simulate_route(query, self.fallback) if self.simulate else None

        raw_text = None
        context_consumed = False
        if self.llm_client is not None:
            try:
                result = self.llm_client.generate(
                    self.model, prompt, mocked_response=mocked
                )
                context_consumed = bool(context)
                raw_text = result.get("response") if isinstance(result, dict) else None
                telemetry = (
                    result.get("telemetry", {}) if isinstance(result, dict) else {}
                )
                if cost_tracker is not None:
                    cost_tracker.record_call(
                        self.model,
                        int(telemetry.get("input_tokens", len(prompt) // 4)),
                        int(telemetry.get("output_tokens", 20)),
                        float(telemetry.get("latency_ms", 0.0)),
                    )
            except Exception as exc:  # noqa: BLE001 - degrade to keyword routing
                logger.warning("LLM routing failed ({}); using keyword router", exc)
                raw_text = None
        elif self.simulate:
            # No client wired but simulation requested — use the canned decision.
            raw_text = mocked
            if cost_tracker is not None:
                cost_tracker.record_call(self.model, len(prompt) // 4, 20, 5.0)

        decision = self._parse(raw_text)
        if decision is not None:
            decision.context_consumed = context_consumed
            return decision

        # Fallback: keyword routing (deterministic, always available).
        kw = self.fallback.route(query, context)
        kw.strategy = "keyword_fallback"
        kw.context_consumed = context_consumed
        return kw

    def _parse(self, raw_text: Optional[str]) -> Optional[RouteDecision]:
        if not raw_text:
            return None
        try:
            data = json.loads(raw_text)
        except (json.JSONDecodeError, TypeError):
            return None
        if not isinstance(data, dict):
            return None
        tool = data.get("tool")
        if tool is not None and tool not in self.fallback.tool_names:
            # LLM hallucinated a tool — reject and let the caller fall back.
            return None
        return RouteDecision(
            tool=tool,
            arguments=data.get("arguments") or {},
            strategy=self.strategy,
            rationale="llm routing decision",
        )


def build_router(strategy: str = "auto", llm_client=None, **kwargs):
    """Construct a router for the configured strategy.

    ``auto`` uses LLM routing (simulated by default, real when a client + keys
    are wired) with a keyword fallback; ``keyword`` forces the deterministic
    router; ``llm`` forces the LLM router.
    """
    keyword = KeywordRouter()
    if strategy == "keyword":
        return keyword
    return LLMRouter(llm_client=llm_client, keyword_fallback=keyword, **kwargs)
