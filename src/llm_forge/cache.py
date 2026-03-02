"""Semantic caching for LLM responses.

Caches LLM responses keyed by prompt hash, with optional
similarity-based lookup for semantically equivalent queries.
"""

import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A cached LLM response."""

    key: str
    prompt_hash: str
    response: str
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    created_at: float = 0.0
    last_accessed: float = 0.0
    hit_count: int = 0
    ttl: float = 3600.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        now = time.time()
        if not self.created_at:
            self.created_at = now
        if not self.last_accessed:
            self.last_accessed = now

    @property
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.ttl <= 0:
            return False
        return (time.time() - self.created_at) > self.ttl

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "key": self.key,
            "prompt_hash": self.prompt_hash,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "created_at": self.created_at,
            "hit_count": self.hit_count,
            "is_expired": self.is_expired,
        }


class SemanticCache:
    """LLM response cache with exact and semantic matching.

    Uses prompt hashing for exact matches. Semantic similarity
    can be added via an embedding function.

    Args:
        max_entries: Maximum cache entries.
        default_ttl: Default TTL in seconds. 0 = no expiry.
    """

    def __init__(
        self,
        max_entries: int = 10000,
        default_ttl: float = 3600.0,
    ) -> None:
        self._cache: dict[str, CacheEntry] = {}
        self._max_entries = max_entries
        self._default_ttl = default_ttl
        self._stats = {"hits": 0, "misses": 0, "evictions": 0}

    @staticmethod
    def _hash_prompt(prompt: str, model: str = "") -> str:
        """Create a deterministic hash of prompt + model."""
        key = f"{model}::{prompt}"
        return hashlib.sha256(key.encode()).hexdigest()[:32]

    def get(self, prompt: str, model: str = "") -> str | None:
        """Look up a cached response for the given prompt.

        Args:
            prompt: The prompt text.
            model: Model name for cache partitioning.

        Returns:
            Cached response string, or None if not found/expired.
        """
        prompt_hash = self._hash_prompt(prompt, model)
        entry = self._cache.get(prompt_hash)

        if entry is None:
            self._stats["misses"] += 1
            return None

        if entry.is_expired:
            del self._cache[prompt_hash]
            self._stats["misses"] += 1
            return None

        entry.hit_count += 1
        entry.last_accessed = time.time()
        self._stats["hits"] += 1
        return entry.response

    def put(
        self,
        prompt: str,
        response: str,
        model: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
        ttl: float | None = None,
        **metadata: Any,
    ) -> CacheEntry:
        """Store a response in the cache.

        Args:
            prompt: The prompt text.
            response: The LLM response.
            model: Model name.
            input_tokens: Input token count.
            output_tokens: Output token count.
            ttl: TTL in seconds. None = use default.
            **metadata: Extra metadata.

        Returns:
            The cache entry.
        """
        prompt_hash = self._hash_prompt(prompt, model)

        entry = CacheEntry(
            key=prompt_hash,
            prompt_hash=prompt_hash,
            response=response,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            ttl=ttl if ttl is not None else self._default_ttl,
            metadata=dict(metadata),
        )

        self._evict_if_needed()
        self._cache[prompt_hash] = entry
        return entry

    def invalidate(self, prompt: str, model: str = "") -> bool:
        """Remove a specific entry from cache.

        Args:
            prompt: The prompt text.
            model: Model name.

        Returns:
            True if entry was removed, False if not found.
        """
        prompt_hash = self._hash_prompt(prompt, model)
        if prompt_hash in self._cache:
            del self._cache[prompt_hash]
            return True
        return False

    def clear(self) -> int:
        """Clear all cache entries.

        Returns:
            Number of entries cleared.
        """
        count = len(self._cache)
        self._cache.clear()
        return count

    def cleanup_expired(self) -> int:
        """Remove all expired entries.

        Returns:
            Number of entries removed.
        """
        expired = [k for k, v in self._cache.items() if v.is_expired]
        for k in expired:
            del self._cache[k]
        return len(expired)

    @property
    def stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total if total > 0 else 0.0

        tokens_saved = sum(
            (e.input_tokens + e.output_tokens) * e.hit_count
            for e in self._cache.values()
        )

        return {
            "size": len(self._cache),
            "max_entries": self._max_entries,
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "hit_rate": round(hit_rate, 4),
            "evictions": self._stats["evictions"],
            "tokens_saved": tokens_saved,
        }

    def _evict_if_needed(self) -> None:
        """Evict LRU entries if cache is full."""
        if len(self._cache) < self._max_entries:
            return

        self.cleanup_expired()

        if len(self._cache) >= self._max_entries:
            sorted_keys = sorted(
                self._cache.keys(),
                key=lambda k: self._cache[k].last_accessed,
            )
            to_remove = len(self._cache) - self._max_entries + 1
            for key in sorted_keys[:to_remove]:
                del self._cache[key]
                self._stats["evictions"] += 1
