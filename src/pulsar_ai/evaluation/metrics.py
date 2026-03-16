"""Evaluation metrics: accuracy, F1, confusion matrix."""

import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


def compute_metrics(
    predictions: list[dict],
    true_labels: list[dict],
    label_columns: list[str],
) -> dict:
    """Compute evaluation metrics from predictions and ground truth.

    Args:
        predictions: List of prediction dicts with 'parsed' field.
        true_labels: List of dicts with true label values.
        label_columns: List of label column names to evaluate.

    Returns:
        Dict with overall and per-class metrics.
    """
    total = len(predictions)
    if total == 0:
        return {"total": 0, "overall_accuracy": 0.0, "json_parse_rate": 0.0}

    parse_success = sum(1 for p in predictions if p.get("parse_success"))
    json_parse_rate = parse_success / total

    # Per-column accuracy
    column_metrics = {}
    for col in label_columns:
        correct = 0
        evaluated = 0
        per_class: dict[str, dict[str, int]] = defaultdict(lambda: {"correct": 0, "total": 0})

        for pred, true in zip(predictions, true_labels):
            if col not in true:
                continue
            true_val = str(true[col]).strip()
            per_class[true_val]["total"] += 1
            evaluated += 1

            parsed = pred.get("parsed")
            if parsed and col in parsed:
                pred_val = str(parsed[col]).strip()
                if pred_val == true_val:
                    correct += 1
                    per_class[true_val]["correct"] += 1

        accuracy = correct / max(evaluated, 1)
        per_class_acc = {}
        for cls_name, cls_data in per_class.items():
            cls_total = cls_data["total"]
            cls_correct = cls_data["correct"]
            per_class_acc[cls_name] = {
                "accuracy": cls_correct / max(cls_total, 1),
                "correct": cls_correct,
                "count": cls_total,
            }

        column_metrics[col] = {
            "accuracy": accuracy,
            "correct": correct,
            "total": evaluated,
            "per_class": per_class_acc,
        }

    # Confusion matrix for primary column
    primary_col = label_columns[0]
    confusion = _build_confusion_matrix(predictions, true_labels, primary_col)

    # Overall accuracy (all columns must match)
    all_correct = 0
    for pred, true in zip(predictions, true_labels):
        parsed = pred.get("parsed")
        if not parsed:
            continue
        if all(
            str(parsed.get(col, "")).strip() == str(true.get(col, "")).strip()
            for col in label_columns
            if col in true
        ):
            all_correct += 1

    results = {
        "total": total,
        "json_parse_rate": round(json_parse_rate, 4),
        "overall_accuracy": round(all_correct / max(total, 1), 4),
        "per_column": column_metrics,
        "confusion_matrix": confusion,
    }

    logger.info(
        "Metrics: total=%d, parse_rate=%.1f%%, accuracy=%.1f%%",
        total,
        json_parse_rate * 100,
        results["overall_accuracy"] * 100,
    )
    return results


def _build_confusion_matrix(
    predictions: list[dict],
    true_labels: list[dict],
    column: str,
) -> dict:
    """Build confusion matrix for a single label column.

    Args:
        predictions: List of prediction dicts.
        true_labels: List of true label dicts.
        column: Label column name.

    Returns:
        Dict with 'labels' list and 'matrix' (list of lists).
    """
    # Collect all unique labels
    all_labels: set[str] = set()
    pairs: list[tuple[str, str]] = []

    for pred, true in zip(predictions, true_labels):
        if column not in true:
            continue
        true_val = str(true[column]).strip()
        all_labels.add(true_val)

        parsed = pred.get("parsed")
        pred_val = str(parsed.get(column, "PARSE_ERROR")).strip() if parsed else "PARSE_ERROR"
        all_labels.add(pred_val)
        pairs.append((true_val, pred_val))

    labels = sorted(all_labels)
    label_to_idx = {label: idx for idx, label in enumerate(labels)}
    size = len(labels)
    matrix = [[0] * size for _ in range(size)]

    for true_val, pred_val in pairs:
        true_idx = label_to_idx[true_val]
        pred_idx = label_to_idx[pred_val]
        matrix[true_idx][pred_idx] += 1

    return {"labels": labels, "matrix": matrix}


def compute_f1(
    predictions: list[dict],
    true_labels: list[dict],
    column: str,
    average: str = "weighted",
) -> dict:
    """Compute F1 score using sklearn.

    Args:
        predictions: List of prediction dicts.
        true_labels: List of true label dicts.
        column: Label column to compute F1 for.
        average: Averaging strategy ('weighted', 'macro', 'micro').

    Returns:
        Dict with f1, precision, recall.
    """
    try:
        from sklearn.metrics import f1_score, precision_score, recall_score
    except ImportError:
        logger.warning("scikit-learn not installed, skipping F1 computation")
        return {}

    y_true = []
    y_pred = []

    for pred, true in zip(predictions, true_labels):
        if column not in true:
            continue
        true_val = str(true[column]).strip()
        parsed = pred.get("parsed")
        pred_val = str(parsed.get(column, "PARSE_ERROR")).strip() if parsed else "PARSE_ERROR"
        y_true.append(true_val)
        y_pred.append(pred_val)

    if not y_true:
        return {}

    return {
        "f1": round(f1_score(y_true, y_pred, average=average, zero_division=0), 4),
        "precision": round(precision_score(y_true, y_pred, average=average, zero_division=0), 4),
        "recall": round(recall_score(y_true, y_pred, average=average, zero_division=0), 4),
    }
