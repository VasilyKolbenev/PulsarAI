"""Step dispatchers for pipeline execution."""

import logging
from typing import Any

logger = logging.getLogger(__name__)

_STEP_HANDLERS: dict[str, Any] = {}


def register_step(name: str):
    """Decorator to register a step handler.

    Args:
        name: Step type name.
    """
    def wrapper(func):
        _STEP_HANDLERS[name] = func
        return func
    return wrapper


def dispatch_step(step_type: str, config: dict) -> dict[str, Any]:
    """Dispatch a pipeline step to the appropriate handler.

    Args:
        step_type: Step type (training, evaluation, export, register,
                   fingerprint, serve, conditional).
        config: Resolved step config.

    Returns:
        Dict with step outputs (paths, metrics, etc.).

    Raises:
        ValueError: If step type is unknown.
    """
    handler = _STEP_HANDLERS.get(step_type)
    if handler:
        return handler(config)

    builtin = {
        "training": _run_training_step,
        "evaluation": _run_evaluation_step,
        "export": _run_export_step,
        "register": _run_register_step,
        "fingerprint": _run_fingerprint_step,
    }
    if step_type in builtin:
        return builtin[step_type](config)

    raise ValueError(f"Unknown step type: {step_type}")


def _run_training_step(config: dict) -> dict[str, Any]:
    """Execute a training step.

    Args:
        config: Training config with task, model, dataset, etc.

    Returns:
        Training results dict.
    """
    task = config.get("task", "sft")
    logger.info("Training step: task=%s", task)

    if task == "sft":
        from llm_forge.training.sft import train_sft
        return train_sft(config)
    elif task == "dpo":
        from llm_forge.training.dpo import train_dpo
        return train_dpo(config)
    else:
        raise ValueError(f"Unknown training task: {task}")


def _run_evaluation_step(config: dict) -> dict[str, Any]:
    """Execute an evaluation step.

    Args:
        config: Evaluation config with model_path, test_data_path.

    Returns:
        Evaluation results dict.
    """
    logger.info("Evaluation step: model=%s", config.get("model_path"))

    from llm_forge.evaluation.runner import run_evaluation
    return run_evaluation(config)


def _run_export_step(config: dict) -> dict[str, Any]:
    """Execute an export step.

    Args:
        config: Export config with model_path, export format.

    Returns:
        Export results dict.
    """
    export_config = config.get("export", {})
    fmt = export_config.get("format", "gguf")
    logger.info("Export step: format=%s", fmt)

    if fmt == "gguf":
        from llm_forge.export.gguf import export_gguf
        return export_gguf(config)
    elif fmt == "merged":
        from llm_forge.export.merged import export_merged
        return export_merged(config)
    elif fmt == "hub":
        from llm_forge.export.hub import push_to_hub
        return push_to_hub(config)
    else:
        raise ValueError(f"Unknown export format: {fmt}")


def _run_register_step(config: dict) -> dict[str, Any]:
    """Register a model in the registry as a pipeline step.

    Args:
        config: Config with name, model_path, task, base_model.

    Returns:
        Registered model entry dict.
    """
    from llm_forge.registry import ModelRegistry

    reg = ModelRegistry()
    entry = reg.register(
        name=config.get("name", "pipeline-model"),
        model_path=config.get("model_path", ""),
        task=config.get("task", "sft"),
        base_model=config.get("model", {}).get("name", ""),
        dataset_fingerprint=config.get("_dataset_fingerprint", ""),
    )
    logger.info("Registered model: %s", entry["id"])
    return {"model_id": entry["id"], "model_path": entry["model_path"]}


def _run_fingerprint_step(config: dict) -> dict[str, Any]:
    """Compute dataset fingerprint as a pipeline step.

    Args:
        config: Config with dataset.path.

    Returns:
        Dict with fingerprint hash.
    """
    from llm_forge.tracking import fingerprint_dataset

    path = config.get("dataset", {}).get("path", "")
    if not path:
        return {"fingerprint": "", "error": "No dataset path"}

    fp = fingerprint_dataset(path)
    return {"fingerprint": fp, "dataset_path": path}




def _simulated_step(step_type: str, config: dict) -> dict[str, Any]:
    """Return a lightweight result for visual/orchestration-only steps.

    These step types come from the Workflow UI and are used to model
    AgentOffice flows. They intentionally do not invoke heavy training/export
    logic, but still produce deterministic outputs for pipeline chaining.
    """
    return {
        "status": "simulated",
        "step_type": step_type,
        "config": config,
    }


@register_step("data")
def _run_data_step(config: dict) -> dict[str, Any]:
    return _simulated_step("data", config)


@register_step("model")
def _run_model_step(config: dict) -> dict[str, Any]:
    return _simulated_step("model", config)


@register_step("prompt")
def _run_prompt_step(config: dict) -> dict[str, Any]:
    return _simulated_step("prompt", config)


@register_step("agent")
def _run_agent_step(config: dict) -> dict[str, Any]:
    return _simulated_step("agent", config)


@register_step("router")
def _run_router_step(config: dict) -> dict[str, Any]:
    return _simulated_step("router", config)


@register_step("a2a")
def _run_a2a_step(config: dict) -> dict[str, Any]:
    return _simulated_step("a2a", config)


@register_step("gateway")
def _run_gateway_step(config: dict) -> dict[str, Any]:
    return _simulated_step("gateway", config)


@register_step("splitter")
def _run_splitter_step(config: dict) -> dict[str, Any]:
    return _simulated_step("splitter", config)


@register_step("rag")
def _run_rag_step(config: dict) -> dict[str, Any]:
    return _simulated_step("rag", config)


@register_step("inference")
def _run_inference_step(config: dict) -> dict[str, Any]:
    return _simulated_step("inference", config)


@register_step("serve")
def _run_serve_step(config: dict) -> dict[str, Any]:
    return _simulated_step("serve", config)


@register_step("data_generation")
def _run_data_generation_step(config: dict) -> dict[str, Any]:
    return _simulated_step("data_generation", config)


@register_step("conditional")
def _run_conditional_step(config: dict) -> dict[str, Any]:
    return _simulated_step("conditional", config)

def check_condition(condition: dict, step_outputs: dict) -> bool:
    """Evaluate a conditional expression against step outputs.

    Supports: gt, gte, lt, lte, eq, neq operators.

    Args:
        condition: Dict with 'metric' (${step.key}), 'operator', 'value'.
        step_outputs: Dict of step_name -> output_dict.

    Returns:
        True if condition is met.

    Example:
        condition = {
            "metric": "${eval.accuracy}",
            "operator": "gte",
            "value": 0.85,
        }
    """
    import re

    metric_ref = condition.get("metric", "")
    operator = condition.get("operator", "gte")
    threshold = condition.get("value", 0)

    # Resolve ${step.key} reference
    match = re.match(r"\$\{(\w+)\.(\w+)\}", metric_ref)
    if not match:
        logger.warning("Invalid metric reference: %s", metric_ref)
        return False

    step_name, key = match.group(1), match.group(2)
    if step_name not in step_outputs:
        logger.warning("Step '%s' not found in outputs", step_name)
        return False

    actual = step_outputs[step_name].get(key)
    if actual is None:
        logger.warning("Key '%s' not found in step '%s' outputs", key, step_name)
        return False

    ops = {
        "gt": lambda a, b: a > b,
        "gte": lambda a, b: a >= b,
        "lt": lambda a, b: a < b,
        "lte": lambda a, b: a <= b,
        "eq": lambda a, b: a == b,
        "neq": lambda a, b: a != b,
    }

    op_func = ops.get(operator)
    if not op_func:
        logger.warning("Unknown operator: %s", operator)
        return False

    result = op_func(float(actual), float(threshold))
    logger.info(
        "Condition: %s.%s (%s) %s %s -> %s",
        step_name, key, actual, operator, threshold, result,
    )
    return result
