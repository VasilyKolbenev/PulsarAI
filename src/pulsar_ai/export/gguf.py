"""GGUF export for llama.cpp / Ollama deployment."""

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def export_gguf(config: dict) -> dict:
    """Export model to GGUF format.

    Pipeline: merge adapter -> convert to GGUF -> quantize.

    Args:
        config: Config dict with model_path, export.quantization settings.

    Returns:
        Dict with output_path, quantization, file_size_mb.
    """
    model_path = config.get("model_path")
    export_config = config.get("export", {})
    quantization = export_config.get("quantization", "q4_k_m")
    output_path = export_config.get("output_path")

    if not model_path:
        raise ValueError("model_path is required for GGUF export")

    # Step 1: Ensure we have a merged model
    merged_dir = _ensure_merged_model(config, model_path)

    # Step 2: Convert to GGUF
    gguf_path = _convert_to_gguf(merged_dir, quantization, output_path)

    # Step 3: Generate Ollama Modelfile
    modelfile_path = _generate_modelfile(config, gguf_path)

    file_size_mb = Path(gguf_path).stat().st_size / (1024 * 1024)
    logger.info(
        "GGUF export complete: %s (%.1f MB, %s)",
        gguf_path,
        file_size_mb,
        quantization,
    )

    return {
        "output_path": str(gguf_path),
        "quantization": quantization,
        "file_size_mb": round(file_size_mb, 1),
        "modelfile_path": str(modelfile_path) if modelfile_path else None,
    }


def _ensure_merged_model(config: dict, model_path: str) -> str:
    """Ensure we have a merged (non-adapter) model for GGUF conversion.

    Args:
        config: Full config dict.
        model_path: Path to model or adapter.

    Returns:
        Path to merged model directory.
    """
    adapter_config = Path(model_path) / "adapter_config.json"

    if adapter_config.exists():
        logger.info("Merging adapter before GGUF conversion...")
        from pulsar_ai.export.merged import export_merged

        merge_config = dict(config)
        merge_config["export"] = {"output_path": str(Path(model_path).parent / "merged_for_gguf")}
        result = export_merged(merge_config)
        return result["output_path"]

    return model_path


def _convert_to_gguf(
    model_dir: str,
    quantization: str = "q4_k_m",
    output_path: Optional[str] = None,
) -> str:
    """Convert model to GGUF using llama.cpp tools.

    Tries multiple methods:
    1. Unsloth save_pretrained_gguf (if available)
    2. llama.cpp convert_hf_to_gguf.py + llama-quantize

    Args:
        model_dir: Path to merged model directory.
        quantization: Quantization type (q4_k_m, q8_0, f16).
        output_path: Optional explicit output path.

    Returns:
        Path to output GGUF file.

    Raises:
        RuntimeError: If no conversion method is available.
    """
    if output_path is None:
        output_path = str(Path(model_dir).parent / f"model-{quantization}.gguf")

    # Method 1: Try Unsloth
    try:
        return _convert_via_unsloth(model_dir, quantization, output_path)
    except (ImportError, Exception) as e:
        logger.debug("Unsloth GGUF not available: %s", e)

    # Method 2: Try llama.cpp tools
    try:
        return _convert_via_llamacpp(model_dir, quantization, output_path)
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        logger.debug("llama.cpp tools not available: %s", e)

    raise RuntimeError(
        "No GGUF conversion method available. Install either:\n"
        "  - unsloth: pip install unsloth\n"
        "  - llama.cpp: build from source and ensure "
        "convert_hf_to_gguf.py "
        "and llama-quantize are in PATH"
    )


def _convert_via_unsloth(model_dir: str, quantization: str, output_path: str) -> str:
    """Convert to GGUF using Unsloth's built-in method.

    Args:
        model_dir: Path to model directory.
        quantization: Quantization type.
        output_path: Output file path.

    Returns:
        Path to GGUF file.
    """
    from unsloth import FastLanguageModel

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_dir,
        load_in_4bit=False,
    )

    model.save_pretrained_gguf(
        output_path,
        tokenizer,
        quantization_method=quantization,
    )

    logger.info("GGUF exported via Unsloth: %s", output_path)
    return output_path


def _convert_via_llamacpp(model_dir: str, quantization: str, output_path: str) -> str:
    """Convert to GGUF using llama.cpp CLI tools.

    Args:
        model_dir: Path to model directory.
        quantization: Quantization type.
        output_path: Output file path.

    Returns:
        Path to GGUF file.
    """
    # Find convert script
    convert_script = shutil.which("convert_hf_to_gguf.py")
    if not convert_script:
        convert_script = shutil.which("convert-hf-to-gguf.py")
    if not convert_script:
        raise FileNotFoundError("convert_hf_to_gguf.py not found in PATH")

    quantize_bin = shutil.which("llama-quantize")
    if not quantize_bin:
        quantize_bin = shutil.which("quantize")
    if not quantize_bin:
        raise FileNotFoundError("llama-quantize not found in PATH")

    # Step 1: Convert to f16 GGUF
    f16_path = output_path.replace(".gguf", "-f16.gguf")
    subprocess.run(
        [
            "python",
            convert_script,
            model_dir,
            "--outfile",
            f16_path,
            "--outtype",
            "f16",
        ],
        check=True,
        capture_output=True,
    )
    logger.info("Converted to f16 GGUF: %s", f16_path)

    # Step 2: Quantize
    if quantization == "f16":
        Path(f16_path).rename(output_path)
    else:
        subprocess.run(
            [
                quantize_bin,
                f16_path,
                output_path,
                quantization.upper(),
            ],
            check=True,
            capture_output=True,
        )
        Path(f16_path).unlink(missing_ok=True)

    logger.info("Quantized GGUF: %s (%s)", output_path, quantization)
    return output_path


def _generate_modelfile(config: dict, gguf_path: str) -> Optional[str]:
    """Generate Ollama Modelfile for the GGUF model.

    Args:
        config: Full config dict.
        gguf_path: Path to GGUF file.

    Returns:
        Path to Modelfile or None.
    """
    ds_config = config.get("dataset", {})
    system_prompt = ds_config.get("system_prompt", "")

    if ds_config.get("system_prompt_file"):
        try:
            from pulsar_ai.data.formatter import load_system_prompt

            system_prompt = load_system_prompt(ds_config["system_prompt_file"])
        except FileNotFoundError:
            pass

    modelfile_path = Path(gguf_path).parent / "Modelfile"
    gguf_name = Path(gguf_path).name

    lines = [
        f"FROM ./{gguf_name}",
        "",
        "PARAMETER temperature 0.1",
        "PARAMETER top_p 0.9",
        'PARAMETER stop "<|im_end|>"',
        "",
    ]

    if system_prompt:
        lines.append(f'SYSTEM """{system_prompt}"""')

    with open(modelfile_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info("Ollama Modelfile saved: %s", modelfile_path)
    return str(modelfile_path)
