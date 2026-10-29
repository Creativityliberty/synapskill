FROM python:3.11-slim

WORKDIR /app

# Prevent python from buffering stdout/stderr
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/skills/numtema-synapse/scripts

# Install curl for Coolify/Docker healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create directory for SQLite state persistence
RUN mkdir -p /app/state

EXPOSE 8000

# Healthcheck checking both PORT env variable or default 8000/3000
HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT:-8000}/health" || curl -fsS "http://127.0.0.1:8000/health" || curl -fsS "http://127.0.0.1:3000/health" || exit 1

CMD ["python3", "skills/numtema-synapse/scripts/mcp_http_server.py"]
