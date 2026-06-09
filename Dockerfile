FROM python:3.10-slim

WORKDIR /app

COPY shared-core/ /shared-core/
RUN pip install -e /shared-core

COPY aria-agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY aria-agent/src/ ./src/

CMD ["uvicorn", "src.aria_agent.main:app", "--host", "0.0.0.0", "--port", "8000"]
