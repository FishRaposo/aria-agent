from pydantic import BaseModel, Field


class WebSearchInput(BaseModel):
    query: str = Field(description="The search query string")


def web_search(query: str) -> str:
    results = {
        "python": "Python is a high-level programming language created by Guido van Rossum in 1991.",
        "rag": "RAG (Retrieval-Augmented Generation) combines information retrieval with text generation.",
        "default": "No relevant results found for that query.",
    }
    query_lower = query.lower()
    for key in results:
        if key in query_lower:
            return f"Web search result: {results[key]}"
    return f"Web search result: {results['default']}"
