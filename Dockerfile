FROM python:3.11-slim

WORKDIR /app

# The image is built from this repository alone.  Optional PostgreSQL/Redis
# services are supplied by docker-compose, never copied from a sibling repo.
COPY pyproject.toml README.md LICENSE requirements.txt ./
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./

RUN pip install --no-cache-dir .

ENV PYTHONPATH=/app/src

EXPOSE 8000
CMD ["uvicorn", "aria.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
