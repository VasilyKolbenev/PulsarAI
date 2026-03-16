"""Tests for pipeline conditional execution and new step types."""

import pytest
from unittest.mock import patch, MagicMock

from pulsar_ai.pipeline.steps import check_condition, dispatch_step
from pulsar_ai.pipeline.executor import PipelineExecutor
from pulsar_ai.pipeline.tracker import PipelineTracker


class TestCheckCondition:
    """Test conditional step evaluation."""

    def test_gte_true(self):
        outputs = {"eval": {"accuracy": 0.9}}
        condition = {
            "metric": "${eval.accuracy}",
            "operator": "gte",
            "value": 0.85,
        }
        assert check_condition(condition, outputs) is True

    def test_gte_false(self):
        outputs = {"eval": {"accuracy": 0.7}}
        condition = {
            "metric": "${eval.accuracy}",
            "operator": "gte",
            "value": 0.85,
        }
        assert check_condition(condition, outputs) is False

    def test_lt(self):
        outputs = {"train": {"loss": 0.1}}
        condition = {
            "metric": "${train.loss}",
            "operator": "lt",
            "value": 0.5,
        }
        assert check_condition(condition, outputs) is True

    def test_eq(self):
        outputs = {"check": {"status_code": 200}}
        condition = {
            "metric": "${check.status_code}",
            "operator": "eq",
            "value": 200,
        }
        assert check_condition(condition, outputs) is True

    def test_neq(self):
        outputs = {"check": {"status_code": 500}}
        condition = {
            "metric": "${check.status_code}",
            "operator": "neq",
            "value": 200,
        }
        assert check_condition(condition, outputs) is True

    def test_gt(self):
        outputs = {"eval": {"f1": 0.92}}
        condition = {"metric": "${eval.f1}", "operator": "gt", "value": 0.9}
        assert check_condition(condition, outputs) is True

    def test_lte(self):
        outputs = {"train": {"loss": 0.5}}
        condition = {"metric": "${train.loss}", "operator": "lte", "value": 0.5}
        assert check_condition(condition, outputs) is True

    def test_missing_step(self):
        outputs = {}
        condition = {"metric": "${missing.key}", "operator": "gte", "value": 0}
        assert check_condition(condition, outputs) is False

    def test_missing_key(self):
        outputs = {"eval": {"accuracy": 0.9}}
        condition = {"metric": "${eval.missing}", "operator": "gte", "value": 0}
        assert check_condition(condition, outputs) is False

    def test_invalid_metric_ref(self):
        outputs = {"eval": {"accuracy": 0.9}}
        condition = {"metric": "not_a_ref", "operator": "gte", "value": 0}
        assert check_condition(condition, outputs) is False

    def test_unknown_operator(self):
        outputs = {"eval": {"accuracy": 0.9}}
        condition = {"metric": "${eval.accuracy}", "operator": "xor", "value": 0}
        assert check_condition(condition, outputs) is False


class TestConditionalPipeline:
    """Test pipeline executor with conditional steps."""

    @patch("pulsar_ai.pipeline.executor.dispatch_step")
    def test_skip_conditional_step(self, mock_dispatch, tmp_path):
        """Step with unmet condition should be skipped."""
        config = {
            "pipeline": {"name": "conditional"},
            "steps": [
                {
                    "name": "train",
                    "type": "training",
                    "config": {"task": "sft"},
                },
                {
                    "name": "eval",
                    "type": "evaluation",
                    "depends_on": ["train"],
                    "config": {"model_path": "${train.adapter_dir}"},
                },
                {
                    "name": "dpo",
                    "type": "training",
                    "depends_on": ["eval"],
                    "condition": {
                        "metric": "${eval.accuracy}",
                        "operator": "lt",
                        "value": 0.95,
                    },
                    "config": {"task": "dpo"},
                },
            ],
        }

        mock_dispatch.side_effect = [
            {"adapter_dir": "/lora", "training_loss": 0.1},
            {"accuracy": 0.98},  # Above threshold → DPO should be skipped
        ]

        tracker = PipelineTracker("cond-test", runs_dir=tmp_path)
        executor = PipelineExecutor(config, tracker=tracker)
        outputs = executor.run()

        assert outputs["dpo"]["_skipped"] is True
        assert mock_dispatch.call_count == 2  # train + eval, not dpo

    @patch("pulsar_ai.pipeline.executor.dispatch_step")
    def test_run_conditional_step(self, mock_dispatch, tmp_path):
        """Step with met condition should run."""
        config = {
            "pipeline": {"name": "conditional2"},
            "steps": [
                {
                    "name": "eval",
                    "type": "evaluation",
                    "config": {},
                },
                {
                    "name": "retrain",
                    "type": "training",
                    "depends_on": ["eval"],
                    "condition": {
                        "metric": "${eval.accuracy}",
                        "operator": "lt",
                        "value": 0.9,
                    },
                    "config": {"task": "sft"},
                },
            ],
        }

        mock_dispatch.side_effect = [
            {"accuracy": 0.75},  # Below 0.9 → retrain runs
            {"training_loss": 0.05},
        ]

        tracker = PipelineTracker("cond-test2", runs_dir=tmp_path)
        executor = PipelineExecutor(config, tracker=tracker)
        outputs = executor.run()

        assert "_skipped" not in outputs.get("retrain", {})
        assert mock_dispatch.call_count == 2  # eval + retrain


class TestNewStepTypes:
    """Test new pipeline step types."""

    @patch("pulsar_ai.registry.ModelRegistry")
    def test_register_step(self, MockRegistry):
        mock_reg = MagicMock()
        mock_reg.register.return_value = {"id": "test-v1", "model_path": "/test"}
        MockRegistry.return_value = mock_reg

        result = dispatch_step(
            "register",
            {
                "name": "test",
                "model_path": "/test",
                "task": "sft",
                "model": {"name": "qwen"},
            },
        )
        assert result["model_id"] == "test-v1"

    def test_fingerprint_step(self, tmp_path):
        data_file = tmp_path / "data.csv"
        data_file.write_text("text,label\nhello,pos\n")

        result = dispatch_step(
            "fingerprint",
            {
                "dataset": {"path": str(data_file)},
            },
        )
        assert len(result["fingerprint"]) == 64

    def test_fingerprint_step_no_path(self):
        result = dispatch_step("fingerprint", {"dataset": {}})
        assert result["fingerprint"] == ""

    def test_unknown_step_raises(self):
        with pytest.raises(ValueError, match="Unknown step type"):
            dispatch_step("nonexistent", {})
