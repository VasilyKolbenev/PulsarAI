"""Tests for llm_forge.evaluation.llm_judge module.

Tests LLMJudge: build_prompt, parse_scores, compute_overall,
evaluate end-to-end, build_comparison_prompt, and default criteria.
"""

import pytest

from llm_forge.evaluation.llm_judge import (
    DEFAULT_CRITERIA,
    JudgeCriterion,
    JudgeResult,
    JudgeScore,
    LLMJudge,
)


@pytest.fixture
def judge() -> LLMJudge:
    """Create a judge with default criteria."""
    return LLMJudge()


@pytest.fixture
def custom_judge() -> LLMJudge:
    """Create a judge with custom weighted criteria."""
    return LLMJudge(
        criteria=[
            JudgeCriterion("relevance", "How relevant is the response?", weight=2.0),
            JudgeCriterion("clarity", "How clear is the response?", weight=1.0),
            JudgeCriterion("depth", "How thorough is the response?", weight=1.0),
        ],
        model="custom-judge",
    )


class TestDefaultCriteria:
    """Tests for default evaluation criteria."""

    def test_default_criteria_count(self) -> None:
        """Default criteria has 4 items."""
        assert len(DEFAULT_CRITERIA) == 4

    def test_default_criteria_names(self) -> None:
        """Default criteria includes helpfulness, accuracy, coherence, safety."""
        names = {c.name for c in DEFAULT_CRITERIA}
        assert names == {"helpfulness", "accuracy", "coherence", "safety"}

    def test_default_criteria_scale(self) -> None:
        """Default criteria use 1-5 scale."""
        for c in DEFAULT_CRITERIA:
            assert c.scale_min == 1
            assert c.scale_max == 5

    def test_judge_uses_default_criteria(self, judge: LLMJudge) -> None:
        """Judge without explicit criteria uses defaults."""
        assert len(judge.criteria) == 4
        names = {c.name for c in judge.criteria}
        assert "helpfulness" in names


class TestBuildPrompt:
    """Tests for build_prompt()."""

    def test_prompt_contains_instruction(self, judge: LLMJudge) -> None:
        """Built prompt contains the original instruction."""
        prompt = judge.build_prompt("Explain quantum computing", "QC is...")
        assert "Explain quantum computing" in prompt

    def test_prompt_contains_response(self, judge: LLMJudge) -> None:
        """Built prompt contains the model response."""
        prompt = judge.build_prompt("Question", "Answer text here")
        assert "Answer text here" in prompt

    def test_prompt_contains_criteria(self, judge: LLMJudge) -> None:
        """Built prompt lists all criteria with descriptions."""
        prompt = judge.build_prompt("Q", "A")
        assert "helpfulness" in prompt
        assert "accuracy" in prompt
        assert "coherence" in prompt
        assert "safety" in prompt

    def test_prompt_contains_format_instructions(self, judge: LLMJudge) -> None:
        """Built prompt contains output format instructions."""
        prompt = judge.build_prompt("Q", "A")
        assert "CRITERION_NAME: SCORE | EXPLANATION" in prompt

    def test_prompt_contains_evaluator_role(self, judge: LLMJudge) -> None:
        """Built prompt begins with evaluator role."""
        prompt = judge.build_prompt("Q", "A")
        assert "expert evaluator" in prompt

    def test_custom_criteria_in_prompt(self, custom_judge: LLMJudge) -> None:
        """Custom criteria appear in the built prompt."""
        prompt = custom_judge.build_prompt("Q", "A")
        assert "relevance" in prompt
        assert "clarity" in prompt
        assert "depth" in prompt

    def test_prompt_scale_range(self, judge: LLMJudge) -> None:
        """Prompt includes the scoring scale range."""
        prompt = judge.build_prompt("Q", "A")
        assert "(1-5)" in prompt


class TestParseScores:
    """Tests for parse_scores()."""

    def test_parse_valid_output(self, judge: LLMJudge) -> None:
        """Parse well-formatted judge output into scores."""
        output = (
            "helpfulness: 4 | Very helpful response\n"
            "accuracy: 5 | Factually correct\n"
            "coherence: 3 | Could be more structured\n"
            "safety: 5 | No issues\n"
        )
        scores = judge.parse_scores(output)
        assert len(scores) == 4
        score_map = {s.criterion: s for s in scores}
        assert score_map["helpfulness"].score == 4
        assert score_map["accuracy"].score == 5
        assert score_map["coherence"].score == 3
        assert score_map["safety"].score == 5
        assert "Very helpful" in score_map["helpfulness"].explanation

    def test_parse_scores_without_explanation(self, judge: LLMJudge) -> None:
        """Scores without explanation (no pipe separator) are parsed."""
        output = "helpfulness: 4\naccuracy: 3\n"
        scores = judge.parse_scores(output)
        assert len(scores) == 2
        score_map = {s.criterion: s for s in scores}
        assert score_map["helpfulness"].score == 4
        assert score_map["helpfulness"].explanation == ""

    def test_parse_scores_malformed_output(self, judge: LLMJudge) -> None:
        """Malformed output returns empty or partial scores."""
        output = "This is not in the expected format at all."
        scores = judge.parse_scores(output)
        assert len(scores) == 0

    def test_parse_scores_partial_output(self, judge: LLMJudge) -> None:
        """Partially formatted output extracts what it can."""
        output = (
            "helpfulness: 4 | Good\n"
            "some garbage line\n"
            "accuracy: five | word instead of number\n"
            "coherence: 3 | OK\n"
        )
        scores = judge.parse_scores(output)
        # 'accuracy' has non-numeric score so it's skipped
        assert len(scores) == 2
        criteria = {s.criterion for s in scores}
        assert "helpfulness" in criteria
        assert "coherence" in criteria

    def test_parse_scores_clamps_to_scale(self, judge: LLMJudge) -> None:
        """Scores outside the scale range are clamped."""
        output = "helpfulness: 10 | Way too high\n"
        scores = judge.parse_scores(output)
        assert len(scores) == 1
        assert scores[0].score == 5  # clamped to scale_max

    def test_parse_scores_clamps_below_min(self, judge: LLMJudge) -> None:
        """Scores below scale_min are clamped up."""
        output = "helpfulness: 0 | Too low\n"
        scores = judge.parse_scores(output)
        assert len(scores) == 1
        assert scores[0].score == 1  # clamped to scale_min

    def test_parse_unknown_criterion_ignored(self, judge: LLMJudge) -> None:
        """Unknown criterion names are silently ignored."""
        output = (
            "helpfulness: 4 | OK\n"
            "unknown_criterion: 5 | Should be ignored\n"
        )
        scores = judge.parse_scores(output)
        assert len(scores) == 1
        assert scores[0].criterion == "helpfulness"

    def test_parse_scores_case_insensitive(self, judge: LLMJudge) -> None:
        """Criterion names are matched case-insensitively."""
        output = "Helpfulness: 4 | Good\nACCURACY: 5 | Great\n"
        scores = judge.parse_scores(output)
        assert len(scores) == 2

    def test_parse_scores_strips_bold_markers(self, judge: LLMJudge) -> None:
        """Bold markers (**) around criterion names are stripped."""
        output = "**helpfulness**: 4 | Good\n"
        scores = judge.parse_scores(output)
        assert len(scores) == 1
        assert scores[0].criterion == "helpfulness"


class TestComputeOverall:
    """Tests for compute_overall() weighted average."""

    def test_uniform_weights(self, judge: LLMJudge) -> None:
        """Uniform weights produce simple average."""
        scores = [
            JudgeScore(criterion="helpfulness", score=4),
            JudgeScore(criterion="accuracy", score=5),
            JudgeScore(criterion="coherence", score=3),
            JudgeScore(criterion="safety", score=4),
        ]
        overall = judge.compute_overall(scores)
        assert overall == pytest.approx(4.0)

    def test_weighted_average(self, custom_judge: LLMJudge) -> None:
        """Weighted criteria produce correct weighted average."""
        # relevance=2.0, clarity=1.0, depth=1.0
        scores = [
            JudgeScore(criterion="relevance", score=5),  # weight 2
            JudgeScore(criterion="clarity", score=3),     # weight 1
            JudgeScore(criterion="depth", score=3),       # weight 1
        ]
        overall = custom_judge.compute_overall(scores)
        expected = (5 * 2 + 3 * 1 + 3 * 1) / (2 + 1 + 1)
        assert overall == pytest.approx(expected, abs=0.01)

    def test_empty_scores(self, judge: LLMJudge) -> None:
        """Empty scores list returns 0.0."""
        assert judge.compute_overall([]) == 0.0

    def test_single_score(self, judge: LLMJudge) -> None:
        """Single score returns that score as overall."""
        scores = [JudgeScore(criterion="helpfulness", score=4)]
        overall = judge.compute_overall(scores)
        assert overall == pytest.approx(4.0)


class TestEvaluate:
    """Tests for evaluate() end-to-end."""

    def test_evaluate_returns_judge_result(self, judge: LLMJudge) -> None:
        """evaluate() returns a JudgeResult with scores and overall."""
        judge_output = (
            "helpfulness: 4 | Helpful\n"
            "accuracy: 5 | Accurate\n"
            "coherence: 4 | Well-structured\n"
            "safety: 5 | Safe\n"
        )
        result = judge.evaluate(
            instruction="What is AI?",
            response="AI is...",
            judge_output=judge_output,
            sample_id="s1",
        )
        assert isinstance(result, JudgeResult)
        assert result.sample_id == "s1"
        assert len(result.scores) == 4
        assert result.overall_score > 0

    def test_evaluate_metadata(self, judge: LLMJudge) -> None:
        """evaluate() stores model and instruction in metadata."""
        result = judge.evaluate(
            instruction="Q", response="A",
            judge_output="helpfulness: 3 | OK\n",
        )
        assert result.metadata["model"] == "judge"
        assert result.metadata["instruction"] == "Q"

    def test_evaluate_to_dict(self, judge: LLMJudge) -> None:
        """JudgeResult.to_dict() contains all expected fields."""
        result = judge.evaluate(
            instruction="Q", response="A",
            judge_output="helpfulness: 4 | Good\n",
            sample_id="s1",
        )
        d = result.to_dict()
        assert d["sample_id"] == "s1"
        assert "scores" in d
        assert "overall_score" in d
        assert "metadata" in d

    def test_evaluate_with_malformed_output(self, judge: LLMJudge) -> None:
        """evaluate() with malformed output returns zero overall."""
        result = judge.evaluate(
            instruction="Q", response="A",
            judge_output="totally invalid output",
        )
        assert result.overall_score == 0.0
        assert len(result.scores) == 0


class TestBuildComparisonPrompt:
    """Tests for build_comparison_prompt()."""

    def test_comparison_contains_both_responses(self, judge: LLMJudge) -> None:
        """Comparison prompt contains both Response A and Response B."""
        prompt = judge.build_comparison_prompt(
            instruction="What is AI?",
            response_a="AI is artificial intelligence.",
            response_b="AI stands for Artificial Intelligence.",
        )
        assert "Response A" in prompt
        assert "Response B" in prompt
        assert "AI is artificial intelligence." in prompt
        assert "AI stands for Artificial Intelligence." in prompt

    def test_comparison_contains_instruction(self, judge: LLMJudge) -> None:
        """Comparison prompt contains the original instruction."""
        prompt = judge.build_comparison_prompt("Q", "A1", "A2")
        assert "Q" in prompt

    def test_comparison_contains_criteria(self, judge: LLMJudge) -> None:
        """Comparison prompt lists evaluation criteria."""
        prompt = judge.build_comparison_prompt("Q", "A1", "A2")
        assert "helpfulness" in prompt
        assert "accuracy" in prompt

    def test_comparison_format_instructions(self, judge: LLMJudge) -> None:
        """Comparison prompt includes expected output format."""
        prompt = judge.build_comparison_prompt("Q", "A1", "A2")
        assert "OVERALL: A|B" in prompt

    def test_comparison_evaluator_role(self, judge: LLMJudge) -> None:
        """Comparison prompt starts with evaluator role."""
        prompt = judge.build_comparison_prompt("Q", "A1", "A2")
        assert "expert evaluator" in prompt


class TestJudgeScoreDataclass:
    """Tests for JudgeScore and JudgeCriterion dataclasses."""

    def test_judge_score_defaults(self) -> None:
        """JudgeScore has sensible defaults."""
        score = JudgeScore(criterion="test", score=3)
        assert score.explanation == ""
        assert score.confidence == 1.0

    def test_judge_criterion_defaults(self) -> None:
        """JudgeCriterion has sensible defaults."""
        criterion = JudgeCriterion("name", "description")
        assert criterion.weight == 1.0
        assert criterion.scale_min == 1
        assert criterion.scale_max == 5
