import json
from typing import Literal, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from auto_k8s_pilot.settings import Settings


class MCPK8sInput(BaseModel):
    op: Literal["env_check", "config_snippet"] = Field(..., description="Operation")


class MCPK8sTool(BaseTool):
    name: str = "mcp_k8s_tool"
    description: str = "Validate env for mcp-server-kubernetes and produce a client config snippet."
    args_schema: Type[BaseModel] = MCPK8sInput

    def _run(self, op: str) -> str:
        settings = Settings()
        if op == "env_check":
            missing = []
            if not (settings.MCP_K8S_SERVER_URL or settings.MCP_K8S_CMD):
                missing.append("MCP_K8S_SERVER_URL or MCP_K8S_CMD")
            details = {
                "server_url": settings.MCP_K8S_SERVER_URL,
                "cmd": settings.MCP_K8S_CMD,
                "insecure": settings.MCP_K8S_INSECURE,
            }
            if missing:
                return f"ERROR: Missing env: {', '.join(missing)}"
            return f"OK: {json.dumps(details)}"
        elif op == "config_snippet":
            snippet = {
                "stdio": {
                    "mcpServers": {
                        "kubernetes": {
                            "command": settings.MCP_K8S_CMD or "mcp-server-kubernetes",
                            "args": [],
                            "env": {},
                        }
                    }
                },
                "websocket": {
                    "mcpServers": {
                        "kubernetes": {
                            "transport": "websocket",
                            "url": settings.MCP_K8S_SERVER_URL or "ws://localhost:8765",
                            "headers": {
                                "Authorization": (
                                    f"Bearer {settings.MCP_K8S_API_KEY}"
                                    if settings.MCP_K8S_API_KEY
                                    else ""
                                )
                            },
                            "insecure": settings.MCP_K8S_INSECURE,
                        }
                    }
                }
            }
            return "SNIPPET:\n" + json.dumps(snippet, indent=2)
        else:
            return "ERROR: unsupported op"

