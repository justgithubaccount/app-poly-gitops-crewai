"""FastAPI server for AutoK8sPilot with FlowRunner."""

from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from auto_k8s_pilot.crew import AutoK8sPilot
from auto_k8s_pilot.flow_runner import FlowRunner
from auto_k8s_pilot.observability import enrich_context, setup_tracing
from auto_k8s_pilot.settings import CONFIG_DIR, SETTINGS

app = FastAPI(
    title="AutoK8sPilot API",
    description="Multi-agent AI service for Kubernetes cluster monitoring",
    version="1.0.0",
)

# Setup OpenTelemetry tracing
setup_tracing(app)

# Initialize
crew_instance = AutoK8sPilot()
flow_runner = FlowRunner(crew_instance, CONFIG_DIR)


class RunRequest(BaseModel):
    namespace: str = "default"
    app_name: Optional[str] = None
    context: Optional[dict] = None


class StepResult(BaseModel):
    agent: str
    task: str
    output: str
    duration_ms: int


class RunResponse(BaseModel):
    final_answer: str
    steps: list[StepResult]
    metadata: dict


@app.get("/health")
async def health():
    """Health check endpoint."""
    enrich_context(event="health_check").info("Health check called")
    return {"status": "ok"}


@app.get("/flows")
async def list_flows():
    """List available flows."""
    log = enrich_context(event="list_flows_api")
    flows = flow_runner.list_flows()
    log.bind(flows_count=len(flows)).info("Listed available flows")
    return {"flows": flows}


@app.get("/agents")
async def list_agents():
    """List available agents from behavior.yaml."""
    log = enrich_context(event="list_agents_api")
    agents = flow_runner.list_agents()
    log.bind(agents_count=len(agents)).info("Listed available agents")
    return {"agents": agents}


@app.post("/run", response_model=RunResponse)
async def run_default(request: RunRequest):
    """Run default flow (k8s-healthcheck)."""
    return await run_flow_endpoint(SETTINGS.DEFAULT_FLOW, request)


@app.post("/run/{flow_name}", response_model=RunResponse)
async def run_flow_endpoint(flow_name: str, request: RunRequest):
    """Run specific flow by name."""
    log = enrich_context(
        event="run_flow_api",
        flow_name=flow_name,
        namespace=request.namespace,
    )
    log.info("Flow execution started")

    try:
        inputs = {
            "namespace": request.namespace,
            "app_name": request.app_name or "chat-api",
            **(request.context or {}),
        }

        result = flow_runner.run_flow(flow_name, inputs)

        log.bind(
            event="run_flow_complete",
            steps_count=len(result["steps"]),
            total_duration_ms=result["metadata"].get("total_duration_ms", 0),
        ).info("Flow execution completed")

        return RunResponse(
            final_answer=result["final_answer"],
            steps=[StepResult(**s) for s in result["steps"]],
            metadata=result["metadata"],
        )
    except FileNotFoundError:
        log.bind(event="flow_not_found").warning(f"Flow not found: {flow_name}")
        raise HTTPException(status_code=404, detail=f"Flow not found: {flow_name}")
    except Exception as e:
        log.bind(event="flow_error", error=str(e)).error("Flow execution failed")
        raise HTTPException(status_code=500, detail=str(e))


def main():
    """Entry point for API server."""
    import uvicorn

    uvicorn.run(
        "auto_k8s_pilot.api:app",
        host=SETTINGS.API_HOST,
        port=SETTINGS.API_PORT,
        reload=SETTINGS.ENVIRONMENT == "development",
    )


if __name__ == "__main__":
    main()
