import subprocess
from typing import Literal, Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, field_validator

from auto_k8s_pilot.settings import SETTINGS, Settings


class KubectlInput(BaseModel):
    action: Literal[
        "get", "logs", "describe", "top", "rollout_restart", "cordon", "uncordon"
    ] = Field(
        ..., description="Kubernetes action"
    )
    kind: Optional[str] = Field(None, description="Resource kind, e.g. pods, deploy, sts")
    name: Optional[str] = Field(None, description="Resource name, optional")
    namespace: Optional[str] = Field(
        None, description="Kubernetes namespace, defaults to env DEFAULT_NAMESPACE"
    )
    selector: Optional[str] = Field(None, description='Label selector, e.g. app=web')
    container: Optional[str] = Field(None, description='Container name for logs')
    tail: int = Field(200, description="Lines for logs")
    output: Literal["wide", "yaml", "json", "name"] = Field("wide", description="kubectl -o format")
    limit: int = Field(200, description="Max items for get (server-side)")
    context: Optional[str] = Field(None, description="Kube context override")

    @field_validator("namespace", mode="before")
    @classmethod
    def default_ns(cls, value):
        return value or SETTINGS.DEFAULT_NAMESPACE


class KubectlTool(BaseTool):
    name: str = "kubectl_tool"
    description: str = (
        "Safe kubectl wrapper. Read-only by default. "
        "Allowed actions: get/logs/describe/top. "
        "Mutations (rollout_restart, cordon/uncordon) require ALLOW_MUTATING=true."
    )
    args_schema: Type[BaseModel] = KubectlInput

    def _run(
        self,
        action: str,
        kind: Optional[str] = None,
        name: Optional[str] = None,
        namespace: Optional[str] = None,
        selector: Optional[str] = None,
        container: Optional[str] = None,
        tail: int = 200,
        output: str = "wide",
        limit: int = 200,
        context: Optional[str] = None,
    ) -> str:
        settings = Settings()
        allow_mutating = settings.ALLOW_MUTATING
        mutating_actions = {"rollout_restart", "cordon", "uncordon"}
        if action in mutating_actions and not allow_mutating:
            return "ERROR: Mutating actions are disabled. Set ALLOW_MUTATING=true to enable."

        kubeconfig = settings.KUBECONFIG
        base = ["kubectl"]
        if kubeconfig:
            base.append(f"--kubeconfig={kubeconfig}")
        if context:
            base += [f"--context={context}"]

        ns_flag = ["-A"] if namespace in (None, "", "all") else ["-n", namespace]
        cmd = base[:]
        if action == "get":
            if not kind:
                return "ERROR: 'kind' is required for action=get"
            cmd += ["get", kind]
            if name:
                cmd += [name]
            if selector:
                cmd += ["-l", selector]
            cmd += ["--chunk-size=0", "-o", output]
            if output not in ("yaml", "json"):
                cmd += ["--no-headers=true"]
            cmd += ["--ignore-not-found=true"]
            cmd += ns_flag
        elif action == "logs":
            if not kind:
                kind = "pods"
            if kind not in ("pod", "pods"):
                return "ERROR: logs currently supports 'pod(s)' kind only"
            if not name and not selector:
                return "ERROR: provide 'name' or 'selector' for logs"
            cmd += ["logs"]
            if name:
                cmd += [name]
            if selector:
                cmd += ["-l", selector]
            if container:
                cmd += ["-c", container]
            cmd += ["--tail", str(tail)]
            cmd += ns_flag
        elif action == "describe":
            if not kind:
                return "ERROR: 'kind' is required for action=describe"
            cmd += ["describe", kind]
            if name:
                cmd += [name]
            if selector:
                cmd += ["-l", selector]
            cmd += ns_flag
        elif action == "top":
            if kind not in ("pods", "nodes"):
                return "ERROR: top supports kind in ['pods','nodes']"
            cmd += ["top", kind]
            if name:
                cmd += [name]
            if selector and kind == "pods":
                cmd += ["-l", selector]
            cmd += ns_flag
        elif action == "rollout_restart":
            if kind not in ("deploy", "deployment", "statefulset", "daemonset"):
                return "ERROR: rollout_restart supports deploy/statefulset/daemonset"
            if not name:
                return "ERROR: 'name' is required for rollout_restart"
            cmd += ["rollout", "restart", kind, name] + ns_flag
        elif action in ("cordon", "uncordon"):
            if kind not in ("node", "nodes"):
                return "ERROR: cordon/uncordon works on nodes"
            if not name:
                return "ERROR: 'name' (node) is required"
            cmd += [action, name]
        else:
            return f"ERROR: unsupported action '{action}'"

        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=int(settings.KUBECTL_TIMEOUT)
            )
        except Exception as e:
            return f"ERROR: execution failed ({e})"

        if proc.returncode != 0:
            stderr = proc.stderr
            if kubeconfig:
                stderr = stderr.replace(kubeconfig, "<KUBECONFIG>")
            return f"ERROR: kubectl exited {proc.returncode}: {stderr.strip()[:4000]}"

        out = proc.stdout.strip()
        if out.startswith("{") or out.startswith("["):
            try:
                import json as _json
                data = _json.loads(out)
                preview = _json.dumps(data, ensure_ascii=False)[:4000]
                return preview
            except Exception:
                pass

        return out[:4000]

