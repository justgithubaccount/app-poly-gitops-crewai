import datetime as dt
from typing import Type

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from auto_k8s_pilot.settings import Settings


class LokiInput(BaseModel):
    query: str = Field(..., description='LogQL query, e.g. {app="chat-api"} |= "ERROR"')
    minutes: int = Field(30, description='Lookback window in minutes')
    limit: int = Field(200, description='Max entries to fetch')


class LokiQueryTool(BaseTool):
    name: str = "loki_query"
    description: str = "Query Grafana Loki via HTTP API and summarize recent log events."
    args_schema: Type[BaseModel] = LokiInput

    def _run(self, query: str, minutes: int = 30, limit: int = 200) -> str:
        settings = Settings()
        base = settings.LOKI_URL
        now = int(dt.datetime.utcnow().timestamp() * 1e9)
        start = now - minutes * 60 * int(1e9)
        params = {"query": query, "limit": str(limit), "start": str(start), "end": str(now)}
        try:
            r = requests.get(f"{base}/loki/api/v1/query_range", params=params, timeout=10)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            return f"ERROR: Loki request failed ({e})."

        streams = data.get("data", {}).get("result", [])
        total = sum(len(s.get("values", [])) for s in streams)
        lines = []
        for s in streams[:5]:
            lbl = s.get("stream", {})
            sample = s.get("values", [])[:3]
            for _, msg in sample:
                lines.append(f"{lbl} :: {msg[:200]}")

        preview = "\n".join(lines[:10]) or "no matches"
        return f"Matches: {total}\nPreview:\n{preview}"

