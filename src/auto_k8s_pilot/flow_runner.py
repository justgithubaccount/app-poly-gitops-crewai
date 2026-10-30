"""FlowRunner - executes flow-*.yaml step by step using CrewAI tasks."""

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
        self._validate_flows()

    def _build_tasks_map(self) -> Dict[str, Any]:
        """Discover routed task factories from the behavior configuration."""
        behavior = self._load_behavior()
        configured_tasks = behavior.get("tasks", [])
        if not isinstance(configured_tasks, list):
            raise ValueError("behavior tasks must be a list")

        tasks_map: Dict[str, Any] = {}
        for configured in configured_tasks:
            if not isinstance(configured, dict) or not isinstance(configured.get("id"), str):
                raise ValueError("every behavior task must have a string id")
            task_id = configured["id"]
            if task_id in tasks_map:
                raise ValueError(f"duplicate behavior task: {task_id}")
            task_factory = getattr(self.crew, task_id, None)
            if not callable(task_factory):
                raise ValueError(f"behavior task has no CrewAI factory: {task_id}")
            tasks_map[task_id] = task_factory
        return tasks_map

    def _validate_flows(self) -> None:
        """Fail closed when a discovered flow references an unrouted task."""
        layers_dir = self.config_dir / "layers"
        for path in sorted(layers_dir.glob("flow-*.yaml")):
            with open(path) as stream:
                flow = yaml.safe_load(stream)
            if not isinstance(flow, dict) or not isinstance(flow.get("steps"), list):
                raise ValueError(f"flow config must contain a steps list: {path}")
            for step in flow["steps"]:
                task_id = step.get("run") if isinstance(step, dict) else None
                if not isinstance(task_id, str) or task_id not in self.tasks_map:
                    raise ValueError(f"flow {path.name} references unknown task: {task_id}")

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

        behavior = self._load_behavior()
        task_agent_map = {t["id"]: t["agent"] for t in behavior.get("tasks", [])}

        results: List[Dict[str, Any]] = []
        context: Dict[str, str] = {}
        total_start = time.time()

        for step in steps_config:
            task_id = step.get("run")
            if not task_id:
                continue

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
                    task = task_method()
                    task_context = yaml.safe_dump(
                        {**inputs, **context},
                        allow_unicode=True,
                        sort_keys=False,
                    )
                    task_output = task.execute_sync(context=task_context)
                    output = task_output.raw
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

            context[task_id] = output
            if evidence_scope:
                context[f"{task_id}_scope"] = evidence_scope

        total_duration_ms = int((time.time() - total_start) * 1000)

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
        if task_id == "cluster_summary":
            actual_scope = context.get("k8s_pods_overview_scope", scope)
            return self._build_evidence_summary(context, actual_scope), actual_scope
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

        failing = sum(
            count
            for phase, count in phases.items()
            if FlowRunner._is_explicit_failure_phase(phase)
        )
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
    def _is_explicit_failure_phase(phase: str) -> bool:
        """Classify failure reasons emitted in kubectl's human STATUS column."""
        normalized = phase.casefold()
        failure_markers = (
            "error",
            "failed",
            "crashloopbackoff",
            "imagepullbackoff",
            "errimagepull",
            "oomkilled",
            "evicted",
            "runcontainererror",
            "deadlineexceeded",
        )
        return any(marker in normalized for marker in failure_markers)

    @staticmethod
    def _build_evidence_summary(context: Dict[str, str], scope: str) -> str:
        """Build the health report only from recorded evidence, without an LLM."""
        pod_summary = context.get("explain_pods", f"{scope}\nNo pod evidence available.")
        sections = [pod_summary]

        evidence_sources = (
            ("Node metrics", "k8s_top_nodes"),
            ("Pod metrics", "k8s_top_pods_ns_default"),
        )
        for title, key in evidence_sources:
            evidence = context.get(key, "").strip()
            if evidence:
                sections.append(f"{title} (verbatim):\n{evidence}")

        sections.append(
            "Architecture note: component presence or absence is not inferred "
            "from this bounded health snapshot."
        )
        return "\n\n".join(sections)

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
                metadata["cluster_summary"] = r["output"][:500] if r["output"] else ""
            if r["task"] == "incident_create_issue_if_needed":
                if "Created issue" in r.get("output", ""):
                    metadata["incident_created"] = True
                else:
                    metadata["incident_created"] = False
        return metadata
