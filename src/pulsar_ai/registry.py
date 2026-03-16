"""Model registry: catalog trained models with metadata and status."""

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

REGISTRY_PATH = Path("./data/model_registry.json")


class ModelRegistry:
    """Local model registry for tracking trained models.

    Stores metadata about each model version: config, metrics,
    serving format, dataset fingerprint, and deployment status.

    Args:
        registry_path: Path to the registry JSON file.
    """

    def __init__(self, registry_path: Path | None = None) -> None:
        self.registry_path = registry_path or REGISTRY_PATH
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.registry_path.exists():
            self._save([])

    def register(
        self,
        name: str,
        model_path: str,
        task: str = "sft",
        base_model: str = "",
        config: dict | None = None,
        metrics: dict | None = None,
        dataset_fingerprint: str = "",
        tags: list[str] | None = None,
        serving_format: str = "",
    ) -> dict:
        """Register a new model version.

        Args:
            name: Model name.
            model_path: Path to model/adapter directory.
            task: Training task (sft, dpo).
            base_model: Base model name.
            config: Training config used.
            metrics: Evaluation metrics.
            dataset_fingerprint: SHA256 of training data.
            tags: Optional tags.
            serving_format: Format (lora, merged, gguf, etc.).

        Returns:
            Registered model entry dict.
        """
        models = self._load()
        version = sum(1 for m in models if m["name"] == name) + 1

        entry = {
            "id": f"{name}-v{version}",
            "name": name,
            "version": version,
            "model_path": model_path,
            "task": task,
            "base_model": base_model,
            "config": config or {},
            "metrics": metrics or {},
            "dataset_fingerprint": dataset_fingerprint,
            "tags": tags or [],
            "serving_format": serving_format,
            "status": "registered",
            "created_at": datetime.now().isoformat(),
            "deployed_at": None,
        }

        models.append(entry)
        self._save(models)
        logger.info("Registered model: %s (v%d)", name, version)
        return entry

    def list_models(
        self,
        name: str | None = None,
        status: str | None = None,
        tag: str | None = None,
    ) -> list[dict]:
        """List registered models.

        Args:
            name: Filter by model name.
            status: Filter by status.
            tag: Filter by tag.

        Returns:
            List of model entries (newest first).
        """
        models = self._load()
        if name:
            models = [m for m in models if m["name"] == name]
        if status:
            models = [m for m in models if m["status"] == status]
        if tag:
            models = [m for m in models if tag in m.get("tags", [])]
        return sorted(models, key=lambda m: m["created_at"], reverse=True)

    def get(self, model_id: str) -> dict | None:
        """Get a model by ID.

        Args:
            model_id: Model identifier (name-vN).

        Returns:
            Model entry or None.
        """
        for m in self._load():
            if m["id"] == model_id:
                return m
        return None

    def get_latest(self, name: str) -> dict | None:
        """Get the latest version of a model.

        Args:
            name: Model name.

        Returns:
            Latest model entry or None.
        """
        versions = [m for m in self._load() if m["name"] == name]
        if not versions:
            return None
        return max(versions, key=lambda m: m["version"])

    def update_status(self, model_id: str, status: str) -> dict | None:
        """Update model deployment status.

        Args:
            model_id: Model identifier.
            status: New status (registered, staging, production, archived).

        Returns:
            Updated entry or None.
        """
        models = self._load()
        for m in models:
            if m["id"] == model_id:
                m["status"] = status
                if status == "production":
                    m["deployed_at"] = datetime.now().isoformat()
                self._save(models)
                return m
        return None

    def update_metrics(self, model_id: str, metrics: dict) -> dict | None:
        """Update model metrics (e.g., after evaluation).

        Args:
            model_id: Model identifier.
            metrics: New metrics to merge.

        Returns:
            Updated entry or None.
        """
        models = self._load()
        for m in models:
            if m["id"] == model_id:
                m["metrics"].update(metrics)
                self._save(models)
                return m
        return None

    def delete(self, model_id: str) -> bool:
        """Delete a model from the registry.

        Args:
            model_id: Model identifier.

        Returns:
            True if deleted.
        """
        models = self._load()
        original_len = len(models)
        models = [m for m in models if m["id"] != model_id]
        if len(models) < original_len:
            self._save(models)
            return True
        return False

    def compare(self, model_ids: list[str]) -> dict:
        """Compare multiple models side by side.

        Args:
            model_ids: List of model IDs to compare.

        Returns:
            Comparison dict with metrics and configs.
        """
        models = [self.get(mid) for mid in model_ids]
        models = [m for m in models if m is not None]

        if len(models) < 2:
            return {"error": "Need at least 2 models to compare"}

        # Collect all metric keys
        all_metrics: set[str] = set()
        for m in models:
            all_metrics.update(m.get("metrics", {}).keys())

        comparison = {
            "models": [
                {
                    "id": m["id"],
                    "name": m["name"],
                    "version": m["version"],
                    "task": m["task"],
                    "base_model": m["base_model"],
                    "status": m["status"],
                }
                for m in models
            ],
            "metrics": {
                key: [m.get("metrics", {}).get(key) for m in models] for key in sorted(all_metrics)
            },
        }
        return comparison

    def _load(self) -> list[dict]:
        with open(self.registry_path, encoding="utf-8") as f:
            return json.load(f)

    def _save(self, models: list[dict]) -> None:
        with open(self.registry_path, "w", encoding="utf-8") as f:
            json.dump(models, f, ensure_ascii=False, indent=2)
