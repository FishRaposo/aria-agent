FROM python:3.10-slim

WORKDIR /app

COPY shared-core/ /shared-core/
RUN pip install -e /shared-core

COPY hermes-agent-framework/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY hermes-agent-framework/src/ ./src/

CMD ["uvicorn", "src.hermes.main:app", "--host", "0.0.0.0", "--port", "8000"]
