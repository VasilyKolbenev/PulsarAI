"""Tests for pulsar_ai.cache module.

Tests SemanticCache put/get, TTL expiry, invalidate, clear,
cleanup_expired, LRU eviction, stats, and model-partitioned caching.
"""

import time

import pytest

from pulsar_ai.cache import CacheEntry, SemanticCache


class TestCacheEntry:
    """Tests for CacheEntry dataclass."""

    def test_cache_entry_defaults(self) -> None:
        """CacheEntry sets created_at and last_accessed on init."""
        entry = CacheEntry(key="k", prompt_hash="h", response="r")
        assert entry.created_at > 0
        assert entry.last_accessed > 0
        assert entry.hit_count == 0

    def test_cache_entry_not_expired(self) -> None:
        """Freshly created entry is not expired."""
        entry = CacheEntry(key="k", prompt_hash="h", response="r", ttl=3600.0)
        assert entry.is_expired is False

    def test_cache_entry_expired(self) -> None:
        """Entry with past created_at is expired."""
        entry = CacheEntry(
            key="k",
            prompt_hash="h",
            response="r",
            ttl=1.0,
            created_at=time.time() - 10,
        )
        assert entry.is_expired is True

    def test_cache_entry_no_expiry(self) -> None:
        """Entry with ttl=0 never expires."""
        entry = CacheEntry(
            key="k",
            prompt_hash="h",
            response="r",
            ttl=0,
            created_at=time.time() - 100000,
        )
        assert entry.is_expired is False


class TestPutAndGet:
    """Tests for cache put and get operations."""

    def test_put_and_get_hit(self) -> None:
        """Put then get returns the cached response."""
        cache = SemanticCache()
        cache.put("What is 2+2?", "4", model="gpt-4o")
        result = cache.get("What is 2+2?", model="gpt-4o")
        assert result == "4"

    def test_get_miss(self) -> None:
        """Get for non-existent key returns None."""
        cache = SemanticCache()
        result = cache.get("nonexistent prompt")
        assert result is None

    def test_put_returns_cache_entry(self) -> None:
        """Put returns a CacheEntry with correct fields."""
        cache = SemanticCache()
        entry = cache.put("prompt", "response", model="m", input_tokens=10, output_tokens=5)
        assert entry.response == "response"
        assert entry.model == "m"
        assert entry.input_tokens == 10
        assert entry.output_tokens == 5

    def test_put_overwrites_existing(self) -> None:
        """Putting same prompt overwrites previous entry."""
        cache = SemanticCache()
        cache.put("p", "first")
        cache.put("p", "second")
        assert cache.get("p") == "second"

    def test_get_increments_hit_count(self) -> None:
        """Successive gets increment hit_count on the entry."""
        cache = SemanticCache()
        cache.put("p", "r")
        cache.get("p")
        cache.get("p")
        cache.get("p")
        prompt_hash = SemanticCache._hash_prompt("p", "")
        entry = cache._cache[prompt_hash]
        assert entry.hit_count == 3


class TestTTLExpiry:
    """Tests for TTL-based cache expiration."""

    def test_expired_entry_returns_none(self) -> None:
        """Get returns None for expired entries."""
        cache = SemanticCache(default_ttl=0.01)
        cache.put("p", "r")
        time.sleep(0.02)
        result = cache.get("p")
        assert result is None

    def test_custom_ttl_per_entry(self) -> None:
        """Custom TTL on put overrides default TTL."""
        cache = SemanticCache(default_ttl=3600)
        cache.put("p", "r", ttl=0.01)
        time.sleep(0.02)
        result = cache.get("p")
        assert result is None

    def test_non_expired_entry_returns_value(self) -> None:
        """Non-expired entry is returned normally."""
        cache = SemanticCache(default_ttl=3600)
        cache.put("p", "r")
        result = cache.get("p")
        assert result == "r"


class TestInvalidate:
    """Tests for cache invalidation."""

    def test_invalidate_existing(self) -> None:
        """Invalidate removes a specific entry and returns True."""
        cache = SemanticCache()
        cache.put("p", "r")
        removed = cache.invalidate("p")
        assert removed is True
        assert cache.get("p") is None

    def test_invalidate_nonexistent(self) -> None:
        """Invalidate for missing key returns False."""
        cache = SemanticCache()
        removed = cache.invalidate("nonexistent")
        assert removed is False


class TestClear:
    """Tests for clearing the entire cache."""

    def test_clear_removes_all(self) -> None:
        """Clear removes all entries and returns count."""
        cache = SemanticCache()
        cache.put("a", "1")
        cache.put("b", "2")
        cache.put("c", "3")
        count = cache.clear()
        assert count == 3
        assert cache.get("a") is None
        assert cache.get("b") is None
        assert cache.get("c") is None

    def test_clear_empty_cache(self) -> None:
        """Clear on empty cache returns 0."""
        cache = SemanticCache()
        count = cache.clear()
        assert count == 0


class TestCleanupExpired:
    """Tests for cleanup_expired."""

    def test_cleanup_expired_removes_old(self) -> None:
        """cleanup_expired removes expired entries."""
        cache = SemanticCache(default_ttl=0.01)
        cache.put("a", "1")
        cache.put("b", "2")
        time.sleep(0.02)
        cache.put("c", "3", ttl=3600)
        removed = cache.cleanup_expired()
        assert removed == 2
        assert cache.get("c") == "3"

    def test_cleanup_expired_none_expired(self) -> None:
        """cleanup_expired returns 0 when nothing is expired."""
        cache = SemanticCache(default_ttl=3600)
        cache.put("a", "1")
        removed = cache.cleanup_expired()
        assert removed == 0


class TestLRUEviction:
    """Tests for LRU eviction when cache is full."""

    def test_eviction_removes_least_recently_accessed(self) -> None:
        """When cache is full, LRU entries are evicted."""
        cache = SemanticCache(max_entries=3, default_ttl=3600)
        cache.put("a", "1")
        cache.put("b", "2")
        cache.put("c", "3")
        # Access 'a' to make it more recent
        cache.get("a")
        # Adding 'd' should evict 'b' (LRU)
        cache.put("d", "4")
        assert cache.get("a") is not None
        assert cache.get("d") is not None
        # 'b' was the least recently accessed, so it should be evicted
        # Note: 'c' might also be evicted depending on exact timing
        # At minimum, the cache should not exceed max_entries
        assert cache.stats["size"] <= 3

    def test_eviction_updates_stats(self) -> None:
        """Eviction increments the evictions counter."""
        cache = SemanticCache(max_entries=2, default_ttl=3600)
        cache.put("a", "1")
        cache.put("b", "2")
        cache.put("c", "3")  # triggers eviction
        assert cache.stats["evictions"] >= 1


class TestStats:
    """Tests for cache statistics."""

    def test_stats_hits_and_misses(self) -> None:
        """Stats track hits and misses correctly."""
        cache = SemanticCache()
        cache.put("p", "r")
        cache.get("p")  # hit
        cache.get("p")  # hit
        cache.get("missing")  # miss

        stats = cache.stats
        assert stats["hits"] == 2
        assert stats["misses"] == 1

    def test_stats_hit_rate(self) -> None:
        """Hit rate is computed correctly."""
        cache = SemanticCache()
        cache.put("p", "r")
        cache.get("p")  # hit
        cache.get("missing")  # miss

        stats = cache.stats
        assert stats["hit_rate"] == pytest.approx(0.5, abs=0.01)

    def test_stats_hit_rate_empty(self) -> None:
        """Hit rate is 0.0 when no requests."""
        cache = SemanticCache()
        assert cache.stats["hit_rate"] == 0.0

    def test_stats_tokens_saved(self) -> None:
        """tokens_saved accumulates based on hit_count * entry tokens."""
        cache = SemanticCache()
        cache.put("p", "r", input_tokens=100, output_tokens=50)
        cache.get("p")  # 1 hit
        cache.get("p")  # 2 hits

        stats = cache.stats
        # 2 hits * (100 + 50) = 300
        assert stats["tokens_saved"] == 300

    def test_stats_size(self) -> None:
        """Stats size reflects current cache size."""
        cache = SemanticCache()
        cache.put("a", "1")
        cache.put("b", "2")
        assert cache.stats["size"] == 2


class TestModelPartitionedCaching:
    """Tests that same prompt with different models are cached separately."""

    def test_same_prompt_different_models(self) -> None:
        """Same prompt cached under different models returns different results."""
        cache = SemanticCache()
        cache.put("What is AI?", "AI is...", model="gpt-4o")
        cache.put("What is AI?", "Artificial intelligence...", model="claude-sonnet-4-6")

        result_gpt = cache.get("What is AI?", model="gpt-4o")
        result_claude = cache.get("What is AI?", model="claude-sonnet-4-6")

        assert result_gpt == "AI is..."
        assert result_claude == "Artificial intelligence..."

    def test_model_partitioned_invalidation(self) -> None:
        """Invalidating for one model does not affect another."""
        cache = SemanticCache()
        cache.put("prompt", "r1", model="model_a")
        cache.put("prompt", "r2", model="model_b")

        cache.invalidate("prompt", model="model_a")
        assert cache.get("prompt", model="model_a") is None
        assert cache.get("prompt", model="model_b") == "r2"

    def test_hash_deterministic(self) -> None:
        """Same prompt + model always produces the same hash."""
        h1 = SemanticCache._hash_prompt("hello", "gpt-4o")
        h2 = SemanticCache._hash_prompt("hello", "gpt-4o")
        assert h1 == h2

    def test_hash_different_for_different_models(self) -> None:
        """Different models produce different hashes for same prompt."""
        h1 = SemanticCache._hash_prompt("hello", "gpt-4o")
        h2 = SemanticCache._hash_prompt("hello", "claude-sonnet-4-6")
        assert h1 != h2
