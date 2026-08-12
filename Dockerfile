FROM python:3.11-slim

WORKDIR /app

# Install shared-core first so its layer caches well.
COPY shared-core/ /shared-core/
RUN pip install --no-cache-dir -e /shared-core

COPY aria-agent-framework/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY aria-agent-framework/src/ ./src/
COPY aria-agent-framework/alembic/ ./alembic/
COPY aria-agent-framework/alembic.ini .

ENV PYTHONPATH=/app/src

CMD ["uvicorn", "aria.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
