"""Tests for config loading, merging, and resolution."""

from pathlib import Path

import pytest

from pulsar_ai.config import deep_merge, load_yaml, load_config, _set_nested, _parse_value


class TestDeepMerge:
    """Tests for deep_merge function."""

    def test_deep_merge_flat_dicts(self) -> None:
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_deep_merge_nested_dicts(self) -> None:
        base = {"training": {"lr": 1e-4, "epochs": 3}}
        override = {"training": {"lr": 2e-4}}
        result = deep_merge(base, override)
        assert result == {"training": {"lr": 2e-4, "epochs": 3}}

    def test_deep_merge_does_not_mutate_originals(self) -> None:
        base = {"a": {"b": 1}}
        override = {"a": {"c": 2}}
        result = deep_merge(base, override)
        assert "c" not in base["a"]
        assert result["a"] == {"b": 1, "c": 2}

    def test_deep_merge_override_replaces_non_dict(self) -> None:
        base = {"a": [1, 2, 3]}
        override = {"a": [4, 5]}
        result = deep_merge(base, override)
        assert result["a"] == [4, 5]

    def test_deep_merge_empty_base(self) -> None:
        result = deep_merge({}, {"a": 1})
        assert result == {"a": 1}

    def test_deep_merge_empty_override(self) -> None:
        result = deep_merge({"a": 1}, {})
        assert result == {"a": 1}


class TestLoadYaml:
    """Tests for YAML file loading."""

    def test_load_yaml_valid_file(self, tmp_path: Path) -> None:
        config_file = tmp_path / "test.yaml"
        config_file.write_text("training:\n  lr: 0.001\n  epochs: 3\n")
        result = load_yaml(config_file)
        assert result == {"training": {"lr": 0.001, "epochs": 3}}

    def test_load_yaml_empty_file(self, tmp_path: Path) -> None:
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("")
        result = load_yaml(config_file)
        assert result == {}

    def test_load_yaml_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_yaml(Path("/nonexistent/path.yaml"))


class TestSetNested:
    """Tests for _set_nested dot notation setter."""

    def test_set_nested_simple_key(self) -> None:
        d: dict = {}
        _set_nested(d, "key", "value")
        assert d == {"key": "value"}

    def test_set_nested_dot_notation(self) -> None:
        d: dict = {}
        _set_nested(d, "training.learning_rate", 1e-4)
        assert d == {"training": {"learning_rate": 1e-4}}

    def test_set_nested_deep_path(self) -> None:
        d: dict = {}
        _set_nested(d, "a.b.c.d", 42)
        assert d["a"]["b"]["c"]["d"] == 42

    def test_set_nested_overwrites_existing(self) -> None:
        d = {"training": {"lr": 1e-3}}
        _set_nested(d, "training.lr", 2e-4)
        assert d["training"]["lr"] == 2e-4


class TestParseValue:
    """Tests for CLI value parsing."""

    def test_parse_int(self) -> None:
        assert _parse_value("42") == 42

    def test_parse_float(self) -> None:
        assert _parse_value("1e-4") == 1e-4

    def test_parse_bool_true(self) -> None:
        assert _parse_value("true") is True
        assert _parse_value("yes") is True

    def test_parse_bool_false(self) -> None:
        assert _parse_value("false") is False
        assert _parse_value("no") is False

    def test_parse_string(self) -> None:
        assert _parse_value("hello") == "hello"

    def test_parse_non_string_passthrough(self) -> None:
        assert _parse_value(42) == 42
        assert _parse_value([1, 2]) == [1, 2]


class TestLoadConfig:
    """Tests for full config loading pipeline."""

    def test_load_config_simple(self, tmp_path: Path) -> None:
        config_file = tmp_path / "experiment.yaml"
        config_file.write_text("strategy: qlora\n" "training:\n" "  epochs: 5\n")
        result = load_config(str(config_file), auto_hardware=False)
        assert result["strategy"] == "qlora"
        assert result["training"]["epochs"] == 5

    def test_load_config_with_cli_overrides(self, tmp_path: Path) -> None:
        config_file = tmp_path / "experiment.yaml"
        config_file.write_text("training:\n  epochs: 3\n")
        result = load_config(
            str(config_file),
            cli_overrides={"training.epochs": "10"},
            auto_hardware=False,
        )
        assert result["training"]["epochs"] == 10

    def test_load_config_with_inheritance(self, tmp_path: Path) -> None:
        # Create base config
        base_file = tmp_path / "base.yaml"
        base_file.write_text("training:\n  lr: 0.001\n  epochs: 3\n")

        # Create experiment config that inherits
        exp_file = tmp_path / "experiment.yaml"
        exp_file.write_text(f"inherit:\n  - {base_file}\n" "training:\n  epochs: 5\n")
        result = load_config(str(exp_file), auto_hardware=False)
        assert result["training"]["lr"] == 0.001
        assert result["training"]["epochs"] == 5
