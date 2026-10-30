"""Native CrewAI provider routing: no live LLM requests."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from auto_k8s_pilot import crew as crew_module
from auto_k8s_pilot.crew import AutoK8sPilot

ROOT = Path(__file__).resolve().parents[1]


def test_crewai_lock_does_not_install_litellm() -> None:
    """LiteLLM is neither a direct dependency nor a resolved transitive package."""
    lock = (ROOT / "uv.lock").read_text()
    project = (ROOT / "pyproject.toml").read_text()
    assert '"crewai==1.15.33"' in project
    assert 'name = "crewai"\nversion = "1.15.33"' in lock
    assert 'name = "litellm"' not in lock
    assert "crewai[litellm]" not in project


def test_default_agents_keep_the_existing_native_openai_provider(monkeypatch) -> None:
    """With no OpenRouter credential, existing OPENAI_API_KEY routing stays intact."""
    fake = SimpleNamespace(
        agents_config={"k8s_operator": {"llm": "openai/gpt-4o-mini", "temperature": 0.0}}
    )
    monkeypatch.setattr(
        crew_module,
        "SETTINGS",
        SimpleNamespace(
            OPENROUTER_API_KEY=None,
            OPENROUTER_BASE_URL="https://openrouter.ai/api/v1",
        ),
    )
    factory = Mock()
    monkeypatch.setattr(crew_module, "LLM", factory)

    result = AutoK8sPilot._agent_config(fake, "k8s_operator")

    assert result == {"llm": "openai/gpt-4o-mini", "temperature": 0.0}
    assert fake.agents_config["k8s_operator"] == result
    factory.assert_not_called()


def test_openrouter_agents_use_native_openai_compatible_endpoint(monkeypatch) -> None:
    """Keep OpenRouter's provider/model ID intact when CrewAI strips one prefix."""
    original = {"llm": "openai/gpt-4o-mini", "temperature": 0.0}
    fake = SimpleNamespace(agents_config={"k8s_operator": original})
    monkeypatch.setattr(
        crew_module,
        "SETTINGS",
        SimpleNamespace(
            OPENROUTER_API_KEY="fixture-only",
            OPENROUTER_BASE_URL="https://openrouter.ai/api/v1",
        ),
    )
    factory = Mock(return_value=object())
    monkeypatch.setattr(crew_module, "LLM", factory)

    result = AutoK8sPilot._agent_config(fake, "k8s_operator")

    assert result["llm"] is factory.return_value
    assert original == {"llm": "openai/gpt-4o-mini", "temperature": 0.0}
    factory.assert_called_once_with(
        model="openai/openai/gpt-4o-mini",
        custom_openai=True,
        base_url="https://openrouter.ai/api/v1",
        api_key="fixture-only",
        temperature=0.0,
    )


def test_openrouter_agent_rejects_missing_model(monkeypatch) -> None:
    fake = SimpleNamespace(agents_config={"broken": {"temperature": 0}})
    monkeypatch.setattr(
        crew_module,
        "SETTINGS",
        SimpleNamespace(
            OPENROUTER_API_KEY="fixture-only",
            OPENROUTER_BASE_URL="https://openrouter.ai/api/v1",
        ),
    )
    with pytest.raises(ValueError, match="requires a configured model"):
        AutoK8sPilot._agent_config(fake, "broken")


def test_crewai_openrouter_route_is_native_without_network() -> None:
    """Verify real CrewAI routing preserves the provider/model ID."""
    from crewai import LLM
    from crewai.llms.providers.openai.completion import OpenAICompletion

    provider = LLM(
        model="openai/openai/gpt-4o-mini",
        custom_openai=True,
        base_url="https://openrouter.ai/api/v1",
        api_key="fixture-only",
    )
    assert isinstance(provider, OpenAICompletion)
    assert provider.model == "openai/gpt-4o-mini"
    assert provider.custom_openai is True
