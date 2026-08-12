"""ARIA safe arithmetic calculator tool.

Evaluates a mathematical expression using a restricted AST walk rather than
``eval()``. Only literals and a small whitelist of binary/unary operators are
permitted, so the tool can never execute arbitrary code, call functions, access
attributes, or read names. This is a ``safe`` permission-level tool.
"""

import ast
import operator
from typing import Any

from pydantic import BaseModel, Field

# Whitelisted operators. Anything outside this map is rejected.
_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

# Guard against resource-exhaustion via huge exponents (e.g. ``9**9**9``).
_MAX_POW_EXPONENT = 1000


class CalculatorInput(BaseModel):
    expression: str = Field(
        description="Arithmetic expression to evaluate, e.g. '2 + 2 * 3'"
    )


class _SafeEvaluator(ast.NodeVisitor):
    """Recursively evaluate a parsed arithmetic expression AST."""

    def visit(self, node: ast.AST) -> Any:  # noqa: C901
        if isinstance(node, ast.Expression):
            return self.visit(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise ValueError("Only numeric literals are allowed")
            return node.value
        if isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type not in _BIN_OPS:
                raise ValueError(f"Operator {op_type.__name__} is not allowed")
            left = self.visit(node.left)
            right = self.visit(node.right)
            if op_type is ast.Pow and abs(right) > _MAX_POW_EXPONENT:
                raise ValueError("Exponent too large")
            return _BIN_OPS[op_type](left, right)
        if isinstance(node, ast.UnaryOp):
            op_type = type(node.op)
            if op_type not in _UNARY_OPS:
                raise ValueError(f"Unary operator {op_type.__name__} is not allowed")
            return _UNARY_OPS[op_type](self.visit(node.operand))
        raise ValueError(f"Unsupported expression element: {type(node).__name__}")


def safe_eval(expression: str) -> float:
    """Evaluate an arithmetic expression with no access to names or calls.

    Raises ``ValueError`` for any disallowed construct (names, attribute access,
    function calls, comparisons, subscripts, etc.).
    """
    parsed = ast.parse(expression, mode="eval")
    result = _SafeEvaluator().visit(parsed)
    if isinstance(result, complex):
        raise ValueError("complex result not supported")
    return result


def calculator(expression: str) -> str:
    """Safely evaluate ``expression`` and return a formatted result string."""
    try:
        result = safe_eval(expression)
    except ZeroDivisionError:
        return "Error evaluating expression: division by zero"
    except (ValueError, SyntaxError, TypeError, OverflowError) as exc:
        return f"Error evaluating expression: {exc}"
    # Normalise integral floats (4.0 -> 4) for readability.
    if isinstance(result, float) and result.is_integer():
        result = int(result)
    return f"Result: {result}"
