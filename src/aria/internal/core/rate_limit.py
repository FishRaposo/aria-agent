"""Deterministic in-memory fixed-window rate limiting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    retry_after_seconds: float = 0.0
    reason: str = "allowed"

    def to_dict(self) -> dict[str, object]:
        return {
            "allowed": self.allowed,
            "remaining": self.remaining,
            "retry_after_seconds": self.retry_after_seconds,
            "reason": self.reason,
        }


class FixedWindowRateLimiter:
    def __init__(
        self,
        *,
        limit: int,
        window_seconds: float,
        clock: Callable[[], float],
    ) -> None:
        if limit < 1 or window_seconds <= 0:
            raise ValueError("limit must be positive and window_seconds must be > 0")
        self.limit = limit
        self.window_seconds = window_seconds
        self.clock = clock
        self._windows: dict[tuple[str, str], tuple[int, int]] = {}

    def allow(self, session_id: str, tool: str) -> RateLimitDecision:
        now = self.clock()
        window = int(now // self.window_seconds)
        key = (session_id, tool)
        current_window, count = self._windows.get(key, (window, 0))
        if current_window != window:
            count = 0
            current_window = window
        if count >= self.limit:
            retry_after = (window + 1) * self.window_seconds - now
            self._windows[key] = (current_window, count)
            return RateLimitDecision(
                allowed=False,
                remaining=0,
                retry_after_seconds=round(max(0.0, retry_after), 3),
                reason="rate limit exceeded",
            )
        count += 1
        self._windows[key] = (current_window, count)
        return RateLimitDecision(
            allowed=True,
            remaining=self.limit - count,
        )
