from typing import Literal, Type

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from auto_k8s_pilot.settings import Settings


class ORInput(BaseModel):
    op: Literal["models", "ping"] = Field(..., description="Operation")
    timeout: int = Field(10, description="HTTP timeout seconds")


class OpenRouterHealthTool(BaseTool):
    name: str = "openrouter_health_tool"
    description: str = "OpenRouter gateway health: models listing / ping."
    args_schema: Type[BaseModel] = ORInput

    def _headers(self):
        settings = Settings()
        h = (
            {"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"}
            if settings.OPENROUTER_API_KEY
            else {}
        )
        if settings.OPENROUTER_SITE_URL:
            h["HTTP-Referer"] = settings.OPENROUTER_SITE_URL
        if settings.OPENROUTER_APP_NAME:
            h["X-Title"] = settings.OPENROUTER_APP_NAME
        return h

    def _run(self, op: str, timeout: int = 10) -> str:
        settings = Settings()
        base = settings.OPENROUTER_BASE_URL
        try:
            if op == "ping":
                r = requests.get(base, headers=self._headers(), timeout=timeout)
                return f"PING {r.status_code}"
            elif op == "models":
                r = requests.get(f"{base}/models", headers=self._headers(), timeout=timeout)
                r.raise_for_status()
                data = r.json()
                models = data.get("data", []) if isinstance(data, dict) else data
                count = len(models)
                preview = [m.get("id", str(m)) for m in models[:10]]
                return "Models:%d\nPreview:\n%s" % (count, "\n".join(preview))
            else:
                return "ERROR: unsupported op"
        except Exception as e:
            return f"ERROR: OpenRouter request failed ({e})"

