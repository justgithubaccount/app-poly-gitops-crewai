# Multi-stage build with uv package manager
FROM python:3.12-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy source code for install
COPY pyproject.toml ./
COPY src/ ./src/

# Install dependencies with increased timeout for large packages
ENV UV_HTTP_TIMEOUT=300
RUN uv venv .venv && \
    . .venv/bin/activate && \
    uv pip install --no-cache -e .

# Final stage
FROM python:3.12-slim

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY src/ ./src/
COPY knowledge/ ./knowledge/
COPY mcp/ ./mcp/

# Create output directory
RUN mkdir -p /app/output

# Set environment
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run API server
CMD ["python", "-m", "auto_k8s_pilot.api"]
