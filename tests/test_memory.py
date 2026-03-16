"""Tests for agent ShortTermMemory."""

from pulsar_ai.agent.memory import ShortTermMemory


class TestShortTermMemory:
    """Tests for ShortTermMemory."""

    def test_init_empty(self) -> None:
        mem = ShortTermMemory()
        assert mem.message_count == 0
        assert mem.get_messages() == []

    def test_init_with_system_prompt(self) -> None:
        mem = ShortTermMemory(system_prompt="You are helpful.")
        assert mem.message_count == 1
        msgs = mem.get_messages()
        assert msgs[0]["role"] == "system"
        assert msgs[0]["content"] == "You are helpful."

    def test_add_messages(self) -> None:
        mem = ShortTermMemory()
        mem.add("user", "Hello")
        mem.add("assistant", "Hi there!")
        assert mem.message_count == 2
        msgs = mem.get_messages()
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"

    def test_clear_preserves_system(self) -> None:
        mem = ShortTermMemory(system_prompt="System msg")
        mem.add("user", "Hello")
        mem.add("assistant", "Hi")
        assert mem.message_count == 3

        mem.clear()
        assert mem.message_count == 1
        assert mem.get_messages()[0]["role"] == "system"

    def test_clear_empty_without_system(self) -> None:
        mem = ShortTermMemory()
        mem.add("user", "Hello")
        mem.clear()
        assert mem.message_count == 0

    def test_token_count(self) -> None:
        mem = ShortTermMemory()
        # 100 chars / 4 = 25 tokens
        mem.add("user", "x" * 100)
        assert mem.token_count() == 25

    def test_trim_removes_oldest_non_system(self) -> None:
        # Small budget: ~10 tokens = 40 chars
        mem = ShortTermMemory(max_tokens=10, system_prompt="Hi")
        mem.add("user", "a" * 20)  # 5 tokens
        mem.add("user", "b" * 20)  # 5 tokens
        mem.add("user", "c" * 20)  # 5 tokens — triggers trim

        # System message (2 chars = 0 tokens) should be preserved
        msgs = mem.get_messages()
        assert msgs[0]["role"] == "system"
        # Some messages should have been trimmed
        assert mem.token_count() <= 10

    def test_trim_preserves_system_message(self) -> None:
        mem = ShortTermMemory(max_tokens=5, system_prompt="Important system")
        mem.add("user", "x" * 40)  # exceeds budget
        msgs = mem.get_messages()
        system_msgs = [m for m in msgs if m["role"] == "system"]
        assert len(system_msgs) == 1
        assert system_msgs[0]["content"] == "Important system"

    def test_get_messages_returns_copy(self) -> None:
        mem = ShortTermMemory()
        mem.add("user", "Hello")
        msgs = mem.get_messages()
        msgs.append({"role": "fake", "content": "injected"})
        assert mem.message_count == 1  # Original not modified

    def test_repr(self) -> None:
        mem = ShortTermMemory(max_tokens=100)
        mem.add("user", "Hello")
        r = repr(mem)
        assert "messages=1" in r
        assert "/100" in r
