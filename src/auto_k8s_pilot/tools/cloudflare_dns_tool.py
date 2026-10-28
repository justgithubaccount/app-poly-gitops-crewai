from typing import Any, Literal, Optional, Type

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from auto_k8s_pilot.settings import Settings


class CFInput(BaseModel):
    op: Literal["list", "get", "upsert"] = Field(..., description="Operation")
    name: Optional[str] = Field(None, description="Record name (relative or FQDN)")
    type: Optional[str] = Field(None, description="DNS type A/AAAA/CNAME/TXT etc.")
    content: Optional[str] = Field(None, description="IP/hostname/content")
    proxied: Optional[bool] = Field(None, description="Proxy through Cloudflare")
    ttl: Optional[int] = Field(None, description="TTL seconds")


class CloudflareDNSTool(BaseTool):
    name: str = "cloudflare_dns_tool"
    description: str = "Cloudflare DNS API wrapper (list/get). Upsert requires ALLOW_MUTATING=true."
    args_schema: Type[BaseModel] = CFInput

    def _base(self) -> tuple[Optional[dict[str, str]], Optional[str], Optional[str]]:
        settings = Settings()
        token = settings.CLOUDFLARE_API_TOKEN
        zone = settings.CLOUDFLARE_ZONE_ID
        if not token or not zone:
            return None, None, "ERROR: Set CLOUDFLARE_API_TOKEN and CLOUDFLARE_ZONE_ID"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        return headers, zone, None

    def _run(
        self,
        op: str,
        name: Optional[str] = None,
        type: Optional[str] = None,
        content: Optional[str] = None,
        proxied: Optional[bool] = None,
        ttl: Optional[int] = None,
    ) -> str:
        settings = Settings()
        headers, zone, err = self._base()
        if err:
            return err
        if headers is None or zone is None:
            return "ERROR: Cloudflare API configuration is incomplete"
        base = f"https://api.cloudflare.com/client/v4/zones/{zone}/dns_records"

        try:
            if op == "list":
                r = requests.get(base, headers=headers, timeout=10)
                r.raise_for_status()
                data = r.json().get("result", [])
                lines = [
                    (
                        f"{d.get('type')} {d.get('name')} {d.get('content')} "
                        f"proxied={d.get('proxied')} ttl={d.get('ttl')}"
                    )
                    for d in data[:100]
                ]
                return "Records:\n" + "\n".join(lines)
            elif op == "get":
                if not name:
                    return "ERROR: 'name' required"
                r = requests.get(base, headers=headers, params={"name": name}, timeout=10)
                r.raise_for_status()
                rs = r.json().get("result", [])
                if not rs:
                    return "NOT FOUND"
                d = rs[0]
                return (
                    f"{d.get('type')} {d.get('name')} {d.get('content')} "
                    f"proxied={d.get('proxied')} ttl={d.get('ttl')} id={d.get('id')}"
                )
            elif op == "upsert":
                if not settings.ALLOW_MUTATING:
                    return "ERROR: Mutating ops disabled (ALLOW_MUTATING=false)"
                if not all([name, type, content]):
                    return "ERROR: name/type/content required"
                r = requests.get(
                    base,
                    headers=headers,
                    params={"name": name, "type": type},
                    timeout=10,
                )
                r.raise_for_status()
                rs = r.json().get("result", [])
                payload: dict[str, Any] = {"type": type, "name": name, "content": content}
                if proxied is not None:
                    payload["proxied"] = proxied
                if ttl:
                    payload["ttl"] = ttl
                if rs:
                    rec_id = rs[0]["id"]
                    r = requests.put(f"{base}/{rec_id}", headers=headers, json=payload, timeout=10)
                    r.raise_for_status()
                    return f"UPSERT OK: {rec_id}"
                else:
                    r = requests.post(base, headers=headers, json=payload, timeout=10)
                    r.raise_for_status()
                    return f"UPSERT OK: {r.json().get('result', {}).get('id')}"
            else:
                return "ERROR: unsupported op"
        except Exception as e:
            return f"ERROR: Cloudflare API failed ({e})"

