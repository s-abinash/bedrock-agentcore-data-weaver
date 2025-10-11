FROM --platform=linux/arm64 python:3.11-slim

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

CMD ["python", "-m", "server.app"]
