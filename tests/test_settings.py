"""Tests for settings module."""

from auto_k8s_pilot.settings import CONFIG_DIR, LAYERS_DIR, SETTINGS, Settings


def test_settings_instance():
    """Test SETTINGS singleton exists."""
    assert SETTINGS is not None
    assert isinstance(SETTINGS, Settings)


def test_default_values(monkeypatch):
    """Test default values are set."""
    # Clear test env overrides from conftest.py
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    settings = Settings()

    # Core
    assert settings.DEFAULT_NAMESPACE == "default"
    assert settings.ALLOW_MUTATING is False
    assert settings.KUBECTL_TIMEOUT == 20

    # API
    assert settings.API_HOST == "0.0.0.0"
    assert settings.API_PORT == 8000

    # OTEL
    assert settings.OTEL_SERVICE_NAME == "auto-k8s-pilot"
    assert settings.ENVIRONMENT == "development"

    # Flow
    assert settings.DEFAULT_FLOW == "k8s-healthcheck"


def test_env_override(monkeypatch):
    """Test environment variables override defaults."""
    monkeypatch.setenv("DEFAULT_NAMESPACE", "production")
    monkeypatch.setenv("API_PORT", "9000")
    monkeypatch.setenv("OTEL_SERVICE_NAME", "test-service")

    settings = Settings()

    assert settings.DEFAULT_NAMESPACE == "production"
    assert settings.API_PORT == 9000
    assert settings.OTEL_SERVICE_NAME == "test-service"


def test_paths_exist():
    """Test path constants point to existing directories."""
    assert CONFIG_DIR.exists()
    assert LAYERS_DIR.exists()


def test_optional_fields_default_none(monkeypatch):
    """Test optional fields default to None."""
    # Clear any env vars that might override defaults
    monkeypatch.delenv("KUBECONFIG", raising=False)
    monkeypatch.delenv("ARGOCD_BASE_URL", raising=False)
    monkeypatch.delenv("ARGOCD_API_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("MCP_K8S_SERVER_URL", raising=False)

    settings = Settings()

    assert settings.KUBECONFIG is None
    assert settings.ARGOCD_BASE_URL is None
    assert settings.ARGOCD_API_TOKEN is None
    assert settings.GITHUB_TOKEN is None
    assert settings.CLOUDFLARE_API_TOKEN is None
    assert settings.OPENROUTER_API_KEY is None
    assert settings.MCP_K8S_SERVER_URL is None


def test_k8s_metadata_defaults_empty():
    """Test K8s metadata fields default to empty."""
    settings = Settings()

    assert settings.K8S_POD_NAME == ""
    assert settings.K8S_NAMESPACE == ""
    assert settings.K8S_NODE_NAME == ""


def test_loki_url_default():
    """Test Loki URL has default value."""
    settings = Settings()
    assert settings.LOKI_URL == "http://loki:3100"


def test_openrouter_base_url_default():
    """Test OpenRouter base URL has default value."""
    settings = Settings()
    assert settings.OPENROUTER_BASE_URL == "https://openrouter.ai/api/v1"
