"""Small injectable retry policy used by safe tool execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 1
    backoff_seconds: float = 0.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.backoff_seconds < 0:
            raise ValueError("backoff_seconds cannot be negative")


@dataclass(frozen=True)
class RetryOutcome(Generic[T]):
    value: T
    attempts: int


def execute_with_retry(
    operation: Callable[[], T],
    policy: RetryPolicy,
    *,
    sleep: Callable[[float], None],
) -> RetryOutcome[T]:
    """Execute an operation, doubling the configured delay after each failure."""
    last_error: Exception | None = None
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return RetryOutcome(operation(), attempt)
        except Exception as exc:  # noqa: BLE001 - caller receives final failure
            last_error = exc
            if attempt < policy.max_attempts:
                sleep(policy.backoff_seconds * (2 ** (attempt - 1)))
    assert last_error is not None
    raise last_error
