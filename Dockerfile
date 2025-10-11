FROM --platform=linux/arm64 python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install uv && uv pip install --system --no-cache -r pyproject.toml

COPY agents/ ./agents/
COPY tools/ ./tools/
COPY s3_loader.py .
COPY data_analyzer.py .
COPY app.py .

RUN mkdir -p /app/static

EXPOSE 8080

CMD ["python", "app.py"]
