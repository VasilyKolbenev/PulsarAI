"""vLLM OpenAI-compatible server for model serving."""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def start_server(
    model_path: str,
    host: str = "0.0.0.0",
    port: int = 8000,
    tensor_parallel_size: int = 1,
    max_model_len: Optional[int] = None,
    quantization: Optional[str] = None,
    gpu_memory_utilization: float = 0.9,
) -> None:
    """Start vLLM OpenAI-compatible server.

    Args:
        model_path: Path to model directory (HF format, not GGUF).
        host: Server host.
        port: Server port.
        tensor_parallel_size: Number of GPUs for tensor parallelism.
        max_model_len: Maximum model context length.
        quantization: Quantization method (awq, gptq, None).
        gpu_memory_utilization: GPU memory fraction to use.

    Raises:
        ImportError: If vllm is not installed.
        ValueError: If model format is not supported.
    """
    model_dir = Path(model_path)
    if model_dir.suffix == ".gguf":
        raise ValueError(
            "vLLM requires HuggingFace model format, not GGUF. "
            "Use 'pulsar serve --backend llamacpp' for GGUF models, "
            "or 'pulsar export --format merged' first."
        )

    try:
        from vllm.entrypoints.openai.api_server import run_server
        from vllm.entrypoints.openai.cli_args import make_arg_parser
    except ImportError:
        raise ImportError("vLLM is not installed. Install with: " "pip install 'pulsar-ai[vllm]'")

    args = [
        "--model",
        str(model_path),
        "--host",
        host,
        "--port",
        str(port),
        "--tensor-parallel-size",
        str(tensor_parallel_size),
        "--gpu-memory-utilization",
        str(gpu_memory_utilization),
    ]

    if max_model_len:
        args.extend(["--max-model-len", str(max_model_len)])

    if quantization:
        args.extend(["--quantization", quantization])

    # Check for adapter
    adapter_config = model_dir / "adapter_config.json"
    if adapter_config.exists():
        logger.warning(
            "Model appears to be a LoRA adapter. "
            "For best performance, merge first: "
            "pulsar export --format merged"
        )
        import json

        with open(adapter_config) as f:
            cfg = json.load(f)
        base_model = cfg.get("base_model_name_or_path")
        if base_model:
            args = [
                "--model",
                base_model,
                "--enable-lora",
                "--lora-modules",
                f"adapter={model_path}",
                "--host",
                host,
                "--port",
                str(port),
                "--tensor-parallel-size",
                str(tensor_parallel_size),
                "--gpu-memory-utilization",
                str(gpu_memory_utilization),
            ]

    logger.info(
        "Starting vLLM server on %s:%d (model: %s)",
        host,
        port,
        model_path,
    )
    logger.info(
        "OpenAI-compatible API: http://%s:%d/v1/chat/completions",
        host,
        port,
    )

    parser = make_arg_parser()
    parsed = parser.parse_args(args)
    run_server(parsed)
