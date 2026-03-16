"""Tests for agent built-in tools."""

from pathlib import Path


from pulsar_ai.agent.builtin_tools import (
    search_files,
    read_file,
    list_directory,
    calculate,
    get_default_registry,
)


class TestSearchFiles:
    """Tests for search_files tool."""

    def test_finds_matching_files(self, tmp_path: Path) -> None:
        (tmp_path / "hello.txt").write_text("content")
        (tmp_path / "world.txt").write_text("content")
        (tmp_path / "other.py").write_text("content")

        result = search_files.execute(query=".txt", directory=str(tmp_path))
        assert "hello.txt" in result
        assert "world.txt" in result
        assert "other.py" not in result

    def test_no_matches(self, tmp_path: Path) -> None:
        (tmp_path / "hello.txt").write_text("content")
        result = search_files.execute(query=".xyz", directory=str(tmp_path))
        assert "No files found" in result

    def test_nonexistent_directory(self) -> None:
        result = search_files.execute(query="test", directory="/nonexistent")
        assert "Error" in result


class TestReadFile:
    """Tests for read_file tool."""

    def test_reads_file_content(self, tmp_path: Path) -> None:
        (tmp_path / "test.txt").write_text("Hello World")
        result = read_file.execute(path=str(tmp_path / "test.txt"))
        assert result == "Hello World"

    def test_nonexistent_file(self) -> None:
        result = read_file.execute(path="/nonexistent/file.txt")
        assert "Error" in result

    def test_truncates_long_files(self, tmp_path: Path) -> None:
        content = "\n".join(f"line {i}" for i in range(300))
        (tmp_path / "long.txt").write_text(content)
        result = read_file.execute(path=str(tmp_path / "long.txt"), max_lines=10)
        assert "truncated" in result


class TestListDirectory:
    """Tests for list_directory tool."""

    def test_lists_contents(self, tmp_path: Path) -> None:
        (tmp_path / "file.txt").write_text("content")
        (tmp_path / "subdir").mkdir()
        result = list_directory.execute(path=str(tmp_path))
        assert "file.txt" in result
        assert "[DIR]" in result
        assert "subdir" in result

    def test_nonexistent_dir(self) -> None:
        result = list_directory.execute(path="/nonexistent")
        assert "Error" in result

    def test_empty_dir(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        result = list_directory.execute(path=str(empty))
        assert "empty" in result.lower()


class TestCalculate:
    """Tests for calculate tool."""

    def test_basic_math(self) -> None:
        assert calculate.execute(expression="2 + 3") == "5"
        assert calculate.execute(expression="10 * 5") == "50"
        assert calculate.execute(expression="100 / 4") == "25.0"

    def test_complex_expression(self) -> None:
        result = calculate.execute(expression="(2 + 3) * 4")
        assert result == "20"

    def test_invalid_expression(self) -> None:
        result = calculate.execute(expression="import os")
        assert "Error" in result

    def test_division_by_zero(self) -> None:
        result = calculate.execute(expression="1/0")
        assert "Error" in result


class TestDefaultRegistry:
    """Tests for get_default_registry."""

    def test_has_all_builtin_tools(self) -> None:
        registry = get_default_registry()
        assert "search_files" in registry
        assert "read_file" in registry
        assert "list_directory" in registry
        assert "calculate" in registry
        assert len(registry) == 4
