"""Tests for llm_forge.dataset_version module.

Tests DatasetVersionStore: register, get_version, list_versions,
list_datasets, diff, get_lineage, and persistence with tmp_path.
"""

import json
from pathlib import Path

import pytest

from llm_forge.dataset_version import DatasetVersion, DatasetVersionStore


@pytest.fixture
def store() -> DatasetVersionStore:
    """Create an in-memory DatasetVersionStore."""
    return DatasetVersionStore()


@pytest.fixture
def persistent_store(tmp_path: Path) -> DatasetVersionStore:
    """Create a persistent DatasetVersionStore."""
    return DatasetVersionStore(storage_path=str(tmp_path / "versions.json"))


class TestRegister:
    """Tests for registering new dataset versions."""

    def test_register_creates_version_1(self, store: DatasetVersionStore) -> None:
        """First registration creates version 1."""
        v = store.register("train", path="/data/train.jsonl", num_rows=1000)
        assert v.version == 1
        assert v.path == "/data/train.jsonl"
        assert v.num_rows == 1000

    def test_register_increments_version(self, store: DatasetVersionStore) -> None:
        """Subsequent registrations increment the version number."""
        v1 = store.register("train", path="/data/v1.jsonl")
        v2 = store.register("train", path="/data/v2.jsonl")
        v3 = store.register("train", path="/data/v3.jsonl")
        assert v1.version == 1
        assert v2.version == 2
        assert v3.version == 3

    def test_register_with_all_fields(self, store: DatasetVersionStore) -> None:
        """Registration stores all provided fields."""
        v = store.register(
            "ds", path="/data/ds.jsonl",
            num_rows=5000, num_columns=10,
            columns=["text", "label", "id"],
            size_bytes=1024000,
            parent_version=0,
            transform="filter_empty",
            fingerprint="abc123",
            source="production",
        )
        assert v.num_columns == 10
        assert v.columns == ["text", "label", "id"]
        assert v.size_bytes == 1024000
        assert v.transform == "filter_empty"
        assert v.fingerprint == "abc123"
        assert v.metadata["source"] == "production"

    def test_register_auto_computes_fingerprint(
        self, store: DatasetVersionStore, tmp_path: Path,
    ) -> None:
        """Fingerprint is auto-computed from file if it exists."""
        data_file = tmp_path / "data.jsonl"
        data_file.write_text("test data content\n", encoding="utf-8")
        v = store.register("ds", path=str(data_file))
        assert len(v.fingerprint) == 16
        assert v.fingerprint != ""

    def test_register_auto_fingerprint_nonexistent_file(
        self, store: DatasetVersionStore,
    ) -> None:
        """Fingerprint falls back to path hash for non-existent file."""
        v = store.register("ds", path="/nonexistent/file.jsonl")
        assert len(v.fingerprint) == 16

    def test_register_sets_created_at(self, store: DatasetVersionStore) -> None:
        """Registration sets created_at timestamp."""
        v = store.register("ds", path="/data.jsonl")
        assert v.created_at > 0

    def test_register_different_datasets(self, store: DatasetVersionStore) -> None:
        """Different dataset names maintain separate version chains."""
        v1 = store.register("train", path="/train.jsonl")
        v2 = store.register("eval", path="/eval.jsonl")
        assert v1.version == 1
        assert v2.version == 1  # independent numbering


class TestGetVersion:
    """Tests for get_version()."""

    def test_get_version_latest(self, store: DatasetVersionStore) -> None:
        """version=0 returns the latest version."""
        store.register("ds", path="/v1.jsonl", num_rows=100)
        store.register("ds", path="/v2.jsonl", num_rows=200)
        latest = store.get_version("ds")
        assert latest is not None
        assert latest.version == 2
        assert latest.num_rows == 200

    def test_get_version_by_number(self, store: DatasetVersionStore) -> None:
        """Specific version number returns that version."""
        store.register("ds", path="/v1.jsonl", num_rows=100)
        store.register("ds", path="/v2.jsonl", num_rows=200)
        v1 = store.get_version("ds", version=1)
        assert v1 is not None
        assert v1.version == 1
        assert v1.num_rows == 100

    def test_get_version_nonexistent_dataset(
        self, store: DatasetVersionStore,
    ) -> None:
        """Non-existent dataset returns None."""
        assert store.get_version("nonexistent") is None

    def test_get_version_nonexistent_number(
        self, store: DatasetVersionStore,
    ) -> None:
        """Non-existent version number returns None."""
        store.register("ds", path="/v1.jsonl")
        assert store.get_version("ds", version=99) is None


class TestListVersions:
    """Tests for list_versions()."""

    def test_list_versions(self, store: DatasetVersionStore) -> None:
        """list_versions returns all versions as dicts."""
        store.register("ds", path="/v1.jsonl", num_rows=100)
        store.register("ds", path="/v2.jsonl", num_rows=200)
        versions = store.list_versions("ds")
        assert len(versions) == 2
        assert versions[0]["version"] == 1
        assert versions[1]["version"] == 2

    def test_list_versions_empty(self, store: DatasetVersionStore) -> None:
        """list_versions for unknown dataset returns empty list."""
        assert store.list_versions("nonexistent") == []


class TestListDatasets:
    """Tests for list_datasets()."""

    def test_list_datasets(self, store: DatasetVersionStore) -> None:
        """list_datasets returns all tracked datasets."""
        store.register("train", path="/train.jsonl", num_rows=1000)
        store.register("eval", path="/eval.jsonl", num_rows=500)
        datasets = store.list_datasets()
        names = {d["name"] for d in datasets}
        assert names == {"train", "eval"}

    def test_list_datasets_includes_version_count(
        self, store: DatasetVersionStore,
    ) -> None:
        """Each dataset entry includes version count."""
        store.register("ds", path="/v1.jsonl")
        store.register("ds", path="/v2.jsonl")
        datasets = store.list_datasets()
        ds_info = next(d for d in datasets if d["name"] == "ds")
        assert ds_info["versions"] == 2

    def test_list_datasets_empty(self, store: DatasetVersionStore) -> None:
        """Empty store returns empty list."""
        assert store.list_datasets() == []


class TestDiff:
    """Tests for diff() between versions."""

    def test_diff_rows_delta(self, store: DatasetVersionStore) -> None:
        """Diff shows correct rows_delta."""
        store.register("ds", path="/v1.jsonl", num_rows=100)
        store.register("ds", path="/v2.jsonl", num_rows=150)
        d = store.diff("ds", 1, 2)
        assert d["rows_delta"] == 50

    def test_diff_columns_added_removed(
        self, store: DatasetVersionStore,
    ) -> None:
        """Diff detects added and removed columns."""
        store.register("ds", path="/v1.jsonl", columns=["a", "b", "c"])
        store.register("ds", path="/v2.jsonl", columns=["a", "c", "d"])
        d = store.diff("ds", 1, 2)
        assert d["columns_added"] == ["d"]
        assert d["columns_removed"] == ["b"]

    def test_diff_size_delta(self, store: DatasetVersionStore) -> None:
        """Diff shows correct size_delta."""
        store.register("ds", path="/v1.jsonl", size_bytes=1000)
        store.register("ds", path="/v2.jsonl", size_bytes=1500)
        d = store.diff("ds", 1, 2)
        assert d["size_delta"] == 500

    def test_diff_fingerprint_changed(self, store: DatasetVersionStore) -> None:
        """Diff detects fingerprint change."""
        store.register("ds", path="/v1.jsonl", fingerprint="aaa")
        store.register("ds", path="/v2.jsonl", fingerprint="bbb")
        d = store.diff("ds", 1, 2)
        assert d["fingerprint_changed"] is True

    def test_diff_same_fingerprint(self, store: DatasetVersionStore) -> None:
        """Diff detects identical fingerprints."""
        store.register("ds", path="/v1.jsonl", fingerprint="same")
        store.register("ds", path="/v2.jsonl", fingerprint="same")
        d = store.diff("ds", 1, 2)
        assert d["fingerprint_changed"] is False

    def test_diff_includes_transform(self, store: DatasetVersionStore) -> None:
        """Diff includes the transform of v2."""
        store.register("ds", path="/v1.jsonl")
        store.register("ds", path="/v2.jsonl", transform="dedup")
        d = store.diff("ds", 1, 2)
        assert d["transform"] == "dedup"

    def test_diff_version_not_found(self, store: DatasetVersionStore) -> None:
        """Diff returns error when version not found."""
        store.register("ds", path="/v1.jsonl")
        d = store.diff("ds", 1, 99)
        assert "error" in d


class TestGetLineage:
    """Tests for get_lineage()."""

    def test_lineage_chain(self, store: DatasetVersionStore) -> None:
        """Lineage returns all versions in order."""
        store.register("ds", path="/raw.jsonl", num_rows=1000)
        store.register(
            "ds", path="/clean.jsonl", num_rows=900,
            parent_version=1, transform="clean",
        )
        store.register(
            "ds", path="/augmented.jsonl", num_rows=1800,
            parent_version=2, transform="augment",
        )
        lineage = store.get_lineage("ds")
        assert len(lineage) == 3
        assert lineage[0]["transform"] == "initial"
        assert lineage[1]["transform"] == "clean"
        assert lineage[2]["transform"] == "augment"
        assert lineage[1]["parent"] == 1
        assert lineage[2]["parent"] == 2

    def test_lineage_empty(self, store: DatasetVersionStore) -> None:
        """Lineage for unknown dataset returns empty list."""
        assert store.get_lineage("nonexistent") == []

    def test_lineage_fingerprint_truncated(
        self, store: DatasetVersionStore,
    ) -> None:
        """Lineage fingerprints are truncated to 12 chars."""
        store.register("ds", path="/v1.jsonl", fingerprint="abcdefghijklmnop")
        lineage = store.get_lineage("ds")
        assert lineage[0]["fingerprint"] == "abcdefghijkl"


class TestPersistence:
    """Tests for persistence using storage_path."""

    def test_save_and_load(self, tmp_path: Path) -> None:
        """Saved data is loadable by a new store instance."""
        storage = str(tmp_path / "versions.json")
        store1 = DatasetVersionStore(storage_path=storage)
        store1.register("ds", path="/v1.jsonl", num_rows=100, fingerprint="fp1")
        store1.register("ds", path="/v2.jsonl", num_rows=200, fingerprint="fp2")

        store2 = DatasetVersionStore(storage_path=storage)
        versions = store2.list_versions("ds")
        assert len(versions) == 2
        assert versions[0]["num_rows"] == 100
        assert versions[1]["num_rows"] == 200

    def test_persistence_file_created(
        self, persistent_store: DatasetVersionStore, tmp_path: Path,
    ) -> None:
        """Registering a version creates the JSON file."""
        persistent_store.register("ds", path="/v1.jsonl")
        filepath = tmp_path / "versions.json"
        assert filepath.exists()

    def test_persisted_file_is_valid_json(
        self, persistent_store: DatasetVersionStore, tmp_path: Path,
    ) -> None:
        """Persisted file is valid JSON."""
        persistent_store.register("ds", path="/v1.jsonl", fingerprint="fp1")
        filepath = tmp_path / "versions.json"
        data = json.loads(filepath.read_text(encoding="utf-8"))
        assert "ds" in data
        assert len(data["ds"]) == 1

    def test_empty_store_no_file(self, tmp_path: Path) -> None:
        """No file is created if nothing is registered."""
        storage = str(tmp_path / "empty.json")
        DatasetVersionStore(storage_path=storage)
        assert not (tmp_path / "empty.json").exists()
