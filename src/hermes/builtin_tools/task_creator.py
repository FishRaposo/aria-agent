from pydantic import BaseModel, Field


class TaskCreatorInput(BaseModel):
    title: str = Field(description="Title of the task")
    description: str = Field(description="Description of what needs to be done")


def task_creator(title: str, description: str) -> str:
    return f"Task created: '{title}' — {description[:200]}"
