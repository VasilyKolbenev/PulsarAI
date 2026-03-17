"""Artifact storage abstraction for model adapters and exports.

Supports two backends:
- ``LocalArtifactStore``: filesystem (default)
- ``S3ArtifactStore``: S3/MinIO for production deployments

Selected via ``PULSAR_S3_BUCKET`` environment variable.
"""

import logging
import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ArtifactStore(ABC):
    """Abstract interface for artifact storage."""

    @abstractmethod
    def save(self, local_path: str, artifact_key: str) -> str:
        """Upload a local file/directory to the store.

        Returns:
            Storage URI for the artifact.
        """

    @abstractmethod
    def load(self, artifact_key: str, local_path: str) -> str:
        """Download an artifact to a local path.

        Returns:
            Local path of the downloaded artifact.
        """

    @abstractmethod
    def list_artifacts(self, prefix: str = "") -> list[str]:
        """List artifact keys matching a prefix."""

    @abstractmethod
    def delete(self, artifact_key: str) -> bool:
        """Delete an artifact. Returns True if deleted."""

    @abstractmethod
    def get_url(self, artifact_key: str) -> str:
        """Get a URL/path for the artifact."""


class LocalArtifactStore(ArtifactStore):
    """Filesystem-based artifact storage.

    Args:
        base_dir: Root directory for artifacts.
    """

    def __init__(self, base_dir: str = "data/artifacts") -> None:
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)

    def save(self, local_path: str, artifact_key: str) -> str:
        """Copy a file or directory to the artifact store."""
        src = Path(local_path)
        dest = self._base / artifact_key
        dest.parent.mkdir(parents=True, exist_ok=True)

        if src.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(str(src), str(dest))
        else:
            shutil.copy2(str(src), str(dest))

        logger.info("Saved artifact: %s → %s", local_path, dest)
        return str(dest)

    def load(self, artifact_key: str, local_path: str) -> str:
        """Copy an artifact to a local destination."""
        src = self._base / artifact_key
        if not src.exists():
            raise FileNotFoundError(f"Artifact not found: {artifact_key}")

        dest = Path(local_path)
        dest.parent.mkdir(parents=True, exist_ok=True)

        if src.is_dir():
            shutil.copytree(str(src), str(dest))
        else:
            shutil.copy2(str(src), str(dest))

        return str(dest)

    def list_artifacts(self, prefix: str = "") -> list[str]:
        """List artifact keys."""
        results = []
        search_path = self._base / prefix if prefix else self._base
        if search_path.exists():
            for p in search_path.rglob("*"):
                if p.is_file():
                    results.append(str(p.relative_to(self._base)))
        return sorted(results)

    def delete(self, artifact_key: str) -> bool:
        """Delete an artifact."""
        path = self._base / artifact_key
        if path.is_dir():
            shutil.rmtree(path)
            return True
        elif path.is_file():
            path.unlink()
            return True
        return False

    def get_url(self, artifact_key: str) -> str:
        """Get the filesystem path."""
        return str(self._base / artifact_key)


class S3ArtifactStore(ArtifactStore):
    """S3/MinIO-backed artifact storage.

    Requires: ``pip install pulsar-ai[s3]``

    Args:
        bucket: S3 bucket name.
        prefix: Key prefix within the bucket.
        endpoint_url: Custom S3 endpoint (for MinIO).
    """

    def __init__(
        self,
        bucket: str,
        prefix: str = "artifacts",
        endpoint_url: Optional[str] = None,
    ) -> None:
        try:
            import boto3
        except ImportError as exc:
            raise ImportError(
                "boto3 is required for S3 artifact storage. "
                "Install with: pip install pulsar-ai[s3]"
            ) from exc

        kwargs: dict = {}
        if endpoint_url:
            kwargs["endpoint_url"] = endpoint_url

        self._s3 = boto3.client("s3", **kwargs)
        self._bucket = bucket
        self._prefix = prefix
        logger.info("S3 artifact store: s3://%s/%s", bucket, prefix)

    def _key(self, artifact_key: str) -> str:
        return f"{self._prefix}/{artifact_key}"

    def save(self, local_path: str, artifact_key: str) -> str:
        """Upload a file to S3."""
        s3_key = self._key(artifact_key)
        src = Path(local_path)

        if src.is_dir():
            for f in src.rglob("*"):
                if f.is_file():
                    rel = f.relative_to(src)
                    self._s3.upload_file(str(f), self._bucket, f"{s3_key}/{rel}")
        else:
            self._s3.upload_file(str(src), self._bucket, s3_key)

        uri = f"s3://{self._bucket}/{s3_key}"
        logger.info("Uploaded artifact: %s → %s", local_path, uri)
        return uri

    def load(self, artifact_key: str, local_path: str) -> str:
        """Download an artifact from S3."""
        s3_key = self._key(artifact_key)
        dest = Path(local_path)
        dest.parent.mkdir(parents=True, exist_ok=True)

        # Check if it's a "directory" (multiple objects with prefix)
        response = self._s3.list_objects_v2(
            Bucket=self._bucket, Prefix=s3_key, MaxKeys=2
        )
        objects = response.get("Contents", [])

        if len(objects) == 1 and objects[0]["Key"] == s3_key:
            self._s3.download_file(self._bucket, s3_key, str(dest))
        else:
            # Download all files under the prefix
            paginator = self._s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self._bucket, Prefix=s3_key):
                for obj in page.get("Contents", []):
                    rel = obj["Key"][len(s3_key) :].lstrip("/")
                    file_dest = dest / rel
                    file_dest.parent.mkdir(parents=True, exist_ok=True)
                    self._s3.download_file(self._bucket, obj["Key"], str(file_dest))

        return str(dest)

    def list_artifacts(self, prefix: str = "") -> list[str]:
        """List artifact keys in S3."""
        s3_prefix = self._key(prefix) if prefix else self._prefix
        results = []
        paginator = self._s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=s3_prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.startswith(self._prefix + "/"):
                    key = key[len(self._prefix) + 1 :]
                results.append(key)
        return sorted(results)

    def delete(self, artifact_key: str) -> bool:
        """Delete an artifact from S3."""
        s3_key = self._key(artifact_key)
        try:
            self._s3.delete_object(Bucket=self._bucket, Key=s3_key)
            return True
        except Exception:
            return False

    def get_url(self, artifact_key: str) -> str:
        """Get the S3 URI."""
        return f"s3://{self._bucket}/{self._key(artifact_key)}"


_store: Optional[ArtifactStore] = None


def get_artifact_store() -> ArtifactStore:
    """Get the configured artifact store singleton.

    Returns:
        LocalArtifactStore or S3ArtifactStore.
    """
    global _store  # noqa: PLW0603
    if _store is not None:
        return _store

    bucket = os.environ.get("PULSAR_S3_BUCKET", "").strip()
    if bucket:
        endpoint = os.environ.get("PULSAR_S3_ENDPOINT", "").strip() or None
        _store = S3ArtifactStore(bucket=bucket, endpoint_url=endpoint)
    else:
        _store = LocalArtifactStore()
    return _store
