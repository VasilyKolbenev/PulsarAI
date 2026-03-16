"""Tests for evaluation metrics."""

import pytest

from pulsar_ai.evaluation.metrics import compute_metrics, _build_confusion_matrix


class TestComputeMetrics:
    """Tests for metrics computation."""

    def test_perfect_predictions(self) -> None:
        predictions = [
            {"parsed": {"label": "A"}, "parse_success": True},
            {"parsed": {"label": "B"}, "parse_success": True},
            {"parsed": {"label": "C"}, "parse_success": True},
        ]
        true_labels = [
            {"label": "A"},
            {"label": "B"},
            {"label": "C"},
        ]
        results = compute_metrics(predictions, true_labels, ["label"])
        assert results["overall_accuracy"] == 1.0
        assert results["json_parse_rate"] == 1.0

    def test_all_wrong_predictions(self) -> None:
        predictions = [
            {"parsed": {"label": "X"}, "parse_success": True},
            {"parsed": {"label": "Y"}, "parse_success": True},
        ]
        true_labels = [
            {"label": "A"},
            {"label": "B"},
        ]
        results = compute_metrics(predictions, true_labels, ["label"])
        assert results["overall_accuracy"] == 0.0

    def test_parse_failures(self) -> None:
        predictions = [
            {"parsed": None, "parse_success": False},
            {"parsed": {"label": "A"}, "parse_success": True},
        ]
        true_labels = [
            {"label": "A"},
            {"label": "A"},
        ]
        results = compute_metrics(predictions, true_labels, ["label"])
        assert results["json_parse_rate"] == 0.5
        assert results["overall_accuracy"] == 0.5

    def test_empty_predictions(self) -> None:
        results = compute_metrics([], [], ["label"])
        assert results["total"] == 0
        assert results["overall_accuracy"] == 0.0

    def test_multi_column_accuracy(self) -> None:
        predictions = [
            {"parsed": {"domain": "A", "skill": "X"}, "parse_success": True},
            {"parsed": {"domain": "B", "skill": "Y"}, "parse_success": True},
        ]
        true_labels = [
            {"domain": "A", "skill": "X"},
            {"domain": "B", "skill": "Z"},  # skill mismatch
        ]
        results = compute_metrics(predictions, true_labels, ["domain", "skill"])
        # Only first sample has all columns matching
        assert results["overall_accuracy"] == 0.5
        # But domain accuracy is 100%
        assert results["per_column"]["domain"]["accuracy"] == 1.0


class TestConfusionMatrix:
    """Tests for confusion matrix building."""

    def test_simple_confusion_matrix(self) -> None:
        predictions = [
            {"parsed": {"label": "A"}},
            {"parsed": {"label": "B"}},
            {"parsed": {"label": "A"}},
        ]
        true_labels = [
            {"label": "A"},
            {"label": "B"},
            {"label": "B"},  # misclassified
        ]
        result = _build_confusion_matrix(predictions, true_labels, "label")
        assert "labels" in result
        assert "matrix" in result
        assert "A" in result["labels"]
        assert "B" in result["labels"]

    def test_confusion_matrix_with_parse_errors(self) -> None:
        predictions = [
            {"parsed": None},
            {"parsed": {"label": "A"}},
        ]
        true_labels = [
            {"label": "A"},
            {"label": "A"},
        ]
        result = _build_confusion_matrix(predictions, true_labels, "label")
        assert "PARSE_ERROR" in result["labels"]
