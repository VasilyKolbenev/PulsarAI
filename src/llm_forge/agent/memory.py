"""Memory management for agent conversations.

Provides ShortTermMemory (sliding window) and LongTermMemory (vector store).
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ShortTermMemory:
    """Sliding-window memory that keeps recent messages within token budget.

    Maintains conversation history with automatic trimming when the
    token count exceeds the configured maximum. Always preserves the
    system message.

    Args:
        max_tokens: Maximum approximate token count for the memory.
        system_prompt: System message to always keep at the start.
    """

    CHARS_PER_TOKEN = 4  # rough estimate for token counting

    def __init__(
        self, max_tokens: int = 4096, system_prompt: str = ""
    ) -> None:
        self.max_tokens = max_tokens
        self._messages: list[dict[str, Any]] = []
        self._system_prompt = system_prompt

        if system_prompt:
            self._messages.append({
                "role": "system",
                "content": system_prompt,
            })

    def add(self, role: str, content: str, **kwargs: Any) -> None:
        """Add a message to memory.

        Args:
            role: Message role ('user', 'assistant', 'tool', 'system').
            content: Message content.
            **kwargs: Extra fields (e.g. tool_calls, tool_call_id).
        """
        msg: dict[str, Any] = {"role": role, "content": content}
        msg.update(kwargs)
        self._messages.append(msg)
        self._trim()

    def get_messages(self) -> list[dict[str, Any]]:
        """Get all messages in memory.

        Returns:
            List of message dicts with 'role', 'content', and optional fields.
        """
        return list(self._messages)

    def clear(self) -> None:
        """Clear all messages except the system prompt."""
        self._messages = []
        if self._system_prompt:
            self._messages.append({
                "role": "system",
                "content": self._system_prompt,
            })

    def token_count(self) -> int:
        """Estimate total token count of all messages.

        Returns:
            Approximate token count.
        """
        total_chars = sum(len(m.get("content") or "") for m in self._messages)
        return total_chars // self.CHARS_PER_TOKEN

    def _trim(self) -> None:
        """Remove oldest non-system messages if over token budget."""
        while self.token_count() > self.max_tokens and len(self._messages) > 1:
            # Find first non-system message to remove
            for i, msg in enumerate(self._messages):
                if msg["role"] != "system":
                    removed = self._messages.pop(i)
                    logger.debug(
                        "Trimmed %s message (%d chars) from memory",
                        removed["role"],
                        len(removed["content"]),
                    )
                    break
            else:
                break  # Only system messages left

    @property
    def message_count(self) -> int:
        """Number of messages in memory."""
        return len(self._messages)

    def __repr__(self) -> str:
        return (
            f"ShortTermMemory(messages={self.message_count}, "
            f"tokens=~{self.token_count()}/{self.max_tokens})"
        )


class LongTermMemory:
    """Persistent vector store memory for agent knowledge.

    Uses a simple JSON-based store by default. When chromadb is available,
    uses it for semantic similarity search.

    Args:
        store_path: Path to the storage directory.
        collection_name: Name of the collection/namespace.
        use_chromadb: Whether to use chromadb backend. If None, auto-detect.
    """

    def __init__(
        self,
        store_path: str = "./.agent_memory",
        collection_name: str = "default",
        use_chromadb: bool | None = None,
    ) -> None:
        self.store_path = Path(store_path)
        self.collection_name = collection_name
        self._chroma_collection: Any = None
        self._json_store: list[dict[str, Any]] = []

        if use_chromadb is None:
            try:
                import chromadb  # noqa: F401
                use_chromadb = True
            except ImportError:
                use_chromadb = False

        self._use_chromadb = use_chromadb

        if self._use_chromadb:
            self._init_chromadb()
        else:
            self._init_json_store()

    def _init_chromadb(self) -> None:
        """Initialize chromadb backend."""
        import chromadb

        self.store_path.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(self.store_path))
        self._chroma_collection = client.get_or_create_collection(
            name=self.collection_name,
        )
        logger.debug(
            "LongTermMemory: chromadb collection '%s' at %s",
            self.collection_name, self.store_path,
        )

    def _init_json_store(self) -> None:
        """Initialize simple JSON file store."""
        self.store_path.mkdir(parents=True, exist_ok=True)
        self._json_file = self.store_path / f"{self.collection_name}.json"
        if self._json_file.exists():
            self._json_store = json.loads(
                self._json_file.read_text(encoding="utf-8")
            )
        logger.debug(
            "LongTermMemory: JSON store with %d entries at %s",
            len(self._json_store), self._json_file,
        )

    def add(self, text: str, metadata: dict[str, Any] | None = None) -> str:
        """Store a text entry with optional metadata.

        Args:
            text: Text content to store.
            metadata: Optional metadata dict.

        Returns:
            Entry ID.
        """
        entry_id = hashlib.sha256(text.encode()).hexdigest()[:16]
        metadata = metadata or {}

        if self._use_chromadb:
            self._chroma_collection.add(
                documents=[text],
                metadatas=[metadata],
                ids=[entry_id],
            )
        else:
            self._json_store.append({
                "id": entry_id,
                "text": text,
                "metadata": metadata,
            })
            self._save_json()

        logger.debug("Stored entry %s (%d chars)", entry_id, len(text))
        return entry_id

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Search for similar entries.

        With chromadb, uses semantic similarity. Without it, uses
        simple substring matching.

        Args:
            query: Search query string.
            top_k: Maximum number of results.

        Returns:
            List of dicts with 'text', 'metadata', and 'score'.
        """
        if self._use_chromadb:
            results = self._chroma_collection.query(
                query_texts=[query],
                n_results=min(top_k, self._chroma_collection.count()),
            )
            entries = []
            if results["documents"] and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    entries.append({
                        "text": doc,
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "score": 1.0 - (results["distances"][0][i] if results["distances"] else 0),
                    })
            return entries
        else:
            return self._json_search(query, top_k)

    def _json_search(
        self, query: str, top_k: int
    ) -> list[dict[str, Any]]:
        """Simple substring-based search for JSON store.

        Args:
            query: Search query.
            top_k: Max results.

        Returns:
            Matching entries sorted by relevance.
        """
        query_lower = query.lower()
        query_words = query_lower.split()

        scored: list[tuple[float, dict[str, Any]]] = []
        for entry in self._json_store:
            text_lower = entry["text"].lower()
            word_matches = sum(1 for w in query_words if w in text_lower)
            if word_matches > 0:
                score = word_matches / len(query_words)
                scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)

        return [
            {"text": e["text"], "metadata": e["metadata"], "score": s}
            for s, e in scored[:top_k]
        ]

    def _save_json(self) -> None:
        """Persist JSON store to disk."""
        self._json_file.write_text(
            json.dumps(self._json_store, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @property
    def count(self) -> int:
        """Number of entries in the store."""
        if self._use_chromadb:
            return self._chroma_collection.count()
        return len(self._json_store)

    def __repr__(self) -> str:
        backend = "chromadb" if self._use_chromadb else "json"
        return f"LongTermMemory(backend={backend}, entries={self.count})"
