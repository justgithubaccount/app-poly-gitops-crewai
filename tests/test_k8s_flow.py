# tests/test_k8s_flow.py
from crewai import Crew, Process
from crewai.llms.providers.openai.completion import OpenAICompletion

from auto_k8s_pilot.crew import AutoK8sPilot
from auto_k8s_pilot.tools import kubectl_tool as ktool


def test_k8s_health_flow(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    def fake_run(self, action, **kwargs):
        if action == "get":
            return "pod-1 1/1 Running 2d node-a\npod-2 0/1 CrashLoopBackOff 1h node-b\n"
        return ""

    monkeypatch.setattr(ktool.KubectlTool, "_run", fake_run)

    monkeypatch.setenv("OPENAI_API_KEY", "test")

    def fake_completion(self, messages, **kwargs):
        return "pod-1 CrashLoopBackOff"

    monkeypatch.setattr(OpenAICompletion, "call", fake_completion)

    c = AutoK8sPilot()
    crew = Crew(
        agents=[c.k8s_operator(), c.reporting_analyst()],
        tasks=[c.k8s_pods_overview(), c.explain_pods()],
        process=Process.sequential,
        verbose=False,
    )
    res = crew.kickoff()
    assert "CrashLoopBackOff" in str(res)
