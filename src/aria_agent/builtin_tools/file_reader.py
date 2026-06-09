from pydantic import BaseModel, Field


class FileReaderInput(BaseModel):
    filepath: str = Field(description="Path to the file to read")


def file_reader(filepath: str) -> str:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read(2000)
        return f"File contents (first 2000 chars):\n{content}"
    except FileNotFoundError:
        return f"Error: File not found at '{filepath}'"
    except PermissionError:
        return f"Error: Permission denied for '{filepath}'"
    except Exception as e:
        return f"Error reading file: {e}"
