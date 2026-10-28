"""Tests for FlowRunner."""

import types

import litellm
import pytest
import yaml

from auto_k8s_pilot.crew import AutoK8sPilot
from auto_k8s_pilot.flow_runner import FlowRunner
from auto_k8s_pilot.settings import CONFIG_DIR


def write_flow_config(config_dir, task_id="k8s_pods_overview"):
    """Write the smallest real FlowRunner configuration for one task."""
    layers_dir = config_dir / "layers"
    layers_dir.mkdir(parents=True)
    (layers_dir / "flow-test.yaml").write_text(
        yaml.safe_dump({"steps": [{"run": task_id}]}),
        encoding="utf-8",
    )
    (layers_dir / "behavior.yaml").write_text(
        yaml.safe_dump(
            {
                "agents": [{"id": "k8s_operator", "profile": "k8s_operator"}],
                "tasks": [{"id": task_id, "agent": "k8s_operator"}],
            }
        ),
        encoding="utf-8",
    )


@pytest.fixture
def flow_runner():
    """Create FlowRunner instance."""
    crew = AutoK8sPilot()
    return FlowRunner(crew, CONFIG_DIR)


def test_flow_runner_instantiation(flow_runner):
    """Test FlowRunner can be instantiated."""
    assert flow_runner is not None


def test_flow_runner_has_crew(flow_runner):
    """Test FlowRunner has crew attribute."""
    assert hasattr(flow_runner, "crew")
    assert flow_runner.crew is not None


def test_flow_runner_has_config_dir(flow_runner):
    """Test FlowRunner has config_dir attribute."""
    assert hasattr(flow_runner, "config_dir")
    assert flow_runner.config_dir == CONFIG_DIR


def test_flow_runner_has_tasks_map(flow_runner):
    """Test FlowRunner has tasks_map."""
    assert hasattr(flow_runner, "tasks_map")
    assert isinstance(flow_runner.tasks_map, dict)


def test_flow_runner_tasks_map_has_core_tasks(flow_runner):
    """Test tasks_map contains core K8s tasks."""
    core_tasks = [
        "k8s_pods_overview",
        "explain_pods",
        "cluster_summary",
        "k8s_top_nodes",
        "argocd_list_apps",
        "loki_recent_errors_chat_api",
        "dns_check_records",
        "llm_gateway_health",
        "mcp_k8s_env_check",
        "incident_create_issue_if_needed",
    ]

    for task_id in core_tasks:
        assert task_id in flow_runner.tasks_map, f"Task '{task_id}' not in tasks_map"


def test_list_flows(flow_runner):
    """Test list_flows returns available flows."""
    flows = flow_runner.list_flows()
    assert isinstance(flows, list)
    assert "k8s-healthcheck" in flows
    assert "infra-health" in flows


def test_list_agents(flow_runner):
    """Test list_agents returns available agents."""
    agents = flow_runner.list_agents()
    assert isinstance(agents, list)
    assert len(agents) == 9

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
        assert agent_id in agents


def test_load_flow_k8s_healthcheck(flow_runner):
    """Test load_flow loads k8s-healthcheck flow."""
    flow = flow_runner.load_flow("k8s-healthcheck")
    assert flow is not None
    assert "steps" in flow


def test_load_flow_not_found(flow_runner):
    """Test load_flow raises FileNotFoundError for unknown flow."""
    with pytest.raises(FileNotFoundError):
        flow_runner.load_flow("nonexistent-flow")


def test_extract_final_answer_from_results(flow_runner):
    """Test _extract_final_answer extracts from last step."""
    results = [
        {"task": "k8s_pods_overview", "output": "pods output"},
        {"task": "cluster_summary", "output": "cluster summary here"},
    ]

    answer = flow_runner._extract_final_answer(results)
    assert answer == "cluster summary here"


def test_extract_final_answer_empty_results(flow_runner):
    """Test _extract_final_answer handles empty results."""
    answer = flow_runner._extract_final_answer([])
    assert answer == ""


def test_extract_metadata(flow_runner):
    """Test _extract_metadata extracts relevant data."""
    results = [
        {"task": "cluster_summary", "output": "All pods healthy"},
        {"task": "incident_create_issue_if_needed", "output": "No incident filed"},
    ]

    metadata = flow_runner._extract_metadata(results)
    assert "cluster_summary" in metadata
    assert metadata.get("incident_created") is False


def test_extract_metadata_with_incident(flow_runner):
    """Test _extract_metadata detects incident creation."""
    results = [
        {"task": "cluster_summary", "output": "Pods failing"},
        {"task": "incident_create_issue_if_needed", "output": "Created issue #123"},
    ]

    metadata = flow_runner._extract_metadata(results)
    assert metadata.get("incident_created") is True


def test_run_flow_executes_real_crewai_task(monkeypatch, tmp_path):
    """Catch regressions that call a removed CrewAI Task execution method."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def fake_completion(*args, **kwargs):
        return types.SimpleNamespace(
            choices=[
                types.SimpleNamespace(
                    message=types.SimpleNamespace(content="pod-1 1/1 Running 2d node-a")
                )
            ]
        )

    monkeypatch.setattr(litellm, "completion", fake_completion)
    write_flow_config(tmp_path)

    runner = FlowRunner(AutoK8sPilot(), tmp_path)
    real_task_factory = runner.tasks_map["k8s_pods_overview"]

    def task_with_temporary_output():
        task = real_task_factory()
        task.output_file = str(tmp_path / "pods_overview.md")
        return task

    runner.tasks_map["k8s_pods_overview"] = task_with_temporary_output
    result = runner.run_flow("test", {"namespace": "default"})

    assert result["final_answer"] == "pod-1 1/1 Running 2d node-a"
    assert result["steps"] == [
        {
            "agent": "k8s_operator",
            "task": "k8s_pods_overview",
            "output": "pod-1 1/1 Running 2d node-a",
            "duration_ms": result["steps"][0]["duration_ms"],
        }
    ]


def test_run_flow_does_not_mask_task_execution_failure(tmp_path):
    """A failed task must fail the request instead of returning a false success."""

    class FailingTask:
        def execute_sync(self, context=None):
            raise ValueError("LLM unavailable")

    write_flow_config(tmp_path)
    runner = FlowRunner(AutoK8sPilot(), tmp_path)
    runner.tasks_map["k8s_pods_overview"] = lambda: FailingTask()

    with pytest.raises(
        RuntimeError,
        match="Flow 'test' failed at task 'k8s_pods_overview': LLM unavailable",
    ):
        runner.run_flow("test", {"namespace": "default"})
