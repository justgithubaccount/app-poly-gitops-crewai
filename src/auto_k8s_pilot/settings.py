from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Core
    DEFAULT_NAMESPACE: str = "default"
    ALLOW_MUTATING: bool = False
    KUBECONFIG: Optional[str] = None
    KUBECTL_TIMEOUT: int = 20

    # ArgoCD
    ARGOCD_BASE_URL: Optional[str] = None
    ARGOCD_API_TOKEN: Optional[str] = None

    # Loki
    LOKI_URL: str = "http://loki:3100"

    # GitHub
    GITHUB_TOKEN: Optional[str] = None

    # Cloudflare
    CLOUDFLARE_API_TOKEN: Optional[str] = None
    CLOUDFLARE_ZONE_ID: Optional[str] = None

    # OpenRouter (LLM Gateway)
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_SITE_URL: Optional[str] = None  # optional Referer
    OPENROUTER_APP_NAME: Optional[str] = None  # optional X-Title

    # MCP Kubernetes server
    MCP_K8S_SERVER_URL: Optional[str] = None   # ws:// or wss:// if applicable
    MCP_K8S_API_KEY: Optional[str] = None
    MCP_K8S_INSECURE: bool = False
    MCP_K8S_CMD: Optional[str] = None          # optional: stdio command (e.g., "mcp-server-kubernetes")

    # API Server
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # OpenTelemetry
    OTEL_SERVICE_NAME: str = "auto-k8s-pilot"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4318"
    ENVIRONMENT: str = "development"
    APP_VERSION: str = "0.1.0"

    # Kubernetes metadata (set by downward API in K8s)
    K8S_POD_NAME: str = ""
    K8S_NAMESPACE: str = ""
    K8S_NODE_NAME: str = ""
    K8S_DEPLOYMENT_NAME: str = "auto-k8s-pilot"
    K8S_CONTAINER_NAME: str = "auto-k8s-pilot"
    K8S_POD_UID: str = ""

    # Grafana (optional)
    GRAFANA_TENANT_ID: Optional[str] = None

    # Logging
    LOG_LEVEL: str = "INFO"

    # Flow
    DEFAULT_FLOW: str = "k8s-healthcheck"

    class Config:
        env_file = ".env"
        case_sensitive = False


# Singleton
SETTINGS = Settings()

# Paths
BASE_DIR = Path(__file__).parent
CONFIG_DIR = BASE_DIR / "config"
LAYERS_DIR = CONFIG_DIR / "layers"

