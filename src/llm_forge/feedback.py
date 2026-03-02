"""Human feedback collection for RLHF/DPO.

Collects thumbs up/down, ratings, and preference pairs
from production usage for training data generation.
"""

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class FeedbackEntry:
    """A single piece of human feedback."""

    id: str = ""
    prompt: str = ""
    response: str = ""
    rating: int = 0  # 1-5 or -1/+1 for thumbs
    feedback_type: str = "thumbs"  # thumbs, rating, preference, text
    text_feedback: str = ""
    chosen: str = ""  # For preference pairs
    rejected: str = ""  # For preference pairs
    model: str = ""
    user_id: str = ""
    timestamp: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = time.time()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "id": self.id,
            "prompt": self.prompt,
            "response": self.response,
            "rating": self.rating,
            "feedback_type": self.feedback_type,
            "text_feedback": self.text_feedback,
            "chosen": self.chosen,
            "rejected": self.rejected,
            "model": self.model,
            "user_id": self.user_id,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


class FeedbackCollector:
    """Collects and stores human feedback for model improvement.

    Supports exporting feedback as DPO training pairs.

    Args:
        storage_dir: Directory to persist feedback. None = memory only.
    """

    def __init__(self, storage_dir: str | None = None) -> None:
        self._entries: list[FeedbackEntry] = []
        self._storage_dir = Path(storage_dir) if storage_dir else None
        if self._storage_dir:
            self._storage_dir.mkdir(parents=True, exist_ok=True)

    def record_thumbs(
        self,
        prompt: str,
        response: str,
        is_positive: bool,
        model: str = "",
        user_id: str = "",
        **metadata: Any,
    ) -> FeedbackEntry:
        """Record thumbs up/down feedback.

        Args:
            prompt: The original prompt.
            response: The model response.
            is_positive: True for thumbs up, False for thumbs down.
            model: Model name.
            user_id: User identifier.
            **metadata: Extra metadata.

        Returns:
            The recorded entry.
        """
        entry = FeedbackEntry(
            prompt=prompt,
            response=response,
            rating=1 if is_positive else -1,
            feedback_type="thumbs",
            model=model,
            user_id=user_id,
            metadata=dict(metadata),
        )
        self._entries.append(entry)
        self._persist(entry)
        return entry

    def record_rating(
        self,
        prompt: str,
        response: str,
        rating: int,
        model: str = "",
        user_id: str = "",
        text_feedback: str = "",
        **metadata: Any,
    ) -> FeedbackEntry:
        """Record a numeric rating (1-5).

        Args:
            prompt: The original prompt.
            response: The model response.
            rating: Numeric rating 1-5.
            model: Model name.
            user_id: User identifier.
            text_feedback: Optional text feedback.
            **metadata: Extra metadata.

        Returns:
            The recorded entry.
        """
        entry = FeedbackEntry(
            prompt=prompt,
            response=response,
            rating=max(1, min(5, rating)),
            feedback_type="rating",
            text_feedback=text_feedback,
            model=model,
            user_id=user_id,
            metadata=dict(metadata),
        )
        self._entries.append(entry)
        self._persist(entry)
        return entry

    def record_preference(
        self,
        prompt: str,
        chosen: str,
        rejected: str,
        model: str = "",
        user_id: str = "",
        **metadata: Any,
    ) -> FeedbackEntry:
        """Record a preference pair (chosen vs rejected).

        Args:
            prompt: The original prompt.
            chosen: The preferred response.
            rejected: The non-preferred response.
            model: Model name.
            user_id: User identifier.
            **metadata: Extra metadata.

        Returns:
            The recorded entry.
        """
        entry = FeedbackEntry(
            prompt=prompt,
            chosen=chosen,
            rejected=rejected,
            feedback_type="preference",
            model=model,
            user_id=user_id,
            metadata=dict(metadata),
        )
        self._entries.append(entry)
        self._persist(entry)
        return entry

    def export_dpo_pairs(self, min_rating: int = 0) -> list[dict[str, str]]:
        """Export feedback as DPO training pairs.

        Converts thumbs/ratings to chosen/rejected pairs.
        Positive = chosen template, negative = rejected.

        Args:
            min_rating: Minimum rating to include as "chosen".

        Returns:
            List of DPO pair dicts with prompt, chosen, rejected.
        """
        pairs: list[dict[str, str]] = []

        # Direct preference pairs
        for entry in self._entries:
            if entry.feedback_type == "preference" and entry.chosen and entry.rejected:
                pairs.append({
                    "prompt": entry.prompt,
                    "chosen": entry.chosen,
                    "rejected": entry.rejected,
                })

        # Convert thumbs: pair positive with negative for same prompt
        by_prompt: dict[str, dict[str, list[str]]] = {}
        for entry in self._entries:
            if entry.feedback_type in ("thumbs", "rating"):
                p = entry.prompt
                if p not in by_prompt:
                    by_prompt[p] = {"positive": [], "negative": []}

                is_positive = (
                    entry.rating > min_rating
                    if entry.feedback_type == "rating"
                    else entry.rating > 0
                )

                if is_positive:
                    by_prompt[p]["positive"].append(entry.response)
                else:
                    by_prompt[p]["negative"].append(entry.response)

        for prompt, responses in by_prompt.items():
            for chosen in responses["positive"]:
                for rejected in responses["negative"]:
                    pairs.append({
                        "prompt": prompt,
                        "chosen": chosen,
                        "rejected": rejected,
                    })

        return pairs

    def get_stats(self) -> dict[str, Any]:
        """Get feedback collection statistics."""
        by_type: dict[str, int] = {}
        by_rating: dict[int, int] = {}

        for entry in self._entries:
            by_type[entry.feedback_type] = by_type.get(entry.feedback_type, 0) + 1
            by_rating[entry.rating] = by_rating.get(entry.rating, 0) + 1

        positive = sum(1 for e in self._entries if e.rating > 0)
        total = len(self._entries) or 1

        return {
            "total_entries": len(self._entries),
            "by_type": by_type,
            "by_rating": by_rating,
            "positive_ratio": round(positive / total, 4),
            "dpo_pairs_available": len(self.export_dpo_pairs()),
        }

    def _persist(self, entry: FeedbackEntry) -> None:
        """Write entry to storage if configured."""
        if not self._storage_dir:
            return
        filepath = self._storage_dir / "feedback.jsonl"
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")
