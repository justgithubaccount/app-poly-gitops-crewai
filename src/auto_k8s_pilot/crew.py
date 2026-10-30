from pathlib import Path
from typing import Any, Dict, List

from crewai import LLM, Agent, Crew, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task

from auto_k8s_pilot.settings import SETTINGS
from auto_k8s_pilot.tools.argocd_tool import ArgoCDTool
from auto_k8s_pilot.tools.cloudflare_dns_tool import CloudflareDNSTool
from auto_k8s_pilot.tools.github_issue_tool import GitHubIssueTool
from auto_k8s_pilot.tools.kubectl_tool import KubectlTool
from auto_k8s_pilot.tools.loki_tool import LokiQueryTool
from auto_k8s_pilot.tools.mcp_k8s_tool import MCPK8sTool
from auto_k8s_pilot.tools.openrouter_health_tool import OpenRouterHealthTool

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@CrewBase
class AutoK8sPilot:
    """AutoK8sPilot crew"""

    agents: List[BaseAgent]
    tasks: List[Task]
    agents_config: Dict[str, Dict[str, Any]]
    tasks_config: Dict[str, Dict[str, Any]]

    def _agent_config(self, agent_id: str) -> Dict[str, Any]:
        """Use native OpenAI-compatible OpenRouter only when explicitly configured.

        The standard Kubernetes deployment still uses OPENAI_API_KEY. Do not
        silently switch providers when OPENROUTER_API_KEY is absent.
        """
        config = dict(self.agents_config[agent_id])
        if not SETTINGS.OPENROUTER_API_KEY:
            return config

        model = config.get("llm")
        if not isinstance(model, str) or not model:
            raise ValueError(f"agent {agent_id} requires a configured model")

        # CrewAI custom_openai strips one 'openai/' routing prefix. Prepending
        # it here preserves OpenRouter's complete provider/model identifier.
        config["llm"] = LLM(
            model=f"openai/{model}",
            custom_openai=True,
            base_url=SETTINGS.OPENROUTER_BASE_URL,
            api_key=SETTINGS.OPENROUTER_API_KEY,
            temperature=config.get("temperature", 0.0),
        )
        return config

    def _task_from_config(self, task_id: str, output_file: str) -> Task:
        """Supply fields explicitly required by CrewAI 1.15's typed Task API."""
        config = self.tasks_config[task_id]
        return Task(
            description=config["description"],
            expected_output=config["expected_output"],
            config=config,
            output_file=output_file,
        )

    @agent
    def reporting_analyst(self) -> Agent:
        return Agent(
            config=self._agent_config('reporting_analyst'),
            verbose=True,
        )

    @agent
    def k8s_operator(self) -> Agent:
        return Agent(
            config=self._agent_config('k8s_operator'),
            verbose=True,
            tools=[KubectlTool()],
        )

    @agent
    def infra_architect(self) -> Agent:
        return Agent(
            config=self._agent_config('infra_architect'),
            verbose=True,
        )

    @agent
    def argocd_observer(self) -> Agent:
        return Agent(
            config=self._agent_config('argocd_observer'),
            verbose=True,
            tools=[ArgoCDTool()],
        )

    @agent
    def loki_analyst(self) -> Agent:
        return Agent(
            config=self._agent_config('loki_analyst'),
            verbose=True,
            tools=[LokiQueryTool()],
        )

    @agent
    def incident_triager(self) -> Agent:
        return Agent(
            config=self._agent_config('incident_triager'),
            verbose=True,
            tools=[GitHubIssueTool()],
        )

    @agent
    def cloudflare_admin(self) -> Agent:
        return Agent(
            config=self._agent_config('cloudflare_admin'),
            verbose=True,
            tools=[CloudflareDNSTool()],
        )

    @agent
    def llm_gateway_observer(self) -> Agent:
        return Agent(
            config=self._agent_config('llm_gateway_observer'),
            verbose=True,
            tools=[OpenRouterHealthTool()],
        )

    @agent
    def mcp_bridge(self) -> Agent:
        return Agent(
            config=self._agent_config('mcp_bridge'),
            verbose=True,
            tools=[MCPK8sTool()],
        )

    @task
    def k8s_pods_overview(self) -> Task:
        return self._task_from_config("k8s_pods_overview", "output/pods_overview.md")

    @task
    def explain_pods(self) -> Task:
        return self._task_from_config("explain_pods", "output/pods_explained.md")

    @task
    def cluster_summary(self) -> Task:
        return self._task_from_config("cluster_summary", "output/cluster_summary.md")

    @task
    def k8s_top_nodes(self) -> Task:
        return self._task_from_config("k8s_top_nodes", "output/top_nodes.md")

    @task
    def k8s_top_pods_ns_default(self) -> Task:
        return self._task_from_config("k8s_top_pods_ns_default", "output/top_pods_default.md")

    @task
    def k8s_events_recent(self) -> Task:
        return self._task_from_config("k8s_events_recent", "output/events.md")

    @task
    def argocd_list_apps(self) -> Task:
        return self._task_from_config("argocd_list_apps", "output/argocd_apps.md")

    @task
    def argocd_app_status_chat_api(self) -> Task:
        return self._task_from_config(
            "argocd_app_status_chat_api", "output/argocd_chat_api_status.md"
        )

    @task
    def argocd_sync_chat_api(self) -> Task:
        return self._task_from_config("argocd_sync_chat_api", "output/argocd_chat_api_sync.md")

    @task
    def loki_recent_errors_chat_api(self) -> Task:
        return self._task_from_config(
            "loki_recent_errors_chat_api", "output/loki_chat_api_errors.md"
        )

    @task
    def loki_http_activity_chat_api(self) -> Task:
        return self._task_from_config("loki_http_activity_chat_api", "output/loki_chat_api_http.md")

    @task
    def dns_check_records(self) -> Task:
        return self._task_from_config("dns_check_records", "output/dns_records.md")

    @task
    def dns_get_record_api(self) -> Task:
        return self._task_from_config("dns_get_record_api", "output/dns_api_record.md")

    @task
    def dns_upsert_record_api(self) -> Task:
        return self._task_from_config("dns_upsert_record_api", "output/dns_api_upsert.md")

    @task
    def llm_gateway_health(self) -> Task:
        return self._task_from_config("llm_gateway_health", "output/llm_gateway_health.md")

    @task
    def mcp_k8s_env_check(self) -> Task:
        return self._task_from_config("mcp_k8s_env_check", "output/mcp_env_check.md")

    @task
    def incident_create_issue_if_needed(self) -> Task:
        return self._task_from_config("incident_create_issue_if_needed", "output/incident_issue.md")

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )

