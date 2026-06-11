"""Calculator tool (v0.1 builtin, v0.4 hardened).

Replaces the original `eval()` call with a safe AST-walked arithmetic parser.
The prior version used `eval(expression, {"__builtins__": {}}, {})` which is
safer than raw eval but still risky — a sandbox escape in CPython could
allow arbitrary execution. The new version parses the expression into an AST
and only walks a fixed set of node types: BinOp, UnaryOp, Constant, Add, Sub,
Mult, Div, FloorDiv, Mod, Pow, USub/UAdd, and parentheses.

Supported:
- Integer and float literals (incl. scientific notation like `1e3`)
- `+ - * / // % **` and unary `- +`
- Parentheses for grouping
- Mixed int/float arithmetic

Not supported (returns a friendly error):
- Variables, function calls, attribute access, subscripts
- String operations, comparisons, boolean logic
- Anything that isn't pure arithmetic

The error message tells the user what went wrong and what is allowed.
"""
from __future__ import annotations

import ast
import math
import operator
from typing import Union

from pydantic import BaseModel, Field


class CalculatorInput(BaseModel):
    expression: str = Field(description="Mathematical expression to evaluate, e.g. '2 + 2'")


Number = Union[int, float]


# AST node -> (callable taking two operands, or None for unary).
_BINOPS: dict[type, object] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARYOPS: dict[type, object] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _eval_node(node: ast.AST) -> Number:
    """Recursively evaluate a whitelisted AST node. Raises ValueError on anything else."""
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ValueError(f"unsupported literal: {type(node.value).__name__}")
        return node.value
    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _UNARYOPS:
            raise ValueError(f"unsupported unary operator: {op_type.__name__}")
        return _UNARYOPS[op_type](_eval_node(node.operand))  # type: ignore[operator]
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _BINOPS:
            raise ValueError(f"unsupported binary operator: {op_type.__name__}")
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        try:
            return _BINOPS[op_type](left, right)  # type: ignore[operator]
        except ZeroDivisionError as exc:
            raise ValueError(str(exc)) from exc
    raise ValueError(f"unsupported expression node: {type(node).__name__}")


def calculator(expression: str) -> str:
    """Safely evaluate a pure-arithmetic expression. Returns 'Result: <n>' or 'Error: ...'.

    Examples:
        calculator("2 + 2")             -> "Result: 4"
        calculator("(3 + 4) * 2")       -> "Result: 14"
        calculator("2 ** 10")           -> "Result: 1024"
        calculator("math.sqrt(16)")     -> "Error: unsupported expression node: Call"
    """
    if not isinstance(expression, str) or not expression.strip():
        return "Error: expression must be a non-empty string"
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        return f"Error: invalid syntax ({exc.msg})"
    try:
        result = _eval_node(tree)
    except ValueError as exc:
        return f"Error: {exc}"
    except Exception as exc:  # last-resort guard; should not be reachable
        return f"Error: unexpected failure: {exc}"
    # Normalize ints when the result is whole, otherwise keep the float repr.
    if isinstance(result, float) and result.is_integer() and abs(result) < 1e16:
        result = int(result)
    return f"Result: {result}"


__all__ = ["CalculatorInput", "calculator"]
