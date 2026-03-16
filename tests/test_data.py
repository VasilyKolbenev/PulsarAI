"""Tests for data loading, formatting, and splitting."""

import json
from pathlib import Path

import pandas as pd
import pytest

from pulsar_ai.data.loader import load_dataset_from_config, _detect_format
from pulsar_ai.data.formatter import (
    build_chat_examples,
    load_system_prompt,
    build_dpo_pairs,
)


class TestDetectFormat:
    """Tests for file format detection."""

    def test_detect_csv(self) -> None:
        assert _detect_format("data.csv") == "csv"

    def test_detect_jsonl(self) -> None:
        assert _detect_format("data.jsonl") == "jsonl"

    def test_detect_json(self) -> None:
        assert _detect_format("data.json") == "jsonl"

    def test_detect_parquet(self) -> None:
        assert _detect_format("data.parquet") == "parquet"

    def test_detect_excel(self) -> None:
        assert _detect_format("data.xlsx") == "excel"

    def test_detect_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="Cannot detect format"):
            _detect_format("data.txt")


class TestLoadDataset:
    """Tests for dataset loading from config."""

    def test_load_csv(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("text,label\nhello,greet\nbye,farewell\n")
        config = {"dataset": {"path": str(csv_file), "text_column": "text"}}
        df = load_dataset_from_config(config)
        assert len(df) == 2
        assert "text" in df.columns

    def test_load_jsonl(self, tmp_path: Path) -> None:
        jsonl_file = tmp_path / "data.jsonl"
        lines = [
            json.dumps({"text": "hello", "label": "greet"}),
            json.dumps({"text": "bye", "label": "farewell"}),
        ]
        jsonl_file.write_text("\n".join(lines))
        config = {"dataset": {"path": str(jsonl_file), "text_column": "text"}}
        df = load_dataset_from_config(config)
        assert len(df) == 2

    def test_load_missing_path_raises(self) -> None:
        with pytest.raises(ValueError, match="dataset.path is required"):
            load_dataset_from_config({"dataset": {}})

    def test_load_drops_duplicates(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "dup.csv"
        csv_file.write_text("text,label\nhello,greet\nhello,greet\nbye,farewell\n")
        config = {"dataset": {"path": str(csv_file), "text_column": "text"}}
        df = load_dataset_from_config(config)
        assert len(df) == 2


class TestBuildChatExamples:
    """Tests for chat example formatting."""

    def test_build_json_format(self) -> None:
        df = pd.DataFrame(
            {
                "phrase": ["hello world", "test input"],
                "domain": ["GREETING", "TEST"],
            }
        )
        examples = build_chat_examples(
            df=df,
            system_prompt="You are a classifier.",
            text_column="phrase",
            label_columns=["domain"],
            output_format="json",
        )
        assert len(examples) == 2
        assert len(examples[0]["messages"]) == 3
        assert examples[0]["messages"][0]["role"] == "system"
        assert examples[0]["messages"][1]["role"] == "user"
        assert examples[0]["messages"][2]["role"] == "assistant"

        # Check JSON output contains the label
        assistant_text = examples[0]["messages"][2]["content"]
        parsed = json.loads(assistant_text)
        assert parsed["domain"] == "GREETING"

    def test_build_text_format(self) -> None:
        df = pd.DataFrame(
            {
                "phrase": ["hello"],
                "label": ["greet"],
            }
        )
        examples = build_chat_examples(
            df=df,
            system_prompt="Classify.",
            text_column="phrase",
            label_columns=["label"],
            output_format="text",
        )
        assert examples[0]["messages"][2]["content"] == "greet"

    def test_build_skips_empty_text(self) -> None:
        df = pd.DataFrame(
            {
                "phrase": ["hello", "", "  "],
                "label": ["greet", "empty", "space"],
            }
        )
        examples = build_chat_examples(
            df=df,
            system_prompt="Classify.",
            text_column="phrase",
            label_columns=["label"],
        )
        assert len(examples) == 1


class TestLoadSystemPrompt:
    """Tests for system prompt loading."""

    def test_load_existing_prompt(self, tmp_path: Path) -> None:
        prompt_file = tmp_path / "prompt.txt"
        prompt_file.write_text("  You are a classifier.  \n")
        result = load_system_prompt(str(prompt_file))
        assert result == "You are a classifier."

    def test_load_missing_prompt_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_system_prompt("/nonexistent/prompt.txt")


class TestBuildDpoPairs:
    """Tests for DPO pair generation."""

    def test_build_pairs_from_errors(self) -> None:
        errors_df = pd.DataFrame(
            {
                "phrase": ["hello world"],
                "true_domain": ["GREETING"],
                "pred_domain": ["FAREWELL"],
            }
        )
        all_data = pd.DataFrame(
            {
                "phrase": ["hello", "bye", "test"],
                "domain": ["GREETING", "FAREWELL", "TEST"],
            }
        )
        pairs = build_dpo_pairs(
            errors_df=errors_df,
            all_data=all_data,
            label_columns=["domain"],
            n_synthetic=2,
            seed=42,
        )
        # Should have 1 error pair + up to 2 synthetic
        assert len(pairs) >= 1
        assert all("prompt" in p and "chosen" in p and "rejected" in p for p in pairs)

    def test_build_pairs_chosen_differs_from_rejected(self) -> None:
        errors_df = pd.DataFrame(
            {
                "phrase": ["test"],
                "true_domain": ["A"],
                "pred_domain": ["B"],
            }
        )
        all_data = pd.DataFrame(
            {
                "phrase": ["x", "y", "z"],
                "domain": ["A", "B", "C"],
            }
        )
        pairs = build_dpo_pairs(
            errors_df=errors_df,
            all_data=all_data,
            label_columns=["domain"],
            n_synthetic=0,
        )
        assert pairs[0]["chosen"] != pairs[0]["rejected"]
