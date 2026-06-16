FROM python:3.11-slim

WORKDIR /app

# Install shared-core first so its layer caches well.
COPY shared-core/ /shared-core/
RUN pip install --no-cache-dir -e /shared-core

COPY hermes-agent-framework/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY hermes-agent-framework/src/ ./src/
COPY hermes-agent-framework/alembic/ ./alembic/
COPY hermes-agent-framework/alembic.ini .

ENV PYTHONPATH=/app/src

CMD ["uvicorn", "hermes.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
