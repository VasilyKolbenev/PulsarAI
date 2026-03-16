"""Centralized environment variable access with FORGE_ -> PULSAR_ deprecation.

Usage::
    from pulsar_ai.env import get_env
    port = get_env("PORT", "8888")
"""

import os
import warnings

_warned: set[str] = set()


def get_env(name: str, default: str | None = None) -> str | None:
    """Read an environment variable with PULSAR_ prefix, falling back to FORGE_.

    Args:
        name: Variable name without prefix (e.g. "PORT", "AUTH_ENABLED").
        default: Default value if neither prefix is set.

    Returns:
        The value, or *default*.
    """
    pulsar_val = os.environ.get(f"PULSAR_{name}")
    if pulsar_val is not None:
        return pulsar_val

    forge_val = os.environ.get(f"FORGE_{name}")
    if forge_val is not None:
        if name not in _warned:
            warnings.warn(
                f"FORGE_{name} is deprecated, use PULSAR_{name} instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            _warned.add(name)
        return forge_val

    return default
