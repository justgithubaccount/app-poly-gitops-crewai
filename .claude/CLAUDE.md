# AutoK8sPilot - Project Context for Claude

## Overview

AutoK8sPilot is a multi-agent Kubernetes monitoring and incident management system built with crewAI framework. It provides automated cluster health monitoring, log analysis, and incident creation through specialized AI agents.

## Tech Stack

- **Python**: 3.10-3.13
- **Framework**: crewAI (multi-agent orchestration)
- **API**: FastAPI + Uvicorn
- **Package Manager**: uv (Astral)
- **Observability**: OpenTelemetry + structlog
- **Container**: Docker (multi-stage build)
- **Testing**: pytest + pytest-asyncio

## Project Structure

```
src/auto_k8s_pilot/
├── api.py              # FastAPI REST API (main entry point)
├── crew.py             # CrewAI agents and tasks definitions
├── flow_runner.py      # YAML flow orchestrator
├── main.py             # CLI entry point
├── settings.py         # Pydantic settings (env vars)
├── tools/              # Custom crewAI tools
│   ├── kubectl.py      # Kubernetes CLI wrapper
│   ├── argocd.py       # ArgoCD integration
│   ├── loki.py         # Loki log queries
│   ├── cloudflare.py   # DNS management
│   ├── openrouter.py   # LLM gateway
│   ├── mcp_k8s.py      # MCP server bridge
│   └── github.py       # GitHub issues
├── config/
│   ├── agents.yaml     # 9 agent definitions
│   ├── tasks.yaml      # 17+ task definitions
│   └── layers/
│       ├── behavior.yaml
│       ├── flow-k8s-healthcheck.yaml
│       └── flow-infra-health.yaml
└── observability/
    ├── logger.py       # structlog with trace_id
    └── tracing.py      # OpenTelemetry setup

tests/
├── conftest.py         # pytest fixtures
├── test_api.py         # FastAPI endpoint tests
├── test_flow_runner.py # FlowRunner tests
├── test_config.py      # YAML config validation
└── test_settings.py    # Settings tests
```

## Key Components

### Agents (9)

1. `k8s_operator` - Kubernetes operations (kubectl)
2. `reporting_analyst` - Report generation
3. `infra_architect` - Infrastructure analysis
4. `argocd_observer` - ArgoCD monitoring
5. `loki_analyst` - Log analysis
6. `incident_triager` - Incident management
7. `cloudflare_admin` - DNS management
8. `llm_gateway_observer` - LLM gateway health
9. `mcp_bridge` - MCP server integration

### API Endpoints

- `GET /health` - Health check
- `GET /flows` - List available flows
- `GET /agents` - List agents
- `POST /run` - Run default flow
- `POST /run/{flow_name}` - Run specific flow

### FlowRunner

Orchestrates task execution based on YAML flow definitions:

```yaml
steps:
  - run: k8s_pods_overview
  - run: explain_pods
  - run: cluster_summary
```

## Development Commands

```bash
# Install dependencies
uv sync --dev

# Run API server
uv run api

# Run crew directly
uv run run_crew

# Run tests
uv run pytest

# Type check
uv run mypy src/

# Lint
uv run ruff check src/

# Build Docker
docker build -t auto-k8s-pilot .
```

## Environment Variables

Key settings in `.env`:

- `DEFAULT_NAMESPACE` - K8s namespace (default: "default")
- `ALLOW_MUTATING` - Allow write operations (default: false)
- `API_HOST` / `API_PORT` - API server config
- `OTEL_EXPORTER_OTLP_ENDPOINT` - OpenTelemetry endpoint
- `OPENROUTER_API_KEY` - LLM API key
- `LOKI_URL` - Loki server
- `ARGOCD_BASE_URL` / `ARGOCD_API_TOKEN` - ArgoCD
- `CLOUDFLARE_API_TOKEN` - Cloudflare DNS
- `GITHUB_TOKEN` - GitHub issues

## Testing

Tests are in `tests/` directory:

- 40 unit tests covering API, FlowRunner, config, settings
- Uses pytest-asyncio for async tests
- Mocks kubectl and external services

## Important Notes

1. **Safety**: `ALLOW_MUTATING=false` by default - no write operations
2. **Flows**: Defined in `config/layers/flow-*.yaml`
3. **Agents/Tasks**: Defined in `config/agents.yaml` and `config/tasks.yaml`
4. **Behavior**: Layer overrides in `config/layers/behavior.yaml`
5. **Docker**: Multi-stage build, ~1GB image size

## Common Tasks

### Add new agent

1. Add to `config/agents.yaml`
2. Add to `config/layers/behavior.yaml`
3. Create tool in `tools/` if needed
4. Update `crew.py` with @agent decorator

### Add new task

1. Add to `config/tasks.yaml`
2. Add to `config/layers/behavior.yaml`
3. Update `crew.py` with @task decorator
4. Add to `flow_runner.py` tasks_map

### Add new flow

1. Create `config/layers/flow-{name}.yaml`
2. Define steps with task names
3. Flow will be auto-discovered by FlowRunner
