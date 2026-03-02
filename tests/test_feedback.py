"""Tests for llm_forge.feedback module.

Tests FeedbackCollector recording thumbs/rating/preference,
DPO pair export, get_stats(), and persistence to storage_dir.
"""

import json
from pathlib import Path

import pytest

from llm_forge.feedback import FeedbackCollector, FeedbackEntry


@pytest.fixture
def collector() -> FeedbackCollector:
    """Create an in-memory FeedbackCollector."""
    return FeedbackCollector()


@pytest.fixture
def persistent_collector(tmp_path: Path) -> FeedbackCollector:
    """Create a FeedbackCollector with file persistence."""
    return FeedbackCollector(storage_dir=str(tmp_path / "feedback"))


class TestFeedbackEntry:
    """Tests for FeedbackEntry dataclass."""

    def test_entry_auto_generates_id(self) -> None:
        """FeedbackEntry generates a UUID id."""
        entry = FeedbackEntry(prompt="p", response="r")
        assert len(entry.id) > 0

    def test_entry_auto_sets_timestamp(self) -> None:
        """FeedbackEntry sets timestamp on creation."""
        entry = FeedbackEntry()
        assert entry.timestamp > 0

    def test_entry_to_dict(self) -> None:
        """to_dict contains all fields."""
        entry = FeedbackEntry(prompt="p", response="r", rating=5)
        d = entry.to_dict()
        assert d["prompt"] == "p"
        assert d["response"] == "r"
        assert d["rating"] == 5
        assert "id" in d
        assert "timestamp" in d


class TestRecordThumbs:
    """Tests for recording thumbs up/down feedback."""

    def test_record_thumbs_positive(self, collector: FeedbackCollector) -> None:
        """Positive thumbs records rating=1."""
        entry = collector.record_thumbs("prompt", "good response", is_positive=True)
        assert entry.feedback_type == "thumbs"
        assert entry.rating == 1

    def test_record_thumbs_negative(self, collector: FeedbackCollector) -> None:
        """Negative thumbs records rating=-1."""
        entry = collector.record_thumbs("prompt", "bad response", is_positive=False)
        assert entry.feedback_type == "thumbs"
        assert entry.rating == -1

    def test_record_thumbs_with_model_and_user(
        self, collector: FeedbackCollector,
    ) -> None:
        """Thumbs record stores model and user_id."""
        entry = collector.record_thumbs(
            "p", "r", is_positive=True, model="gpt-4o", user_id="u1",
        )
        assert entry.model == "gpt-4o"
        assert entry.user_id == "u1"

    def test_record_thumbs_with_metadata(
        self, collector: FeedbackCollector,
    ) -> None:
        """Extra kwargs are stored as metadata."""
        entry = collector.record_thumbs(
            "p", "r", is_positive=True, session="s1",
        )
        assert entry.metadata["session"] == "s1"


class TestRecordRating:
    """Tests for recording numeric ratings."""

    def test_record_rating_in_range(self, collector: FeedbackCollector) -> None:
        """Rating within 1-5 is stored as-is."""
        entry = collector.record_rating("p", "r", rating=4)
        assert entry.rating == 4
        assert entry.feedback_type == "rating"

    def test_record_rating_clamped_low(self, collector: FeedbackCollector) -> None:
        """Rating below 1 is clamped to 1."""
        entry = collector.record_rating("p", "r", rating=-5)
        assert entry.rating == 1

    def test_record_rating_clamped_high(self, collector: FeedbackCollector) -> None:
        """Rating above 5 is clamped to 5."""
        entry = collector.record_rating("p", "r", rating=100)
        assert entry.rating == 5

    def test_record_rating_with_text_feedback(
        self, collector: FeedbackCollector,
    ) -> None:
        """Text feedback is stored alongside the rating."""
        entry = collector.record_rating("p", "r", rating=3, text_feedback="okay")
        assert entry.text_feedback == "okay"


class TestRecordPreference:
    """Tests for recording preference pairs."""

    def test_record_preference(self, collector: FeedbackCollector) -> None:
        """Preference records chosen and rejected."""
        entry = collector.record_preference("p", chosen="best", rejected="worst")
        assert entry.feedback_type == "preference"
        assert entry.chosen == "best"
        assert entry.rejected == "worst"

    def test_record_preference_with_model(
        self, collector: FeedbackCollector,
    ) -> None:
        """Preference records model name."""
        entry = collector.record_preference(
            "p", chosen="a", rejected="b", model="gpt-4o",
        )
        assert entry.model == "gpt-4o"


class TestExportDPOPairs:
    """Tests for export_dpo_pairs()."""

    def test_export_from_preferences(self, collector: FeedbackCollector) -> None:
        """Preference entries are exported directly as DPO pairs."""
        collector.record_preference("p1", chosen="good", rejected="bad")
        collector.record_preference("p2", chosen="great", rejected="poor")
        pairs = collector.export_dpo_pairs()
        assert len(pairs) >= 2
        prompts = {p["prompt"] for p in pairs}
        assert "p1" in prompts
        assert "p2" in prompts

    def test_export_from_thumbs_cross_join(
        self, collector: FeedbackCollector,
    ) -> None:
        """Thumbs are cross-joined into chosen/rejected pairs for same prompt."""
        collector.record_thumbs("p", "good_a", is_positive=True)
        collector.record_thumbs("p", "good_b", is_positive=True)
        collector.record_thumbs("p", "bad_a", is_positive=False)
        pairs = collector.export_dpo_pairs()
        # 2 positive x 1 negative = 2 pairs
        thumbs_pairs = [p for p in pairs if p["prompt"] == "p"]
        assert len(thumbs_pairs) == 2
        chosen_set = {p["chosen"] for p in thumbs_pairs}
        assert chosen_set == {"good_a", "good_b"}
        rejected_set = {p["rejected"] for p in thumbs_pairs}
        assert rejected_set == {"bad_a"}

    def test_export_empty(self, collector: FeedbackCollector) -> None:
        """Empty collector exports no pairs."""
        assert collector.export_dpo_pairs() == []

    def test_export_thumbs_only_positive_no_pairs(
        self, collector: FeedbackCollector,
    ) -> None:
        """Only positive thumbs (no negatives) produce no DPO pairs."""
        collector.record_thumbs("p", "good", is_positive=True)
        pairs = collector.export_dpo_pairs()
        # No negative responses means no cross-join pairs
        thumbs_pairs = [p for p in pairs if p["prompt"] == "p"]
        assert len(thumbs_pairs) == 0

    def test_export_mixed_types(self, collector: FeedbackCollector) -> None:
        """Both preference and thumbs pairs are included in export."""
        collector.record_preference("p1", chosen="a", rejected="b")
        collector.record_thumbs("p2", "good", is_positive=True)
        collector.record_thumbs("p2", "bad", is_positive=False)
        pairs = collector.export_dpo_pairs()
        prompts = [p["prompt"] for p in pairs]
        assert "p1" in prompts
        assert "p2" in prompts


class TestGetStats:
    """Tests for get_stats()."""

    def test_stats_total_entries(self, collector: FeedbackCollector) -> None:
        """Stats show correct total_entries count."""
        collector.record_thumbs("p", "r", is_positive=True)
        collector.record_rating("p", "r", rating=4)
        collector.record_preference("p", "a", "b")
        stats = collector.get_stats()
        assert stats["total_entries"] == 3

    def test_stats_by_type(self, collector: FeedbackCollector) -> None:
        """Stats break down entries by feedback_type."""
        collector.record_thumbs("p", "r", is_positive=True)
        collector.record_thumbs("p", "r", is_positive=False)
        collector.record_rating("p", "r", rating=5)
        stats = collector.get_stats()
        assert stats["by_type"]["thumbs"] == 2
        assert stats["by_type"]["rating"] == 1

    def test_stats_positive_ratio(self, collector: FeedbackCollector) -> None:
        """Stats compute positive_ratio correctly."""
        collector.record_thumbs("p", "r", is_positive=True)
        collector.record_thumbs("p", "r", is_positive=True)
        collector.record_thumbs("p", "r", is_positive=False)
        stats = collector.get_stats()
        assert stats["positive_ratio"] == pytest.approx(2 / 3, abs=0.01)

    def test_stats_dpo_pairs_count(self, collector: FeedbackCollector) -> None:
        """Stats include dpo_pairs_available count."""
        collector.record_preference("p", "a", "b")
        stats = collector.get_stats()
        assert stats["dpo_pairs_available"] >= 1


class TestPersistence:
    """Tests for persistence to storage_dir."""

    def test_persist_creates_jsonl_file(
        self, persistent_collector: FeedbackCollector, tmp_path: Path,
    ) -> None:
        """Recording feedback creates a feedback.jsonl file."""
        persistent_collector.record_thumbs("p", "r", is_positive=True)
        filepath = tmp_path / "feedback" / "feedback.jsonl"
        assert filepath.exists()

    def test_persist_appends_entries(
        self, persistent_collector: FeedbackCollector, tmp_path: Path,
    ) -> None:
        """Multiple records append lines to feedback.jsonl."""
        persistent_collector.record_thumbs("p1", "r1", is_positive=True)
        persistent_collector.record_rating("p2", "r2", rating=3)
        persistent_collector.record_preference("p3", "a", "b")
        filepath = tmp_path / "feedback" / "feedback.jsonl"
        lines = filepath.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 3

    def test_persisted_entries_are_valid_json(
        self, persistent_collector: FeedbackCollector, tmp_path: Path,
    ) -> None:
        """Each persisted line is valid JSON."""
        persistent_collector.record_thumbs("p", "r", is_positive=True)
        filepath = tmp_path / "feedback" / "feedback.jsonl"
        for line in filepath.read_text(encoding="utf-8").strip().split("\n"):
            data = json.loads(line)
            assert "id" in data
            assert "prompt" in data

    def test_storage_dir_created_automatically(self, tmp_path: Path) -> None:
        """storage_dir is created if it doesn't exist."""
        dir_path = tmp_path / "deep" / "nested" / "feedback"
        collector = FeedbackCollector(storage_dir=str(dir_path))
        assert dir_path.exists()
