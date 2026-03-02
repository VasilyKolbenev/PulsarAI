"""Dataset versioning — tracks changes to datasets over time.

Provides DVC-like versioning with fingerprints, diffs, and lineage tracking.
"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DatasetVersion:
    """A versioned snapshot of a dataset."""

    version: int
    fingerprint: str
    path: str
    num_rows: int = 0
    num_columns: int = 0
    columns: list[str] = field(default_factory=list)
    size_bytes: int = 0
    created_at: float = 0.0
    parent_version: int = 0
    transform: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "version": self.version,
            "fingerprint": self.fingerprint,
            "path": self.path,
            "num_rows": self.num_rows,
            "num_columns": self.num_columns,
            "columns": self.columns,
            "size_bytes": self.size_bytes,
            "created_at": self.created_at,
            "parent_version": self.parent_version,
            "transform": self.transform,
            "metadata": self.metadata,
        }


class DatasetVersionStore:
    """Tracks dataset versions with fingerprints and lineage.

    Args:
        storage_path: Path to JSON storage file. None = memory only.
    """

    def __init__(self, storage_path: str | None = None) -> None:
        self._versions: dict[str, list[DatasetVersion]] = {}
        self._storage_path = Path(storage_path) if storage_path else None

        if self._storage_path and self._storage_path.exists():
            self._load()

    def register(
        self,
        name: str,
        path: str,
        num_rows: int = 0,
        num_columns: int = 0,
        columns: list[str] | None = None,
        size_bytes: int = 0,
        parent_version: int = 0,
        transform: str = "",
        fingerprint: str = "",
        **metadata: Any,
    ) -> DatasetVersion:
        """Register a new dataset version.

        Args:
            name: Dataset name.
            path: File path.
            num_rows: Number of rows.
            num_columns: Number of columns.
            columns: Column names.
            size_bytes: File size in bytes.
            parent_version: Parent version number.
            transform: Description of the transform applied.
            fingerprint: Pre-computed fingerprint. Auto-computed if empty.
            **metadata: Extra metadata.

        Returns:
            The new DatasetVersion.
        """
        if name not in self._versions:
            self._versions[name] = []

        if not fingerprint:
            fingerprint = self._compute_fingerprint(path)

        version_num = len(self._versions[name]) + 1

        version = DatasetVersion(
            version=version_num,
            fingerprint=fingerprint,
            path=path,
            num_rows=num_rows,
            num_columns=num_columns,
            columns=columns or [],
            size_bytes=size_bytes,
            parent_version=parent_version,
            transform=transform,
            metadata=dict(metadata),
        )

        self._versions[name].append(version)
        self._save()
        return version

    def get_version(self, name: str, version: int = 0) -> DatasetVersion | None:
        """Get a specific dataset version.

        Args:
            name: Dataset name.
            version: Version number. 0 = latest.

        Returns:
            DatasetVersion or None.
        """
        versions = self._versions.get(name, [])
        if not versions:
            return None
        if version == 0:
            return versions[-1]
        for v in versions:
            if v.version == version:
                return v
        return None

    def list_versions(self, name: str) -> list[dict[str, Any]]:
        """List all versions of a dataset.

        Args:
            name: Dataset name.

        Returns:
            List of version summary dicts.
        """
        return [v.to_dict() for v in self._versions.get(name, [])]

    def list_datasets(self) -> list[dict[str, Any]]:
        """List all tracked datasets.

        Returns:
            List of dataset summary dicts.
        """
        result = []
        for name, versions in self._versions.items():
            latest = versions[-1] if versions else None
            result.append({
                "name": name,
                "versions": len(versions),
                "latest_fingerprint": latest.fingerprint if latest else "",
                "latest_rows": latest.num_rows if latest else 0,
            })
        return result

    def diff(self, name: str, v1: int, v2: int) -> dict[str, Any]:
        """Compare two versions of a dataset.

        Args:
            name: Dataset name.
            v1: First version number.
            v2: Second version number.

        Returns:
            Diff dict with changes.
        """
        ver1 = self.get_version(name, v1)
        ver2 = self.get_version(name, v2)

        if not ver1 or not ver2:
            return {"error": "Version not found"}

        return {
            "dataset": name,
            "v1": v1,
            "v2": v2,
            "fingerprint_changed": ver1.fingerprint != ver2.fingerprint,
            "rows_delta": ver2.num_rows - ver1.num_rows,
            "columns_added": [c for c in ver2.columns if c not in ver1.columns],
            "columns_removed": [c for c in ver1.columns if c not in ver2.columns],
            "size_delta": ver2.size_bytes - ver1.size_bytes,
            "transform": ver2.transform,
        }

    def get_lineage(self, name: str) -> list[dict[str, Any]]:
        """Get the full lineage chain of a dataset.

        Args:
            name: Dataset name.

        Returns:
            List of version dicts in chronological order.
        """
        versions = self._versions.get(name, [])
        return [
            {
                "version": v.version,
                "fingerprint": v.fingerprint[:12],
                "transform": v.transform or "initial",
                "rows": v.num_rows,
                "parent": v.parent_version,
            }
            for v in versions
        ]

    @staticmethod
    def _compute_fingerprint(path: str) -> str:
        """Compute SHA-256 fingerprint of a file."""
        p = Path(path)
        if not p.exists():
            return hashlib.sha256(path.encode()).hexdigest()[:16]

        h = hashlib.sha256()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()[:16]

    def _save(self) -> None:
        """Persist to JSON file."""
        if not self._storage_path:
            return
        data: dict[str, list[dict]] = {}
        for name, versions in self._versions.items():
            data[name] = [v.to_dict() for v in versions]
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _load(self) -> None:
        """Load from JSON file."""
        if not self._storage_path or not self._storage_path.exists():
            return
        with open(self._storage_path, encoding="utf-8") as f:
            data = json.load(f)
        for name, versions in data.items():
            self._versions[name] = []
            for vd in versions:
                cols = vd.pop("columns", [])
                meta = vd.pop("metadata", {})
                v = DatasetVersion(**vd, columns=cols, metadata=meta)
                self._versions[name].append(v)
