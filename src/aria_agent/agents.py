"""KeywordRouterAgent — the v0.1 keyword-routing tool agent (preserved).

This is the ORIGINAL Aria agent logic from v0.1: it does keyword matching on
the query, picks a tool, and runs the tool. It carries the v0.1 reason-and-act
loop, in-memory conversation memory, approval gate, cost tracker, and trace
log.

In v0.3, this class is **not** the main entry point. It's a specialist that
the new `AriaAgent` (in `agent.py`) delegates to when the query matches a
tool keyword (e.g. "calculate 2 + 2" → calculator tool, "read foo.txt" →
file_reader tool). The new AriaAgent wraps the result in a `CooperationResult`
so the API surface stays uniform.

What we kept verbatim from v0.1:
- The reason-and-act loop (`for _step in range(self.max_steps)`)
- `AgentMemory` (conversation history)
- `ApprovalGate` (human-in-the-loop hook)
- `ToolRegistry` + the 5 builtin tools (calculator, web_search, file_reader,
  task_creator, email_draft)
- `CostTracker` and `TraceLog` integration
- The keyword-matching logic in `_plan_action` (calculator/search/file/task/email)
- The optional LLM fallback in `_plan_action` and `_generate_response`

What we renamed:
- The class `AriaAgent` → `KeywordRouterAgent` to free up the name for the
  new orchestrator in `agent.py`. The new AriaAgent is the canonical entry
  point; KeywordRouterAgent is one of the strategies it can use.

What we deliberately did NOT change:
- The keyword vocabulary. Adding/changing keywords is a behavior change.
- The `max_steps` default. Loops forever in name only (the original bug),
  but we don't fix that here — that's a KeywordRouterAgent-level concern,
  not the orchestrator's job. Fix it by either (a) giving it a real LLM in
  `_plan_action` that can decide when to stop, or (b) replacing the loop
  with the new router+cooperation flow.
- The `llm_client` shim. It's a placeholder for a real LLM client; real
  calls happen via the new provider layer.
"""
import re

from loguru import logger

from .approvals import ApprovalGate
from .memory import AgentMemory
from .tools import ToolRegistry


class KeywordRouterAgent:
    """Runs the original reason-and-act loop with keyword-based tool dispatch.

    This is the v0.1 Aria agent, preserved. The new `AriaAgent` (v0.3) is a
    cross-provider model router with cooperation patterns; it delegates
    tool-friendly queries here so all the v0.1 behavior still works.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        approval_gate: ApprovalGate,
        max_steps: int = 5,
        llm_client=None,
    ):
        self.registry = registry
        self.memory = AgentMemory()
        self.approval_gate = approval_gate
        self.max_steps = max_steps
        self.llm_client = llm_client

    def run(self, user_query: str, trace=None, cost_tracker=None) -> str:
        logger.info(f"KeywordRouterAgent received prompt: {user_query}")
        self.memory.add_message("user", user_query)
        context = self.memory.get_context()

        if trace:
            trace.add_reasoning(f"Processing query: {user_query}")

        for _step in range(self.max_steps):
            action, params = self._plan_action(user_query, context)

            if action is None:
                return self._generate_response(user_query, context)

            if not self.approval_gate.request_approval(action, params or {}):
                if trace:
                    trace.add_reasoning(f"Action '{action}' blocked by approval gate")
                return "Action blocked by approval gate."

            try:
                import time

                start = time.time()
                result = self.registry.call_tool(action, params or {})
                latency = (time.time() - start) * 1000.0

                if trace:
                    trace.add_tool_call(action, params or {}, result, latency)
                if cost_tracker:
                    cost_tracker.record_call("gpt-4o-mini", 100, 50, latency)

                self.memory.add_message(
                    "system", f"Tool '{action}' result: {result}"
                )
                return str(result)
            except KeyError as e:
                logger.error(f"Tool not found: {action} - {e}")
                return f"Error: Tool '{action}' not available."
            except Exception as e:
                logger.error(f"Tool '{action}' failed: {e}")
                if _step < self.max_steps - 1:
                    continue
                return f"Error executing '{action}': {e}"

        return "Agent reached maximum steps without resolving the request."

    def _plan_action(self, query: str, context: list) -> tuple:
        lowered = query.lower()

        if "calculate" in lowered:
            expr_match = re.search(
                r"(\d+(?:\.\d+)?)\s*([+\-*/])\s*(\d+(?:\.\d+)?)", query
            )
            if expr_match:
                return ("calculator", {"expression": expr_match.group(0)})
            return ("calculator", {"expression": "0"})

        if "search" in lowered or "find" in lowered or "look up" in lowered:
            return ("web_search", {"query": query})

        if "read" in lowered or "file" in lowered:
            import re as _re

            path_match = _re.search(r'["\']?([\w./\\-]+\.\w+)["\']?', query)
            path = path_match.group(1) if path_match else "README.md"
            return ("file_reader", {"filepath": path})

        if "task" in lowered or "create" in lowered or "remind" in lowered:
            return ("task_creator", {"title": query[:80], "description": query})

        if "email" in lowered or "draft" in lowered:
            return ("email_draft", {
                "recipient": "team@example.com",
                "subject": query[:80],
                "body": query,
            })

        if self.llm_client:
            try:
                self.llm_client.generate(
                    "gpt-4o-mini",
                    f"Choose the best tool for: {query}",
                    mocked_response="No matching tool found",
                )
                return (None, None)
            except Exception:
                pass

        return (None, None)

    def _generate_response(self, query: str, context: list) -> str:
        if self.llm_client:
            try:
                result = self.llm_client.generate(
                    "gpt-4o-mini",
                    f"Respond to: {query}. Context: {context[-3:]}",
                    mocked_response="I understand your request. Let me help with that.",
                )
                return result["response"]
            except Exception:
                pass
        return "I processed your request but no tool was matched."


# Backwards-compat alias. Old code that imports `AriaAgent` from
# `aria_agent.agents` will still get a working class — it's the same
# keyword-router logic, just under its old name. This keeps v0.1 callers
# working without changes.
AriaAgent = KeywordRouterAgent


__all__ = ["KeywordRouterAgent", "AriaAgent"]
