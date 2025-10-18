FROM python:3.11-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install uv && uv pip install --system --no-cache -r pyproject.toml

COPY server/ ./server/

RUN mkdir -p /app/server/static

EXPOSE 8080

CMD ["uv", "run", "uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "warning", "--no-access-log"]
