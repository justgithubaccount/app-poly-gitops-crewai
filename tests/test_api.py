"""Tests for FastAPI endpoints."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client."""
    from auto_k8s_pilot.api import app

    return TestClient(app)


def test_health_endpoint(client):
    """Test GET /health returns ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_flows_endpoint(client):
    """Test GET /flows returns list of flows."""
    response = client.get("/flows")
    assert response.status_code == 200

    data = response.json()
    assert "flows" in data
    assert isinstance(data["flows"], list)
    # Should have k8s-healthcheck and infra-health
    assert "k8s-healthcheck" in data["flows"]


def test_agents_endpoint(client):
    """Test GET /agents returns list of agents."""
    response = client.get("/agents")
    assert response.status_code == 200

    data = response.json()
    assert "agents" in data
    assert isinstance(data["agents"], list)
    assert len(data["agents"]) == 9  # 9 agents in app-crewai-cluster

    expected_agents = [
        "k8s_operator",
        "reporting_analyst",
        "infra_architect",
        "argocd_observer",
        "loki_analyst",
        "incident_triager",
        "cloudflare_admin",
        "llm_gateway_observer",
        "mcp_bridge",
    ]

    for agent_id in expected_agents:
        assert agent_id in data["agents"]


def test_run_endpoint_requires_no_body(client):
    """Test POST /run works without body (uses defaults)."""
    # This will attempt to run but may fail due to missing K8s - that's OK for unit test
    response = client.post("/run", json={})
    # Should not be 422 validation error
    assert response.status_code != 422


def test_run_flow_not_found(client):
    """Test POST /run/{flow} returns 404 for unknown flow."""
    response = client.post(
        "/run/nonexistent-flow",
        json={"namespace": "default"},
    )
    assert response.status_code == 404


def test_run_request_schema(client):
    """Test run request accepts valid schema."""
    request_data = {
        "namespace": "default",
        "app_name": "chat-api",
        "context": {"key": "value"},
    }
    # Validate schema is accepted (not 422)
    response = client.post("/run/nonexistent-flow", json=request_data)
    # Should be 404 (flow not found) not 422 (validation error)
    assert response.status_code == 404
