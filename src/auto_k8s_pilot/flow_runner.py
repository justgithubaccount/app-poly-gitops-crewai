"""FlowRunner - executes flow-*.yaml step by step using CrewAI tasks."""

import re
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from auto_k8s_pilot.observability import enrich_context
from auto_k8s_pilot.tools.kubectl_tool import KubectlTool


class FlowRunner:
    """Executes flow-*.yaml step by step using CrewAI tasks."""

    def __init__(
        self,
        crew_instance: Any,
        config_dir: Path,
        kubectl_tool: Optional[KubectlTool] = None,
    ):
        self.crew = crew_instance
        self.config_dir = config_dir
        self.kubectl_tool = kubectl_tool or KubectlTool()
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
        if not isinstance(flow_config, dict):
            raise ValueError(f"Flow config must be a mapping: {path}")
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

            # Execute evidence collection and phase counting deterministically.
            # LLMs are useful for narrative synthesis, but they must not choose
            # the kubectl scope or reinterpret Kubernetes phases.
            start = time.time()
            try:
                deterministic = self._execute_deterministic_task(
                    task_id, inputs, context
                )
                evidence_scope = None
                if deterministic is not None:
                    output, evidence_scope = deterministic
                else:
                    task = task_method()  # Get CrewAI Task object
                    task_context = yaml.safe_dump(
                        {**inputs, **context},
                        allow_unicode=True,
                        sort_keys=False,
                    )
                    task_output = task.execute_sync(context=task_context)
                    output = task_output.raw
                    if task_id == "cluster_summary":
                        evidence_scope = self._scope_label(inputs)
                        self._validate_cluster_summary(
                            output,
                            evidence_scope,
                            context,
                        )
                step_log.bind(
                    event="step_complete", duration_ms=int((time.time() - start) * 1000)
                ).info("Task completed")
            except Exception as e:
                step_log.bind(event="step_error", error=str(e)).error("Task failed")
                raise RuntimeError(
                    f"Flow '{flow_name}' failed at task '{task_id}': {e}"
                ) from e

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
            if evidence_scope:
                context[f"{task_id}_scope"] = evidence_scope

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

    def _execute_deterministic_task(
        self,
        task_id: str,
        inputs: dict,
        context: Dict[str, str],
    ) -> Optional[Tuple[str, str]]:
        """Run raw Kubernetes reads and pod phase accounting without an LLM."""
        namespace = self._namespace_value(inputs)
        scope = self._scope_label(inputs)

        if task_id == "k8s_top_nodes":
            return self.kubectl_tool._run(action="top", kind="nodes"), "all nodes"
        if task_id == "k8s_top_pods_ns_default":
            return (
                self.kubectl_tool._run(
                    action="top", kind="pods", namespace=namespace
                ),
                scope,
            )
        if task_id == "k8s_pods_overview":
            return (
                self.kubectl_tool._run(
                    action="get", kind="pods", namespace=namespace
                ),
                scope,
            )
        if task_id == "k8s_events_recent":
            return (
                self.kubectl_tool._run(
                    action="get", kind="events", namespace=namespace
                ),
                scope,
            )
        if task_id == "explain_pods":
            raw = context.get("k8s_pods_overview", "")
            actual_scope = context.get("k8s_pods_overview_scope", scope)
            return self._summarize_pods(raw, actual_scope), actual_scope
        return None

    @staticmethod
    def _namespace_value(inputs: dict) -> str:
        value = str(inputs.get("namespace") or "default").strip()
        return "all" if value.lower() in {"all", "*"} else value

    @classmethod
    def _scope_label(cls, inputs: dict) -> str:
        namespace = cls._namespace_value(inputs)
        if namespace == "all":
            return "Scope: all namespaces"
        return f"Scope: namespace {namespace}"

    @staticmethod
    def _summarize_pods(raw: str, scope: str) -> str:
        """Summarize kubectl's table while preserving exact phase semantics."""
        if raw.startswith("ERROR:"):
            return f"{scope}\nPod evidence unavailable: {raw}"

        lines = [line for line in raw.splitlines() if line.strip()]
        all_namespaces = scope == "Scope: all namespaces"
        status_index = 3 if all_namespaces else 2
        name_index = 1 if all_namespaces else 0
        phases: Counter[str] = Counter()
        names_by_phase: Dict[str, List[str]] = {}

        for line in lines:
            fields = line.split()
            if len(fields) <= status_index:
                continue
            phase = fields[status_index]
            name = fields[name_index]
            phases[phase] += 1
            names_by_phase.setdefault(phase, []).append(name)

        if not phases:
            return f"{scope}\nNo pods were observed in the supplied snapshot."

        failure_states = {
            "Failed",
            "Error",
            "CrashLoopBackOff",
            "ImagePullBackOff",
            "ErrImagePull",
        }
        failing = sum(count for phase, count in phases.items() if phase in failure_states)
        phase_counts = ", ".join(
            f"{phase}: {count}" for phase, count in sorted(phases.items())
        )
        details = [
            f"- {phase}: {', '.join(names)}"
            for phase, names in sorted(names_by_phase.items())
        ]
        return "\n".join(
            [
                scope,
                (
                    f"Observed pods: {sum(phases.values())}; {phase_counts}; "
                    f"explicit failures: {failing}."
                ),
                "Completed and Succeeded are successful terminal Job states.",
                *details,
            ]
        )

    @staticmethod
    def _validate_cluster_summary(
        output: str,
        scope: str,
        evidence: Dict[str, str],
    ) -> None:
        """Reject a plausible-looking LLM summary that exceeds its evidence."""
        first_line = next(
            (line.strip() for line in output.splitlines() if line.strip()), ""
        )
        if first_line != scope:
            raise ValueError(f"cluster summary must start with '{scope}'")

        output_lower = output.lower()
        evidence_lower = "\n".join(
            value for key, value in evidence.items() if not key.endswith("_scope")
        ).lower()

        if scope != "Scope: all namespaces":
            unsupported_absence = (
                "not deployed",
                "not installed",
                "there is no",
                "no indication of",
                "no indications of",
            )
            if any(phrase in output_lower for phrase in unsupported_absence):
                raise ValueError(
                    "namespace-scoped evidence cannot prove cluster-wide absence"
                )

        component_terms = (
            "argocd",
            "argo cd",
            "ingress",
            "vector",
            "loki",
            "grafana",
            "opentelemetry",
            "cni",
        )
        unsupported = [
            term
            for term in component_terms
            if term in output_lower and term not in evidence_lower
        ]
        if unsupported:
            raise ValueError(
                "cluster summary mentions components absent from evidence: "
                + ", ".join(unsupported)
            )

        pod_evidence = evidence.get("k8s_pods_overview", "")
        explicit_failure = re.search(
            r"\b(?:Failed|Error|CrashLoopBackOff|ImagePullBackOff|ErrImagePull)\b",
            pod_evidence,
        )
        false_failure_claim = re.search(
            r"(?:failing\s*:\s*[1-9]|\b[1-9][0-9]*\s+(?:pods?\s+)?failing\b)",
            output,
            flags=re.IGNORECASE,
        )
        if false_failure_claim and not explicit_failure:
            raise ValueError("cluster summary invents failing pods")

    def _load_behavior(self) -> dict:
        """Load behavior.yaml."""
        path = self.config_dir / "layers" / "behavior.yaml"
        with open(path) as f:
            behavior = yaml.safe_load(f)
        if not isinstance(behavior, dict):
            raise ValueError(f"Behavior config must be a mapping: {path}")
        return behavior

    def _extract_final_answer(self, results: List[Dict[str, Any]]) -> str:
        """Get final answer from incident_create_issue_if_needed or last step."""
        for r in reversed(results):
            if r["task"] == "incident_create_issue_if_needed":
                return str(r["output"])
            if r["task"] == "cluster_summary":
                return str(r["output"])
        if results:
            return str(results[-1]["output"])
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
