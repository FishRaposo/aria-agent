"""ARIA email draft tool — returns a structured draft, never sends.

Produces a JSON-serialisable draft object (and a human-readable rendering) but
performs no network I/O and dispatches no mail. This is a ``requires_approval``
permission-level tool because it produces an outbound communication artifact.
"""

import json

from pydantic import BaseModel, Field, field_validator


class EmailDraftInput(BaseModel):
    recipient: str = Field(description="Email recipient address")
    subject: str = Field(description="Email subject line")
    body: str = Field(description="Email body text")

    @field_validator("recipient")
    @classmethod
    def _basic_email_shape(cls, value: str) -> str:
        # Lightweight sanity check (avoids a hard email-validator dependency).
        if "@" not in value or "." not in value.split("@")[-1]:
            raise ValueError("recipient must look like an email address")
        return value


__all__ = ["EmailDraftInput", "email_draft"]


def email_draft(recipient: str, subject: str, body: str) -> str:
    """Return a structured (never-sent) email draft as a JSON string."""
    draft = {
        "status": "drafted",
        "sent": False,
        "to": recipient,
        "subject": subject,
        "body": body,
        "note": "Draft only — this tool never sends mail.",
    }
    return json.dumps(draft)
