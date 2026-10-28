# Multi-stage build with uv package manager
FROM python:3.12-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /usr/local/bin/uv

WORKDIR /app

# Copy source code for install
COPY pyproject.toml uv.lock ./
COPY src/ ./src/

# Install dependencies with increased timeout for large packages
ENV UV_HTTP_TIMEOUT=300
RUN uv sync --locked --no-dev --no-editable

ARG TARGETARCH=amd64
ARG KUBECTL_VERSION=v1.34.2
RUN python - "$TARGETARCH" "$KUBECTL_VERSION" <<'PY'
import hashlib
import pathlib
import sys
import urllib.request

arch, version = sys.argv[1:]
checksums = {
    "amd64": "9591f3d75e1581f3f7392e6ad119aab2f28ae7d6c6e083dc5d22469667f27253",
    "arm64": "95df604e914941f3172a93fa8feeb1a1a50f4011dfbe0c01e01b660afc8f9b85",
}
if arch not in checksums:
    raise SystemExit(f"unsupported architecture: {arch}")
target = pathlib.Path("/tmp/kubectl")
urllib.request.urlretrieve(
    f"https://dl.k8s.io/release/{version}/bin/linux/{arch}/kubectl", target
)
actual = hashlib.sha256(target.read_bytes()).hexdigest()
if actual != checksums[arch]:
    raise SystemExit(f"kubectl checksum mismatch: {actual}")
target.chmod(0o755)
PY

# Final stage
FROM python:3.12-slim

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /tmp/kubectl /usr/local/bin/kubectl

# Copy application code
COPY src/ ./src/
COPY knowledge/ ./knowledge/
COPY mcp/ ./mcp/
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

# Create output directory
RUN mkdir -p /app/output

# Set environment
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"
ENV ENVIRONMENT="production"

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run API server
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["python", "-m", "auto_k8s_pilot.api"]
