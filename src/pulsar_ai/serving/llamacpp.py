"""llama.cpp server wrapper for GGUF model serving."""

import logging
import os
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def start_server(
    model_path: str,
    host: str = "0.0.0.0",
    port: int = 8080,
    n_ctx: int = 2048,
    n_gpu_layers: int = -1,
) -> None:
    """Start llama.cpp server for GGUF model.

    Tries multiple methods:
    1. llama-server binary (llama.cpp)
    2. llama-cpp-python HTTP server
    3. Ollama (if installed)

    Args:
        model_path: Path to GGUF model file.
        host: Server host.
        port: Server port.
        n_ctx: Context window size.
        n_gpu_layers: GPU layers (-1 = all).

    Raises:
        RuntimeError: If no serving backend is available.
    """
    model_file = Path(model_path)
    if not model_file.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")

    if model_file.suffix != ".gguf":
        raise ValueError(f"llama.cpp requires .gguf model file, got: {model_file.suffix}")

    # Method 1: llama-server binary
    llama_server = shutil.which("llama-server")
    if llama_server:
        logger.info("Starting llama-server on %s:%d", host, port)
        _run_llama_server(llama_server, model_path, host, port, n_ctx, n_gpu_layers)
        return

    # Method 2: llama-cpp-python
    try:
        _run_llamacpp_python(model_path, host, port, n_ctx, n_gpu_layers)
        return
    except ImportError:
        logger.debug("llama-cpp-python not installed")

    # Method 3: Ollama
    ollama_bin = shutil.which("ollama")
    if ollama_bin:
        _run_ollama(model_path, host, port)
        return

    raise RuntimeError(
        "No llama.cpp serving backend found. Install one of:\n"
        "  - llama.cpp: build llama-server from source\n"
        "  - llama-cpp-python: pip install 'pulsar-ai[llamacpp]'\n"
        "  - ollama: https://ollama.ai"
    )


def _run_llama_server(
    binary: str,
    model_path: str,
    host: str,
    port: int,
    n_ctx: int,
    n_gpu_layers: int,
) -> None:
    """Run native llama-server binary.

    Args:
        binary: Path to llama-server executable.
        model_path: Path to GGUF file.
        host: Server host.
        port: Server port.
        n_ctx: Context window.
        n_gpu_layers: GPU layers.
    """
    cmd = [
        binary,
        "--model",
        model_path,
        "--host",
        host,
        "--port",
        str(port),
        "--ctx-size",
        str(n_ctx),
        "--n-gpu-layers",
        str(n_gpu_layers),
    ]

    logger.info("Running: %s", " ".join(cmd))

    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        logger.info("Server stopped")


def _run_llamacpp_python(
    model_path: str,
    host: str,
    port: int,
    n_ctx: int,
    n_gpu_layers: int,
) -> None:
    """Run llama-cpp-python HTTP server.

    Args:
        model_path: Path to GGUF file.
        host: Server host.
        port: Server port.
        n_ctx: Context window.
        n_gpu_layers: GPU layers.
    """
    from llama_cpp.server.app import create_app, Settings
    import uvicorn

    settings = Settings(
        model=model_path,
        n_ctx=n_ctx,
        n_gpu_layers=n_gpu_layers,
        host=host,
        port=port,
    )

    app = create_app(settings=settings)
    logger.info(
        "Starting llama-cpp-python server on %s:%d",
        host,
        port,
    )

    uvicorn.run(app, host=host, port=port)


def _run_ollama(model_path: str, host: str, port: int) -> None:
    """Run model via Ollama.

    Creates/updates Ollama model from GGUF file.

    Args:
        model_path: Path to GGUF file.
        host: Server host (Ollama uses its own port management).
        port: Server port.
    """
    model_dir = Path(model_path).parent
    modelfile = model_dir / "Modelfile"

    if not modelfile.exists():
        # Create a basic Modelfile
        with open(modelfile, "w") as f:
            f.write(f"FROM {model_path}\n")
            f.write("PARAMETER temperature 0.1\n")

    model_name = Path(model_path).stem.replace(".", "-").lower()

    logger.info("Creating Ollama model: %s", model_name)
    subprocess.run(
        ["ollama", "create", model_name, "-f", str(modelfile)],
        check=True,
    )

    logger.info("Starting Ollama server for %s", model_name)
    logger.info(
        "Access via: curl http://localhost:%d/api/generate "
        '-d \'{"model":"%s","prompt":"test"}\'',
        port,
        model_name,
    )
    env = {**os.environ, "OLLAMA_HOST": f"{host}:{port}"}
    subprocess.run(
        ["ollama", "serve"],
        env=env,
        check=True,
    )
