"""FlowRunner - executes flow-*.yaml step by step using CrewAI tasks."""

import time
from pathlib import Path
from typing import Any, Dict, List

import yaml

from auto_k8s_pilot.observability import enrich_context


class FlowRunner:
    """Executes flow-*.yaml step by step using CrewAI tasks."""

    def __init__(self, crew_instance: Any, config_dir: Path):
        self.crew = crew_instance
        self.config_dir = config_dir
        self.tasks_map = self._build_tasks_map()

    def _build_tasks_map(self) -> Dict[str, Any]:
        """Map task_id -> task method from crew (decorated with @task)."""
        return {
            "k8s_pods_overview": self.crew.k8s_pods_overview,
            "explain_pods": self.crew.explain_pods,
            "cluster_summary": self.crew.cluster_summary,
            "k8s_top_nodes": self.crew.k8s_top_nodes,
            "k8s_top_pods_ns_default": self.crew.k8s_top_pods_ns_default,
            "k8s_events_recent": self.crew.k8s_events_recent,
            "argocd_list_apps": self.crew.argocd_list_apps,
            "argocd_app_status_chat_api": self.crew.argocd_app_status_chat_api,
            "argocd_sync_chat_api": self.crew.argocd_sync_chat_api,
            "loki_recent_errors_chat_api": self.crew.loki_recent_errors_chat_api,
            "loki_http_activity_chat_api": self.crew.loki_http_activity_chat_api,
            "dns_check_records": self.crew.dns_check_records,
            "dns_get_record_api": self.crew.dns_get_record_api,
            "dns_upsert_record_api": self.crew.dns_upsert_record_api,
            "llm_gateway_health": self.crew.llm_gateway_health,
            "mcp_k8s_env_check": self.crew.mcp_k8s_env_check,
            "incident_create_issue_if_needed": self.crew.incident_create_issue_if_needed,
        }

    def list_flows(self) -> List[str]:
        """Return available flow names."""
        log = enrich_context(event="list_flows")
        layers_dir = self.config_dir / "layers"
        flows = []
        for f in layers_dir.glob("flow-*.yaml"):
            name = f.stem.replace("flow-", "")
            flows.append(name)
        log.bind(flows=flows, count=len(flows)).info("Listed available flows")
        return flows

    def list_agents(self) -> List[str]:
        """Return available agent names from behavior.yaml."""
        log = enrich_context(event="list_agents")
        behavior = self._load_behavior()
        agents = [a["id"] for a in behavior.get("agents", [])]
        log.bind(agents=agents, count=len(agents)).info("Listed available agents")
        return agents

    def load_flow(self, flow_name: str) -> dict:
        """Load flow YAML by name."""
        log = enrich_context(event="load_flow", flow_name=flow_name)
        path = self.config_dir / "layers" / f"flow-{flow_name}.yaml"
        if not path.exists():
            log.bind(event="flow_not_found", path=str(path)).warning("Flow file not found")
            raise FileNotFoundError(f"Flow not found: {flow_name}")
        with open(path) as f:
            flow_config = yaml.safe_load(f)
        steps_count = len(flow_config.get("steps", []))
        log.bind(steps_count=steps_count).info("Flow loaded successfully")
        return flow_config

    def run_flow(self, flow_name: str, inputs: dict) -> dict:
        """
        Execute flow steps sequentially.

        Args:
            flow_name: Name of flow (e.g. "k8s-healthcheck")
            inputs: Dict with namespace, app_name, etc.

        Returns:
            {
                "final_answer": str,
                "steps": [{"agent": str, "task": str, "output": str, "duration_ms": int}],
                "metadata": {...}
            }
        """
        log = enrich_context(event="flow_start", flow_name=flow_name)
        log.info("Starting flow execution")

        flow = self.load_flow(flow_name)
        steps_config = flow.get("steps", [])

        # Load behavior.yaml for task -> agent mapping
        behavior = self._load_behavior()
        task_agent_map = {t["id"]: t["agent"] for t in behavior.get("tasks", [])}

        results: List[Dict[str, Any]] = []
        context: Dict[str, str] = {}  # accumulated context from previous steps
        total_start = time.time()

        for step in steps_config:
            task_id = step.get("run")
            if not task_id:
                continue

            # Check if task exists
            task_method = self.tasks_map.get(task_id)
            if not task_method:
                enrich_context(
                    event="task_not_found",
                    flow_name=flow_name,
                    task=task_id,
                ).error(f"Task '{task_id}' not found in tasks_map")
                results.append(
                    {
                        "agent": "unknown",
                        "task": task_id,
                        "output": f"ERROR: task '{task_id}' not found",
                        "duration_ms": 0,
                    }
                )
                continue

            agent_id = task_agent_map.get(task_id, "unknown")

            step_log = enrich_context(
                event="flow_step",
                flow_name=flow_name,
                task=task_id,
                agent=agent_id,
            )
            step_log.info("Executing task")

            # Execute task via task.run() — agent is called internally by CrewAI
            start = time.time()
            try:
                task = task_method()  # Get CrewAI Task object
                # Pass inputs + accumulated context
                result = task.run(context={**inputs, **context})
                output = str(result)
                step_log.bind(
                    event="step_complete", duration_ms=int((time.time() - start) * 1000)
                ).info("Task completed")
            except Exception as e:
                output = f"ERROR: {e}"
                step_log.bind(event="step_error", error=str(e)).error("Task failed")

            duration_ms = int((time.time() - start) * 1000)

            results.append(
                {
                    "agent": agent_id,
                    "task": task_id,
                    "output": output,
                    "duration_ms": duration_ms,
                }
            )

            # Add to context for next steps
            context[task_id] = output

        total_duration_ms = int((time.time() - total_start) * 1000)

        # Determine final answer
        final_answer = self._extract_final_answer(results)
        metadata = self._extract_metadata(results)
        metadata["total_duration_ms"] = total_duration_ms

        log.bind(
            event="flow_complete",
            steps_count=len(results),
            total_duration_ms=total_duration_ms,
        ).info("Flow execution completed")

        return {
            "final_answer": final_answer,
            "steps": results,
            "metadata": metadata,
        }

    def _load_behavior(self) -> dict:
        """Load behavior.yaml."""
        path = self.config_dir / "layers" / "behavior.yaml"
        with open(path) as f:
            return yaml.safe_load(f)

    def _extract_final_answer(self, results: List[Dict[str, Any]]) -> str:
        """Get final answer from incident_create_issue_if_needed or last step."""
        for r in reversed(results):
            if r["task"] == "incident_create_issue_if_needed":
                return r["output"]
            if r["task"] == "cluster_summary":
                return r["output"]
        if results:
            return results[-1]["output"]
        return ""

    def _extract_metadata(self, results: List[Dict[str, Any]]) -> dict:
        """Extract metadata from results (cluster health, incidents, etc.)."""
        metadata: Dict[str, Any] = {}
        for r in results:
            if r["task"] == "cluster_summary":
                # Extract first 500 chars as summary
                metadata["cluster_summary"] = r["output"][:500] if r["output"] else ""
            if r["task"] == "incident_create_issue_if_needed":
                if "Created issue" in r.get("output", ""):
                    metadata["incident_created"] = True
                else:
                    metadata["incident_created"] = False
        return metadata
