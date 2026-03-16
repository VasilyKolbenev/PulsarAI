"""DAG-based pipeline executor with variable substitution and callbacks."""

import logging
import re
import time
from typing import Any, Protocol

from pulsar_ai.pipeline.steps import check_condition, dispatch_step
from pulsar_ai.pipeline.tracker import PipelineTracker

logger = logging.getLogger(__name__)

_VAR_PATTERN = re.compile(r"\$\{(\w+)\.(\w+)\}")


class PipelineCallback(Protocol):
    """Protocol for pipeline execution callbacks."""

    def on_pipeline_start(self, pipeline_name: str, step_names: list[str]) -> None: ...

    def on_step_start(self, step_name: str, step_type: str) -> None: ...

    def on_step_complete(
        self, step_name: str, result: dict[str, Any], duration_s: float
    ) -> None: ...

    def on_step_skip(self, step_name: str) -> None: ...

    def on_step_fail(self, step_name: str, error: str) -> None: ...

    def on_pipeline_complete(self, outputs: dict[str, Any]) -> None: ...

    def on_pipeline_fail(self, step_name: str, error: str) -> None: ...


class NullCallback:
    """No-op callback for when no external listener is needed."""

    def on_pipeline_start(self, pipeline_name: str, step_names: list[str]) -> None:
        pass

    def on_step_start(self, step_name: str, step_type: str) -> None:
        pass

    def on_step_complete(self, step_name: str, result: dict[str, Any], duration_s: float) -> None:
        pass

    def on_step_skip(self, step_name: str) -> None:
        pass

    def on_step_fail(self, step_name: str, error: str) -> None:
        pass

    def on_pipeline_complete(self, outputs: dict[str, Any]) -> None:
        pass

    def on_pipeline_fail(self, step_name: str, error: str) -> None:
        pass


class PipelineExecutor:
    """Execute a pipeline of training/eval/export steps in dependency order.

    Supports ${step_name.output_key} variable substitution across steps
    and optional callbacks for unified execution monitoring.

    Args:
        pipeline_config: Parsed pipeline YAML config.
        tracker: Optional tracker for persisting run state.
        callback: Optional callback for execution events.
    """

    def __init__(
        self,
        pipeline_config: dict,
        tracker: PipelineTracker | None = None,
        callback: PipelineCallback | None = None,
    ) -> None:
        self.name = pipeline_config.get("pipeline", {}).get("name", "unnamed")
        self.steps = pipeline_config.get("steps", [])
        self.tracker = tracker or PipelineTracker(self.name)
        self.callback: PipelineCallback = callback or NullCallback()
        self._outputs: dict[str, dict[str, Any]] = {}

    def run(self) -> dict[str, Any]:
        """Execute all steps in dependency order.

        Returns:
            Dict mapping step names to their outputs.

        Raises:
            RuntimeError: If a step fails.
        """
        execution_order = self._resolve_order()
        logger.info(
            "Pipeline '%s' — %d steps: %s",
            self.name,
            len(execution_order),
            " → ".join(execution_order),
        )

        self.tracker.start_run(step_names=execution_order)
        self.callback.on_pipeline_start(self.name, execution_order)

        for step_name in execution_order:
            step = self._get_step(step_name)

            # Check conditional — skip step if condition not met
            condition = step.get("condition")
            if condition and not check_condition(condition, self._outputs):
                logger.info("Skipping step '%s': condition not met", step_name)
                self.tracker.update_step(step_name, "skipped")
                self.callback.on_step_skip(step_name)
                self._outputs[step_name] = {"_skipped": True}
                continue

            resolved_config = self._resolve_vars(step.get("config", {}))

            step_type = step.get("type", "unknown")
            logger.info("Running step: %s (type=%s)", step_name, step_type)
            self.tracker.update_step(step_name, "running")
            self.callback.on_step_start(step_name, step_type)

            start = time.time()
            try:
                result = dispatch_step(
                    step_type=step["type"],
                    config=resolved_config,
                )
                elapsed = time.time() - start

                self._outputs[step_name] = result
                self.tracker.update_step(
                    step_name, "completed", result=result, duration_s=round(elapsed, 1)
                )
                self.callback.on_step_complete(step_name, result, round(elapsed, 1))
                logger.info("Step '%s' completed in %.1fs", step_name, elapsed)
            except Exception as e:
                self.tracker.update_step(step_name, "failed", error=str(e))
                self.callback.on_step_fail(step_name, str(e))
                self.callback.on_pipeline_fail(step_name, str(e))
                logger.exception("Step '%s' failed", step_name)
                raise RuntimeError(f"Pipeline step '{step_name}' failed: {e}") from e

        self.tracker.finish_run()
        self.callback.on_pipeline_complete(self._outputs)
        logger.info("Pipeline '%s' completed successfully", self.name)
        return self._outputs

    def _resolve_order(self) -> list[str]:
        """Topological sort of steps by depends_on.

        Returns:
            Ordered list of step names.

        Raises:
            ValueError: If dependencies are missing or circular.
        """
        step_names = {s["name"] for s in self.steps}
        deps: dict[str, list[str]] = {}
        for step in self.steps:
            name = step["name"]
            step_deps = step.get("depends_on", [])
            for d in step_deps:
                if d not in step_names:
                    raise ValueError(f"Step '{name}' depends on unknown step '{d}'")
            deps[name] = step_deps

        ordered: list[str] = []
        visited: set[str] = set()
        visiting: set[str] = set()

        def visit(name: str) -> None:
            if name in visiting:
                raise ValueError(f"Circular dependency involving '{name}'")
            if name in visited:
                return
            visiting.add(name)
            for dep in deps.get(name, []):
                visit(dep)
            visiting.remove(name)
            visited.add(name)
            ordered.append(name)

        for step in self.steps:
            visit(step["name"])

        return ordered

    def _get_step(self, name: str) -> dict:
        """Find step config by name."""
        for step in self.steps:
            if step["name"] == name:
                return step
        raise ValueError(f"Step '{name}' not found")

    def _resolve_vars(self, config: Any) -> Any:
        """Recursively resolve ${step.key} variables in config.

        Args:
            config: Config value (dict, list, or scalar).

        Returns:
            Config with variables replaced by step outputs.
        """
        if isinstance(config, str):
            return _VAR_PATTERN.sub(self._var_replacer, config)
        elif isinstance(config, dict):
            return {k: self._resolve_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._resolve_vars(item) for item in config]
        return config

    def _var_replacer(self, match: re.Match) -> str:
        """Replace a ${step.key} match with actual value."""
        step_name = match.group(1)
        key = match.group(2)
        if step_name not in self._outputs:
            logger.warning("Variable ${%s.%s} references unfinished step", step_name, key)
            return match.group(0)
        value = self._outputs[step_name].get(key, match.group(0))
        return str(value)
