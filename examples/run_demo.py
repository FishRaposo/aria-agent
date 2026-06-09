import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from pydantic import BaseModel, Field

from hermes.agents import HermesAgent
from hermes.approvals import ApprovalGate
from hermes.tools import ToolRegistry


class CalculatorSchema(BaseModel):
    expression: str = Field(description="Math expression to compute")

def main():
    registry = ToolRegistry()

    @registry.register("calculator", CalculatorSchema)
    def calculator_fn(expression: str) -> str:
        try:
            return str(eval(expression, {"__builtins__": None}))
        except Exception as e:
            return f"Error: {e}"

    gate = ApprovalGate(enabled=True)
    agent = HermesAgent(registry, gate)

    print("--- Running Aria Agent Flow Demo ---")
    response = agent.run("Please calculate 120 + 350")
    print(f"Agent Final Output: {response}")

if __name__ == "__main__":
    main()
