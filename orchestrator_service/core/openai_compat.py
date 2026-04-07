"""OpenAI parameter compatibility helper.

Modern OpenAI models (gpt-5 family, o1/o3/o4 series) reject the legacy
`max_tokens` parameter and require `max_completion_tokens` instead. The gpt-5
family also rejects any `temperature` other than the default (1).

This module centralizes the logic so call sites can build chat-completion
kwargs without hardcoding model-specific assumptions.

See: openspec/changes/openai-param-compat/spec.md
"""

from typing import Any, Optional

# Prefixes of OpenAI model families that use the modern Chat Completions API
# contract (max_completion_tokens, fixed temperature=1).
_MODERN_PREFIXES = ("gpt-5", "o1", "o3", "o4")


def is_modern_openai_model(model: str) -> bool:
    """Return True if the model belongs to the modern OpenAI family."""
    if not model:
        return False
    name = model.strip().lower()
    return any(name.startswith(p) for p in _MODERN_PREFIXES)


def build_openai_chat_kwargs(
    model: str,
    max_tokens: int,
    temperature: Optional[float] = None,
    **extra: Any,
) -> dict:
    """Build a chat-completion kwargs dict compatible with the given model.

    - Modern models receive `max_completion_tokens` and only get `temperature`
      when it is explicitly 1 (the only value gpt-5 accepts).
    - Legacy models receive `max_tokens` and `temperature` as-is.
    - Extra kwargs (messages, response_format, ...) are merged last.
    """
    kwargs: dict = {"model": model}

    if is_modern_openai_model(model):
        kwargs["max_completion_tokens"] = max_tokens
        if temperature is not None and temperature == 1:
            kwargs["temperature"] = 1
    else:
        kwargs["max_tokens"] = max_tokens
        if temperature is not None:
            kwargs["temperature"] = temperature

    # Reserved keys that the helper owns; ignore any caller attempt to inject them.
    reserved = {"model", "max_tokens", "max_completion_tokens", "temperature"}
    for key, value in extra.items():
        if key in reserved:
            continue
        kwargs[key] = value

    return kwargs
