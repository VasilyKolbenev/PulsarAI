"""Dataset loading from various formats."""

import logging
from pathlib import Path
from typing import Optional

import pandas as pd
from datasets import Dataset

logger = logging.getLogger(__name__)


def load_dataset_from_config(config: dict) -> pd.DataFrame:
    """Load dataset based on config.dataset settings.

    Supports formats: csv, jsonl, parquet, excel.
    Also supports HuggingFace Hub datasets via dataset.source: huggingface.

    Args:
        config: Full config dict with 'dataset' section.

    Returns:
        Pandas DataFrame with loaded data.

    Raises:
        ValueError: If format is not supported or path is missing.
    """
    ds_config = config.get("dataset", {})

    # HuggingFace Hub datasets
    source = ds_config.get("source", "local")
    if source == "huggingface":
        return _load_from_huggingface(ds_config)

    path = ds_config.get("path")
    if not path:
        raise ValueError("dataset.path is required in config")

    fmt = ds_config.get("format", _detect_format(path))
    logger.info("Loading dataset from %s (format=%s)", path, fmt)

    if fmt == "csv":
        df = pd.read_csv(path)
    elif fmt == "jsonl":
        df = pd.read_json(path, lines=True)
    elif fmt == "parquet":
        df = pd.read_parquet(path)
    elif fmt in ("excel", "xlsx"):
        df = pd.read_excel(path)
    else:
        raise ValueError(f"Unsupported dataset format: {fmt}")

    # Basic cleaning
    df = df.dropna(subset=[ds_config.get("text_column", "text")])
    df = df.drop_duplicates()
    df = df.reset_index(drop=True)

    logger.info("Loaded %d samples", len(df))
    return df


def _detect_format(path: str) -> str:
    """Auto-detect file format from extension.

    Args:
        path: File path.

    Returns:
        Format string.
    """
    suffix = Path(path).suffix.lower()
    format_map = {
        ".csv": "csv",
        ".jsonl": "jsonl",
        ".json": "jsonl",
        ".parquet": "parquet",
        ".xlsx": "excel",
        ".xls": "excel",
    }
    if suffix not in format_map:
        raise ValueError(
            f"Cannot detect format for '{suffix}'. "
            f"Supported: {list(format_map.keys())}"
        )
    return format_map[suffix]


def _load_from_huggingface(ds_config: dict) -> pd.DataFrame:
    """Load dataset from HuggingFace Hub.

    Config keys:
        hub_name: Dataset name on HuggingFace (e.g., "squad", "imdb").
        hub_split: Split to load (default: "train").
        hub_subset: Optional dataset subset/config name.
        hub_columns: Optional list of columns to keep.
        text_column: Column name to use as text (for cleaning).

    Args:
        ds_config: Dataset config section.

    Returns:
        Pandas DataFrame.
    """
    from datasets import load_dataset

    hub_name = ds_config.get("hub_name")
    if not hub_name:
        raise ValueError("dataset.hub_name is required when source=huggingface")

    split = ds_config.get("hub_split", "train")
    subset = ds_config.get("hub_subset")

    logger.info("Loading from HuggingFace Hub: %s (split=%s)", hub_name, split)

    kwargs: dict = {"split": split}
    if subset:
        kwargs["name"] = subset

    hf_dataset = load_dataset(hub_name, **kwargs)
    df = hf_dataset.to_pandas()

    # Keep only specified columns if provided
    columns = ds_config.get("hub_columns")
    if columns:
        available = [c for c in columns if c in df.columns]
        df = df[available]

    # Basic cleaning
    text_col = ds_config.get("text_column", "text")
    if text_col in df.columns:
        df = df.dropna(subset=[text_col])
    df = df.drop_duplicates()
    df = df.reset_index(drop=True)

    logger.info("Loaded %d samples from HuggingFace Hub: %s", len(df), hub_name)
    return df


def dataframe_to_hf_dataset(
    df: pd.DataFrame,
    text_field: str = "text",
) -> Dataset:
    """Convert a DataFrame to HuggingFace Dataset.

    Args:
        df: Source DataFrame.
        text_field: Name of the text field in the resulting dataset.

    Returns:
        HuggingFace Dataset.
    """
    return Dataset.from_pandas(df, preserve_index=False)
