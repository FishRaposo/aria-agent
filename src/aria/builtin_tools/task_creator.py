"""ARIA task creator tool — persists a task.

By default (no store wired) it returns a deterministic confirmation string so the
tool works fully offline in tests and the demo. When bound to a task store via
``make_task_creator`` it persists a real row (DB-backed or in-memory) and returns
the created task's id. This is a ``requires_approval`` permission-level tool
because it performs a write.
"""

from typing import Any, Callable

from pydantic import BaseModel, Field


class TaskCreatorInput(BaseModel):
    title: str = Field(description="Title of the task")
    description: str = Field(
        default="", description="Description of what needs to be done"
    )


def task_creator(title: str, description: str = "") -> str:
    """Stateless task creation (no persistence) — used in tests/demo."""
    return f"Task created: '{title}' — {description[:200]}"


def make_task_creator(store: Any) -> Callable[[str, str], str]:
    """Return a task_creator bound to ``store`` that persists each task."""

    def _persisting_task_creator(title: str, description: str = "") -> str:
        task = store.create(title=title, description=description)
        return f"Task created (id={task['id']}): '{title}' — {description[:200]}"

    return _persisting_task_creator
