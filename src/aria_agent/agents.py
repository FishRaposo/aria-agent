import re

from loguru import logger

from .approvals import ApprovalGate
from .memory import AgentMemory
from .tools import ToolRegistry


class AriaAgent:
    """Runs the central reason-and-act loop with tool execution constraints."""

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
        logger.info(f"Agent received prompt: {user_query}")
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
