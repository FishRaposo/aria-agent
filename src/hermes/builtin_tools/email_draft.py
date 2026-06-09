from pydantic import BaseModel, Field


class EmailDraftInput(BaseModel):
    recipient: str = Field(description="Email recipient address")
    subject: str = Field(description="Email subject line")
    body: str = Field(description="Email body text")


def email_draft(recipient: str, subject: str, body: str) -> str:
    return (
        f"Draft email created:\n"
        f"To: {recipient}\n"
        f"Subject: {subject}\n"
        f"Body: {body[:200]}"
    )
