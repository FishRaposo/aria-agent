FROM python:3.11-slim

WORKDIR /app

# uv is used only to export the locked runtime dependency set from uv.lock.
COPY --from=ghcr.io/astral-sh/uv:0.8.17 /uv /usr/local/bin/uv

# The image is built from this repository alone.  Optional PostgreSQL/Redis
# services are supplied by docker-compose, never copied from a sibling repo.
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Runtime dependencies come hash-checked from uv.lock; the package adds none.
RUN uv export --locked --quiet --no-dev --no-emit-project --format requirements-txt -o /tmp/requirements.lock \
    && pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock \
    && pip install --no-cache-dir --no-deps . \
    && pip check \
    && rm /tmp/requirements.lock

ENV PYTHONPATH=/app/src

EXPOSE 8000
CMD ["uvicorn", "aria.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
