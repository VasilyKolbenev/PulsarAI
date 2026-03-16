"""Tests for LongTermMemory (JSON backend)."""

from pathlib import Path


from pulsar_ai.agent.memory import LongTermMemory


class TestLongTermMemory:
    """Tests for LongTermMemory with JSON backend."""

    def test_init_creates_store(self, tmp_path: Path) -> None:
        mem = LongTermMemory(
            store_path=str(tmp_path / "memory"),
            use_chromadb=False,
        )
        assert mem.count == 0
        assert (tmp_path / "memory").exists()

    def test_add_and_count(self, tmp_path: Path) -> None:
        mem = LongTermMemory(
            store_path=str(tmp_path / "memory"),
            use_chromadb=False,
        )
        mem.add("Python is a programming language")
        mem.add("JavaScript runs in the browser")
        assert mem.count == 2

    def test_add_returns_id(self, tmp_path: Path) -> None:
        mem = LongTermMemory(
            store_path=str(tmp_path / "memory"),
            use_chromadb=False,
        )
        entry_id = mem.add("Test entry")
        assert isinstance(entry_id, str)
        assert len(entry_id) == 16

    def test_add_with_metadata(self, tmp_path: Path) -> None:
        mem = LongTermMemory(
            store_path=str(tmp_path / "memory"),
            use_chromadb=False,
        )
        mem.add("Test entry", metadata={"source": "test", "score": 0.9})
        results = mem.search("test")
        assert len(results) == 1
        assert results[0]["metadata"]["source"] == "test"

    def test_search_finds_matching(self, tmp_path: Path) -> None:
        mem = LongTermMemory(
            store_path=str(tmp_path / "memory"),
            use_chromadb=False,
        )
        mem.add("Python is great for data science")
        mem.add("JavaScript is for web development")
        mem.add("Rust is fast and safe")

        results = mem.search("Python data")
        assert len(results) >= 1
        assert "Python" in results[0]["text"]

    def test_search_returns_scores(self, tmp_path: Path) -> None:
        mem = LongTermMemory(
            store_path=str(tmp_path / "memory"),
            use_chromadb=False,
        )
        mem.add("Python programming language")
        mem.add("JavaScript web browser")

        results = mem.search("Python")
        assert len(results) >= 1
        assert results[0]["score"] > 0

    def test_search_top_k(self, tmp_path: Path) -> None:
        mem = LongTermMemory(
            store_path=str(tmp_path / "memory"),
            use_chromadb=False,
        )
        for i in range(10):
            mem.add(f"Entry number {i} about testing")

        results = mem.search("testing", top_k=3)
        assert len(results) <= 3

    def test_search_no_match(self, tmp_path: Path) -> None:
        mem = LongTermMemory(
            store_path=str(tmp_path / "memory"),
            use_chromadb=False,
        )
        mem.add("Python programming")
        results = mem.search("xyznonexistent")
        assert len(results) == 0

    def test_persistence(self, tmp_path: Path) -> None:
        store = str(tmp_path / "memory")

        # Write
        mem1 = LongTermMemory(store_path=store, use_chromadb=False)
        mem1.add("Persistent entry")

        # Read in new instance
        mem2 = LongTermMemory(store_path=store, use_chromadb=False)
        assert mem2.count == 1
        results = mem2.search("persistent")
        assert len(results) == 1

    def test_repr(self, tmp_path: Path) -> None:
        mem = LongTermMemory(
            store_path=str(tmp_path / "memory"),
            use_chromadb=False,
        )
        r = repr(mem)
        assert "json" in r
        assert "entries=0" in r
