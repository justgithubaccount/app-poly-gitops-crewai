# AutoK8sPilot

Multi-agent Kubernetes monitoring and incident management system powered by [crewAI](https://crewai.com).

## Features

- **9 Specialized Agents**: k8s_operator, reporting_analyst, infra_architect, argocd_observer, loki_analyst, incident_triager, cloudflare_admin, llm_gateway_observer, mcp_bridge
- **17 Tasks**: From pods overview to incident creation
- **YAML Flow Orchestration**: Define execution flows in YAML
- **FastAPI REST API**: HTTP endpoints for flow execution
- **Observability**: OpenTelemetry tracing + structlog JSON logging
- **Docker Ready**: Multi-stage build with uv package manager

## Quick Start

### Local Development

```bash
# Install dependencies
pip install uv
uv sync --dev

# Run API server
uv run api

# Or run crew directly
uv run run_crew
```

### Docker

```bash
# Build image
docker build -t auto-k8s-pilot .

# Run container
docker run -p 8000:8000 \
  -e OPENROUTER_API_KEY=your-key \
  auto-k8s-pilot
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/flows` | List available flows |
| GET | `/agents` | List available agents |
| POST | `/run` | Run default flow (k8s-healthcheck) |
| POST | `/run/{flow_name}` | Run specific flow |

### Example

```bash
# Health check
curl http://localhost:8000/health
# {"status":"ok"}

# List flows
curl http://localhost:8000/flows
# {"flows":["k8s-healthcheck","infra-health"]}

# List agents
curl http://localhost:8000/agents
# {"agents":["k8s_operator","reporting_analyst",...]}

# Run flow
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"namespace":"default"}'
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Core
DEFAULT_NAMESPACE=default
ALLOW_MUTATING=false

# API Server
API_HOST=0.0.0.0
API_PORT=8000

# OpenTelemetry
OTEL_SERVICE_NAME=auto-k8s-pilot
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318

# LLM Gateway
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_API_KEY=your-key

# Optional integrations
# ARGOCD_BASE_URL=https://argocd.example.com
# ARGOCD_API_TOKEN=
# LOKI_URL=http://loki:3100
# CLOUDFLARE_API_TOKEN=
# GITHUB_TOKEN=
```

### YAML Flows

Flows are defined in `src/auto_k8s_pilot/config/layers/`:

- `flow-k8s-healthcheck.yaml` - Kubernetes health monitoring
- `flow-infra-health.yaml` - Infrastructure health check

Example flow:

```yaml
steps:
  - run: k8s_pods_overview
  - run: explain_pods
  - run: k8s_top_nodes
  - run: cluster_summary
  - run: incident_create_issue_if_needed
```

## Project Structure

```
src/auto_k8s_pilot/
├── api.py              # FastAPI REST API
├── crew.py             # CrewAI agents and tasks
├── flow_runner.py      # YAML flow orchestrator
├── settings.py         # Pydantic settings
├── tools/              # Custom tools (kubectl, argocd, loki, etc.)
├── config/
│   ├── agents.yaml     # Agent definitions
│   ├── tasks.yaml      # Task definitions
│   └── layers/
│       ├── behavior.yaml
│       ├── flow-k8s-healthcheck.yaml
│       └── flow-infra-health.yaml
└── observability/
    ├── logger.py       # structlog JSON logging
    └── tracing.py      # OpenTelemetry setup
```

## Agents

| Agent | Role |
|-------|------|
| k8s_operator | Kubernetes cluster operations |
| reporting_analyst | Report generation |
| infra_architect | Infrastructure analysis |
| argocd_observer | ArgoCD monitoring |
| loki_analyst | Log analysis |
| incident_triager | Incident management |
| cloudflare_admin | DNS management |
| llm_gateway_observer | LLM gateway health |
| mcp_bridge | MCP server integration |

## Development

```bash
# Install dev dependencies
uv sync --dev

# Run tests
uv run pytest

# Type check
uv run mypy src/

# Lint
uv run ruff check src/
```

## License

MIT
