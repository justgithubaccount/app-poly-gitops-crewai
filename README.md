# AutoK8sPilot

FastAPI and CrewAI service for inspecting Kubernetes and related platform
integrations. It provides YAML-defined flows, bounded tools, and OpenTelemetry
instrumentation for the `app-poly-gitops` engineering lab.

## Overview

The default `k8s-healthcheck` flow is deterministic: it runs read-only
`kubectl` queries, preserves their evidence scope, counts pod states without an
LLM, and reports unavailable metrics as unknown. It does not infer that an
unobserved component is healthy, unhealthy, installed, or absent.

The longer `infra-health` flow also invokes CrewAI tasks for Argo CD, Loki,
Cloudflare, an LLM gateway, MCP, and incident handling. Those steps require the
corresponding endpoints and credentials. Mutating tool operations remain disabled
unless `ALLOW_MUTATING=true`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Service liveness |
| `GET` | `/flows` | List discovered flow files |
| `GET` | `/agents` | List configured agents |
| `POST` | `/run` | Run the configured default flow |
| `POST` | `/run/{flow_name}` | Run a named flow |

Flow responses contain a final answer, completed step records, timing metadata,
and a trace ID when tracing is active. Execution is synchronous; the API does not
provide run persistence, progress streaming, or cancellation.

`behavior.yaml` is the routed task registry. On startup the API discovers task
factories from it and validates every `flow-*.yaml` reference, so an unknown task
fails configuration instead of producing a partial successful run.

## Getting started

Requirements: Python 3.10–3.13, [uv](https://docs.astral.sh/uv/), and
`kubectl` for Kubernetes reads.

~~~bash
cp .env.example .env
uv sync --locked --dev
uv run api
~~~

The API listens on `http://127.0.0.1:8000` by default. Inspect the available
flows and run the deterministic health check:

~~~bash
curl http://127.0.0.1:8000/flows
curl -X POST http://127.0.0.1:8000/run/k8s-healthcheck \
  -H 'Content-Type: application/json' \
  -d '{"namespace":"default"}'
~~~

Set `KUBECONFIG` or use the in-cluster service account identity. The container
includes a matching `kubectl` client and configures the mounted service-account
credentials at startup.

## Configuration

The complete example is in [.env.example](.env.example). Important boundaries:

- `DEFAULT_NAMESPACE` and `DEFAULT_FLOW` select the default scope.
- `ALLOW_MUTATING` defaults to `false`.
- `OPENAI_API_KEY` is used by CrewAI tasks that call a model.
- `ARGOCD_BASE_URL`, `LOKI_URL`, Cloudflare, GitHub, OpenRouter, and MCP
  variables configure optional integrations.
- `OTEL_EXPORTER_OTLP_ENDPOINT` and `OTEL_TRACES_EXPORTER=otlp` enable trace
  export; export is disabled by default.

## Repository structure

- `src/auto_k8s_pilot/api.py` — HTTP API
- `src/auto_k8s_pilot/flow_runner.py` — YAML flow execution and deterministic health reporting
- `src/auto_k8s_pilot/crew.py` — CrewAI agents and tasks
- `src/auto_k8s_pilot/config/` — agent, task, behavior, and flow definitions
- `src/auto_k8s_pilot/tools/` — Kubernetes and integration tools
- `output/` — ignored generated task results; never a runtime or test input
- `tests/` — contract, safety, flow, telemetry, and container tests

The Docker image retains `knowledge/user_preference.txt` and
`mcp/mcp-argocd.json` as optional CrewAI/MCP scaffolding. Neither is read by the
current API or deterministic health flow, so their operational status is
optional/unknown rather than grounds for deleting their compatibility surface.
`config/layers/crew-infra-cluster.yaml` is likewise descriptive scaffold; the
active API registry and flow definitions are `behavior.yaml` and `flow-*.yaml`.
The service uses custom `BaseTool` implementations from CrewAI core; the
unreferenced `crewai-tools` extra is intentionally not installed.

## Development

~~~bash
uv run ruff check src tests
OTEL_SDK_DISABLED=true uv run pytest
uv run mypy src
sh tests/test_container_entrypoint.sh
~~~

Tagged releases publish
`ghcr.io/justgithubaccount/app-poly-gitops-crewai:<version>`.

## Related repositories

- [app-poly-gitops-ui](https://github.com/justgithubaccount/app-poly-gitops-ui) — manual flow UI
- [app-poly-gitops-k8s](https://github.com/justgithubaccount/app-poly-gitops-k8s) — Kubernetes runtime and RBAC
- [app-poly-gitops-infra](https://github.com/justgithubaccount/app-poly-gitops-infra) — provisioning and smoke workflows
- [app-mono-gitops](https://github.com/justgithubaccount/app-mono-gitops) — archived predecessor

## License

MIT
