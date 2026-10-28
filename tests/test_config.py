"""Tests for configuration files."""

import yaml

from auto_k8s_pilot.settings import CONFIG_DIR, LAYERS_DIR


def test_config_dir_exists():
    """Test config directory exists."""
    assert CONFIG_DIR.exists()
    assert CONFIG_DIR.is_dir()


def test_layers_dir_exists():
    """Test layers directory exists."""
    assert LAYERS_DIR.exists()
    assert LAYERS_DIR.is_dir()


def test_agents_yaml_exists():
    """Test agents.yaml exists and is valid."""
    agents_file = CONFIG_DIR / "agents.yaml"
    assert agents_file.exists()

    with open(agents_file) as f:
        agents = yaml.safe_load(f)

    assert agents is not None
    assert len(agents) == 9  # 9 agents defined


def test_tasks_yaml_exists():
    """Test tasks.yaml exists and is valid."""
    tasks_file = CONFIG_DIR / "tasks.yaml"
    assert tasks_file.exists()

    with open(tasks_file) as f:
        tasks = yaml.safe_load(f)

    assert tasks is not None
    assert len(tasks) >= 17  # 17+ tasks


def test_behavior_yaml_exists():
    """Test behavior.yaml exists and is valid."""
    behavior_file = LAYERS_DIR / "behavior.yaml"
    assert behavior_file.exists()

    with open(behavior_file) as f:
        behavior = yaml.safe_load(f)

    assert "agents" in behavior
    assert "tasks" in behavior
    assert len(behavior["agents"]) == 9
    assert len(behavior["tasks"]) >= 15


def test_flow_files_exist():
    """Test flow-*.yaml files exist."""
    flow_files = list(LAYERS_DIR.glob("flow-*.yaml"))
    assert len(flow_files) >= 2

    flow_names = [f.stem.replace("flow-", "") for f in flow_files]
    assert "k8s-healthcheck" in flow_names
    assert "infra-health" in flow_names


def test_flow_k8s_healthcheck_structure():
    """Test k8s-healthcheck flow has correct structure."""
    flow_file = LAYERS_DIR / "flow-k8s-healthcheck.yaml"

    with open(flow_file) as f:
        flow = yaml.safe_load(f)

    assert "steps" in flow
    step_tasks = [s.get("run") for s in flow["steps"]]
    assert step_tasks == [
        "k8s_top_nodes",
        "k8s_top_pods_ns_default",
        "k8s_pods_overview",
        "explain_pods",
        "cluster_summary",
        "k8s_events_recent",
    ]


def test_agents_have_required_fields():
    """Test all agents have required fields."""
    agents_file = CONFIG_DIR / "agents.yaml"

    with open(agents_file) as f:
        agents = yaml.safe_load(f)

    for agent_id, agent_config in agents.items():
        assert "role" in agent_config, f"Agent {agent_id} missing 'role'"
        assert "goal" in agent_config, f"Agent {agent_id} missing 'goal'"
        assert "backstory" in agent_config, f"Agent {agent_id} missing 'backstory'"


def test_tasks_have_required_fields():
    """Test all tasks have required fields."""
    tasks_file = CONFIG_DIR / "tasks.yaml"

    with open(tasks_file) as f:
        tasks = yaml.safe_load(f)

    for task_id, task_config in tasks.items():
        assert "description" in task_config, f"Task {task_id} missing 'description'"
        assert "expected_output" in task_config, f"Task {task_id} missing 'expected_output'"


def test_k8s_health_prompts_are_grounded_and_namespace_aware():
    """Health reports must not invent components or ignore the requested namespace."""
    tasks_file = CONFIG_DIR / "tasks.yaml"

    with open(tasks_file) as f:
        tasks = yaml.safe_load(f)

    summary = tasks["cluster_summary"]["description"]
    assert "Only report components explicitly present" in summary
    assert "not observed in the supplied snapshot" in summary
    assert "Do not infer" in summary

    top_pods = tasks["k8s_top_pods_ns_default"]["description"]
    assert "namespace from the flow context" in top_pods
    assert "default only when no namespace" in top_pods

    top_nodes = tasks["k8s_top_nodes"]["description"]
    assert "Do not claim that Metrics Server is running" in top_nodes

    incident = tasks["incident_create_issue_if_needed"]["description"]
    assert "ALLOW_MUTATING=true" in incident
