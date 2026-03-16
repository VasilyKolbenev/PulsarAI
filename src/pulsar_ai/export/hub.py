"""Push model to HuggingFace Hub."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def push_to_hub(config: dict) -> dict:
    """Push model or adapter to HuggingFace Hub.

    Args:
        config: Config dict with model_path and hub settings.

    Returns:
        Dict with repo_id and url.
    """
    model_path = config.get("model_path")
    export_config = config.get("export", {})
    hub_config = export_config.get("hub", {})

    repo_id = hub_config.get("repo_id")
    if not repo_id:
        raise ValueError(
            "export.hub.repo_id is required for Hub push. " "Example: 'username/model-name'"
        )

    private = hub_config.get("private", True)
    commit_message = hub_config.get("commit_message", "Upload model via Pulsar AI")

    if not model_path:
        raise ValueError("model_path is required for Hub push")

    # Check if it's an adapter or full model
    adapter_config = Path(model_path) / "adapter_config.json"
    is_adapter = adapter_config.exists()

    if is_adapter:
        url = _push_adapter(model_path, repo_id, private, commit_message)
    else:
        url = _push_model(model_path, repo_id, private, commit_message)

    logger.info("Pushed to HuggingFace Hub: %s", url)
    return {
        "output_path": url,
        "repo_id": repo_id,
        "is_adapter": is_adapter,
    }


def _push_adapter(
    adapter_path: str,
    repo_id: str,
    private: bool,
    commit_message: str,
) -> str:
    """Push LoRA adapter to Hub.

    Args:
        adapter_path: Path to adapter directory.
        repo_id: HuggingFace repo ID.
        private: Whether repo should be private.
        commit_message: Commit message.

    Returns:
        Hub URL.
    """
    from huggingface_hub import HfApi

    api = HfApi()
    api.create_repo(repo_id=repo_id, private=private, exist_ok=True)
    api.upload_folder(
        folder_path=adapter_path,
        repo_id=repo_id,
        commit_message=commit_message,
    )

    return f"https://huggingface.co/{repo_id}"


def _push_model(
    model_path: str,
    repo_id: str,
    private: bool,
    commit_message: str,
) -> str:
    """Push full model to Hub.

    Args:
        model_path: Path to model directory.
        repo_id: HuggingFace repo ID.
        private: Whether repo should be private.
        commit_message: Commit message.

    Returns:
        Hub URL.
    """
    from huggingface_hub import HfApi

    api = HfApi()
    api.create_repo(repo_id=repo_id, private=private, exist_ok=True)
    api.upload_folder(
        folder_path=model_path,
        repo_id=repo_id,
        commit_message=commit_message,
    )

    return f"https://huggingface.co/{repo_id}"
