"""Tests for HuggingFace Datasets integration in data loader."""

import pytest
from unittest.mock import patch, MagicMock
import pandas as pd

from pulsar_ai.data.loader import load_dataset_from_config


class TestHuggingFaceLoader:
    """Test HuggingFace Hub dataset loading."""

    @patch("datasets.load_dataset")
    def test_load_from_huggingface(self, mock_load):
        """Test loading dataset from HF Hub."""
        mock_hf_ds = MagicMock()
        mock_hf_ds.to_pandas.return_value = pd.DataFrame(
            {
                "text": ["hello", "world", "test"],
                "label": [0, 1, 0],
            }
        )
        mock_load.return_value = mock_hf_ds

        config = {
            "dataset": {
                "source": "huggingface",
                "hub_name": "imdb",
                "hub_split": "train",
                "text_column": "text",
            }
        }

        df = load_dataset_from_config(config)
        assert len(df) == 3
        mock_load.assert_called_once_with("imdb", split="train")

    @patch("datasets.load_dataset")
    def test_load_with_subset(self, mock_load):
        """Test loading dataset with subset/config name."""
        mock_hf_ds = MagicMock()
        mock_hf_ds.to_pandas.return_value = pd.DataFrame(
            {
                "question": ["what?"],
                "answer": ["this"],
            }
        )
        mock_load.return_value = mock_hf_ds

        config = {
            "dataset": {
                "source": "huggingface",
                "hub_name": "squad",
                "hub_subset": "plain_text",
                "hub_split": "validation",
                "text_column": "question",
            }
        }

        df = load_dataset_from_config(config)
        assert len(df) == 1
        mock_load.assert_called_once_with("squad", split="validation", name="plain_text")

    @patch("datasets.load_dataset")
    def test_load_with_column_filter(self, mock_load):
        """Test keeping only specified columns."""
        mock_hf_ds = MagicMock()
        mock_hf_ds.to_pandas.return_value = pd.DataFrame(
            {
                "text": ["hello"],
                "label": [1],
                "extra_col": ["drop me"],
                "another_col": [42],
            }
        )
        mock_load.return_value = mock_hf_ds

        config = {
            "dataset": {
                "source": "huggingface",
                "hub_name": "test",
                "hub_columns": ["text", "label"],
                "text_column": "text",
            }
        }

        df = load_dataset_from_config(config)
        assert list(df.columns) == ["text", "label"]

    def test_missing_hub_name_raises(self):
        """Test error when hub_name is missing."""
        config = {
            "dataset": {
                "source": "huggingface",
            }
        }

        with pytest.raises(ValueError, match="hub_name"):
            load_dataset_from_config(config)

    @patch("datasets.load_dataset")
    def test_deduplication(self, mock_load):
        """Test that HF datasets get deduplicated."""
        mock_hf_ds = MagicMock()
        mock_hf_ds.to_pandas.return_value = pd.DataFrame(
            {
                "text": ["hello", "hello", "world"],
                "label": [1, 1, 0],
            }
        )
        mock_load.return_value = mock_hf_ds

        config = {
            "dataset": {
                "source": "huggingface",
                "hub_name": "test",
                "text_column": "text",
            }
        }

        df = load_dataset_from_config(config)
        assert len(df) == 2  # "hello" deduplicated

    def test_local_source_default(self, tmp_path):
        """Test that source defaults to local (existing behavior)."""
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("text,label\nhello,pos\nworld,neg\n")

        config = {
            "dataset": {
                "path": str(csv_file),
                "format": "csv",
                "text_column": "text",
            }
        }

        df = load_dataset_from_config(config)
        assert len(df) == 2
