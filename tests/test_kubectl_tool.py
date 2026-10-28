import os

from auto_k8s_pilot.tools.kubectl_tool import KubectlTool


class Proc:
    def __init__(self, rc=0, out="", err=""):
        self.returncode = rc
        self.stdout = out
        self.stderr = err

def test_mutating_blocked(monkeypatch):
    os.environ["ALLOW_MUTATING"] = "false"
    tool = KubectlTool()
    out = tool._run(action="rollout_restart", kind="deployment", name="api")
    assert out.startswith("ERROR:")

def test_get_pods_wide(monkeypatch):
    # Фальшивый subprocess.run
    def fake_run(cmd, capture_output, text, timeout):
        sample = (
            "pod-1   1/1   Running   2d   node-a\n"
            "pod-2   0/1   CrashLoopBackOff   3h   node-b\n"
        )
        return Proc(0, sample, "")

    import subprocess
    monkeypatch.setattr(subprocess, "run", fake_run)
    os.environ["KUBECONFIG"] = "/dev/null"

    tool = KubectlTool()
    out = tool._run(action="get", kind="pods", namespace="default", output="wide")
    assert "pod-1" in out and "pod-2" in out


def test_get_uses_default_kubectl_config_when_env_is_unset(monkeypatch):
    captured = {}

    def fake_run(cmd, capture_output, text, timeout):
        captured["cmd"] = cmd
        return Proc(0, "pod-1   1/1   Running\n", "")

    import subprocess

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.delenv("KUBECONFIG", raising=False)

    out = KubectlTool()._run(action="get", kind="pods", namespace="default")

    assert "pod-1" in out
    assert not any(arg.startswith("--kubeconfig=") for arg in captured["cmd"])
